"""意图路由画像的 schema、纯校验与模块闭包解析。

模型输出只作为候选画像；模块集合由注册表的意图映射和依赖闭包解析，任何
未知标签、冲突、越界模块或低置信画像都在这里被确定性拒绝或降级为澄清。
注册表本身的加载与数据合同见 `routing_registry`。本模块不做模型调用，也不
读写任何运行态日志。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from routing_registry import (
    Registry,
    RoutingContractError,
    load_registry,
    registry_fingerprint,
)

PROFILE_SCHEMA = "docs-harness/routing-profile/v1"
DEFAULT_REGISTRY_RELATIVE = "routing/registry.json"
RISK_LEVEL_ORDER = ("low", "medium", "high", "unknown")
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
PROFILE_FIELDS = frozenset(
    {
        "intents",
        "modules",
        "triggers",
        "must_clarify",
        "confidence",
        "evidence",
        "model",
        "model_version",
    }
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "field": self.field}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    profile: Mapping[str, Any]
    modules: tuple[str, ...]
    effective_clarify: bool
    errors: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]
    registry_version: str
    registry_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "profile": dict(self.profile),
            "modules": list(self.modules),
            "effective_clarify": self.effective_clarify,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
            "registry_version": self.registry_version,
            "registry_fingerprint": self.registry_fingerprint,
        }


@dataclass(frozen=True)
class _ProfileFields:
    intents: list[str]
    candidates: list[str]
    triggers: list[str]
    must_clarify: bool
    confidence: float | None
    evidence: list[str]
    model: str | None
    model_version: str | None


def profile_schema(registry: Registry) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"Docs Harness Routing Profile ({registry.version})",
        "type": "object",
        "additionalProperties": False,
        "required": ["intents", "triggers", "must_clarify", "confidence"],
        "properties": {
            "intents": {
                "type": "array",
                "items": {"enum": sorted(registry.intents)},
                "uniqueItems": True,
            },
            "modules": {
                "type": "array",
                "items": {"enum": sorted(registry.modules)},
                "uniqueItems": True,
            },
            "triggers": {
                "type": "array",
                "items": {"enum": sorted(registry.triggers)},
                "uniqueItems": True,
            },
            "must_clarify": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": {
                "type": "array",
                "maxItems": 8,
                "items": {"type": "string", "minLength": 1, "maxLength": 200},
            },
            "model": {"type": "string", "pattern": MODEL_NAME_PATTERN.pattern},
            "model_version": {"type": "string", "pattern": MODEL_NAME_PATTERN.pattern},
        },
    }


def validate_profile(
    profile: Mapping[str, Any], registry: Registry
) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    if not isinstance(profile, Mapping):
        error = ValidationIssue("invalid_profile", "profile 必须是对象")
        return _result(empty_profile(), (), False, [error], warnings, registry)
    unknown = sorted(set(profile) - PROFILE_FIELDS)
    if unknown:
        errors.append(
            ValidationIssue(
                "unknown_profile_field",
                f"profile 含未登记字段：{', '.join(unknown)}",
                "profile",
            )
        )
    fields = _collect_fields(profile, registry, errors)
    _check_intent_conflicts(fields.intents, errors)
    effective = _effective_clarify(fields, registry, warnings)
    if not fields.intents and not effective:
        errors.append(
            ValidationIssue(
                "intents_required", "非澄清画像必须至少有一个意图", "intents"
            )
        )
    triggers = _normalized_triggers(
        fields.triggers, fields.intents, fields.must_clarify, effective, errors, warnings
    )
    modules = _resolve_from_intents(fields.intents, registry)
    if fields.candidates and not effective:
        _candidate_issues(fields.candidates, modules, errors, warnings)
    if fields.must_clarify and fields.candidates:
        errors.append(
            ValidationIssue(
                "clarify_with_modules", "must_clarify=true 时 modules 必须为空", "modules"
            )
        )
    if effective:
        modules = ()
    normalized = _normalized_profile(fields, triggers, effective)
    if errors:
        modules = ()
    return _result(normalized, modules, effective, errors, warnings, registry)


def resolve_modules(
    profile: Mapping[str, Any], registry: Registry
) -> tuple[str, ...]:
    if not isinstance(profile, Mapping):
        raise RoutingContractError("profile 必须是对象", code="invalid_profile")
    intents = _strict_intents(profile.get("intents"), registry)
    if "answer_only" in intents and len(intents) > 1:
        raise RoutingContractError(
            "answer_only 不能与任何动作意图共存", code="answer_only_conflict"
        )
    must_clarify = profile.get("must_clarify", False)
    if not isinstance(must_clarify, bool):
        raise RoutingContractError(
            "must_clarify 必须是布尔值", code="invalid_must_clarify"
        )
    confidence = profile.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= float(confidence) <= 1
    ):
        raise RoutingContractError(
            "confidence 必须是 0 到 1 之间的数字", code="invalid_confidence"
        )
    if must_clarify or float(confidence) < float(registry.clarify["min_confidence"]):
        return ()
    if not intents:
        raise RoutingContractError(
            "非澄清画像必须至少有一个意图", code="intents_required"
        )
    return tuple(sorted(_resolve_from_intents(intents, registry)))


def direct_override_requested(task_text: str, registry: Registry) -> bool:
    if not isinstance(task_text, str):
        raise RoutingContractError("task_text 必须是字符串", code="invalid_task_text")
    lowered = task_text.lower()
    compact = re.sub(r"\s+", "", lowered)
    for phrase in registry.clarify["direct_override_phrases"]:
        candidate = phrase.lower()
        if candidate in lowered or re.sub(r"\s+", "", candidate) in compact:
            return True
    return False


def _collect_fields(
    profile: Mapping[str, Any],
    registry: Registry,
    errors: list[ValidationIssue],
) -> _ProfileFields:
    return _ProfileFields(
        intents=_label_list(
            profile.get("intents"), "intent", registry.intents, errors, required=True
        ),
        candidates=_label_list(
            profile.get("modules"), "module", registry.modules, errors
        ),
        triggers=_label_list(
            profile.get("triggers"), "trigger", registry.triggers, errors, required=True
        ),
        must_clarify=_bool_value(profile.get("must_clarify"), "must_clarify", errors),
        confidence=_confidence_value(profile.get("confidence"), errors),
        evidence=_evidence_value(profile.get("evidence"), errors),
        model=_model_value(profile.get("model"), "model", errors),
        model_version=_model_value(
            profile.get("model_version"), "model_version", errors
        ),
    )


def _check_intent_conflicts(
    intents: Sequence[str], errors: list[ValidationIssue]
) -> None:
    if "answer_only" in intents and len(intents) > 1:
        errors.append(
            ValidationIssue(
                "answer_only_conflict",
                "answer_only 不能与任何动作意图共存",
                "intents",
            )
        )


def _effective_clarify(
    fields: _ProfileFields,
    registry: Registry,
    warnings: list[ValidationIssue],
) -> bool:
    if fields.confidence is None:
        return fields.must_clarify
    effective = fields.must_clarify or fields.confidence < float(
        registry.clarify["min_confidence"]
    )
    if not fields.must_clarify and effective:
        warnings.append(
            ValidationIssue(
                "low_confidence_clarify",
                "置信度低于澄清阈值，画像已被降级为澄清",
                "confidence",
            )
        )
    return effective


def _candidate_issues(
    candidates: Sequence[str],
    modules: Sequence[str],
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
) -> None:
    extra = sorted(set(candidates) - set(modules))
    if extra:
        errors.append(
            ValidationIssue(
                "module_not_implied_by_intent",
                f"候选模块未被意图映射覆盖：{', '.join(extra)}",
                "modules",
            )
        )
    elif set(candidates) != set(modules):
        warnings.append(
            ValidationIssue(
                "candidate_modules_incomplete",
                "候选模块是依赖闭包的子集，宿主将补齐缺失模块",
                "modules",
            )
        )


def empty_profile() -> dict[str, Any]:
    return {
        "intents": [],
        "candidate_modules": [],
        "triggers": [],
        "must_clarify": False,
        "confidence": 0.0,
        "evidence_count": 0,
        "evidence": [],
    }


def _result(
    profile: Mapping[str, Any],
    modules: Sequence[str],
    effective_clarify: bool,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
    registry: Registry,
) -> ValidationResult:
    return ValidationResult(
        ok=not errors,
        profile=profile,
        modules=tuple(modules),
        effective_clarify=effective_clarify,
        errors=tuple(errors),
        warnings=tuple(warnings),
        registry_version=registry.version,
        registry_fingerprint=registry.fingerprint,
    )


def _label_list(
    value: Any,
    kind: str,
    allowed: Mapping[str, str],
    errors: list[ValidationIssue],
    *,
    required: bool = False,
) -> list[str]:
    field = f"{kind}s"
    if value is None:
        if required:
            errors.append(
                ValidationIssue(f"{kind}_required", f"{field} 不能为空", field)
            )
        return []
    if not isinstance(value, list):
        errors.append(
            ValidationIssue(f"invalid_{kind}_list", f"{field} 必须是数组", field)
        )
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(
                ValidationIssue(
                    f"invalid_{kind}", f"{field} 只能包含非空字符串", field
                )
            )
            continue
        if item not in allowed:
            errors.append(
                ValidationIssue(f"unknown_{kind}", f"未知{kind}：{item}", field)
            )
            continue
        result.append(item)
    if len(result) != len(set(result)):
        errors.append(
            ValidationIssue(f"duplicate_{kind}", f"{field} 不能重复", field)
        )
    return sorted(set(result))


def _bool_value(value: Any, field: str, errors: list[ValidationIssue]) -> bool:
    if not isinstance(value, bool):
        errors.append(
            ValidationIssue("invalid_must_clarify", f"{field} 必须是布尔值", field)
        )
        return False
    return value


def _confidence_value(value: Any, errors: list[ValidationIssue]) -> float | None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0 <= float(value) <= 1
    ):
        errors.append(
            ValidationIssue(
                "invalid_confidence",
                "confidence 必须是 0 到 1 之间的数字",
                "confidence",
            )
        )
        return None
    return float(value)


def _evidence_value(value: Any, errors: list[ValidationIssue]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 8:
        errors.append(
            ValidationIssue(
                "invalid_evidence", "evidence 必须是至多 8 项的数组", "evidence"
            )
        )
        return []
    result = []
    for item in value:
        if not isinstance(item, str) or not item or len(item) > 200:
            errors.append(
                ValidationIssue(
                    "invalid_evidence",
                    "evidence 每项必须是 1 到 200 字符的字符串",
                    "evidence",
                )
            )
            continue
        result.append(item)
    return result


def _model_value(
    value: Any, field: str, errors: list[ValidationIssue]
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not MODEL_NAME_PATTERN.fullmatch(value):
        errors.append(
            ValidationIssue(
                f"invalid_{field}",
                f"{field} 必须匹配 {MODEL_NAME_PATTERN.pattern}",
                field,
            )
        )
        return None
    return value


def _normalized_triggers(
    triggers: Sequence[str],
    intents: Sequence[str],
    must_clarify: bool,
    effective_clarify: bool,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
) -> list[str]:
    if effective_clarify:
        if must_clarify and set(triggers) - {"clarify_required"}:
            errors.append(
                ValidationIssue(
                    "clarify_trigger_mismatch",
                    "must_clarify=true 时 triggers 只能是 clarify_required",
                    "triggers",
                )
            )
        return ["clarify_required"]
    if "clarify_required" in triggers:
        errors.append(
            ValidationIssue(
                "clarify_trigger_mismatch",
                "must_clarify=false 时不能包含 clarify_required",
                "triggers",
            )
        )
    result = set(triggers) - {"clarify_required"}
    intent_set = set(intents)
    _check_trigger_dependencies(result, intent_set, errors)
    _derive_triggers(result, intent_set, warnings)
    return sorted(result)


def _check_trigger_dependencies(
    triggers: set[str], intents: set[str], errors: list[ValidationIssue]
) -> None:
    requirements = {
        "read_only": {"answer_only"},
        "bug_report": {"bug_fix"},
        "plan_required": {"plan_decision"},
        "asset_operation": {"asset_lifecycle"},
        "release": {"release"},
        "docs_edit": {"docs_change"},
        "code_edit": {"code_task", "bug_fix"},
        "code_verify": {"code_task", "bug_fix"},
    }
    for trigger, allowed in requirements.items():
        if trigger in triggers and not (intents & allowed):
            errors.append(
                ValidationIssue(
                    "trigger_conflict",
                    f"触发项 {trigger} 与意图 {sorted(intents)} 不兼容",
                    "triggers",
                )
            )


def _derive_triggers(
    triggers: set[str], intents: set[str], warnings: list[ValidationIssue]
) -> None:
    derived = {
        "answer_only": "read_only",
        "bug_fix": "bug_report",
        "plan_decision": "plan_required",
        "asset_lifecycle": "asset_operation",
        "release": "release",
        "docs_change": "docs_edit",
    }
    for intent in intents:
        trigger = derived.get(intent)
        if trigger:
            triggers.add(trigger)
    if "code_task" in intents and not ({"code_edit", "code_verify"} & triggers):
        warnings.append(
            ValidationIssue(
                "code_task_trigger_missing",
                "code_task 未给出 code_edit 或 code_verify，宿主无法判断改动还是验证",
                "triggers",
            )
        )


def _normalized_profile(
    fields: _ProfileFields,
    triggers: Sequence[str],
    effective_clarify: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "intents": sorted(set(fields.intents)),
        "candidate_modules": sorted(set(fields.candidates)),
        "triggers": sorted(set(triggers)),
        "must_clarify": bool(effective_clarify),
        "confidence": 0.0 if fields.confidence is None else float(fields.confidence),
        "evidence_count": len(fields.evidence),
        "evidence": list(fields.evidence),
    }
    if fields.model is not None:
        result["model"] = fields.model
    if fields.model_version is not None:
        result["model_version"] = fields.model_version
    return result


def _resolve_from_intents(
    intents: Sequence[str], registry: Registry
) -> list[str]:
    modules: set[str] = set()
    for intent in intents:
        modules.update(registry.intent_modules.get(intent, ()))
    pending = list(modules)
    while pending:
        current = pending.pop()
        for dependency in registry.module_dependencies.get(current, ()):
            if dependency not in modules:
                modules.add(dependency)
                pending.append(dependency)
    return sorted(modules)


def _strict_intents(value: Any, registry: Registry) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RoutingContractError("intents 必须是字符串数组", code="invalid_intents")
    if len(value) != len(set(value)):
        raise RoutingContractError("intents 不能重复", code="duplicate_intent")
    unknown = sorted(set(value) - set(registry.intents))
    if unknown:
        raise RoutingContractError(
            f"未知意图：{', '.join(unknown)}", code="unknown_intent"
        )
    return value
