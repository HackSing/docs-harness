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

FAKE_PROFILE_RELATIVE = "routing/hosts/qoder/fake_profile.json"


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
        started = time.monotonic()
        profile, model = _route_task(prompt, registry)
        latency_ms = round((time.monotonic() - started) * 1000, 1)
        result = validate_profile(profile, registry)
        if not result.ok:
            _report_error(project, "profile_invalid", result.errors[0].code, session_id)
            return 0
        phase = os.environ.get("DOCS_HARNESS_ROUTER_PHASE", "shadow")
        if phase not in PHASES:
            _report_error(project, "phase_invalid", "DOCS_HARNESS_ROUTER_PHASE", session_id)
            return 0
        event = build_shadow_event(
            _task_id(session_id, prompt),
            profile,
            list(result.modules),
            {"clarify_asked": False, "rework": [], "completed": None},
            phase=phase,
            registry=registry,
            model={
                "name": model["name"],
                "version": model["version"],
                "latency_ms": latency_ms,
            },
            task_text=prompt,
        )
        append_shadow_event(event, shadow_log_path(project))
        if result.effective_clarify or not result.modules:
            return 0
        _emit(_render_context(result.modules, registry))
        return 0
    except (HookError, RoutingContractError, RoutingShadowError, OSError, UnicodeDecodeError) as exc:
        _report_error(
            project,
            getattr(exc, "code", "hook_error"),
            _error_field(exc),
            session_id,
        )
        return 0


def _route_task(
    prompt: str, registry: Registry
) -> tuple[Mapping[str, Any], Mapping[str, str]]:
    """Prototype seam: replace with a low-context model call.

    The real implementation should send only the taxonomy, one-page contracts and
    the user prompt, then return the model's parsed profile plus model metadata.
    """
    del prompt, registry
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
    directory = project / ".docs-harness" / "routing"
    entry = {
        "ts": _now(),
        "code": code,
        "field": field or None,
        "session_hash": hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16],
    }
    try:
        directory.mkdir(parents=True, exist_ok=True)
        gitignore = directory / ".gitignore"
        if not gitignore.is_file():
            gitignore.write_text("*\n", encoding="utf-8")
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
