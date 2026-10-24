"""Qoder hook 的会话级路由缓存。

同一会话的后续消息通常延续上一个任务。缓存上一次成功路由，避免每条消息
都启动一次 Qoder CLI。新任务标记或 /route-reset 会绕过/清除缓存。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

from routing_contract import Registry, validate_profile

CACHE_TTL_SECONDS = 7200
CACHE_DIR_RELATIVE = ".docs-harness/routing/sessions"
NEW_TASK_MARKERS = (
    "新任务",
    "另一个任务",
    "换个任务",
    "换一个任务",
    "重新开始",
    "从头开始",
    "另外做",
    "再做一个",
    "下一个任务",
    "新需求",
    "需求变了",
    "new task",
    "another task",
    "different task",
    "start over",
    "switch task",
)


def routing_dir(project: Path) -> Path:
    directory = project / ".docs-harness" / "routing"
    directory.mkdir(parents=True, exist_ok=True)
    gitignore = directory / ".gitignore"
    if not gitignore.is_file():
        gitignore.write_text("*\n", encoding="utf-8")
    return directory


def cache_path(project: Path, session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return project / CACHE_DIR_RELATIVE / f"{digest}.json"


def is_reset(prompt: str) -> bool:
    return prompt.strip().lower() in {"/route-reset", "/route_reset"}


def is_new_task(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(marker.lower() in lowered for marker in NEW_TASK_MARKERS)


def read_cache(
    project: Path, session_id: str, registry: Registry
) -> Mapping[str, Any] | None:
    ttl = _cache_ttl()
    if ttl <= 0:
        return None
    path = cache_path(project, session_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, Mapping):
        return None
    if data.get("registry_fingerprint") != registry.fingerprint:
        return None
    updated = _parse_iso(data.get("updated_at"))
    if updated is None:
        return None
    age = (dt.datetime.now(dt.timezone.utc) - updated).total_seconds()
    if age < 0 or age > ttl:
        return None
    cached_profile = data.get("profile")
    modules = data.get("modules")
    if not isinstance(cached_profile, Mapping):
        return None
    if not isinstance(modules, list) or any(
        not isinstance(item, str) for item in modules
    ):
        return None
    profile = {
        "intents": cached_profile.get("intents", []),
        "modules": cached_profile.get("candidate_modules", []),
        "triggers": cached_profile.get("triggers", []),
        "must_clarify": bool(cached_profile.get("must_clarify", False)),
        "confidence": cached_profile.get("confidence", 0.0),
    }
    result = validate_profile(profile, registry)
    if not result.ok or result.effective_clarify or not result.modules:
        return None
    if sorted(result.modules) != sorted(modules):
        return None
    return {"profile": profile, "modules": list(result.modules)}


def write_cache(
    project: Path, session_id: str, result: Any, registry: Registry
) -> None:
    if result.effective_clarify or not result.modules:
        return
    profile = {key: value for key, value in result.profile.items() if key != "evidence"}
    data = {
        "registry_version": registry.version,
        "registry_fingerprint": registry.fingerprint,
        "updated_at": _now(),
        "profile": profile,
        "modules": list(result.modules),
    }
    try:
        directory = routing_dir(project) / "sessions"
        directory.mkdir(parents=True, exist_ok=True)
        cache_path(project, session_id).write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    except (OSError, UnicodeEncodeError) as exc:
        print(f"docs-harness router: cache write failed: {exc}", file=sys.stderr)


def clear_cache(project: Path, session_id: str) -> None:
    try:
        cache_path(project, session_id).unlink(missing_ok=True)
    except OSError:
        pass


def _cache_ttl() -> int:
    raw = os.environ.get("DOCS_HARNESS_ROUTER_CACHE_TTL_SECONDS")
    if raw is None:
        return CACHE_TTL_SECONDS
    try:
        return int(raw)
    except ValueError:
        return CACHE_TTL_SECONDS


def _parse_iso(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
