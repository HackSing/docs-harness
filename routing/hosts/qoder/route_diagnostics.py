"""Qoder hook 的错误落盘与非法画像脱敏诊断。

只保留注册表内的标签、布尔/数值字段和 evidence 条数；未知标签折叠为
`<unknown>`，不把任务原文、证据文本或任意模型字段写进错误日志。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from routing_contract import Registry
from route_cache import routing_dir

DIAGNOSTIC_LABEL_LIMIT = 20


def profile_diagnostic(profile: Mapping[str, Any], registry: Registry) -> dict[str, Any]:
    must_clarify = profile.get("must_clarify")
    evidence = profile.get("evidence")
    return {
        "intents": _known_labels(profile.get("intents"), registry.intents),
        "triggers": _known_labels(profile.get("triggers"), registry.triggers),
        "modules": _known_labels(profile.get("modules"), registry.modules),
        "must_clarify": must_clarify if isinstance(must_clarify, bool) else None,
        "confidence": _diagnostic_confidence(profile.get("confidence")),
        "evidence_count": len(evidence) if isinstance(evidence, list) else None,
    }


def report_error(
    project: Path | None,
    code: str,
    field: str,
    session_id: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> None:
    suffix = f" ({field})" if field else ""
    print(f"docs-harness router: {code}{suffix}", file=sys.stderr)
    if project is None:
        return
    entry: dict[str, Any] = {
        "ts": _now(),
        "code": code,
        "field": field or None,
        "session_hash": hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16],
    }
    if details:
        entry.update(details)
    try:
        directory = routing_dir(project)
        with open(directory / "hook-errors.jsonl", "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    except (OSError, UnicodeEncodeError) as exc:
        print(f"docs-harness router: error log write failed: {exc}", file=sys.stderr)


def _known_labels(value: Any, known: Mapping[str, str]) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    labels: list[str] = []
    unknown = False
    for item in value[:DIAGNOSTIC_LABEL_LIMIT]:
        if isinstance(item, str) and item in known:
            labels.append(item)
        else:
            unknown = True
    if unknown:
        labels.append("<unknown>")
    if len(value) > DIAGNOSTIC_LABEL_LIMIT:
        labels.append("<truncated>")
    return labels


def _diagnostic_confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 4)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
