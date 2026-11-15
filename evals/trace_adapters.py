"""Adapters normalizing behavior eval traces into a canonical offline model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TRACE_SCHEMA_VERSION = "docs-harness/behavior-trace/v1"
SUPPORTED_FORMATS: tuple[str, ...] = ("auto", "v1", "claude_jsonl")

_CMD_TOOLS = frozenset({"bash", "run_command", "shell", "exec", "terminal"})
_MUTATE_TOOLS = frozenset({
    "write", "edit", "multiedit", "write_file", "edit_file",
    "replace_file_content", "multi_replace_file_content",
})
_SPAWN_TOOLS = frozenset({"agent", "task", "invoke_subagent", "swarm"})


class TraceParseError(ValueError):
    """Raised when a trace input cannot be decoded or fails format validation."""


@dataclass(frozen=True)
class NormalizedToolCall:
    """Canonical representation of one tool invocation within a trace."""

    turn_index: int
    name: str
    command: str
    args: dict[str, Any]
    status: str
    exit_code: int | None
    output: str


@dataclass(frozen=True)
class NormalizedTrace:
    """Normalized trace payload consumed by offline behavior rubric checkers."""

    schema_version: str
    adapter: str
    case_id: str | None
    turns: tuple[dict[str, Any], ...]
    tool_calls: tuple[NormalizedToolCall, ...]
    subagent_spawns: tuple[dict[str, Any], ...]
    commands: tuple[dict[str, Any], ...]
    workspace_paths_modified: tuple[str, ...]
    pre_action_text: str
    final_text: str
    assistant_texts: tuple[str, ...]
    metadata: dict[str, Any]


def _normalize_path(raw_path: Any) -> str:
    if not isinstance(raw_path, str):
        return ""
    cleaned = raw_path.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.replace("//", "/")


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [
            item if isinstance(item, str) else str(item.get("text") or "")
            for item in value
            if isinstance(item, str) or (isinstance(item, dict) and item.get("type") == "text")
        ]
        return "\n".join(p for p in parts if p)
    return json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)


def _coerce_exit_code(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _extract_command(name: str, args: dict[str, Any], tc: dict[str, Any]) -> str:
    if name.lower() not in _CMD_TOOLS and "command" not in tc and "CommandLine" not in args:
        return ""
    for key in ("command", "cmd", "CommandLine", "command_line"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    val = tc.get("command")
    return val.strip() if isinstance(val, str) else ""


def _extract_mutated_paths(name: str, args: dict[str, Any]) -> list[str]:
    if name.lower() not in _MUTATE_TOOLS:
        return []
    paths: list[str] = []
    for key in ("file_path", "path", "TargetFile", "Path", "target_file", "filename"):
        norm = _normalize_path(args.get(key))
        if norm and norm not in paths:
            paths.append(norm)
    for item in (args.get("edits") if isinstance(args.get("edits"), list) else ()):
        if isinstance(item, dict):
            norm = _normalize_path(item.get("file_path") or item.get("path"))
            if norm and norm not in paths:
                paths.append(norm)
    return paths


def _extract_path_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        norm = _normalize_path(value)
        return (norm,) if norm else ()
    if isinstance(value, list):
        return tuple(p for p in (_normalize_path(v) for v in value) if p)
    return ()


def _is_subagent_spawn(name: str, args: dict[str, Any]) -> bool:
    low = name.lower()
    return str(args.get("action", "")).strip().lower() == "add" if low == "swarm" else low in _SPAWN_TOOLS


def _build_spawn_record(turn_idx: int, name: str, args: dict[str, Any]) -> dict[str, Any]:
    role = str(args.get("role") or args.get("Role") or args.get("subagent_type") or args.get("name") or args.get("description") or "")
    prompt = str(args.get("prompt") or args.get("Prompt") or args.get("brief") or args.get("Brief") or args.get("task") or "")
    scope = _extract_path_list(args.get("scope_paths") or args.get("paths") or args.get("scope"))
    allow = _extract_path_list(args.get("allowlist_paths") or args.get("file_whitelist") or args.get("whitelist") or args.get("files"))
    return {
        "turn_index": turn_idx, "tool": name, "role": role, "prompt": prompt, "brief": prompt,
        "scope_paths": scope, "allowlist_paths": allow,
        "model": str(args.get("model") or args.get("Model") or ""),
        "name": str(args.get("name") or ""), "args": dict(args),
    }


def _make_tool_call(turn_idx: int, raw_tc: dict[str, Any]) -> tuple[NormalizedToolCall, str]:
    name = str(raw_tc.get("name") or raw_tc.get("tool") or "").strip()
    if not name:
        raise TraceParseError(f"Tool call at turn {turn_idx} is missing tool name")
    raw_args = raw_tc.get("args") or raw_tc.get("input") or raw_tc.get("arguments") or {}
    if not isinstance(raw_args, dict):
        raise TraceParseError(f"Tool call {name} args must be a JSON object")
    command = _extract_command(name, raw_args, raw_tc)
    exit_code = _coerce_exit_code(raw_tc.get("exit_code"))
    status = str(raw_tc.get("status") or ("error" if raw_tc.get("is_error") or (exit_code not in (None, 0)) else "ok"))
    output = _coerce_text(raw_tc.get("output") or raw_tc.get("stdout") or raw_tc.get("result") or "")
    call_id = str(raw_tc.get("id") or raw_tc.get("tool_use_id") or "")
    return NormalizedToolCall(turn_idx, name, command, dict(raw_args), status, exit_code, output), call_id


def _merge_snapshot_metadata(src: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    extra_mod: list[str] = []
    files_map: dict[str, str] = dict(metadata.get("files", {}))
    for key in ("workspace", "artifacts"):
        snap = src.get(key)
        if not isinstance(snap, dict):
            continue
        metadata[key] = snap
        for list_key in ("modified_files", "new_files"):
            existing = list(metadata.get(list_key, ()))
            for p in _extract_path_list(snap.get(list_key)):
                if p not in existing:
                    existing.append(p)
                if p not in extra_mod:
                    extra_mod.append(p)
            if existing:
                metadata[list_key] = tuple(existing)
        if isinstance(snap.get("files"), dict):
            for fp, content in snap["files"].items():
                norm = _normalize_path(fp)
                if norm:
                    files_map[norm] = _coerce_text(content)
    if files_map:
        metadata["files"] = files_map
    return extra_mod


def _build_normalized_trace(
    *, adapter: str, case_id: str | None, turns: list[dict[str, Any]],
    tool_calls: list[NormalizedToolCall], explicit_final: str,
    extra_modified: list[str], metadata: dict[str, Any],
) -> NormalizedTrace:
    spawns, commands, modified = [], [], []
    first_action_turn: int | None = None
    for tc in tool_calls:
        is_spawn = _is_subagent_spawn(tc.name, tc.args)
        mut_paths = _extract_mutated_paths(tc.name, tc.args)
        is_harness = bool(tc.command and "harness.py" in tc.command.lower())
        if first_action_turn is None and (mut_paths or is_spawn or is_harness):
            first_action_turn = tc.turn_index
        if is_spawn:
            spawns.append(_build_spawn_record(tc.turn_index, tc.name, tc.args))
        if tc.command:
            commands.append({"turn_index": tc.turn_index, "tool": tc.name, "command": tc.command, "is_harness_cmd": is_harness, "exit_code": tc.exit_code, "status": tc.status, "output": tc.output})
        for path in mut_paths:
            if path not in modified:
                modified.append(path)
    for path in extra_modified:
        if path not in modified:
            modified.append(path)
    if first_action_turn is None:
        first_action_turn = tool_calls[0].turn_index if tool_calls else len(turns)
    asst_pairs = [(i, str(t.get("text") or "")) for i, t in enumerate(turns) if t.get("role") == "assistant"]
    asst_texts = tuple(txt for _, txt in asst_pairs if txt.strip())
    pre_text = "\n".join(txt for idx, txt in asst_pairs if idx < first_action_turn and txt.strip())
    final_text = asst_texts[-1] if asst_texts else explicit_final
    return NormalizedTrace(TRACE_SCHEMA_VERSION, adapter, case_id, tuple(turns), tuple(tool_calls), tuple(spawns), tuple(commands), tuple(modified), pre_text, final_text, asst_texts, metadata)


def detect_trace_format(raw_text: str) -> str:
    """Detect whether raw trace text uses v1 JSON or claude_jsonl."""
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise TraceParseError("Trace input is empty")
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        for idx, line in enumerate((ln for ln in raw_text.splitlines() if ln.strip()), start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TraceParseError(f"Invalid JSONL at line {idx}: {exc}") from exc
            if not isinstance(item, dict):
                raise TraceParseError(f"JSONL line {idx} must be a JSON object")
        return "claude_jsonl"
    if isinstance(parsed, dict):
        if "schema_version" in parsed or "turns" in parsed:
            return "v1"
        return "claude_jsonl" if any(k in parsed for k in ("type", "message", "role", "tool_calls")) else "v1"
    if isinstance(parsed, list):
        return "claude_jsonl"
    raise TraceParseError("Trace root value must be a JSON object or JSONL records")


def _adapt_v1(raw: str | dict[str, Any]) -> NormalizedTrace:
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TraceParseError(f"Invalid JSON trace: {exc}") from exc
    else:
        data = raw
    if not isinstance(data, dict):
        raise TraceParseError("v1 trace must be a JSON object")
    if data.get("schema_version") != TRACE_SCHEMA_VERSION:
        raise TraceParseError(f"Invalid schema_version: {data.get('schema_version')!r}")
    raw_turns = data.get("turns")
    if not isinstance(raw_turns, list):
        raise TraceParseError("v1 trace requires a list 'turns' field")
    turns, tool_calls = [], []
    for idx, item in enumerate(raw_turns):
        if not isinstance(item, dict):
            raise TraceParseError(f"Turn {idx} must be a JSON object")
        role = str(item.get("role") or "").strip().lower()
        text = _coerce_text(item.get("text") if "text" in item else item.get("content"))
        raw_tcs = item.get("tool_calls") or []
        if not isinstance(raw_tcs, list):
            raise TraceParseError(f"Turn {idx} tool_calls must be a list")
        turn_tcs = []
        for raw_tc in raw_tcs:
            if not isinstance(raw_tc, dict):
                raise TraceParseError(f"Turn {idx} tool_call entry must be an object")
            norm_tc, _ = _make_tool_call(idx, raw_tc)
            tool_calls.append(norm_tc)
            turn_tcs.append({"name": norm_tc.name, "command": norm_tc.command, "status": norm_tc.status})
        turns.append({"turn_index": idx, "role": role, "text": text, "tool_calls": turn_tcs})
    metadata = dict(data.get("metadata")) if isinstance(data.get("metadata"), dict) else {}
    extra_mod = _merge_snapshot_metadata(data, metadata)
    case_id = data.get("case_id") if isinstance(data.get("case_id"), str) else None
    explicit_final = data.get("final_text") if isinstance(data.get("final_text"), str) else ""
    return _build_normalized_trace(adapter="v1", case_id=case_id, turns=turns, tool_calls=tool_calls, explicit_final=explicit_final, extra_modified=extra_mod, metadata=metadata)


def _parse_jsonl_records(raw: str | dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        if not raw or not all(isinstance(x, dict) for x in raw):
            raise TraceParseError("Trace record list must be non-empty JSON objects")
        return raw
    if not isinstance(raw, str) or not raw.strip():
        raise TraceParseError("Empty JSONL trace")
    try:
        return _parse_jsonl_records(json.loads(raw))
    except json.JSONDecodeError:
        records: list[dict[str, Any]] = []
        for idx, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TraceParseError(f"Invalid JSONL at line {idx}: {exc}") from exc
            if not isinstance(obj, dict):
                raise TraceParseError(f"JSONL line {idx} must be a JSON object")
            records.append(obj)
        if not records:
            raise TraceParseError("Empty JSONL trace")
        return records


def _apply_tool_result(block: dict[str, Any], tool_calls: list[NormalizedToolCall], id_index: dict[str, int], extra_exit: int | None = None) -> None:
    ref_id = str(block.get("tool_use_id") or block.get("id") or "")
    if not ref_id or ref_id not in id_index:
        return
    idx = id_index[ref_id]
    prev = tool_calls[idx]
    out = _coerce_text(block.get("content") if "content" in block else block.get("output"))
    exit_code = _coerce_exit_code(block.get("exit_code"))
    if exit_code is None:
        exit_code = extra_exit
    status = "error" if bool(block.get("is_error")) or (exit_code not in (None, 0)) else "ok"
    tool_calls[idx] = NormalizedToolCall(prev.turn_index, prev.name, prev.command, prev.args, status, exit_code, out or prev.output)


def _extract_claude_blocks(turn_idx: int, content: Any, tool_calls: list[NormalizedToolCall], id_index: dict[str, int], extra_exit: int | None) -> tuple[str, list[dict[str, Any]]]:
    if isinstance(content, str):
        return content, []
    if not isinstance(content, list):
        return _coerce_text(content), []
    texts, turn_tcs = [], []
    for block in content:
        if isinstance(block, str):
            texts.append(block)
        elif isinstance(block, dict):
            btype = str(block.get("type") or "").lower()
            if btype == "text" and isinstance(block.get("text"), str):
                texts.append(block["text"])
            elif btype == "tool_use":
                norm_tc, cid = _make_tool_call(turn_idx, block)
                if cid:
                    id_index[cid] = len(tool_calls)
                tool_calls.append(norm_tc)
                turn_tcs.append({"name": norm_tc.name, "command": norm_tc.command, "status": norm_tc.status})
            elif btype == "tool_result":
                _apply_tool_result(block, tool_calls, id_index, extra_exit)
    return "\n".join(texts), turn_tcs


def _process_jsonl_record(rec: dict[str, Any], turns: list[dict[str, Any]], tool_calls: list[NormalizedToolCall], id_index: dict[str, int], metadata: dict[str, Any]) -> str:
    rec_type = str(rec.get("type") or "").lower()
    if rec_type == "result" and isinstance(rec.get("result"), str):
        return rec["result"]
    if rec_type == "tool_result":
        _apply_tool_result(rec, tool_calls, id_index, _coerce_exit_code(rec.get("exit_code")))
        return ""
    if rec_type == "tool_use":
        norm_tc, cid = _make_tool_call(len(turns), rec)
        if cid:
            id_index[cid] = len(tool_calls)
        tool_calls.append(norm_tc)
        turns.append({"turn_index": len(turns), "role": "assistant", "text": "", "tool_calls": [{"name": norm_tc.name}]})
        return ""
    msg = rec.get("message") if isinstance(rec.get("message"), dict) else rec
    role = str(msg.get("role") or rec_type).strip().lower()
    if role not in {"user", "assistant", "system"}:
        metadata.setdefault("trailing_events", []).append(rec)
        return ""
    tur = rec.get("toolUseResult")
    extra_exit = _coerce_exit_code(tur.get("exit_code") if isinstance(tur, dict) else None)
    content = msg.get("content") if "content" in msg else msg.get("text")
    text, turn_tcs = _extract_claude_blocks(len(turns), content, tool_calls, id_index, extra_exit)
    for raw_tc in (msg.get("tool_calls") if isinstance(msg.get("tool_calls"), list) else ()):
        if not isinstance(raw_tc, dict):
            raise TraceParseError("tool_calls items must be objects")
        norm_tc, cid = _make_tool_call(len(turns), raw_tc)
        if cid:
            id_index[cid] = len(tool_calls)
        tool_calls.append(norm_tc)
        turn_tcs.append({"name": norm_tc.name, "command": norm_tc.command, "status": norm_tc.status})
    turns.append({"turn_index": len(turns), "role": role, "text": text, "tool_calls": turn_tcs})
    return ""


def _adapt_claude_jsonl(raw: str | dict[str, Any] | list[dict[str, Any]]) -> NormalizedTrace:
    records = _parse_jsonl_records(raw)
    turns, tool_calls, id_index, metadata, extra_mod = [], [], {}, {}, []
    case_id, explicit_final = None, ""
    for rec in records:
        if isinstance(rec.get("case_id"), str):
            case_id = rec["case_id"]
        if isinstance(rec.get("metadata"), dict):
            metadata.update(rec["metadata"])
        extra_mod.extend(p for p in _merge_snapshot_metadata(rec, metadata) if p not in extra_mod)
        res = _process_jsonl_record(rec, turns, tool_calls, id_index, metadata)
        if res:
            explicit_final = res
    return _build_normalized_trace(adapter="claude_jsonl", case_id=case_id, turns=turns, tool_calls=tool_calls, explicit_final=explicit_final, extra_modified=extra_mod, metadata=metadata)


def adapt_trace_payload(raw: str | dict[str, Any] | list[dict[str, Any]], *, fmt: str = "auto") -> NormalizedTrace:
    """Parse and normalize a trace string/object into NormalizedTrace."""
    if fmt not in SUPPORTED_FORMATS:
        raise TraceParseError(f"Unsupported format: {fmt!r}")
    resolved = fmt
    if fmt == "auto":
        if isinstance(raw, str):
            resolved = detect_trace_format(raw)
        elif isinstance(raw, dict):
            resolved = "v1" if ("schema_version" in raw or "turns" in raw or not any(k in raw for k in ("type", "message", "role", "tool_calls"))) else "claude_jsonl"
        elif isinstance(raw, list):
            resolved = "claude_jsonl"
        else:
            raise TraceParseError("Trace payload must be str, dict, or list of dicts")
    if resolved == "v1":
        if isinstance(raw, list):
            raise TraceParseError("v1 format requires a JSON object, not a list")
        return _adapt_v1(raw)
    return _adapt_claude_jsonl(raw)


def load_trace_file(path: Path, *, fmt: str = "auto") -> NormalizedTrace:
    """Load and normalize a trace file from disk."""
    target = Path(path)
    if not target.exists() or not target.is_file():
        raise TraceParseError(f"Trace file does not exist: {target}")
    try:
        raw_text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TraceParseError(f"Cannot read trace file {target}: {exc}") from exc
    return adapt_trace_payload(raw_text, fmt=fmt)
