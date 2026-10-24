"""意图路由注册表的加载、指纹与数据合同校验。

注册表是路由 taxonomy、意图映射、模块契约、风险级别和政策的数据真源。
本模块只处理注册表本身，不校验模型画像，也不读写运行态日志。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

REGISTRY_SCHEMA = "docs-harness/routing-registry/v1"
FINGERPRINT_PREFIX = "sha256:"
LABEL_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
RATE_THRESHOLD_KEYS = frozenset(
    {
        "critical_miss_rate_max",
        "over_routing_rate_max",
        "clarify_rate_max",
        "rework_rate_max",
        "min_quality_verified_rate",
    }
)
NUMBER_BUDGET_KEYS = frozenset(
    {"latency_p95_ms", "tokens_per_task", "cost_usd_per_task"}
)


class RoutingContractError(Exception):
    """注册表或路由合同无法满足时的结构化错误。"""

    def __init__(
        self,
        message: str,
        code: str = "routing_contract_invalid",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


@dataclass(frozen=True)
class Registry:
    schema_version: str
    version: str
    fingerprint: str
    intents: Mapping[str, str]
    modules: Mapping[str, str]
    triggers: Mapping[str, str]
    intent_modules: Mapping[str, tuple[str, ...]]
    module_dependencies: Mapping[str, tuple[str, ...]]
    module_order: tuple[str, ...]
    risk_levels: Mapping[str, tuple[str, ...]]
    kernel_contract: Mapping[str, Any]
    contracts: Mapping[str, Mapping[str, Any]]
    clarify: Mapping[str, Any]
    budgets: Mapping[str, Any]
    thresholds: Mapping[str, Any]
    coexistence: tuple[Mapping[str, Any], ...]
    source_refs: tuple[str, ...]


def registry_fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "fingerprint"}
    try:
        encoded = json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RoutingContractError(
            f"注册表包含无法规范化序列化的内容：{exc}", code="registry_not_canonical"
        ) from exc
    return FINGERPRINT_PREFIX + hashlib.sha256(encoded).hexdigest()


def load_registry(path: str | Path) -> Registry:
    registry_path = Path(path)
    try:
        text = registry_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RoutingContractError(
            f"无法读取路由注册表 {registry_path}：{exc}",
            code="registry_unreadable",
            details={"path": str(registry_path)},
        ) from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RoutingContractError(
            f"路由注册表不是合法 JSON：{exc}",
            code="registry_invalid_json",
            details={"path": str(registry_path), "line": exc.lineno, "column": exc.colno},
        ) from exc
    return _build_registry(payload, registry_path)


def _build_registry(payload: Any, path: Path) -> Registry:
    if not isinstance(payload, Mapping):
        raise RoutingContractError("注册表顶层必须是对象", code="registry_not_object")
    if payload.get("schema_version") != REGISTRY_SCHEMA:
        raise RoutingContractError(
            f"注册表 schema_version 必须是 {REGISTRY_SCHEMA}",
            code="registry_schema_mismatch",
        )
    version = _non_empty(payload.get("version"), "version", "registry_version_invalid")
    taxonomy = _taxonomy(payload.get("taxonomy"))
    intent_modules, dependencies = _module_policy(
        payload.get("intent_modules"),
        payload.get("module_dependencies", {}),
        taxonomy["intents"],
        taxonomy["modules"],
    )
    module_order = _module_order(payload.get("module_order"), taxonomy["modules"])
    risk_levels = _risk_levels(payload.get("risk_levels"), taxonomy["modules"])
    kernel_contract = _contract(payload.get("kernel_contract"), "kernel_contract", False)
    contracts = _contracts(payload.get("contracts"), taxonomy["modules"])
    coexistence = _coexistence(payload.get("coexistence", []), taxonomy["modules"])
    clarify = _clarify(payload.get("clarify"))
    budgets, thresholds = _budgets_and_thresholds(
        payload.get("budgets", {}), payload.get("thresholds", {})
    )
    source_refs = _source_refs(payload.get("source_refs", []))
    fingerprint = payload.get("fingerprint")
    if not isinstance(fingerprint, str) or not FINGERPRINT_PATTERN.fullmatch(fingerprint):
        raise RoutingContractError(
            "注册表必须包含 fingerprint（sha256:<64 位十六进制>）",
            code="registry_fingerprint_missing",
        )
    expected = registry_fingerprint(payload)
    if fingerprint != expected:
        raise RoutingContractError(
            "注册表指纹不匹配，内容可能被手工修改",
            code="registry_fingerprint_mismatch",
            details={"expected": expected, "actual": fingerprint, "path": str(path)},
        )
    return Registry(
        schema_version=REGISTRY_SCHEMA,
        version=version,
        fingerprint=fingerprint,
        intents=taxonomy["intents"],
        modules=taxonomy["modules"],
        triggers=taxonomy["triggers"],
        intent_modules=intent_modules,
        module_dependencies=dependencies,
        module_order=module_order,
        risk_levels=risk_levels,
        kernel_contract=kernel_contract,
        contracts=contracts,
        clarify=clarify,
        budgets=budgets,
        thresholds=thresholds,
        coexistence=coexistence,
        source_refs=source_refs,
    )


def _taxonomy(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, Mapping):
        raise RoutingContractError("taxonomy 必须是对象", code="registry_taxonomy_invalid")
    result: dict[str, dict[str, str]] = {}
    for name in ("intents", "modules", "triggers"):
        result[name] = _label_map(value.get(name), f"taxonomy.{name}")
    return result


def _module_policy(
    intents_value: Any,
    dependencies_value: Any,
    intents: Mapping[str, str],
    modules: Mapping[str, str],
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    if not isinstance(intents_value, Mapping) or set(intents_value) != set(intents):
        raise RoutingContractError(
            "intent_modules 的键必须与 taxonomy.intents 完全一致",
            code="registry_intent_modules_invalid",
        )
    if "answer_only" not in intents:
        raise RoutingContractError(
            "taxonomy.intents 必须包含 answer_only",
            code="registry_taxonomy_invalid",
        )
    intent_modules = {
        intent: _module_list(values, f"intent_modules[{intent}]", modules)
        for intent, values in intents_value.items()
    }
    if intent_modules["answer_only"]:
        raise RoutingContractError(
            "answer_only 不能映射任何模块", code="registry_answer_only_mapping"
        )
    for intent, mapped in intent_modules.items():
        if intent != "answer_only" and not mapped:
            raise RoutingContractError(
                f"动作意图 {intent} 必须映射至少一个模块",
                code="registry_intent_mapping_empty",
            )
    dependencies = {
        module: _module_list(values, f"module_dependencies[{module}]", modules)
        for module, values in _mapping(dependencies_value, "module_dependencies").items()
    }
    unknown = sorted(set(dependencies) - set(modules))
    if unknown:
        raise RoutingContractError(
            f"module_dependencies 含未知模块：{', '.join(unknown)}",
            code="registry_module_unknown",
        )
    if "bugfix" in modules and "code" not in modules:
        raise RoutingContractError(
            "bugfix 模块存在时必须同时提供 code 模块",
            code="registry_bugfix_dependency_missing",
        )
    return intent_modules, dependencies


def _module_order(value: Any, modules: Mapping[str, str]) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RoutingContractError(
            "module_order 必须是数组", code="registry_module_order_invalid"
        )
    if any(not isinstance(item, str) for item in value):
        raise RoutingContractError(
            "module_order 只能包含字符串", code="registry_module_order_invalid"
        )
    if len(value) != len(set(value)) or set(value) != set(modules):
        raise RoutingContractError(
            "module_order 必须恰好覆盖全部模块且不重复",
            code="registry_module_order_invalid",
        )
    return tuple(value)


def _risk_levels(value: Any, modules: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    levels = _mapping(value, "risk_levels")
    if set(levels) != {"low", "medium", "high"}:
        raise RoutingContractError(
            "risk_levels 必须且只能包含 low/medium/high",
            code="registry_risk_levels_invalid",
        )
    result = {
        level: _module_list(items, f"risk_levels[{level}]", modules)
        for level, items in levels.items()
    }
    assigned = [module for items in result.values() for module in items]
    if len(assigned) != len(set(assigned)) or set(assigned) != set(modules):
        raise RoutingContractError(
            "每个模块必须恰好属于一个风险级别",
            code="registry_risk_levels_invalid",
        )
    return result


def _contracts(value: Any, modules: Mapping[str, str]) -> dict[str, Mapping[str, Any]]:
    contracts = _mapping(value, "contracts")
    if set(contracts) != set(modules):
        raise RoutingContractError(
            "contracts 的键必须与 taxonomy.modules 完全一致",
            code="registry_contracts_invalid",
        )
    return {
        module: _contract(contract, f"contracts[{module}]", True)
        for module, contract in contracts.items()
    }


def _contract(value: Any, name: str, with_scope: bool) -> Mapping[str, Any]:
    contract = _mapping(value, name)
    title = _non_empty(contract.get("title"), f"{name}.title", "registry_contract_invalid")
    rules = _string_list(contract.get("rules"), f"{name}.rules", "registry_contract_invalid")
    result: dict[str, Any] = {"title": title, "rules": rules}
    if with_scope:
        result["scope"] = _non_empty(
            contract.get("scope"), f"{name}.scope", "registry_contract_invalid"
        )
        result["verification"] = _string_list(
            contract.get("verification"),
            f"{name}.verification",
            "registry_contract_invalid",
        )
    return result


def _coexistence(value: Any, modules: Mapping[str, str]) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise RoutingContractError(
            "coexistence 必须是数组", code="registry_coexistence_invalid"
        )
    result = []
    for index, item in enumerate(value):
        entry = _mapping(item, f"coexistence[{index}]")
        names = _module_list(entry.get("modules"), f"coexistence[{index}].modules", modules)
        if len(names) < 2:
            raise RoutingContractError(
                "coexistence 条目至少包含两个模块",
                code="registry_coexistence_invalid",
            )
        rule = _non_empty(
            entry.get("rule"),
            f"coexistence[{index}].rule",
            "registry_coexistence_invalid",
        )
        result.append({"modules": list(names), "rule": rule})
    return tuple(result)


def _clarify(value: Any) -> Mapping[str, Any]:
    clarify = _mapping(value, "clarify")
    min_confidence = clarify.get("min_confidence")
    if (
        not isinstance(min_confidence, (int, float))
        or isinstance(min_confidence, bool)
        or not 0 <= float(min_confidence) <= 1
    ):
        raise RoutingContractError(
            "clarify.min_confidence 必须是 0 到 1 之间的数字",
            code="registry_clarify_invalid",
        )
    if clarify.get("low_confidence_behavior") != "clarify":
        raise RoutingContractError(
            "clarify.low_confidence_behavior 必须是 clarify",
            code="registry_clarify_invalid",
        )
    max_questions = clarify.get("max_questions")
    if not isinstance(max_questions, int) or isinstance(max_questions, bool) or max_questions < 1:
        raise RoutingContractError(
            "clarify.max_questions 必须是正整数", code="registry_clarify_invalid"
        )
    if clarify.get("direct_override_behavior") != "direct":
        raise RoutingContractError(
            "clarify.direct_override_behavior 必须是 direct",
            code="registry_clarify_invalid",
        )
    return {
        "min_confidence": float(min_confidence),
        "low_confidence_behavior": "clarify",
        "max_questions": max_questions,
        "question_scope": _string_list(
            clarify.get("question_scope"),
            "clarify.question_scope",
            "registry_clarify_invalid",
        ),
        "direct_override_phrases": _string_list(
            clarify.get("direct_override_phrases"),
            "clarify.direct_override_phrases",
            "registry_clarify_invalid",
        ),
        "direct_override_behavior": "direct",
    }


def _budgets_and_thresholds(
    budgets_value: Any, thresholds_value: Any
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    budgets = dict(_mapping(budgets_value, "budgets"))
    thresholds = dict(_mapping(thresholds_value, "thresholds"))
    for key, value in budgets.items():
        if key == "calibration":
            continue
        if key not in NUMBER_BUDGET_KEYS:
            raise RoutingContractError(
                f"budgets 含未知键：{key}", code="registry_budgets_invalid"
            )
        if value is not None and (
            not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
        ):
            raise RoutingContractError(
                f"budgets.{key} 必须是非负数或 null", code="registry_budgets_invalid"
            )
    for key, value in thresholds.items():
        if key == "calibration":
            continue
        if key not in RATE_THRESHOLD_KEYS:
            raise RoutingContractError(
                f"thresholds 含未知键：{key}", code="registry_thresholds_invalid"
            )
        if value is None:
            continue
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
        if key in RATE_THRESHOLD_KEYS:
            valid = valid and value <= 1
        if not valid:
            raise RoutingContractError(
                f"thresholds.{key} 必须是范围内的数字或 null",
                code="registry_thresholds_invalid",
            )
    return budgets, thresholds


def _source_refs(value: Any) -> tuple[str, ...]:
    refs = _string_list(value, "source_refs", "registry_source_refs_invalid")
    return tuple(refs)


def _label_map(value: Any, name: str) -> dict[str, str]:
    mapping = _mapping(value, name)
    result: dict[str, str] = {}
    for label, description in mapping.items():
        if not isinstance(label, str) or not LABEL_PATTERN.fullmatch(label):
            raise RoutingContractError(
                f"{name} 的标签必须匹配 {LABEL_PATTERN.pattern}",
                code="registry_taxonomy_invalid",
            )
        result[label] = _non_empty(
            description, f"{name}[{label}]", "registry_taxonomy_invalid"
        )
    return result


def _module_list(value: Any, name: str, modules: Mapping[str, str]) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RoutingContractError(f"{name} 必须是数组", code="registry_mapping_invalid")
    values = []
    for item in value:
        if not isinstance(item, str) or item not in modules:
            raise RoutingContractError(
                f"{name} 含未知模块：{item}", code="registry_module_unknown"
            )
        values.append(item)
    if len(values) != len(set(values)):
        raise RoutingContractError(f"{name} 不能重复", code="registry_mapping_invalid")
    return tuple(values)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RoutingContractError(f"{name} 必须是对象", code="registry_invalid")
    return value


def _non_empty(value: Any, name: str, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoutingContractError(f"{name} 必须是非空字符串", code=code)
    return value


def _string_list(value: Any, name: str, code: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise RoutingContractError(f"{name} 必须是非空数组", code=code)
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RoutingContractError(f"{name} 只能包含非空字符串", code=code)
        result.append(item)
    return result
