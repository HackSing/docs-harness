#!/usr/bin/env python3
"""Qoder UserPromptSubmit hook prototype.

Reads the hook input JSON from stdin, obtains a routing profile (fake fixture in
this prototype), validates it against the Docs Harness registry, writes a
privacy-safe shadow event, and injects the selected module contracts through
`hookSpecificOutput.additionalContext`.

The hook is default-off. It never blocks the user prompt: failures are written
to stderr and a local error log, and the hook exits 0. Replace `_route_task`
with the real low-context model call when the endpoint is available.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

SOURCE_ROOT = Path(
    os.environ.get("DOCS_HARNESS_ROOT") or Path(__file__).resolve().parents[3]
)
sys.path.insert(0, str(SOURCE_ROOT / "scripts"))

from routing_contract import (  # noqa: E402
    Registry,
    RoutingContractError,
    direct_override_requested,
    load_registry,
    validate_profile,
)
from routing_shadow import (  # noqa: E402
    PHASES,
    RoutingShadowError,
    append_shadow_event,
    build_shadow_event,
    shadow_log_path,
)
from route_cache import (  # noqa: E402
    clear_cache,
    is_new_task,
    is_reset,
    read_cache,
    routing_dir,
    write_cache,
)

FAKE_PROFILE_RELATIVE = "routing/hosts/qoder/fake_profile.json"
NATIVE_CLI = Path.home() / ".local/bin/qoderclicn"
NPM_CLI = Path.home() / ".qoder-cn/docs-harness-router/cn/node_modules/.bin/qodercn"
DEFAULT_CLI = NATIVE_CLI if NATIVE_CLI.is_file() else NPM_CLI
DEFAULT_CLI_CONFIG = Path.home() / ".qoder-cn/docs-harness-router/cn-config"
DEFAULT_CLI_EMPTY = Path.home() / ".qoder-cn/docs-harness-router/empty"
CLI_TIMEOUT_SECONDS = 60
CLI_ENV_DROP = frozenset(
    {
        "QODER_AGENT_SDK_ENTRYPOINT",
        "QODER_AGENT_SDK_DAEMON",
        "QODER_AGENT_SDK_VERSION",
        "QODER_SDK_AUTH_PAYLOAD_FILE",
        "QODER_CONFIG_DIR",
        "QODERCN_CONFIG_DIR",
        "QODER_PERSONAL_ACCESS_TOKEN",
    }
)


class HookError(Exception):
    def __init__(self, code: str, field: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.field = field


def main() -> int:
    payload = _read_payload()
    if payload is None or not _enabled():
        return 0
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return 0
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        session_id = "unknown"
    project: Path | None = None
    try:
        project = _project_dir(payload)
        registry = _registry_for(project)
        if direct_override_requested(prompt, registry):
            return 0
        if _handle_cache(project, session_id, prompt, registry):
            return 0
        _run_full_route(project, session_id, prompt, registry)
        return 0
    except (HookError, RoutingContractError, RoutingShadowError, OSError, UnicodeDecodeError) as exc:
        _report_error(
            project,
            getattr(exc, "code", "hook_error"),
            _error_field(exc),
            session_id,
        )
        return 0


def _handle_cache(
    project: Path, session_id: str, prompt: str, registry: Registry
) -> bool:
    if is_reset(prompt):
        clear_cache(project, session_id)
        return True
    if is_new_task(prompt):
        return False
    cached = read_cache(project, session_id, registry)
    if cached is None:
        return False
    result = validate_profile(cached["profile"], registry)
    if not result.ok or result.effective_clarify or not result.modules:
        clear_cache(project, session_id)
        return False
    started = time.monotonic()
    event = build_shadow_event(
        _task_id(session_id, prompt),
        cached["profile"],
        list(result.modules),
        {"clarify_asked": False, "rework": [], "completed": None},
        phase=os.environ.get("DOCS_HARNESS_ROUTER_PHASE", "shadow"),
        registry=registry,
        model={
            "name": "route-cache",
            "version": "1",
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "cache_hit": True,
        },
        task_text=prompt,
    )
    append_shadow_event(event, shadow_log_path(project))
    _emit(_render_cached_context(result.modules, registry))
    return True


def _run_full_route(
    project: Path, session_id: str, prompt: str, registry: Registry
) -> None:
    started = time.monotonic()
    profile, model = _route_task(prompt, registry)
    profile = _normalize_router_profile(profile)
    latency_ms = round((time.monotonic() - started) * 1000, 1)
    result = validate_profile(profile, registry)
    if not result.ok:
        _report_error(project, "profile_invalid", result.errors[0].code, session_id)
        return
    phase = os.environ.get("DOCS_HARNESS_ROUTER_PHASE", "shadow")
    if phase not in PHASES:
        _report_error(project, "phase_invalid", "DOCS_HARNESS_ROUTER_PHASE", session_id)
        return
    event = build_shadow_event(
        _task_id(session_id, prompt),
        profile,
        list(result.modules),
        {"clarify_asked": False, "rework": [], "completed": None},
        phase=phase,
        registry=registry,
        model=_event_model(model, latency_ms),
        task_text=prompt,
    )
    append_shadow_event(event, shadow_log_path(project))
    if result.effective_clarify or not result.modules:
        return
    write_cache(project, session_id, result, registry)
    _emit(_render_context(result.modules, registry))


def _normalize_router_profile(profile: Mapping[str, Any]) -> Mapping[str, Any]:
    if profile.get("must_clarify") is not True:
        return profile
    triggers = profile.get("triggers")
    if isinstance(triggers, list) and triggers == ["clarify_required"]:
        return profile
    normalized = dict(profile)
    normalized["triggers"] = ["clarify_required"]
    normalized.pop("modules", None)
    return normalized


def _route_task(
    prompt: str, registry: Registry
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    backend = os.environ.get("DOCS_HARNESS_ROUTER_BACKEND", "fake").strip().lower()
    if backend == "fake":
        return _route_task_fake()
    if backend == "cli":
        return _route_task_cli(prompt, registry)
    raise HookError("unknown_router_backend", "DOCS_HARNESS_ROUTER_BACKEND")


def _route_task_fake() -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    path = Path(
        os.environ.get("DOCS_HARNESS_ROUTER_FAKE_PROFILE")
        or (SOURCE_ROOT / FAKE_PROFILE_RELATIVE)
    )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HookError("fake_profile_unreadable", "DOCS_HARNESS_ROUTER_FAKE_PROFILE") from exc
    if not isinstance(value, Mapping):
        raise HookError("fake_profile_not_object", "DOCS_HARNESS_ROUTER_FAKE_PROFILE")
    return value, {"name": "fake-router", "version": "prototype"}


def _route_task_cli(
    prompt: str, registry: Registry
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    cli = Path(os.environ.get("DOCS_HARNESS_QODER_CLI", DEFAULT_CLI)).expanduser()
    if not cli.is_file():
        raise HookError("qoder_cli_missing", "DOCS_HARNESS_QODER_CLI")
    config = Path(
        os.environ.get("DOCS_HARNESS_QODER_CONFIG_DIR", DEFAULT_CLI_CONFIG)
    ).expanduser()
    empty = Path(
        os.environ.get("DOCS_HARNESS_QODER_EMPTY_DIR", DEFAULT_CLI_EMPTY)
    ).expanduser()
    model = os.environ.get("DOCS_HARNESS_ROUTER_MODEL")
    config.mkdir(parents=True, exist_ok=True)
    empty.mkdir(parents=True, exist_ok=True)
    args = [
        str(cli),
        "-p",
        prompt,
        "--output-format",
        "json",
        "--max-turns",
        "1",
        "--tools",
        "",
        "--permission-mode",
        "default",
        "--no-session-persistence",
        "--cwd",
        str(empty),
        "--config-dir",
        str(config),
        "--system-prompt",
        _router_system_prompt(registry),
        "--settings",
        '{"general":{"enableAutoUpdate":false}}',
    ]
    if model:
        args.extend(["--model", model])
    env = _cli_env(config)
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_SECONDS,
            env=env,
            cwd=str(empty),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HookError("qoder_cli_timeout", "DOCS_HARNESS_QODER_CLI") from exc
    data = _cli_result(result)
    text = data.get("result")
    if not isinstance(text, str) or not text.strip():
        raise HookError("qoder_cli_empty_result", "qoder")
    return _parse_profile_text(text), _cli_metadata(data, model, cli, env)


def _cli_result(result: subprocess.CompletedProcess[str]) -> Mapping[str, Any]:
    if result.returncode != 0 and not result.stdout.strip():
        raise HookError(f"qoder_cli_exit_{result.returncode}", "DOCS_HARNESS_QODER_CLI")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HookError("qoder_cli_invalid_json", "qoder") from exc
    if not isinstance(data, Mapping):
        raise HookError("qoder_cli_invalid_json", "qoder")
    if data.get("is_error") or data.get("subtype") != "success":
        message = str(data.get("result") or "").lower()
        code = "qoder_cli_not_logged_in" if "not logged in" in message else "qoder_cli_error"
        raise HookError(code, "qoder")
    return data


def _parse_profile_text(text: str) -> Mapping[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise HookError("router_profile_not_json", "qoder")
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise HookError("router_profile_not_json", "qoder") from exc
    if not isinstance(value, Mapping):
        raise HookError("router_profile_not_object", "qoder")
    return value


def _cli_metadata(
    data: Mapping[str, Any], model: str | None, cli: Path, env: Mapping[str, str]
) -> Mapping[str, Any]:
    usage = data.get("usage") if isinstance(data.get("usage"), Mapping) else {}
    model_usage = (
        data.get("modelUsage") if isinstance(data.get("modelUsage"), Mapping) else {}
    )
    metadata: dict[str, Any] = {
        "name": next(iter(model_usage), model or "configured"),
        "version": _cli_version(cli, env),
    }
    for key, field in (("tokens_in", "input_tokens"), ("tokens_out", "output_tokens")):
        value = usage.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            metadata[key] = value
    for key, field in (("cost_usd", "total_cost_usd"), ("credits", "total_credits")):
        value = data.get(field)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value >= 0
        ):
            metadata[key] = float(value)
    cache = usage.get("cache_read_input_tokens")
    if isinstance(cache, int) and not isinstance(cache, bool) and cache > 0:
        metadata["cache_hit"] = True
    return metadata


def _cli_version(cli: Path, env: Mapping[str, str]) -> str:
    override = os.environ.get("DOCS_HARNESS_QODER_CLI_VERSION")
    if override:
        return override
    try:
        result = subprocess.run(
            [str(cli), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            env=dict(env),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    version = result.stdout.strip().splitlines()
    return version[0] if version else "unknown"


def _cli_env(config: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in CLI_ENV_DROP
    }
    env["CI"] = "1"
    env["QODERCN_CONFIG_DIR"] = str(config)
    return env


def _router_system_prompt(registry: Registry) -> str:
    intents = "\n".join(
        f"- {name}: {description}" for name, description in registry.intents.items()
    )
    triggers = "\n".join(
        f"- {name}: {description}"
        for name, description in registry.triggers.items()
    )
    return (
        "You are the Docs Harness intent router. Read the user task and return ONLY "
        "one JSON object.\n"
        "Required keys: intents (array), triggers (array), must_clarify (boolean), "
        "confidence (number 0..1), evidence (array of short strings).\n"
        "Do not return modules; the host resolves them. Do not use tools. Do not wrap "
        "the JSON in markdown.\n"
        f"Intents:\n{intents}\n"
        f"Triggers:\n{triggers}\n"
        "Rules: answer_only is exclusive with action intents. If the target, deliverable, "
        "or scope is too vague, set must_clarify=true, keep tentative intents or [], and "
        "triggers=['clarify_required']; when must_clarify is true, do not include any "
        "other trigger. If the user says not to use Harness, add direct_override. "
        "Confidence below 0.5 is treated as clarify."
    )


def _event_model(
    metadata: Mapping[str, Any], latency_ms: float
) -> dict[str, Any]:
    allowed = {
        "name",
        "version",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "credits",
        "cache_hit",
    }
    result = {key: value for key, value in metadata.items() if key in allowed}
    result["latency_ms"] = latency_ms
    return result


def _render_context(modules: list[str], registry: Registry) -> str:
    lines = [
        f"<!-- docs-harness-routing:{registry.version} modules={','.join(modules)} -->",
        "以下模块契约由 Docs Harness 路由层为本次任务选择；内核规则仍然优先。",
    ]
    for module in modules:
        contract = registry.contracts[module]
        lines.append(f"### {contract['title']}")
        lines.append(str(contract["scope"]))
        lines.extend(f"- {rule}" for rule in contract["rules"])
        lines.append("验证：")
        lines.extend(f"- {item}" for item in contract["verification"])
    return "\n".join(lines)


def _render_cached_context(modules: list[str], registry: Registry) -> str:
    names = ",".join(modules)
    return (
        f"<!-- docs-harness-routing:cache:{registry.version} modules={names} -->\n"
        f"本次是同一会话的后续消息，沿用上次路由的模块：{names}。"
        " 如果本轮交付物或任务类型发生变化，请从 routing/registry.json 读取对应模块契约，"
        "或发送 /route-reset 重新路由。"
    )


def _emit(context: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    json.dump(output, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def _read_payload() -> dict[str, Any] | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"docs-harness router: invalid hook input: {exc}", file=sys.stderr)
        return None
    return value if isinstance(value, dict) else None


def _enabled() -> bool:
    return os.environ.get("DOCS_HARNESS_ROUTER_ENABLED") == "1"


def _project_dir(payload: Mapping[str, Any]) -> Path:
    raw = os.environ.get("QODER_PROJECT_DIR") or payload.get("cwd")
    if not isinstance(raw, str) or not raw:
        raise HookError("project_dir_missing", "QODER_PROJECT_DIR")
    path = Path(raw).expanduser()
    if not path.is_dir():
        raise HookError("project_dir_invalid", "QODER_PROJECT_DIR")
    return path.resolve()


def _registry_for(project: Path) -> Registry:
    explicit = os.environ.get("DOCS_HARNESS_REGISTRY")
    if explicit:
        return load_registry(explicit)
    project_registry = project / "routing" / "registry.json"
    if project_registry.is_file():
        return load_registry(project_registry)
    installed = (project / ".docs-harness" / "config.json").is_file()
    source_registry = SOURCE_ROOT / "routing" / "registry.json"
    if installed and source_registry.is_file():
        return load_registry(source_registry)
    raise HookError("registry_missing", "routing/registry.json")


def _report_error(
    project: Path | None, code: str, field: str, session_id: str
) -> None:
    suffix = f" ({field})" if field else ""
    print(f"docs-harness router: {code}{suffix}", file=sys.stderr)
    if project is None:
        return
    entry = {
        "ts": _now(),
        "code": code,
        "field": field or None,
        "session_hash": hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16],
    }
    try:
        directory = routing_dir(project)
        with open(directory / "hook-errors.jsonl", "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    except (OSError, UnicodeEncodeError) as exc:
        print(f"docs-harness router: error log write failed: {exc}", file=sys.stderr)


def _error_field(exc: Exception) -> str:
    details = getattr(exc, "details", {})
    if isinstance(details, dict):
        field = details.get("field")
        if isinstance(field, str):
            return field
    field = getattr(exc, "field", "")
    return field if isinstance(field, str) else ""


def _task_id(session_id: str, prompt: str) -> str:
    digest = hashlib.sha256(f"{session_id}\0{prompt}".encode("utf-8")).hexdigest()
    return "task-" + digest[:16]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


if __name__ == "__main__":
    raise SystemExit(main())
