"""Shadow 事件的字段白名单、结构校验与时间规范化。

本模块只负责“事件长什么样”，不构造事件，也不写文件。日志存储与事件构造见
`routing_shadow`。严格白名单保证任务原文、证据文本和路径不能进入日志。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Any, Mapping, Sequence

SHADOW_SCHEMA = "docs-harness/routing-shadow-event/v1"
PHASES = ("shadow", "canary", "enforced")
RISK_LEVELS = ("low", "medium", "high", "unknown")
REWORK_KINDS = (
    "cancel",
    "reentry",
    "scope_correction",
    "extra_lifecycle_command",
    "acceptance_failure",
)
LABEL_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "ts",
        "phase",
        "task_id",
        "task_hash",
        "task_chars",
        "registry_version",
        "registry_fingerprint",
        "risk_level",
        "profile",
        "modules",
        "actual_modules",
        "needed_modules",
        "outcome",
        "model",
    }
)
PROFILE_FIELDS = frozenset(
    {
        "intents",
        "candidate_modules",
        "triggers",
        "must_clarify",
        "confidence",
        "evidence_count",
    }
)
OUTCOME_FIELDS = frozenset({"clarify_asked", "rework", "completed"})
MODEL_FIELDS = frozenset(
    {
        "name",
        "version",
        "tokens_in",
        "tokens_out",
        "latency_ms",
        "cost_usd",
        "credits",
        "cache_hit",
    }
)


class RoutingShadowError(Exception):
    """Shadow 事件或日志不可用时抛出。"""

    def __init__(
        self,
        message: str,
        code: str = "routing_shadow_invalid",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


def validate_shadow_event(event: Mapping[str, Any]) -> dict[str, Any]:
    _require(isinstance(event, Mapping), "事件必须是对象", "shadow_event_invalid", "event")
    unknown = sorted(set(event) - EVENT_FIELDS)
    _require(
        not unknown,
        f"事件含未登记字段：{', '.join(unknown)}",
        "shadow_event_invalid",
        "event",
    )
    header = _event_header(event)
    profile = _profile(event.get("profile"))
    modules = _module_sequence(event.get("modules"), "modules", None)
    actual = _module_sequence(event.get("actual_modules"), "actual_modules", None)
    needed = (
        _module_sequence(event["needed_modules"], "needed_modules", None)
        if "needed_modules" in event
        else None
    )
    outcome = _outcome(event.get("outcome"))
    model = _model(event.get("model"))
    _validate_event_consistency(profile, modules)
    normalized: dict[str, Any] = {
        **header,
        "profile": profile,
        "modules": modules,
        "actual_modules": actual,
        "outcome": outcome,
        "model": model,
    }
    if needed is not None:
        normalized["needed_modules"] = needed
    return normalized


def _event_header(event: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        event.get("schema_version") == SHADOW_SCHEMA,
        f"schema_version 必须是 {SHADOW_SCHEMA}",
        "shadow_event_invalid",
        "schema_version",
    )
    parsed_ts = _parse_ts(event["ts"]) if isinstance(event.get("ts"), str) else None
    _require(
        parsed_ts is not None,
        "ts 必须是带时区的 ISO 时间",
        "shadow_event_invalid",
        "ts",
    )
    _require(
        event.get("phase") in PHASES,
        f"phase 必须是 {PHASES}",
        "shadow_event_invalid",
        "phase",
    )
    _require(
        event.get("risk_level") in RISK_LEVELS,
        "risk_level 非法",
        "shadow_event_invalid",
        "risk_level",
    )
    _require(
        isinstance(event.get("registry_version"), str)
        and event["registry_version"].strip(),
        "registry_version 必须是非空字符串",
        "shadow_event_invalid",
        "registry_version",
    )
    _require(
        isinstance(event.get("registry_fingerprint"), str)
        and HASH_PATTERN.fullmatch(event["registry_fingerprint"]),
        "registry_fingerprint 必须是 sha256:<64 位十六进制>",
        "shadow_event_invalid",
        "registry_fingerprint",
    )
    header = {
        "schema_version": SHADOW_SCHEMA,
        "ts": _iso(parsed_ts),
        "phase": event["phase"],
        "task_id": _task_id(event.get("task_id")),
        "registry_version": event["registry_version"],
        "registry_fingerprint": event["registry_fingerprint"],
        "risk_level": event["risk_level"],
    }
    event_hash, task_chars = _task_identity_fields(event)
    if event_hash is not None:
        header["task_hash"] = event_hash
    if task_chars is not None:
        header["task_chars"] = task_chars
    return header


def _validate_event_consistency(
    profile: Mapping[str, Any], modules: Sequence[str]
) -> None:
    _require(
        set(profile["candidate_modules"]) <= set(modules),
        "candidate_modules 必须是 modules 的子集",
        "shadow_event_invalid",
        "profile.candidate_modules",
    )
    if profile["must_clarify"]:
        _require(not modules, "澄清事件不能装配模块", "shadow_event_invalid", "modules")
        _require(
            profile["triggers"] == ["clarify_required"],
            "澄清事件的 triggers 必须是 clarify_required",
            "shadow_event_invalid",
            "profile.triggers",
        )
    else:
        _require(
            "clarify_required" not in profile["triggers"],
            "非澄清事件不能包含 clarify_required",
            "shadow_event_invalid",
            "profile.triggers",
        )
        _require(
            profile["intents"],
            "非澄清事件必须至少有一个意图",
            "shadow_event_invalid",
            "profile.intents",
        )


def _profile(value: Any) -> dict[str, Any]:
    _require(isinstance(value, Mapping), "profile 必须是对象", "shadow_event_invalid", "profile")
    unknown = sorted(set(value) - PROFILE_FIELDS)
    _require(
        not unknown,
        f"profile 含未登记字段：{', '.join(unknown)}",
        "shadow_event_invalid",
        "profile",
    )
    intents = _label_sequence(value.get("intents"), "profile.intents")
    candidates = _label_sequence(value.get("candidate_modules"), "profile.candidate_modules")
    triggers = _label_sequence(value.get("triggers"), "profile.triggers")
    must_clarify = value.get("must_clarify")
    _require(
        isinstance(must_clarify, bool),
        "must_clarify 必须是布尔值",
        "shadow_event_invalid",
        "profile.must_clarify",
    )
    confidence = value.get("confidence")
    _require(
        isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and 0 <= float(confidence) <= 1,
        "confidence 必须是 0 到 1 之间的数字",
        "shadow_event_invalid",
        "profile.confidence",
    )
    evidence_count = value.get("evidence_count")
    _require(
        isinstance(evidence_count, int)
        and not isinstance(evidence_count, bool)
        and evidence_count >= 0,
        "evidence_count 必须是非负整数",
        "shadow_event_invalid",
        "profile.evidence_count",
    )
    return {
        "intents": intents,
        "candidate_modules": candidates,
        "triggers": triggers,
        "must_clarify": must_clarify,
        "confidence": float(confidence),
        "evidence_count": evidence_count,
    }


def _profile_defaults(value: Any) -> dict[str, Any]:
    _require(isinstance(value, Mapping), "profile 必须是对象", "shadow_profile_invalid", "profile")
    defaults = dict(value)
    defaults.pop("evidence", None)
    defaults.setdefault("candidate_modules", [])
    defaults.setdefault("evidence_count", 0)
    return defaults


def _outcome(value: Any) -> dict[str, Any]:
    _require(isinstance(value, Mapping), "outcome 必须是对象", "shadow_event_invalid", "outcome")
    unknown = sorted(set(value) - OUTCOME_FIELDS)
    _require(
        not unknown,
        f"outcome 含未登记字段：{', '.join(unknown)}",
        "shadow_event_invalid",
        "outcome",
    )
    clarify_asked = value.get("clarify_asked")
    _require(
        isinstance(clarify_asked, bool),
        "clarify_asked 必须是布尔值",
        "shadow_event_invalid",
        "outcome.clarify_asked",
    )
    rework = _label_sequence(value.get("rework"), "outcome.rework")
    unknown_rework = sorted(set(rework) - set(REWORK_KINDS))
    _require(
        not unknown_rework,
        f"未知返工类型：{', '.join(unknown_rework)}",
        "shadow_event_invalid",
        "outcome.rework",
    )
    completed = value.get("completed")
    _require(
        completed is None or isinstance(completed, bool),
        "completed 必须是布尔值或 null",
        "shadow_event_invalid",
        "outcome.completed",
    )
    return {"clarify_asked": clarify_asked, "rework": rework, "completed": completed}


def _model(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    _require(isinstance(value, Mapping), "model 必须是对象或 null", "shadow_event_invalid", "model")
    unknown = sorted(set(value) - MODEL_FIELDS)
    _require(
        not unknown,
        f"model 含未登记字段：{', '.join(unknown)}",
        "shadow_event_invalid",
        "model",
    )
    result: dict[str, Any] = {}
    for field in ("name", "version"):
        item = value.get(field)
        _require(
            isinstance(item, str) and MODEL_PATTERN.fullmatch(item),
            f"model.{field} 必须匹配 {MODEL_PATTERN.pattern}",
            "shadow_event_invalid",
            f"model.{field}",
        )
        result[field] = item
    for field in ("tokens_in", "tokens_out"):
        item = value.get(field)
        if item is not None:
            _require(
                isinstance(item, int) and not isinstance(item, bool) and item >= 0,
                f"model.{field} 必须是非负整数",
                "shadow_event_invalid",
                f"model.{field}",
            )
            result[field] = item
    for field in ("latency_ms", "cost_usd", "credits"):
        item = value.get(field)
        if item is not None:
            _require(
                isinstance(item, (int, float))
                and not isinstance(item, bool)
                and item >= 0,
                f"model.{field} 必须是非负数",
                "shadow_event_invalid",
                f"model.{field}",
            )
            result[field] = float(item)
    if "cache_hit" in value:
        _require(
            isinstance(value["cache_hit"], bool),
            "model.cache_hit 必须是布尔值",
            "shadow_event_invalid",
            "model.cache_hit",
        )
        result["cache_hit"] = value["cache_hit"]
    return result


def _module_sequence(value: Any, field: str, registry: Any) -> list[str]:
    labels = _label_sequence(value, field)
    if registry is not None:
        unknown = sorted(set(labels) - set(registry.modules))
        _require(
            not unknown,
            f"{field} 含未知模块：{', '.join(unknown)}",
            "shadow_event_invalid",
            field,
        )
    return labels


def _label_sequence(value: Any, field: str) -> list[str]:
    _require(
        isinstance(value, (list, tuple)),
        f"{field} 必须是数组",
        "shadow_event_invalid",
        field,
    )
    labels = []
    for item in value:
        _require(
            isinstance(item, str) and LABEL_PATTERN.fullmatch(item),
            f"{field} 只能包含标签字符串",
            "shadow_event_invalid",
            field,
        )
        labels.append(item)
    _require(
        len(labels) == len(set(labels)),
        f"{field} 不能重复",
        "shadow_event_invalid",
        field,
    )
    return sorted(labels)


def _task_identity(
    task_text: str | None, task_hash: str | None
) -> tuple[str | None, int | None]:
    if task_text is None:
        return (_task_hash(task_hash), None) if task_hash is not None else (None, None)
    _require(isinstance(task_text, str), "task_text 必须是字符串", "shadow_event_invalid", "task_text")
    computed = "sha256:" + hashlib.sha256(task_text.encode("utf-8")).hexdigest()
    if task_hash is not None:
        _require(
            _task_hash(task_hash) == computed,
            "task_hash 与 task_text 不一致",
            "shadow_event_invalid",
            "task_hash",
        )
    return computed, len(task_text)


def _task_identity_fields(event: Mapping[str, Any]) -> tuple[str | None, int | None]:
    task_hash = _task_hash(event["task_hash"]) if "task_hash" in event else None
    task_chars = event.get("task_chars")
    if task_chars is not None:
        _require(
            isinstance(task_chars, int)
            and not isinstance(task_chars, bool)
            and task_chars >= 0,
            "task_chars 必须是非负整数",
            "shadow_event_invalid",
            "task_chars",
        )
        _require(
            task_hash is not None,
            "task_chars 不能脱离 task_hash",
            "shadow_event_invalid",
            "task_chars",
        )
    return task_hash, task_chars


def _task_hash(value: Any) -> str:
    _require(
        isinstance(value, str) and HASH_PATTERN.fullmatch(value),
        "task_hash 必须是 sha256:<64 位十六进制>",
        "shadow_event_invalid",
        "task_hash",
    )
    return value


def _task_id(value: Any) -> str:
    _require(
        isinstance(value, str) and TASK_ID_PATTERN.fullmatch(value),
        "task_id 必须是不含空白的短标识",
        "shadow_event_invalid",
        "task_id",
    )
    return value


def _normalized_moment(value: dt.datetime | None) -> dt.datetime:
    moment = value or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return _normalized_moment(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _require(condition: bool, message: str, code: str, field: str) -> None:
    if not condition:
        raise RoutingShadowError(message, code=code, details={"field": field})
