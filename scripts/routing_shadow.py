"""Shadow 路由事件的构造与本地日志读写。

事件字段白名单与结构校验在 `routing_shadow_fields`。本模块负责把校验后的
画像、实际模块、结果和模型元数据组装成事件，并做本地 JSONL 读写。写入失败、
日志缺失和日志损坏都是显式失败，不静默放行。
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from routing_contract import RISK_LEVEL_ORDER, Registry, validate_profile
from routing_shadow_fields import (
    HASH_PATTERN,
    PHASES,
    REWORK_KINDS,
    RISK_LEVELS,
    SHADOW_SCHEMA,
    RoutingShadowError,
    _iso,
    _model,
    _module_sequence,
    _normalized_moment,
    _outcome,
    _profile,
    _profile_defaults,
    _require,
    _task_id,
    _task_identity,
    validate_shadow_event,
)

SHADOW_DIR_RELATIVE = ".docs-harness/routing"
SHADOW_GITIGNORE_CONTENT = "*\n"


def shadow_log_path(target: str | Path, moment: dt.datetime | None = None) -> Path:
    timestamp = _normalized_moment(moment)
    return Path(target) / SHADOW_DIR_RELATIVE / f"shadow-{timestamp.strftime('%Y-%m')}.jsonl"


def build_shadow_event(
    task_id: str,
    profile: Mapping[str, Any],
    actual_modules: Sequence[str],
    outcome: Mapping[str, Any],
    *,
    phase: str = "shadow",
    registry: Registry | None = None,
    model: Mapping[str, Any] | None = None,
    risk_level: str | None = None,
    needed_modules: Sequence[str] | None = None,
    task_text: str | None = None,
    task_hash: str | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    _require(phase in PHASES, f"phase 必须是 {PHASES}", "invalid_phase", "phase")
    snapshot, modules, version, fingerprint, clarify = _profile_snapshot(
        profile, registry
    )
    actual = _module_sequence(actual_modules, "actual_modules", registry)
    needed = (
        _module_sequence(needed_modules, "needed_modules", registry)
        if needed_modules is not None
        else None
    )
    event_hash, task_chars = _task_identity(task_text, task_hash)
    event: dict[str, Any] = {
        "schema_version": SHADOW_SCHEMA,
        "ts": _iso(_normalized_moment(now)),
        "phase": phase,
        "task_id": _task_id(task_id),
        "registry_version": version,
        "registry_fingerprint": fingerprint,
        "risk_level": risk_level or _risk_for_modules(modules, registry, clarify),
        "profile": snapshot,
        "modules": modules,
        "actual_modules": actual,
        "outcome": _outcome(outcome),
        "model": _model(model),
    }
    if event_hash is not None:
        event["task_hash"] = event_hash
    if task_chars is not None:
        event["task_chars"] = task_chars
    if needed is not None:
        event["needed_modules"] = needed
    return validate_shadow_event(event)


def _profile_snapshot(
    value: Mapping[str, Any], registry: Registry | None
) -> tuple[dict[str, Any], list[str], str, str, bool]:
    if registry is not None:
        result = validate_profile(value, registry)
        if not result.ok:
            raise RoutingShadowError(
                "路由画像未通过校验",
                code="shadow_profile_invalid",
                details={"errors": [issue.to_dict() for issue in result.errors]},
            )
        return (
            _profile(_profile_defaults(result.profile)),
            list(result.modules),
            result.registry_version,
            result.registry_fingerprint,
            result.effective_clarify,
        )
    _require(
        isinstance(value, Mapping),
        "profile 必须是对象",
        "shadow_profile_invalid",
        "profile",
    )
    if "profile" in value:
        inner = value.get("profile")
        modules = value.get("modules")
        version = value.get("registry_version")
        fingerprint = value.get("registry_fingerprint")
    else:
        inner = value
        modules = value.get("modules")
        version = value.get("registry_version")
        fingerprint = value.get("registry_fingerprint")
    snapshot = _profile(_profile_defaults(inner))
    normalized_modules = _module_sequence(modules, "modules", None)
    _require(
        isinstance(version, str) and version.strip(),
        "registry_version 必须是非空字符串",
        "shadow_profile_invalid",
        "registry_version",
    )
    _require(
        isinstance(fingerprint, str) and HASH_PATTERN.fullmatch(fingerprint),
        "registry_fingerprint 必须是 sha256:<64 位十六进制>",
        "shadow_profile_invalid",
        "registry_fingerprint",
    )
    return snapshot, normalized_modules, version, fingerprint, snapshot["must_clarify"]


def _risk_for_modules(
    modules: Sequence[str], registry: Registry | None, clarify: bool
) -> str:
    if clarify or registry is None:
        return "unknown"
    if not modules:
        return "low"
    if set(modules) - set(registry.modules):
        return "unknown"
    levels = [
        level
        for level, names in registry.risk_levels.items()
        if set(modules) & set(names)
    ]
    if not levels:
        return "unknown"
    return max(levels, key=lambda level: RISK_LEVEL_ORDER.index(level))


def append_shadow_event(event: Mapping[str, Any], path: str | Path) -> None:
    normalized = validate_shadow_event(event)
    target = Path(path)
    _require(not target.is_symlink(), "shadow 日志不能是符号链接", "shadow_path_invalid", "path")
    parent = target.parent
    _require(
        not parent.is_symlink(),
        "shadow 日志父目录不能是符号链接",
        "shadow_path_invalid",
        "path",
    )
    line = json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        parent.mkdir(parents=True, exist_ok=True)
        gitignore = parent / ".gitignore"
        if not gitignore.is_file():
            gitignore.write_text(SHADOW_GITIGNORE_CONTENT, encoding="utf-8")
        with open(target, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
    except (OSError, UnicodeEncodeError) as exc:
        raise RoutingShadowError(
            f"shadow 日志写入失败：{exc}",
            code="shadow_write_failed",
            details={"path": str(target)},
        ) from exc


def read_shadow_events(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if target.is_symlink():
        raise RoutingShadowError(
            "shadow 日志不能是符号链接",
            code="shadow_path_invalid",
            details={"path": str(target)},
        )
    if target.is_dir():
        files = sorted(target.glob("*.jsonl"))
        if not files:
            raise RoutingShadowError(
                f"shadow 日志目录没有 .jsonl 文件：{target}",
                code="shadow_log_missing",
                details={"path": str(target)},
            )
    elif target.is_file():
        files = [target]
    else:
        raise RoutingShadowError(
            f"shadow 日志不存在：{target}",
            code="shadow_log_missing",
            details={"path": str(target)},
        )
    events: list[dict[str, Any]] = []
    for file_path in files:
        events.extend(_read_file(file_path))
    return events


def _read_file(path: Path) -> list[dict[str, Any]]:
    _require(not path.is_symlink(), "shadow 日志文件不能是符号链接", "shadow_path_invalid", "path")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RoutingShadowError(
            f"shadow 日志不可读：{exc}",
            code="shadow_log_unreadable",
            details={"path": str(path)},
        ) from exc
    events: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RoutingShadowError(
                f"shadow 日志第 {number} 行不是合法 JSON：{exc}",
                code="shadow_log_line_invalid",
                details={"path": str(path), "line": number},
            ) from exc
        try:
            events.append(validate_shadow_event(payload))
        except RoutingShadowError as exc:
            raise RoutingShadowError(
                f"shadow 日志第 {number} 行不合法：{exc.message}",
                code="shadow_log_line_invalid",
                details={"path": str(path), "line": number, "reason": exc.code},
            ) from exc
    return events
