"""Read-only blind review prompt builder for draft and frozen plans."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Sequence

REVIEW_LENSES: tuple[str, ...] = ("comprehension", "implementation_readiness")
VALID_LENS_OPTIONS: tuple[str, ...] = ("all", *REVIEW_LENSES)
_DEFAULT_ALLOWED_MARKDOWN_SUFFIXES: frozenset[str] = frozenset({".md", ".markdown"})
_PLAN_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("title", "Title"),
    ("key_symbols", "Key Symbols"),
    ("background", "Background"),
    ("objective", "Objective"),
    ("non_goals", "Non-Goals"),
    ("success_criteria", "Success Criteria"),
    ("execution_scope", "Execution Scope"),
    ("implementation", "Implementation"),
    ("scope", "Scope"),
    ("steps", "Steps"),
    ("acceptance", "Acceptance"),
    ("process_flowchart", "Process Flowchart"),
    ("ux_journey", "Operator / User Journey"),
    ("module_interfaces", "Module Interfaces & Skeleton"),
    ("acceptance_plan", "Acceptance Plan"),
    ("acceptance_required", "Acceptance Required"),
    ("knowledge_impact", "Knowledge Impact"),
    ("constraints", "Constraints"),
    ("risks_and_rollback", "Risks & Rollback"),
    ("current_constraints", "Current Constraints"),
    ("alternatives", "Alternatives"),
    ("tradeoffs", "Tradeoffs"),
    ("decision", "Final Decision"),
    ("boundaries_interfaces", "Boundaries & Interfaces"),
    ("compatibility_migration", "Compatibility & Migration"),
    ("rollback_strategy", "Rollback Strategy"),
    ("architecture_acceptance", "Architecture Acceptance"),
    ("adr_decision", "ADR Decision"),
)


def _harness_controller() -> Any:
    import sys

    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "HarnessError"):
        return main
    import harness as controller

    return controller


def _validate_single_context_ref(controller: Any, target: Path, raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        raise controller.HarnessError("context-ref 不能为空", code="invalid_context_ref")
    target_real = target.resolve()
    raw_path = Path(raw).expanduser()
    candidate = raw_path if raw_path.is_absolute() else target_real / raw_path
    resolved = controller.ensure_within(target_real, candidate, code="invalid_context_ref")
    rel = resolved.relative_to(target_real)
    if not rel.parts:
        raise controller.HarnessError("context-ref 不能指向项目根目录", code="invalid_context_ref")
    norm_candidate = Path(os.path.abspath(str(candidate)))
    try:
        unresolved_parts = norm_candidate.relative_to(target_real).parts
    except ValueError:
        unresolved_parts = rel.parts
    cursor = target_real
    for part in unresolved_parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise controller.HarnessError(
                f"context-ref 包含符号链接：{rel.as_posix()}",
                code="invalid_context_ref",
            )
    if not resolved.exists() or (not resolved.is_file() and not resolved.is_dir()):
        raise controller.HarnessError(
            f"context-ref 不存在或不可读：{raw}",
            code="invalid_context_ref",
        )
    return rel.as_posix()


def validate_context_refs(
    controller: Any,
    target: Path,
    context_refs: Sequence[str] | None,
) -> list[str]:
    """Validate explicit allowlisted file/directory references within target."""
    if not context_refs:
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in context_refs:
        rel = _validate_single_context_ref(controller, target, raw)
        if rel not in seen:
            seen.add(rel)
            normalized.append(rel)
    return normalized


def _infer_draft_level(content: dict[str, Any]) -> str:
    explicit = content.get("plan_level")
    if isinstance(explicit, str) and explicit:
        return explicit
    brief_keys = {"title", "key_symbols", "objective", "scope", "steps", "acceptance"}
    full_markers = {"background", "module_interfaces", "process_flowchart", "ux_journey"}
    if any(key in content for key in full_markers):
        return "full"
    if set(content).issubset(brief_keys | {"non_goals", "risks_and_rollback"}):
        return "brief"
    return "draft"


def _format_plan_content_text(content: dict[str, Any]) -> str:
    sections: list[str] = []
    used: set[str] = set()
    for key, label in _PLAN_FIELD_LABELS:
        if key not in content or content[key] in (None, "", []):
            continue
        used.add(key)
        sections.append(_render_field_block(label, content[key]))
    for key in sorted(content):
        if key in used or content[key] in (None, "", []):
            continue
        sections.append(_render_field_block(key, content[key]))
    return "\n\n".join(sections)


def _render_field_block(label: str, value: Any) -> str:
    if isinstance(value, (list, tuple)):
        items = "\n".join(f"- {item}" for item in value)
        return f"### {label}\n{items}"
    if isinstance(value, dict):
        items = "\n".join(f"- {k}: {v}" for k, v in value.items())
        return f"### {label}\n{items}"
    return f"### {label}\n{value}"


def _extract_from_plan_ref(controller: Any, target: Path, plan_ref: str) -> dict[str, Any]:
    plan_json, document, archived = controller.plan_settle_paths(target, plan_ref)
    if plan_json is not None:
        frozen = controller.validate_frozen_plan(controller.read_json(plan_json))
        plan_level = str(frozen.get("plan_level") or "")
        if plan_level == "none":
            raise controller.HarnessError(
                "plan_level=none 无需方案盲审",
                code="plan_review_not_applicable",
            )
        content = frozen.get("content")
        if not isinstance(content, dict) or not content:
            raise controller.HarnessError("方案内容无效", code="invalid_plan_ref")
        return {
            "kind": "frozen_plan",
            "ref": plan_json.relative_to(target).as_posix(),
            "document_ref": document.relative_to(target).as_posix(),
            "archived": archived,
            "plan_level": plan_level,
            "plan_profile": frozen.get("plan_profile"),
            "plan_fingerprint": frozen.get("plan_fingerprint"),
            "title": str(content.get("title") or plan_json.stem),
            "body": _format_plan_content_text(content),
        }
    markdown = document.read_text(encoding="utf-8")
    return {
        "kind": "handwritten_markdown",
        "ref": document.relative_to(target).as_posix(),
        "document_ref": document.relative_to(target).as_posix(),
        "archived": archived,
        "plan_level": "markdown",
        "plan_profile": None,
        "plan_fingerprint": None,
        "title": _extract_markdown_title(markdown, document.stem),
        "body": markdown.strip(),
    }


def _extract_markdown_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def _extract_from_content_ref(controller: Any, target: Path, content_ref: str) -> dict[str, Any]:
    path = controller.project_input_path(target, content_ref, code="invalid_plan_content")
    rel = path.relative_to(target).as_posix()
    suffix = path.suffix.lower()
    if suffix == ".json":
        raw = controller.read_json(path)
        if not isinstance(raw, dict) or not raw:
            raise controller.HarnessError("方案草案 JSON 必须是非空对象", code="invalid_plan_content")
        if raw.get("plan_level") == "none":
            raise controller.HarnessError(
                "plan_level=none 无需方案盲审",
                code="plan_review_not_applicable",
            )
        content = raw.get("content") if isinstance(raw.get("content"), dict) else raw
        if not content:
            raise controller.HarnessError("方案草案 content 不能为空", code="invalid_plan_content")
        level = str(raw.get("plan_level") or _infer_draft_level(content))
        if level == "none":
            raise controller.HarnessError(
                "plan_level=none 无需方案盲审",
                code="plan_review_not_applicable",
            )
        return {
            "kind": "draft_json",
            "ref": rel,
            "document_ref": None,
            "archived": False,
            "plan_level": level,
            "plan_profile": raw.get("plan_profile"),
            "plan_fingerprint": raw.get("plan_fingerprint"),
            "title": str(content.get("title") or path.stem),
            "body": _format_plan_content_text(content),
        }
    if suffix in _DEFAULT_ALLOWED_MARKDOWN_SUFFIXES:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise controller.HarnessError(
                f"无法读取草案 Markdown：{exc}",
                code="invalid_plan_content",
            ) from exc
        if not text.strip():
            raise controller.HarnessError("草案 Markdown 不能为空", code="invalid_plan_content")
        return {
            "kind": "draft_markdown",
            "ref": rel,
            "document_ref": rel,
            "archived": False,
            "plan_level": "markdown",
            "plan_profile": None,
            "plan_fingerprint": None,
            "title": _extract_markdown_title(text, path.stem),
            "body": text.strip(),
        }
    raise controller.HarnessError(
        "草案输入仅支持 .json 或 .md/.markdown 文件",
        code="invalid_plan_content",
    )


def extract_plan_packet(
    controller: Any,
    target: Path,
    *,
    plan_ref: str | None = None,
    content_ref: str | None = None,
) -> dict[str, Any]:
    """Extract a self-contained plan packet from a frozen/handwritten plan or draft."""
    if bool(plan_ref) == bool(content_ref):
        code = "conflicting_plan_input" if plan_ref and content_ref else "missing_plan_input"
        msg = (
            "--plan 与 --content 不可同时传入"
            if plan_ref and content_ref
            else "plan review-prompt 必须提供 --plan 或 --content"
        )
        raise controller.HarnessError(msg, code=code)
    if plan_ref:
        return _extract_from_plan_ref(controller, target, plan_ref)
    assert content_ref is not None
    return _extract_from_content_ref(controller, target, content_ref)


def _format_context_allowlist(context_refs: Sequence[str]) -> str:
    if not context_refs:
        return "NONE (Plan Packet only; do NOT inspect workspace files or guess unstated details.)"
    lines = "\n".join(f"- {item}" for item in context_refs)
    return (
        "You may read ONLY these allowlisted project paths "
        "(do NOT search or read outside them):\n"
        f"{lines}"
    )


def _comprehension_prompt(packet: dict[str, Any], allowlist_block: str) -> str:
    return (
        "ROLE: Independent Cold-Start Plan Comprehension Reviewer (Zero Prior Context).\n"
        "ISOLATION RULE: Start in a fresh subagent with zero conversation history "
        "(NEVER fork from coordinator). Assume nothing beyond the Plan Packet and "
        "allowlisted context refs.\n"
        "STYLE RULES: Critique First. Zero praise, zero filler, zero apologies. "
        "Cite exact plan field/section names for every finding.\n\n"
        f"CONTEXT ALLOWLIST:\n{allowlist_block}\n\n"
        "EVALUATION CHECKLIST:\n"
        "1. Scope & Non-Goals Clarity: Are scope boundaries and explicit non-goals unmistakable?\n"
        "2. Undefined Terms & Prerequisites: Any symbol, workflow, or assumption referenced "
        "without definition or path?\n"
        "3. Flow & State Gaps: Do objective, flowchart, operator journey, error handling, "
        "and rollback states contradict or omit transitions?\n\n"
        f"PLAN PACKET ({packet['kind']} | level={packet['plan_level']} | title={packet['title']}):\n"
        f"{packet['body']}\n\n"
        "OUTPUT FORMAT:\n"
        "- Blocking / Clarity Findings (numbered; [HIGH|MEDIUM] section -> concrete gap -> fix).\n"
        "- If none: write 'No comprehension blockers found.'\n"
        "- Final line strictly: VERDICT: PASS | REVISE"
    )


def _implementation_readiness_prompt(packet: dict[str, Any], allowlist_block: str) -> str:
    return (
        "ROLE: Zero-Decision Implementation Readiness Reviewer (Zero Prior Context).\n"
        "ISOLATION RULE: Run in a fresh subagent with zero conversation history "
        "(NEVER fork from coordinator). Do NOT reconstruct intent from memory.\n"
        "ZERO-DECISION RULE: If implementing this plan would force an engineer to guess "
        "a file path, public signature, state transition, data schema, error code, "
        "or test command, flag it as GAP (HIGH / needs_design_decision).\n"
        "STYLE RULES: Critique First. Zero glazing, zero filler, zero apologies.\n\n"
        f"CONTEXT ALLOWLIST:\n{allowlist_block}\n\n"
        "READINESS CHECKLIST:\n"
        "1. Interfaces & Reused Helpers: Are target files, exported symbols, and reused "
        "repository APIs concrete and mutually consistent?\n"
        "2. Data Shapes & Error Handling: Are input/output schemas, empty/error/edge states, "
        "exit codes, and rollback paths specified unambiguously?\n"
        "3. Verification Executability: Can every acceptance criterion be executed verbatim "
        "without inventing pass/fail criteria?\n\n"
        f"PLAN PACKET ({packet['kind']} | level={packet['plan_level']} | title={packet['title']}):\n"
        f"{packet['body']}\n\n"
        "OUTPUT FORMAT:\n"
        "- Readiness Findings (numbered; [HIGH|MEDIUM] section -> ambiguous detail -> "
        "required decision or fix).\n"
        "- If implementation-ready: write 'No readiness gaps found.'\n"
        "- Final line strictly: VERDICT: READY | NOT_READY"
    )


def build_review_prompts(
    packet: dict[str, Any],
    *,
    lens: str = "all",
    context_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build zero-context Goldfish blind review prompts for the requested lens."""
    if lens not in VALID_LENS_OPTIONS:
        raise ValueError(f"Unsupported review lens: {lens}")
    selected = REVIEW_LENSES if lens == "all" else (lens,)
    allowlist_block = _format_context_allowlist(context_refs)
    prompts: list[dict[str, str]] = []
    for item in selected:
        if item == "comprehension":
            prompts.append({
                "lens": "comprehension",
                "role": "Zero-Context Plan Comprehension Reviewer",
                "prompt": _comprehension_prompt(packet, allowlist_block),
            })
        else:
            prompts.append({
                "lens": "implementation_readiness",
                "role": "Zero-Decision Implementation Readiness Reviewer",
                "prompt": _implementation_readiness_prompt(packet, allowlist_block),
            })
    warnings: list[str] = []
    if packet.get("plan_level") == "brief":
        warnings.append(
            "brief 方案字段较少，盲审默认面向结构化完整方案，请结合改动尺度判断缺口严重度"
        )
    return {
        "status": "ready",
        "read_only": True,
        "lens": lens,
        "source": {
            "kind": packet["kind"],
            "ref": packet["ref"],
            "document_ref": packet["document_ref"],
            "archived": packet["archived"],
            "plan_level": packet["plan_level"],
            "plan_profile": packet["plan_profile"],
            "plan_fingerprint": packet["plan_fingerprint"],
            "title": packet["title"],
        },
        "context_refs": list(context_refs),
        "warnings": warnings,
        "recommended_execution": {
            "subagent_isolation": "fresh_zero_history_context",
            "forbid_fork_from_coordinator": True,
            "allowlisted_context_only": True,
            "context_ref_count": len(context_refs),
        },
        "prompts": prompts,
    }


def run_plan_review_prompt(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """CLI handler for `harness plan review-prompt`."""
    controller = _harness_controller()
    target = controller.safe_target(args.target)
    lens = getattr(args, "lens", None) or "all"
    if lens not in VALID_LENS_OPTIONS:
        raise controller.HarnessError(
            f"不支持的 --lens：{lens}",
            code="invalid_review_lens",
        )
    packet = extract_plan_packet(
        controller,
        target,
        plan_ref=getattr(args, "plan", None),
        content_ref=getattr(args, "content", None),
    )
    refs = validate_context_refs(controller, target, getattr(args, "context_ref", None))
    return 0, build_review_prompts(packet, lens=lens, context_refs=refs)
