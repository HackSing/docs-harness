#!/usr/bin/env python3
"""Antigravity PreInvocation hook for Docs Harness intent routing.

Reads Antigravity's PreInvocation JSON payload from stdin (`conversationId`,
`workspacePaths`, `lastUserInput`), deduplicates tool-loop continuations within
the same user turn, routes the prompt via `_route_task` (defaulting to `decisions`
/ `gemini-decision-1` when configured), writes a privacy-safe Shadow event, and
outputs `{}` in `shadow` phase or `{"injectSteps": [{"systemMessage": ...}]}` in
`canary`/`enforced` phase. Never blocks the agent loop on errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Mapping

DEFAULT_ROOT = Path(__file__).resolve().parents[3]
USER_REQUEST_RE = re.compile(
    r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", re.DOTALL
)
TRAILING_META_RE = re.compile(
    r"\s*<(?:ADDITIONAL_METADATA|USER_SETTINGS_CHANGE)>.*$", re.DOTALL
)


def _apply_cli_env(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root", default=None)
    parser.add_argument("--enabled", action="store_true")
    parser.add_argument("--phase", default=None)
    parser.add_argument("--backend", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--env-file", default=None)
    args, _ = parser.parse_known_args(argv)
    if args.root:
        os.environ.setdefault("DOCS_HARNESS_ROOT", args.root)
    if args.enabled:
        os.environ.setdefault("DOCS_HARNESS_ROUTER_ENABLED", "1")
    if args.phase:
        os.environ.setdefault("DOCS_HARNESS_ROUTER_PHASE", args.phase)
    if args.backend:
        os.environ.setdefault("DOCS_HARNESS_ROUTER_BACKEND", args.backend)
    if args.model:
        os.environ.setdefault("DOCS_HARNESS_ROUTER_MODEL", args.model)
    if args.env_file:
        os.environ.setdefault("DOCS_HARNESS_GEMINI_ENV_FILE", args.env_file)
    return Path(os.environ.get("DOCS_HARNESS_ROOT") or DEFAULT_ROOT).resolve()


SOURCE_ROOT = _apply_cli_env(sys.argv[1:])
sys.path.insert(0, str(SOURCE_ROOT / "scripts"))
sys.path.insert(0, str(SOURCE_ROOT / "evals" / "intent_routing"))
sys.path.insert(0, str(SOURCE_ROOT / "routing" / "hosts" / "qoder"))

from route_cache import (  # noqa: E402
    clear_cache,
    is_new_task,
    is_reset,
    read_cache,
    routing_dir,
    write_cache,
)
from route_diagnostics import profile_diagnostic, report_error  # noqa: E402
from route_hook import (  # noqa: E402
    HookError,
    _actual_modules,
    _configure_stdio,
    _enabled,
    _error_field,
    _event_model,
    _is_system_notification,
    _normalize_router_profile,
    _phase,
    _read_payload,
    _registry_for,
    _render_cached_context,
    _render_context,
    _route_task,
    _should_inject,
    _task_id,
    _uses_docs_harness,
)
from route_signals import cache_bypass_reason  # noqa: E402
from routing_contract import (  # noqa: E402
    Registry,
    RoutingContractError,
    direct_override_requested,
    validate_profile,
)
from routing_shadow import (  # noqa: E402
    RoutingShadowError,
    append_shadow_event,
    build_shadow_event,
    shadow_log_path,
)


def extract_user_prompt(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return ""
    match = USER_REQUEST_RE.search(raw)
    if match:
        return match.group(1).strip()
    cleaned = TRAILING_META_RE.sub("", raw).strip()
    return cleaned


def _project_dir(payload: Mapping[str, Any]) -> Path:
    explicit = os.environ.get("DOCS_HARNESS_PROJECT_DIR") or os.environ.get(
        "QODER_PROJECT_DIR"
    )
    candidates: list[str] = []
    if isinstance(explicit, str) and explicit.strip():
        candidates.append(explicit.strip())
    workspaces = payload.get("workspacePaths")
    if isinstance(workspaces, list):
        candidates.extend(
            item.strip()
            for item in workspaces
            if isinstance(item, str) and item.strip()
        )
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        candidates.append(cwd.strip())
    if not candidates:
        raise HookError("project_dir_missing", "workspacePaths")
    for raw in candidates:
        path = Path(raw).expanduser()
        if path.is_dir() and _uses_docs_harness(path):
            return path.resolve()
    first = Path(candidates[0]).expanduser()
    if not first.is_dir():
        raise HookError("project_dir_invalid", "workspacePaths")
    return first.resolve()


def _last_input_path(project: Path, session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return project / ".docs-harness" / "routing" / "sessions" / f"{digest}.last"


def _is_same_turn_invocation(project: Path, session_id: str, prompt: str) -> bool:
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    path = _last_input_path(project, session_id)
    try:
        if path.is_file() and path.read_text(encoding="utf-8").strip() == prompt_hash:
            return True
    except OSError:
        return False
    return False


def _record_turn_invocation(project: Path, session_id: str, prompt: str) -> None:
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    try:
        sessions = routing_dir(project) / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        _last_input_path(project, session_id).write_text(
            prompt_hash + "\n", encoding="utf-8"
        )
    except OSError:
        pass


def _emit_agy(context: str | None = None) -> None:
    if not context:
        sys.stdout.write("{}\n")
        return
    output = {
        "injectSteps": [
            {
                "systemMessage": {
                    "systemMessage": context,
                }
            }
        ]
    }
    json.dump(output, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def _handle_agy_cache(
    project: Path, session_id: str, prompt: str, registry: Registry, phase: str
) -> bool:
    if is_reset(prompt):
        clear_cache(project, session_id)
        _emit_agy(None)
        return True
    if is_new_task(prompt):
        return False
    cached = read_cache(project, session_id, registry)
    if cached is None or cache_bypass_reason(prompt, cached["profile"]):
        return False
    result = validate_profile(cached["profile"], registry)
    if not result.ok or result.effective_clarify or not result.modules:
        clear_cache(project, session_id)
        return False
    started = time.monotonic()
    event = build_shadow_event(
        _task_id(session_id, prompt),
        cached["profile"],
        _actual_modules(phase, result.modules, registry),
        {"clarify_asked": False, "rework": [], "completed": None},
        phase=phase,
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
    _emit_agy(
        _render_cached_context(result.modules, registry)
        if _should_inject(phase)
        else None
    )
    return True


def _run_agy_full_route(
    project: Path, session_id: str, prompt: str, registry: Registry, phase: str
) -> None:
    started = time.monotonic()
    profile, model = _route_task(prompt, registry)
    profile = _normalize_router_profile(profile)
    latency_ms = round((time.monotonic() - started) * 1000, 1)
    result = validate_profile(profile, registry)
    if not result.ok:
        report_error(
            project,
            "profile_invalid",
            result.errors[0].code,
            session_id,
            details={"phase": phase, "profile": profile_diagnostic(profile, registry)},
        )
        _emit_agy(None)
        return
    event = build_shadow_event(
        _task_id(session_id, prompt),
        profile,
        _actual_modules(phase, result.modules, registry),
        {"clarify_asked": False, "rework": [], "completed": None},
        phase=phase,
        registry=registry,
        model=_event_model(model, latency_ms),
        task_text=prompt,
    )
    append_shadow_event(event, shadow_log_path(project))
    if result.effective_clarify or not result.modules:
        _emit_agy(None)
        return
    write_cache(project, session_id, result, registry)
    _emit_agy(
        _render_context(result.modules, registry) if _should_inject(phase) else None
    )


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    if argv is not None:
        _apply_cli_env(argv)
    payload = _read_payload()
    if payload is None or not _enabled():
        _emit_agy(None)
        return 0
    raw_prompt = payload.get("lastUserInput") or payload.get("prompt")
    prompt = extract_user_prompt(raw_prompt)
    if not prompt or _is_system_notification(prompt):
        _emit_agy(None)
        return 0
    session_id = str(
        payload.get("conversationId") or payload.get("session_id") or "unknown"
    ).strip() or "unknown"
    project: Path | None = None
    try:
        project = _project_dir(payload)
        if not _uses_docs_harness(project) and not os.environ.get("DOCS_HARNESS_REGISTRY"):
            _emit_agy(None)
            return 0
        if _is_same_turn_invocation(project, session_id, prompt):
            _emit_agy(None)
            return 0
        _record_turn_invocation(project, session_id, prompt)
        registry = _registry_for(project)
        if direct_override_requested(prompt, registry):
            _emit_agy(None)
            return 0
        phase = _phase()
        if _handle_agy_cache(project, session_id, prompt, registry, phase):
            return 0
        _run_agy_full_route(project, session_id, prompt, registry, phase)
        return 0
    except (HookError, RoutingContractError, RoutingShadowError, OSError, UnicodeDecodeError) as exc:
        report_error(
            project,
            getattr(exc, "code", "hook_error"),
            _error_field(exc),
            session_id,
        )
        _emit_agy(None)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
