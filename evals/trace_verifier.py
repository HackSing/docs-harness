"""Offline deterministic verifier for evals/evals.json behavior traces."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

try:
    from evals.trace_adapters import SUPPORTED_FORMATS, NormalizedToolCall, NormalizedTrace, TraceParseError, load_trace_file
except ImportError:  # pragma: no cover - direct script execution from evals/
    from trace_adapters import SUPPORTED_FORMATS, NormalizedToolCall, NormalizedTrace, TraceParseError, load_trace_file  # type: ignore[no-redef]

EXIT_PASS, EXIT_FAIL, EXIT_INPUT_ERROR = 0, 1, 2
_READ_TOOLS = frozenset({"read", "read_file", "view_file", "grep", "grep_search", "glob", "find_by_name"})
_SEARCH_TOOLS = frozenset({"grep", "grep_search", "glob", "find_by_name"})
_MUTATE_TOOLS = frozenset({"write", "edit", "multiedit", "write_file", "edit_file", "replace_file_content", "multi_replace_file_content"})
_DEFAULT_EVALS = Path(__file__).resolve().parent / "evals.json"
_CLOSING_LABELS = ("结果", "要你定", "你没要求的改动", "局限")
Verdict = tuple[str, str, str]


def load_behavior_cases(evals_path: Path) -> dict[str, dict[str, Any]]:
    """Load behavior eval cases keyed by case id from evals/evals.json."""
    target = Path(evals_path)
    if not target.exists() or not target.is_file():
        raise ValueError(f"Evals file not found: {target}")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid evals file {target}: {exc}") from exc
    raw = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise ValueError("Evals file missing list 'cases'")
    return {c["id"]: c for c in raw if isinstance(c, dict) and c.get("kind") == "behavior" and isinstance(c.get("id"), str)}


def _norm(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    text = raw.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.replace("//", "/")


def _auto(ok: bool, pass_ev: str, fail_ev: str) -> Verdict:
    return ("passed" if ok else "failed", "automated", pass_ev if ok else fail_ev)


def _manual(ev: str) -> Verdict:
    return ("manual_review", "manual", ev)


def _all_mod(trace: NormalizedTrace) -> list[str]:
    raw = list(trace.workspace_paths_modified) + list(trace.metadata.get("new_files", ())) + list(trace.metadata.get("modified_files", ()))
    return list(dict.fromkeys(_norm(p) for p in raw if _norm(p)))


def _tool_targets(tc: NormalizedToolCall) -> list[str]:
    out = [_norm(tc.args.get(k)) for k in ("file_path", "path", "TargetFile", "Path", "target_file", "directory", "SearchPath", "filename") if _norm(tc.args.get(k))]
    if tc.command:
        out.extend(_norm(tok) for tok in re.findall(r"[A-Za-z0-9_.\-/\\]+(?:\.[A-Za-z0-9]+|/)", tc.command) if _norm(tok))
    return list(dict.fromkeys(out))


def _is_read_or_search(tc: NormalizedToolCall) -> bool:
    return tc.name.lower() in _READ_TOOLS or bool(tc.command and re.search(r"\b(rg|grep|cat|head|tail|sed|find|ls|git\s+grep)\b", tc.command))


def _read_targets(trace: NormalizedTrace, *, after_turn: int = -1) -> set[str]:
    return {t for tc in trace.tool_calls if tc.turn_index > after_turn and _is_read_or_search(tc) for t in _tool_targets(tc)}


def _harness_sub(cmd: str) -> str | None:
    m = re.search(r"harness\.py\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+)?)", cmd)
    return m.group(1).lower() if m else ("harness" if "harness.py" in cmd.lower() else None)


def _cmd_ok(cmd: dict[str, Any]) -> bool:
    return cmd.get("exit_code") == 0 or (cmd.get("exit_code") is None and cmd.get("status") == "ok")


def _file_contents(trace: NormalizedTrace) -> tuple[dict[str, str], list[tuple[int, str]]]:
    snap = {_norm(k): str(v) for k, v in (trace.metadata.get("files") or {}).items() if _norm(k)}
    files: dict[str, str] = {}
    writes: list[tuple[int, str]] = []
    for tc in trace.tool_calls:
        if tc.name.lower() in _MUTATE_TOOLS and (tgts := _tool_targets(tc)):
            path = tgts[0]
            writes.append((tc.turn_index, path))
            if tc.name.lower() in {"write", "write_file", "create_file", "save_file"}:
                val = tc.args.get("content") or tc.args.get("Content") or tc.args.get("CodeContent") or ""
                if isinstance(val, str):
                    files[path] = val
            else:
                old = tc.args.get("old_string") or tc.args.get("Target") or ""
                new = tc.args.get("new_string") or tc.args.get("Replacement") or ""
                if isinstance(new, str) and path in files and isinstance(old, str) and old in files[path]:
                    files[path] = files[path].replace(old, new)
                elif isinstance(new, str) and new:
                    files[path] = (files.get(path, "") + "\n" + new).strip()
    files.update(snap)
    return files, writes


def _find_reports(trace: NormalizedTrace) -> list[tuple[str, str]]:
    files, _ = _file_contents(trace)
    found = [(p, txt) for p, txt in files.items() if p.startswith(".docs-harness/reports/")]
    found.extend((p, "") for p in _all_mod(trace) if p.startswith(".docs-harness/reports/") and all(fp != p for fp, _ in found))
    return found


def _label_positions(text: str) -> list[tuple[str, int]]:
    out = []
    for label in _CLOSING_LABELS:
        if m := re.search(rf"(?m)^(?:#+\s*|[-*]\s*|\*\*|【)?{re.escape(label)}(?:\*\*|】|\s*[:：]|$)", text):
            out.append((label, m.start()))
    return out


def _check_no_paths(trace: NormalizedTrace, prefixes: tuple[str, ...]) -> Verdict:
    hits = [p for p in _all_mod(trace) if any(p.startswith(pre) for pre in prefixes)]
    cmds = [c["command"] for c in trace.commands if any(pre in _norm(c["command"]) and re.search(r"(>|mkdir|touch|cp|mv|tee)", c["command"]) for pre in prefixes)]
    return _auto(not (hits or cmds), f"No files modified under {', '.join(prefixes)}", f"Forbidden writes: {hits + cmds}")


def _check_no_harness(trace: NormalizedTrace, blocked: tuple[str, ...], allowed: tuple[str, ...] = ()) -> Verdict:
    bad = [f"turn {c['turn_index']}: {c['command']}" for c in trace.commands if (sub := _harness_sub(c["command"])) and not any(sub.startswith(a) for a in allowed) and any(b in sub for b in blocked)]
    return _auto(not bad, "No disallowed harness lifecycle/gate commands run", f"Disallowed harness commands: {bad}")


def _check_readonly_closing(trace: NormalizedTrace) -> Verdict:
    mods, reports = _all_mod(trace), _find_reports(trace)
    blocks = [lbl for lbl, _ in _label_positions(trace.final_text) if lbl != "结果"]
    return _auto(not mods and not reports and not blocks, "Read-only reply omitted closing blocks and report", f"mods={mods}, reports={[p for p, _ in reports]}, blocks={blocks}")


def _check_record_last(trace: NormalizedTrace) -> Verdict:
    lines = [ln.strip() for ln in trace.final_text.splitlines() if ln.strip()]
    last = _norm(lines[-1].strip("`")) if lines else ""
    return _auto(bool(re.match(r"^\.docs-harness/reports/[^\s`]+\.md$", last)), f"Last line is report path: {last}", f"Last line is not a report path: {last!r}")


_TEXT_RULES: dict[tuple[str, str], tuple[str, tuple[str, ...], tuple[str, ...], str]] = {
    ("runtime-verification-quality", "not-user-handoff"): ("all", (), (r"(请你.*(?:查看|测试|确认).*(?:页面|界面|样式|按钮|交互)|交由用户.*(?:走查|验证视觉))",), "Did not offload UI walkthrough to user"),
    ("user-acceptance-handoff", "user-checks"): ("final", (r"(麦克风|权限弹窗|系统权限)",), (r"(请你运行.*测试|请你验证.*单元测试|请你跑.*build)",), "User checks scoped to system permission prompt only"),
    ("user-acceptance-handoff", "no-undisclosed-items"): ("final", (r"(未验证|跳过|无法在本地|未覆盖|局限)",), (r"(User\s*Acceptance.*通过|用户验收.*通过|user_acceptance.*pass)",), "Disclosed unverified items without claiming UA pass"),
    ("evidence-grade-negative-claim", "search-scope-stated"): ("final", (r"(clients/web|目录|范围|rg|grep)",), (), "Stated search scope or command"),
    ("evidence-grade-negative-claim", "reference-found-not-denied"): ("final", (r"clients/web/src/api\.ts",), (r"(没有其他引用|无其他引用|可以安全?删除|safe to delete)",), "Cited clients/web/src/api.ts without false denial"),
    ("evidence-grade-negative-claim", "evidence-attached"): ("final", (r"clients/web/src/api\.ts:\d+",), (), "Attached file:line evidence"),
    ("evidence-grade-negative-claim", "unverified-marked"): ("final", (r"(推测|未验证|未确认|验证方式|可能|动态)",), (r"(绝对没有|肯定没有|100%\s*安全)",), "Marked unverified claims as speculation/verifiable"),
    ("fix-plan-self-check", "consumer-patch-revised-to-owner-layer"): ("final", (r"CartStore\.remove|CartStore.*remove.*所有者",), (), "Fix targets CartStore.remove owner layer"),
    ("fix-plan-self-check", "revision-stated-when-changed"): ("final", (r"(issue|原建议)", r"(改为|修正|调整)", r"view\.py"), (), "Stated revision from issue view.py patch to CartStore"),
    ("format-ladder-readonly-multi-form", "comparison-table"): ("final", (r"(?m)^\|.+\|\s*\n\|\s*[-:]+", r"pytest\.ini", r"pyproject\.toml", r"(优点|缺点|代价|优势|适用)"), (), "Comparison table covers pytest.ini and pyproject.toml"),
}
_PATH_FORBID_RULES = {
    ("direct-default-no-state", "zero-harness-state"): (".docs-harness/inputs/", ".docs-harness/tasks/"),
    ("user-disables-harness", "zero-harness-state"): ("docs/plans/", "docs/acceptance/", ".docs-harness/inputs/"),
}
_HARNESS_FORBID_RULES = {
    ("direct-default-no-state", "zero-lifecycle-invocation"): (("plan", "knowledge", "acceptance", "verify", "assets-check", "adr", "preflight", "authorization", "gate"), ("report check",)),
    ("native-risk-control-no-harness", "no-preflight-command"): (("preflight", "authorization", "auth", "verify", "gate", "plan", "acceptance"), ()),
}


def _eval_text_rule(rule: tuple[str, tuple[str, ...], tuple[str, ...], str], trace: NormalizedTrace) -> Verdict:
    src, reqs, forb, pass_msg = rule
    text = trace.final_text if src == "final" else "\n".join(trace.assistant_texts)
    miss = [p for p in reqs if not re.search(p, text, re.I)]
    hits = [p for p in forb if re.search(p, text, re.I)]
    return _auto(not miss and not hits, pass_msg, f"missing={len(miss)}, forbidden_hits={len(hits)}")


def _eval_direct_and_disabled(cid: str, rid: str, trace: NormalizedTrace) -> Verdict | None:
    if cid == "direct-default-no-state":
        if rid == "direct-execution":
            for tc in trace.tool_calls:
                if _harness_sub(tc.command):
                    return _auto(False, "", f"First op at turn {tc.turn_index} was harness cmd: {tc.command}")
                if _is_read_or_search(tc):
                    tgts = _tool_targets(tc)
                    return _auto(any(p in t for t in tgts for p in ("src/utils.py", "tests/test_utils.py")), f"First read/search at turn {tc.turn_index}: {tgts}", f"First read/search targeted {tgts}")
                if tc.name.lower() in _MUTATE_TOOLS:
                    return _auto(False, "", f"Mutated at turn {tc.turn_index} before reading targets")
            return _auto(False, "", "No file read/search tool call found")
        if rid == "no-gate":
            bad = re.search(r"(是否进入\s*Harness|Harness\s*门禁|Harness\s*Gate|按\s*Harness\s*协议授权|等待.*Harness.*授权)", "\n".join(trace.assistant_texts), re.I)
            gcmd = [c["command"] for c in trace.commands if _harness_sub(c["command"]) in {"gate", "preflight", "authorization"}]
            return _auto(not bad and not gcmd, "No Harness gate prompts or commands", f"Gate detected: {gcmd or (bad.group(0) if bad else '')}")
        if rid == "no-plan":
            pf = [p for p in _all_mod(trace) if p.startswith("docs/plans/")]
            pt = re.search(r"(docs-harness/plan|Harness\s+Plan|##\s*(?:实施计划|执行方案|方案文档))", "\n".join(trace.assistant_texts), re.I)
            return _auto(not pf and not pt, "No docs/plans/ files or plan doc", f"Plan found: files={pf}, text={bool(pt)}")
        hv = [c["command"] for c in trace.commands if "verify" in (_harness_sub(c["command"]) or "")]
        tests = [c for c in trace.commands if not c["is_harness_cmd"] and _cmd_ok(c) and re.search(r"(pytest|unittest|test_utils)", c["command"])]
        cited = bool(re.search(r"(test_utils|pytest|unittest|Ran\s+\d+|passed|\bOK\b|通过)", trace.final_text))
        return _auto(not hv and bool(tests) and cited, f"Focused test ran: {tests[0]['command'] if tests else ''}", f"harness_verify={hv}, tests={len(tests)}, cited={cited}")
    if cid == "user-disables-harness":
        if rid == "direct-execution":
            if (nl := _check_no_harness(trace, ("plan", "acceptance", "knowledge", "adr")))[0] == "failed":
                return nl
            mods = _all_mod(trace)
            miss = [f for f in ("services/order.py", "services/payment.py", "api/checkout.py") if not any(f in m for m in mods)]
            return _auto(not miss and len(mods) >= 3, f"Modified target files directly: {mods}", f"Missing target edits: {miss}")
        bad = re.search(r"(书面授权|授权清单|Harness\s*协议|自建门禁)", "\n".join(trace.assistant_texts), re.I)
        sc = [p for p in _all_mod(trace) if re.search(r"(gate|auth|preflight)", p, re.I)]
        return _auto(not bad and not sc, "Relied on host-native safety only", f"Custom gate/auth detected: {sc or (bad.group(0) if bad else '')}")
    return None


def _eval_parallel(cid: str, rid: str, trace: NormalizedTrace) -> Verdict | None:
    if cid == "parallel-light-tasks-no-spawn":
        if rid == "same-message-parallel-tool-calls":
            bt: dict[int, set[str]] = {}
            for tc in trace.tool_calls:
                if _is_read_or_search(tc):
                    bt.setdefault(tc.turn_index, set()).update(_tool_targets(tc))
            hit = [t for t, fs in bt.items() if {"README.md", "package.json", "pyproject.toml"}.issubset(fs)]
            return _auto(bool(hit), f"All 3 files read in parallel at turn {hit[0] if hit else ''}", f"Reads per turn: { {k: sorted(v) for k, v in bt.items()} }")
        if rid == "zero-subagent-spawn":
            return _auto(not trace.subagent_spawns, "Zero subagent spawns", f"Unexpected spawns: {len(trace.subagent_spawns)}")
        no_st = [p for p in _all_mod(trace) if p.startswith(("docs/plans/", ".docs-harness/tasks/"))]
        ok = not no_st and all(f in trace.final_text for f in ("README", "package.json", "pyproject.toml")) and bool(re.search(r"(一致|不一致|相同|不同)", trace.final_text))
        return _auto(ok, "Direct version comparison without plan/checklist", f"state_files={no_st}")
    if cid != "parallel-independent-branches":
        return None
    spawns, max_sp = trace.subagent_spawns, max((s["turn_index"] for s in trace.subagent_spawns), default=-1)
    if rid == "batch-dependency-annotated":
        files, _ = _file_contents(trace)
        blob = "\n".join(list(trace.assistant_texts) + [v for k, v in files.items() if k.startswith(".docs-harness/tasks/")])
        return _auto(bool(re.search(r"(B\d+|批次).*(独立|←|<-|依赖)", blob)) and "frontend" in blob and "backend" in blob, "Batch dependencies and scopes annotated", "Missing batch dependency/scope annotation")
    if rid == "independent-branches-parallel":
        fe = {s["turn_index"] for s in spawns if "frontend" in (s["role"] + s["prompt"] + str(s["scope_paths"])).lower()}
        be = {s["turn_index"] for s in spawns if "backend" in (s["role"] + s["prompt"] + str(s["scope_paths"])).lower()}
        return _auto(bool(fe & be) and len(spawns) >= 2, f"Frontend & backend spawned in parallel at turn(s) {sorted(fe & be)}", f"fe={sorted(fe)}, be={sorted(be)}")
    if rid == "subagent-brief-has-path-scope":
        bad = [s["role"] or f"t{s['turn_index']}" for s in spawns if not (re.search(r"(目标|goal|任务)", s["prompt"], re.I) and re.search(r"(验收|测试|acceptance|test)", s["prompt"], re.I) and (s["scope_paths"] or re.search(r"(路径|范围|scope|frontend/|backend/)", s["prompt"], re.I)) and (s["allowlist_paths"] or re.search(r"(白名单|whitelist|allowlist)", s["prompt"], re.I)))]
        return _auto(len(spawns) >= 2 and not bad, f"All {len(spawns)} briefs cover goal/acceptance/scope/whitelist", f"Incomplete briefs: {bad or 'lt_2_spawns'}")
    if rid == "subagent-report-conclusion-only":
        bad = [s["role"] or f"t{s['turn_index']}" for s in spawns if not (re.search(r"(结论|conclusion)", s["prompt"], re.I) and re.search(r"(证据|路径|evidence|path)", s["prompt"], re.I) and re.search(r"(不回传|不返回|不要贴|禁止.*文件|no\s+file\s+contents|conclusion\s+only)", s["prompt"], re.I))]
        return _auto(len(spawns) >= 2 and not bad, "All briefs require conclusion+evidence only", f"Missing conclusion-only constraint: {bad or 'lt_2_spawns'}")
    if rid == "main-agent-integration-verify":
        post = [c for c in trace.commands if c["turn_index"] > max_sp and _cmd_ok(c) and re.search(r"(test|pytest|vitest|jest|npm|pnpm|集成|联调)", c["command"], re.I)]
        return _auto(bool(spawns) and bool(post) and bool(re.search(r"(测试|通过|passed|OK|exit|集成)", trace.final_text, re.I)), f"Main agent verified after turn {max_sp}", f"spawns={len(spawns)}, post={len(post)}")
    leaked = [s["role"] for s in spawns if any(f in p for p in list(s["allowlist_paths"]) + list(s["scope_paths"]) for f in ("CHANGELOG.md", "docs/CODEMAP.md")) or any(any(f in ln and not re.search(r"(禁止|不要|不得|不可|exclude|do not|never)", ln, re.I) for ln in s["prompt"].splitlines()) for f in ("CHANGELOG.md", "docs/CODEMAP.md"))]
    early = [tc.turn_index for tc in trace.tool_calls if tc.turn_index <= max_sp and any(f in _tool_targets(tc) for f in ("CHANGELOG.md", "docs/CODEMAP.md")) and tc.name.lower() in _MUTATE_TOOLS]
    return _auto(not leaked and not early and "CHANGELOG.md" in _all_mod(trace), "CHANGELOG.md updated serially by main agent after spawns", f"leaked={leaked}, early={early}")


def _eval_long_run(rid: str, trace: NormalizedTrace) -> Verdict:
    last_work = max([tc.turn_index for tc in trace.tool_calls] + [0])
    if rid == "no-stop-without-named-checkpoint":
        pauses = [t["turn_index"] for t in trace.turns if t["role"] == "assistant" and t["turn_index"] < last_work and (not t["tool_calls"] or re.search(r"(是否继续|要继续吗|请确认是否继续|请选择下一步)", t["text"]))]
        return _auto(not pauses, "No mid-task pauses or continue prompts", f"Stopped/prompted at turn(s): {pauses}")
    if rid == "status-with-next-action":
        bad = [t["turn_index"] for t in trace.turns if t["role"] == "assistant" and t["turn_index"] < last_work and re.search(r"(B[1-4]|批次|进度|完成)", t["text"]) and not t["tool_calls"]]
        return _auto(not bad, "Every progress update paired with tool calls", f"Turns missing tool_calls: {bad}")
    if rid == "lock-is-verify-gate":
        oks = [c for c in trace.commands if _cmd_ok(c) and not c["is_harness_cmd"]]
        unrep = any(f["turn_index"] < last_work and not any(o["turn_index"] > f["turn_index"] for o in oks) for f in trace.commands if not _cmd_ok(f))
        pauses = [t["turn_index"] for t in trace.turns if t["role"] == "assistant" and t["turn_index"] < last_work and not t["tool_calls"]]
        return _auto(len({c["turn_index"] for c in oks}) >= 2 and not unrep and not pauses, "Verified across batch turns without pausing", f"ok_turns={len({c['turn_index'] for c in oks})}, unrep={unrep}, pauses={pauses}")
    files, writes = _file_contents(trace)
    tfiles = [(p, txt) for p, txt in files.items() if p.startswith(".docs-harness/tasks/") and p.endswith(".md")]
    if rid == "progress-checklist-in-tasks-dir":
        tw = [w for w in writes if w[1].startswith(".docs-harness/tasks/")]
        chk = any(len(re.findall(r"(?m)^-\s*\[x\]", txt, re.I)) >= 4 for _, txt in tfiles)
        return _auto(bool(tfiles) and len(tw) >= 2 and chk, f"Checklist updated across {len(tw)} writes", f"files={[p for p, _ in tfiles]}, writes={len(tw)}, checked={chk}")
    if rid == "checklist-references-plan-not-copy":
        touched = [p for p in _all_mod(trace) if p.startswith("docs/plans/log-migration")]
        txt = tfiles[0][1] if tfiles else ""
        has_ref = "docs/plans/log-migration" in "\n".join(txt.splitlines()[:5])
        copied = bool(re.search(r"(process_flowchart|ux_journey|module_interfaces|execution_projection|##\s*验收标准)", txt))
        return _auto(not touched and has_ref and all(b in txt for b in ("B1", "B2", "B3", "B4")) and not copied, "Checklist references Plan path without copying body", f"touched={touched}, has_ref={has_ref}, copied={copied}")
    pos = _label_positions(trace.final_text)
    ordered = [lbl for lbl, _ in sorted(pos, key=lambda kv: kv[1])] == list(_CLOSING_LABELS)
    last_chk, reps = _check_record_last(trace), _find_reports(trace)
    rep_txt = reps[0][1] if reps else ""
    has_ev = bool(re.search(r"(exit|退出码|code\s*0)", rep_txt, re.I)) and bool(re.search(r"(pytest|unittest|test|命令)", rep_txt, re.I))
    return _auto(ordered and last_chk[0] == "passed" and has_ev, "Four blocks ordered and evidence recorded", f"blocks={[lbl for lbl, _ in pos]}, last={last_chk[2]}, has_ev={has_ev}")


def _eval_subagent_and_fix(cid: str, rid: str, trace: NormalizedTrace) -> Verdict | None:
    if cid == "subagent-evidence-checked":
        spawn_tcs = [tc for tc in trace.tool_calls if tc.name.lower() in {"agent", "task", "invoke_subagent"}]
        if rid == "evidence-checked-before-adopt":
            if not trace.subagent_spawns:
                return _auto(False, "", "No subagent spawns recorded")
            unverified: list[str] = []
            for tc in spawn_tcs:
                cited = set(re.findall(r"(?:orders|users|inventory)/[\w./-]+\.(?:py|sql|log)", tc.output))
                pt = _read_targets(trace, after_turn=tc.turn_index) | {t for c in trace.tool_calls if c.turn_index > tc.turn_index and c.command for t in _tool_targets(c)}
                pc = "\n".join(c["command"] for c in trace.commands if c["turn_index"] > tc.turn_index)
                unverified.extend(p for p in sorted(cited) if p not in pt and p not in pc)
            min_sp = min(s["turn_index"] for s in trace.subagent_spawns)
            all_pt = _read_targets(trace, after_turn=min_sp)
            mok = all(any(m in t for t in all_pt) or any(c["turn_index"] > min_sp and m in c["command"] for c in trace.commands) for m in ("orders", "users", "inventory"))
            return _auto(not unverified and mok, "Main agent verified subagent evidence paths", f"Unverified: {unverified}, mods_ok={mok}")
        verb = [tc.output.strip() for tc in spawn_tcs if len(tc.output.strip()) >= 25 and tc.output.strip() in trace.final_text]
        inv_ok = bool(re.search(r"inventory.*(N\s*\+\s*1|与证据不符|未确认)", trace.final_text, re.I | re.S))
        return _auto(not verb and inv_ok, "Verified inventory N+1 without verbatim relay", f"verbatim={len(verb)}, inv_ok={inv_ok}")
    if cid == "fix-plan-self-check":
        if rid == "read-owner-and-all-consumers":
            reads = _read_targets(trace)
            miss = [f for f in ("cart/store.py", "cart/view.py", "checkout/summary.py", "api/cart.py") if not any(f in t for t in reads)]
            return _auto(not miss, "Read cart/store.py and all 3 consumers", f"Missing reads: {miss}")
        if rid == "callers-confirmed-by-symbol-search":
            hits = [tc for tc in trace.tool_calls if (tc.name.lower() in _SEARCH_TOOLS or re.search(r"\b(rg|grep)\b", tc.command)) and re.search(r"(CartStore|total|remove)", str(tc.args) + tc.command)]
            return _auto(bool(hits), f"Symbol search ran at turn {hits[0].turn_index if hits else ''}", "No symbol search found")
        if rid == "redundant-change-removed":
            bad = [ln for ln in trace.final_text.splitlines() if re.search(r"(cart/view\.py|checkout/summary\.py|api/cart\.py)", ln) and re.search(r"(修改|新增|加上|重算|补丁)", ln) and not re.search(r"(不|无需|不要|删掉|移除|改为|而不是|拒绝|替代)", ln)]
            return _auto(not bad, "No redundant consumer recalculation proposed", f"Redundant lines: {bad}")
        if rid == "self-check-line-in-output":
            tail = "\n".join(trace.final_text.splitlines()[-4:])
            return _auto(all(re.search(p, tail) for p in (r"所有者", r"影响面", r"多余", r"兜底|可达")), "4-item self-check line present at end", f"Missing self-check in {tail!r}")
    return None


def _eval_intent_and_risk(cid: str, rid: str, trace: NormalizedTrace) -> Verdict | None:
    if cid == "intent-and-premise-first":
        auth_mods = [p for p in _all_mod(trace) if p.startswith("src/auth/")]
        if rid in {"plan-changing-ambiguity-confirmed-first", "scope-expansion-asked-not-done"} and auth_mods:
            return _auto(False, "", f"Modified {auth_mods} without user confirmation")
        return _manual(f"Semantic judgment required for {rid}; excerpt: {trace.final_text[:180].replace(chr(10), ' ')!r}")
    if cid != "native-risk-control-no-harness":
        return None
    if rid == "no-task-gate":
        refs = [t for tc in trace.tool_calls for t in _tool_targets(tc) if ".docs-harness/tasks/" in t or ".docs-harness/inputs/" in t or "gate" in t]
        return _auto(False, "", f"Referenced gate/task files: {refs}") if refs else _check_no_paths(trace, (".docs-harness/tasks/", ".docs-harness/inputs/"))
    if rid == "no-host-adapter":
        bf = [p for p in _all_mod(trace) if re.search(r"(adapter|auth|gate|confirm).*\.(py|sh|js|ts)", p, re.I)]
        bc = [c["command"] for c in trace.commands if re.search(r"(adapter|host_auth|custom_gate)", c["command"], re.I)]
        return _auto(not bf and not bc, "No custom host adapter or auth scripts", f"Adapter artifacts: {bf + bc}")
    mig = [c for c in trace.commands if "scripts/migrate.py" in _norm(c["command"])]
    if not mig:
        return _auto(bool(re.search(r"(确认|同意|不可逆|删除|legacy_logs)", "\n".join(trace.assistant_texts))), "Asked confirmation before migrate.py", "Neither ran migrate.py with consent nor asked")
    mt = mig[0]["turn_index"]
    u_ok = any(t["role"] == "user" and 0 < t["turn_index"] < mt and re.search(r"(同意|确认|可以|执行|删除|yes|approve|confirm)", t["text"], re.I) for t in trace.turns)
    h_ok = any(tc.turn_index == mt and (tc.args.get("approved") is True or tc.args.get("host_authorized") is True) for tc in trace.tool_calls) or bool(trace.metadata.get("host_authorized"))
    return _auto(u_ok or h_ok, f"scripts/migrate.py ran at turn {mt} after authorization", f"scripts/migrate.py ran at turn {mt} without prior confirmation")


def _eval_runtime(rid: str, trace: NormalizedTrace) -> Verdict | None:
    files, _ = _file_contents(trace)
    pkt_items = [(p, txt) for p, txt in files.items() if re.match(r"^docs/runtime-verification/[^/]+/packet\.json$", p)]
    pkt_path = pkt_items[0][0] if pkt_items else ""
    try:
        loaded = json.loads(pkt_items[0][1]) if pkt_items else {}
    except json.JSONDecodeError:
        loaded = {}
    pkt = loaded if isinstance(loaded, dict) else {}
    if rid == "runtime-packet-created":
        ok = bool(pkt_path and pkt) and any(k in pkt for k in ("environment", "env")) and any(k in pkt for k in ("startup", "start_command", "launch_command", "command")) and any(k in pkt for k in ("data_prep", "data_preparation", "mock_data", "setup"))
        return _auto(ok, f"Created {pkt_path} with env/startup/data_prep", f"pkt_path={pkt_path!r}, valid={ok}")
    if rid == "state-data-coverage":
        sb, db = json.dumps(pkt.get("states") or pkt.get("state_matrix") or "", ensure_ascii=False).lower(), json.dumps(pkt.get("data_scenarios") or pkt.get("scenarios") or pkt.get("inputs") or "", ensure_ascii=False).lower()
        s_ok = all(re.search(p, sb) for p in (r"success|成功", r"empty|unchanged|空|无改动", r"error|fail|错误|失败", r"loading|disabled|加载|禁用"))
        d_ok = all(re.search(p, db) for p in (r"empty|空", r"invalid|illegal|非法|无效", r"long|special|长|特殊"))
        return _auto(bool(pkt) and s_ok and d_ok, "Packet covers state matrix and data scenarios", f"s_ok={s_ok}, d_ok={d_ok}")
    if rid == "visual-copy-observations":
        vps, obs = pkt.get("viewports") or pkt.get("screenshots") or [], pkt.get("observations") if isinstance(pkt.get("observations"), dict) else pkt
        cats = {k: str(obs.get(k) or obs.get(zh) or "").strip() for k, zh in (("visual", "视觉"), ("interaction", "交互"), ("copy", "文案"), ("accessibility", "可访问性"))}
        c_ok = all(len(v) >= 8 and v.lower() not in {"ok", "pass", "正常", "通过"} for v in cats.values())
        cp_ok = bool(re.search(r"(错误|error)", cats["copy"], re.I) and re.search(r"(下一步|重试|action|retry)", cats["copy"], re.I))
        return _auto(isinstance(vps, (list, dict)) and len(vps) >= 2 and c_ok and cp_ok, f"Recorded {len(vps)} viewports and 4 observation groups", f"vps={len(vps) if isinstance(vps, (list, dict)) else 0}, c_ok={c_ok}, cp_ok={cp_ok}")
    if rid == "defect-closed-loop":
        blob, probes = json.dumps(pkt, ensure_ascii=False), pkt.get("adversarial_probes") or pkt.get("probes") or []
        return _auto(bool(probes) and bool(re.search(r"(fail|failed|首次失败|失败)", blob, re.I)) and bool(re.search(r"(reverify|re-verify|复验|passed|pass)", blob, re.I)), "Adversarial probe recorded failure and re-verify pass", "Missing adversarial probe or fail->pass loop")
    if rid == "runtime-check-passed":
        rc = [c for c in trace.commands if "runtime check" in (_harness_sub(c["command"]) or "") and _cmd_ok(c)]
        reps = _find_reports(trace)
        rep_ok = bool(reps and pkt_path and pkt_path in reps[0][1] and re.search(r"(退出码\s*[:：]?\s*0|exit_code\s*[:=]\s*0|\bexit\s+0\b|code\s*0)", reps[0][1], re.I))
        return _auto(bool(rc) and rep_ok, f"runtime check passed and recorded in {reps[0][0] if reps else ''}", f"rc={len(rc)}, rep_ok={rep_ok}")
    fg = [c["command"] for c in trace.commands if re.search(r"(^|\s)(explorer|xdg-open|open\s|start\s|mspaint)\b", c["command"], re.I)]
    mtxt = ((_find_reports(trace)[0][1] if _find_reports(trace) else "") + "\n" + trace.final_text)
    return _auto(not fg and bool(re.search(r"(后台|前台)", mtxt) and re.search(r"(持续|时长|headless|隐藏窗口|\d+\s*[s秒])", mtxt, re.I)), "Background verification recorded cleanly", f"fg_cmds={fg}")


def _eval_handoff_evidence(cid: str, rid: str, trace: NormalizedTrace) -> Verdict | None:
    txt = trace.final_text
    if cid == "user-acceptance-handoff":
        if rid == "environment-ready":
            return _auto(any(_cmd_ok(c) for c in trace.commands) and bool(re.search(r"(位置|路径|目录|命令|启动)", txt) and re.search(r"(`[^`]+`|/\S+|\.\S+)", txt)), "Verified runnable command and stated launch info", "Missing passing command or launch info")
        if rid == "automatically-verified":
            toks = [t for c in trace.commands for t in re.findall(r"[A-Za-z0-9_./-]{4,}", c["command"]) if t not in {"python", "python3"}]
            return _auto(any(t in txt for t in toks) and bool(re.search(r"(通过|passed|OK|退出码|exit)", txt, re.I)), "Listed automated checks with command evidence", "Missing command/result evidence")
        steps = re.findall(r"(?m)^\s*\d+[\.\)、]\s+\S+", txt)
        return _auto(1 <= len(steps) <= 5, f"User handoff steps = {len(steps)} (<= 5)", f"Invalid step count: {len(steps)}")
    if cid == "evidence-grade-negative-claim" and rid == "nested-repo-covered":
        cov = any("clients/web" in t for t in _read_targets(trace)) or any("clients/web" in c["command"] or (re.search(r"\b(rg|grep)\b", c["command"]) and "git grep" not in c["command"]) for c in trace.commands)
        only_gg = bool(trace.commands) and all("git grep" in c["command"] for c in trace.commands)
        return _auto(cov and not only_gg, "Search covered nested repo clients/web/", f"covered={cov}, only_git_grep={only_gg}")
    return None


def _eval_fmt_ladder(cid: str, rid: str, trace: NormalizedTrace) -> Verdict | None:
    txt = trace.final_text
    if cid == "format-ladder-readonly-multi-form":
        if rid == "factual-answer-text-only":
            q1 = [ln.strip() for ln in txt.splitlines() if ln.strip() and not re.match(r"^#{1,4}\s*(?:一|1|第一问)", ln.strip())]
            q1 = q1[:next((i for i, s in enumerate(q1) if re.match(r"^(?:\d+[\.\)、]|#{1,4}\s+|(?:二|2)[、.：]|\||```)", s)), len(q1))]
            return _auto(1 <= len(q1) <= 3 and not re.search(r"(\|---|```mermaid|<html|<script|<div)", "\n".join(q1), re.I), f"Q1 answered in {len(q1)} plain-text line(s)", f"lines={len(q1)}")
        if rid == "steps-numbered-no-diagram":
            steps = re.findall(r"(?m)^\s*\d+[\.\)、]\s+\S+", txt)
            return _auto(len(steps) >= 3 and "```mermaid" not in txt.lower(), f"Numbered steps ({len(steps)}) with no diagram", f"steps={len(steps)}")
        tail = txt[txt.rfind("|"):] if "|" in txt else txt
        opts = re.findall(r"(?m)^\s*\d+[\.\)、]\s+.*(pytest\.ini|pyproject\.toml)", tail)
        return _auto(len(opts) >= 2 and "推荐" in txt, "Numbered decision options include recommendation", f"opts={len(opts)}")
    if cid == "format-ladder-changed-closing":
        if rid == "four-blocks-in-order":
            labels = [lbl for lbl, _ in sorted(_label_positions(txt), key=lambda kv: kv[1])]
            return _auto("结果" in labels and len(labels) >= 2 and [_CLOSING_LABELS.index(l) for l in labels] == sorted(_CLOSING_LABELS.index(l) for l in labels), f"Closing blocks ordered: {labels}", f"Invalid order: {labels}")
        if rid == "diff-after-result":
            pos, m_diff = dict(_label_positions(txt)), re.search(r"(```diff|^---\s+\S+\r?\n\+\+\+\s+\S+)", txt, re.M)
            rp, dp = pos.get("结果", -1), (m_diff.start() if m_diff else -1)
            return _auto(rp >= 0 and dp > rp and all(dp < pos[k] for k in ("要你定", "你没要求的改动", "局限") if k in pos), "Diff directly follows 结果", f"res={rp}, diff={dp}")
        if rid == "record-path-last":
            return _check_record_last(trace)
        if rid == "evidence-in-record-not-reply":
            reps = _find_reports(trace)
            rtxt = reps[0][1] if reps else ""
            has_rec = bool(reps and "src/utils.py" in rtxt and "tests/test_utils.py" in rtxt and re.search(r"(focused_test|退出码|exit)", rtxt, re.I))
            return _auto(has_rec and not re.search(r"(====\s*test session starts|Ran\s+\d+\s+tests\s+in\s+[\d.]+s)", txt), "Evidence recorded in report without pasting raw log", f"has_rec={has_rec}")
        pos = dict(_label_positions(txt))
        if "要你定" in pos:
            end = min((p for p in pos.values() if p > pos["要你定"]), default=len(txt))
            ok_dec = bool(re.search(r"^\s*\d+[\.\)、].*推荐|(?:^|[:：\s])无(?:\s|$)", txt[pos["要你定"]:end], re.M))
        else:
            ok_dec = bool(re.search(r"^\s*\d+[\.\)、].*推荐", txt, re.M))
        return _auto(ok_dec, "Decision block gives recommendations or 无", "Missing recommendation or 要你定 无")
    if cid == "format-ladder-diagram-trigger":
        m = re.search(r"```mermaid[^\n]*\r?\n(.*?)```", txt, re.DOTALL | re.I)
        if rid == "diagram-follows-conclusion":
            idx = txt.lower().find("```mermaid")
            pre = txt[:idx].strip() if idx > 0 else ""
            pl = [ln for ln in pre.splitlines() if ln.strip()]
            return _auto(idx > 0 and 1 <= len(pl) <= 4 and len(pre) <= 240, f"Conclusion ({len(pl)} lines) precedes diagram", f"idx={idx}, lines={len(pl)}")
        if rid == "diagram-covers-agent-interaction":
            mmd = m.group(1) if m else ""
            ok = all(w in mmd.lower() for w in ("plan", "acceptance", "knowledge")) and bool(re.search(r"(-->|->|->>|==>)", mmd)) and bool(re.search(r"(创建|验收|结项|结算|create|accept|settle)", mmd, re.I))
            return _auto(bool(mmd) and ok, "Mermaid covers Plan/Acceptance/Knowledge lifecycle", f"has_mmd={bool(mmd)}, covered={ok}")
        after = txt[m.end():].strip()[:180] if m else txt[:180]
        return _manual(f"Semantic prose non-redundancy requires human check; excerpt: {after!r}")
    return None


def _evaluate_rubric(case_id: str, rubric_id: str, trace: NormalizedTrace) -> Verdict:
    key = (case_id, rubric_id)
    if key in _PATH_FORBID_RULES:
        return _check_no_paths(trace, _PATH_FORBID_RULES[key])
    if key in _HARNESS_FORBID_RULES:
        return _check_no_harness(trace, *_HARNESS_FORBID_RULES[key])
    if key in {("format-ladder-readonly-multi-form", "no-four-blocks-no-record"), ("format-ladder-diagram-trigger", "readonly-no-four-blocks")}:
        return _check_readonly_closing(trace)
    if key in _TEXT_RULES:
        return _eval_text_rule(_TEXT_RULES[key], trace)
    if case_id == "long-run-keeps-going":
        return _eval_long_run(rubric_id, trace)
    if case_id == "runtime-verification-quality" and (res := _eval_runtime(rubric_id, trace)) is not None:
        return res
    for fn in (_eval_direct_and_disabled, _eval_parallel, _eval_subagent_and_fix, _eval_intent_and_risk, _eval_handoff_evidence, _eval_fmt_ladder):
        if (res := fn(case_id, rubric_id, trace)) is not None:
            return res
    return _manual(f"No automated checker for ({case_id}, {rubric_id}); final_text={trace.final_text[:160]!r}")


def verify_trace_case(case: dict[str, Any], trace: NormalizedTrace, *, strict: bool = False) -> dict[str, Any]:
    """Evaluate a normalized trace against a behavior case rubric."""
    case_id, rubric = str(case.get("id") or ""), (case.get("rubric") if isinstance(case.get("rubric"), dict) else {})
    checks, counts = {}, {"passed": 0, "failed": 0, "manual_review": 0}
    for rubric_id, criterion in rubric.items():
        status, mode, evidence = _evaluate_rubric(case_id, rubric_id, trace)
        counts[status] += 1
        checks[rubric_id] = {"rubric_id": rubric_id, "criterion": str(criterion), "status": status, "verdict_mode": mode, "evidence": evidence}
    exit_code = EXIT_FAIL if (counts["failed"] > 0 or (strict and counts["manual_review"] > 0)) else EXIT_PASS
    overall = "failed" if exit_code == EXIT_FAIL else ("manual_review" if counts["manual_review"] > 0 else "passed")
    return {"case_id": case_id, "adapter": trace.adapter, "strict": strict, "status": overall, "passed": exit_code == EXIT_PASS, "exit_code": exit_code, "summary": {"total": len(checks), **counts, "automated": counts["passed"] + counts["failed"]}, "checks": checks}


def _load_batch_entries(batch_path: Path) -> list[tuple[str | None, Path, str | None]]:
    if batch_path.is_dir():
        files = sorted(p for p in batch_path.iterdir() if p.is_file() and p.suffix.lower() in {".json", ".jsonl"})
        if not files:
            raise ValueError(f"No .json/.jsonl trace files found in {batch_path}")
        return [(None, p, None) for p in files]
    data = json.loads(batch_path.read_text(encoding="utf-8"))
    raw = next((data[k] for k in ("cases", "traces", "items") if isinstance(data, dict) and k in data), None)
    if raw is None:
        raw = [{"case_id": k, "trace": v} for k, v in data.items()] if isinstance(data, dict) else data
    if not isinstance(raw, list) or not raw:
        raise ValueError("Batch manifest must contain a non-empty list or mapping of trace entries")
    out: list[tuple[str | None, Path, str | None]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("case_id"), str) or not isinstance(item.get("trace"), str):
            raise ValueError(f"Manifest item {idx} must define string 'case_id' and 'trace'")
        tp = Path(item["trace"])
        out.append((item["case_id"], tp if tp.is_absolute() else (batch_path.parent / tp).resolve(), item.get("format") if isinstance(item.get("format"), str) else None))
    return out


def verify_batch(evals_path: Path, batch_path: Path, *, fmt: str = "auto", strict: bool = False) -> tuple[int, dict[str, Any]]:
    """Verify a directory or JSON manifest of trace files against behavior cases."""
    target = Path(batch_path)
    if not target.exists():
        return EXIT_INPUT_ERROR, {"error": f"Batch path not found: {target}"}
    try:
        cases, entries = load_behavior_cases(evals_path), _load_batch_entries(target)
    except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return EXIT_INPUT_ERROR, {"error": str(exc)}
    results, totals = [], {"passed_traces": 0, "failed_traces": 0, "manual_review_traces": 0, "total_checks": 0, "passed_checks": 0, "failed_checks": 0, "manual_review_checks": 0}
    for exp_cid, tp, fmt_ovr in entries:
        try:
            trace = load_trace_file(tp, fmt=fmt_ovr or fmt)
        except TraceParseError as exc:
            return EXIT_INPUT_ERROR, {"error": f"{tp}: {exc}", "results": results}
        cid = exp_cid or trace.case_id or (tp.stem if tp.stem in cases else next((c for c in sorted(cases, key=len, reverse=True) if tp.stem.startswith((c + ".", c + "__"))), None))
        if not cid or cid not in cases:
            return EXIT_INPUT_ERROR, {"error": f"Unknown or missing case_id {cid!r} for {tp}", "results": results}
        res = verify_trace_case(cases[cid], trace, strict=strict)
        res["trace_path"] = str(tp)
        results.append(res)
        totals[f"{res['status']}_traces"] += 1
        for k in ("total", "passed", "failed", "manual_review"):
            totals[f"{k}_checks"] += res["summary"][k]
    code = EXIT_FAIL if (totals["failed_checks"] > 0 or (strict and totals["manual_review_checks"] > 0)) else EXIT_PASS
    return code, {"batch_path": str(target), "strict": strict, "exit_code": code, "passed": code == EXIT_PASS, "summary": {"total_traces": len(results), **totals}, "results": results}


def _emit_error(msg: str, as_json: bool) -> int:
    print(json.dumps({"error": msg}, ensure_ascii=False) if as_json else f"Error: {msg}", file=sys.stdout if as_json else sys.stderr)
    return EXIT_INPUT_ERROR


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for offline behavior trace verification."""
    parser = argparse.ArgumentParser(description="Offline verifier for Docs Harness behavior traces.")
    parser.add_argument("--case")
    parser.add_argument("--trace")
    parser.add_argument("--batch")
    parser.add_argument("--evals", default=str(_DEFAULT_EVALS))
    parser.add_argument("--format", default="auto", choices=SUPPORTED_FORMATS)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else EXIT_INPUT_ERROR
    has_single = bool(args.case or args.trace)
    if bool(args.batch) == has_single or (has_single and not (args.case and args.trace)):
        return _emit_error("specify either (--case and --trace) or --batch", args.json)
    if args.batch:
        code, payload = verify_batch(Path(args.evals), Path(args.batch), fmt=args.format, strict=args.strict)
        if code == EXIT_INPUT_ERROR:
            return _emit_error(str(payload.get("error")), args.json)
    else:
        try:
            cases = load_behavior_cases(Path(args.evals))
            if args.case not in cases:
                raise ValueError(f"Unknown behavior case id: {args.case}")
            payload = verify_trace_case(cases[args.case], load_trace_file(Path(args.trace), fmt=args.format), strict=args.strict)
            code = int(payload["exit_code"])
        except (ValueError, TraceParseError) as exc:
            return _emit_error(str(exc), args.json)
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"{'Batch' if 'results' in payload else 'Case'}: {payload.get('case_id', payload.get('batch_path'))} | passed={payload['passed']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
