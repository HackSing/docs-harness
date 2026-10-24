#!/usr/bin/env python3
"""意图路由基线评分器：校验用例、跑规则预测器、对比 gold 标签并输出指标。

规则预测器是刻意简单的关键词基线，用来量化“纯代码规则会在哪些输入上错配”，
不是生产路由实现。模型或 jev 的预测结果按 PREDICTION_SCHEMA 写成 JSON 后走
--predictions 评分。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "cases.json"
DATASET_SCHEMA = "docs-harness/intent-routing-eval/v1"
PREDICTION_SCHEMA = "docs-harness/intent-routing-predictions/v1"
DIFFICULTIES = {"explicit", "trap", "ambiguous", "multi_intent"}

INTENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "asset_lifecycle": ("knowledge", "验收", "acceptance", "adr", "结项"),
    "release": ("发版", "发布", "版本", "changelog", "下游", "打包"),
    "plan_decision": ("方案", "计划", "取舍", "回滚", "迁移", "架构", "plan"),
    "bug_fix": ("bug", "报错", "错误", "异常", "根因", "修复", "慢", "问题", "失败"),
    "docs_change": ("readme", "文档", "用户指南", "操作说明", "安装步骤"),
    "code_task": (
        "改", "实现", "重构", "合并", "新增", "删除", "加一个", "写一个",
        "测试", "构建", "跑一遍", "抽成", "实施",
    ),
}
ANSWER_PATTERNS = ("看看", "是否", "为什么", "怎么", "哪些", "?", "？")
DIRECT_OVERRIDE_PATTERNS = ("不使用 harness", "不用 harness", "不走 harness")
CHANGE_VERBS = ("改", "优化", "实现", "处理", "调整", "重构", "加", "删")
VAGUE_REFERENCES = ("这个", "那块", "这块", "一下", "顺便")
VERIFY_PATTERNS = ("测试", "构建", "跑一遍")
SCOPE_MARKERS = re.compile(r"(?:[\w.-]+/)+[\w.-]+|\.[A-Za-z0-9]{1,8}\b|`[^`]+`")


def _label_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} 必须是非空数组")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{name} 只能包含非空字符串")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} 不能重复")
    return value


def _optional_label_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} 必须是数组")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{name} 只能包含非空字符串")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} 不能重复")
    return value


def _check_subset(values: list[str], allowed: set[str], name: str) -> None:
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(f"{name} 含未知标签: {unknown}")


def validate_dataset(data: dict[str, Any]) -> None:
    if data.get("schema_version") != DATASET_SCHEMA:
        raise ValueError(f"schema_version 必须是 {DATASET_SCHEMA}")
    labels = data.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("labels 必须是对象")
    intents = set(_label_list(labels.get("intents"), "labels.intents"))
    modules = set(_label_list(labels.get("modules"), "labels.modules"))
    triggers = set(_label_list(labels.get("triggers"), "labels.triggers"))
    mapping = data.get("intent_modules")
    if not isinstance(mapping, dict) or set(mapping) != intents:
        raise ValueError("intent_modules 的键必须与 labels.intents 完全一致")
    for intent, values in mapping.items():
        _check_subset(values, modules, f"intent_modules[{intent}]")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases 必须是非空数组")
    seen: set[str] = set()
    for index, case in enumerate(cases):
        _validate_case(case, index, intents, modules, triggers, mapping, seen)


def _validate_case(
    case: Any,
    index: int,
    intents: set[str],
    modules: set[str],
    triggers: set[str],
    mapping: dict[str, list[str]],
    seen: set[str],
) -> None:
    if not isinstance(case, dict):
        raise ValueError(f"cases[{index}] 必须是对象")
    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError(f"cases[{index}].id 必须是非空字符串")
    if case_id in seen:
        raise ValueError(f"用例 id 重复: {case_id}")
    seen.add(case_id)
    if case.get("difficulty") not in DIFFICULTIES:
        raise ValueError(f"{case_id}.difficulty 必须是 {sorted(DIFFICULTIES)}")
    for field in ("setup", "prompt", "notes"):
        value = case.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{case_id}.{field} 必须是非空字符串")
    expected_intents = _label_list(case.get("expected_intents"), f"{case_id}.expected_intents")
    _check_subset(expected_intents, intents, f"{case_id}.expected_intents")
    expected_triggers = _label_list(case.get("expected_triggers"), f"{case_id}.expected_triggers")
    _check_subset(expected_triggers, triggers, f"{case_id}.expected_triggers")
    forbidden = case.get("forbidden_modules", [])
    if not isinstance(forbidden, list):
        raise ValueError(f"{case_id}.forbidden_modules 必须是数组")
    _check_subset(forbidden, modules, f"{case_id}.forbidden_modules")
    must_clarify = case.get("must_clarify")
    if not isinstance(must_clarify, bool):
        raise ValueError(f"{case_id}.must_clarify 必须是布尔值")
    required = [] if must_clarify else sorted({
        module for intent in expected_intents for module in mapping[intent]
    })
    if set(forbidden) & set(required):
        raise ValueError(f"{case_id}.forbidden_modules 不能包含必需模块 {sorted(set(forbidden) & set(required))}")
    if must_clarify and "clarify_required" not in expected_triggers:
        raise ValueError(f"{case_id} 需要澄清时必须含 clarify_required 触发项")
    if not must_clarify and "clarify_required" in expected_triggers:
        raise ValueError(f"{case_id} 不需要澄清时不能含 clarify_required")


def expected_modules(data: dict[str, Any], case: dict[str, Any]) -> list[str]:
    if case["must_clarify"]:
        return []
    return sorted({
        module
        for intent in case["expected_intents"]
        for module in data["intent_modules"][intent]
    })


def _needs_clarify(prompt: str, intents: list[str]) -> bool:
    if not intents:
        return True
    if SCOPE_MARKERS.search(prompt):
        return False
    has_change = any(verb in prompt for verb in CHANGE_VERBS)
    has_vague = any(ref in prompt for ref in VAGUE_REFERENCES)
    return has_change and has_vague


def _triggers_for(intents: list[str], prompt: str) -> list[str]:
    triggers: list[str] = []
    for intent in intents:
        if intent == "answer_only":
            triggers.append("read_only")
        elif intent == "code_task":
            code_triggers: list[str] = []
            if any(verb in prompt for verb in CHANGE_VERBS) or any(
                marker in prompt for marker in ("合并", "抽成", "实施", "写一个", "加一个")
            ):
                code_triggers.append("code_edit")
            if any(marker in prompt for marker in VERIFY_PATTERNS):
                code_triggers.append("code_verify")
            triggers.extend(code_triggers or ["code_edit"])
        elif intent == "bug_fix":
            triggers.append("bug_report")
        elif intent == "plan_decision":
            triggers.append("plan_required")
        elif intent == "asset_lifecycle":
            triggers.append("asset_operation")
        elif intent == "release":
            triggers.append("release")
        elif intent == "docs_change":
            triggers.append("docs_edit")
    return triggers


def predict_rules(prompt: str, data: dict[str, Any]) -> dict[str, Any]:
    lowered = prompt.lower()
    intents: list[str] = []
    evidence: list[str] = []
    for intent, patterns in INTENT_PATTERNS.items():
        matched = [pattern for pattern in patterns if pattern in lowered]
        if matched:
            intents.append(intent)
            evidence.extend(f"{intent}:{pattern}" for pattern in matched)
    if not intents:
        matched = [pattern for pattern in ANSWER_PATTERNS if pattern in lowered]
        if matched:
            intents.append("answer_only")
            evidence.extend(f"answer_only:{pattern}" for pattern in matched)
    must_clarify = _needs_clarify(prompt, intents)
    if must_clarify:
        modules: list[str] = []
        triggers = ["clarify_required"]
        evidence.append("clarify:vague_or_missing_intent")
        confidence = 0.2
    else:
        modules = sorted({
            module for intent in intents for module in data["intent_modules"][intent]
        })
        triggers = _triggers_for(intents, prompt)
        if any(pattern in lowered for pattern in DIRECT_OVERRIDE_PATTERNS):
            triggers.append("direct_override")
        triggers = sorted(set(triggers))
        confidence = 1.0 if len(intents) == 1 else 0.6
    return {
        "intents": sorted(intents),
        "modules": modules,
        "triggers": triggers,
        "must_clarify": must_clarify,
        "confidence": confidence,
        "evidence": evidence,
    }


def predictions_from_rules(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": PREDICTION_SCHEMA,
        "predictor": "rules-v1",
        "predictions": [
            {"id": case["id"], **predict_rules(case["prompt"], data)}
            for case in data["cases"]
        ],
    }


def load_dataset(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(data)
    return data


def load_predictions(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("predictions 顶层必须是对象")
    if data.get("schema_version") != PREDICTION_SCHEMA:
        raise ValueError(f"predictions.schema_version 必须是 {PREDICTION_SCHEMA}")
    return data


def validate_predictions(data: dict[str, Any], predictions: dict[str, Any]) -> None:
    labels = data["labels"]
    intents = set(labels["intents"])
    modules = set(labels["modules"])
    triggers = set(labels["triggers"])
    case_ids = {case["id"] for case in data["cases"]}
    items = predictions.get("predictions")
    if not isinstance(items, list):
        raise ValueError("predictions.predictions 必须是数组")
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"predictions[{index}] 必须是对象")
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"predictions[{index}].id 必须是非空字符串")
        if case_id not in case_ids:
            raise ValueError(f"predictions[{index}].id 未在 cases 中登记: {case_id}")
        if case_id in seen:
            raise ValueError(f"predictions 中 id 重复: {case_id}")
        seen.add(case_id)
        _check_subset(_optional_label_list(item.get("intents", []), f"{case_id}.intents"), intents, f"{case_id}.intents")
        _check_subset(_optional_label_list(item.get("modules", []), f"{case_id}.modules"), modules, f"{case_id}.modules")
        _check_subset(_optional_label_list(item.get("triggers", []), f"{case_id}.triggers"), triggers, f"{case_id}.triggers")
        if not isinstance(item.get("must_clarify", False), bool):
            raise ValueError(f"{case_id}.must_clarify 必须是布尔值")


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _aggregate(details: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(details)
    return {
        "case_count": count,
        "case_pass_rate": _ratio(sum(1 for item in details if item["case_pass"]), count),
        "intent_exact_rate": _ratio(sum(1 for item in details if item["intent_exact"]), count),
        "module_exact_rate": _ratio(sum(1 for item in details if item["module_exact"]), count),
        "module_recall": _ratio(sum(item["module_hits"] for item in details), sum(item["required_count"] for item in details)),
        "module_precision": _ratio(sum(item["module_hits"] for item in details), sum(item["predicted_count"] for item in details)),
        "intent_recall": _ratio(sum(item["intent_hits"] for item in details), sum(item["intent_expected_count"] for item in details)),
        "intent_precision": _ratio(sum(item["intent_hits"] for item in details), sum(item["intent_predicted_count"] for item in details)),
        "trigger_recall": _ratio(sum(item["trigger_hits"] for item in details), sum(item["trigger_expected_count"] for item in details)),
        "trigger_precision": _ratio(sum(item["trigger_hits"] for item in details), sum(item["trigger_predicted_count"] for item in details)),
        "critical_miss_rate": _ratio(sum(1 for item in details if item["critical_miss"]), count),
        "misroute_rate": _ratio(sum(1 for item in details if item["misroute"]), count),
        "clarify_accuracy": _ratio(sum(1 for item in details if item["clarify_correct"]), count),
        "must_clarify_recall": _ratio(
            sum(1 for item in details if item["must_clarify"] and item["clarify_correct"]),
            sum(1 for item in details if item["must_clarify"]),
        ),
        "false_clarify_rate": _ratio(
            sum(1 for item in details if not item["must_clarify"] and not item["clarify_correct"]),
            sum(1 for item in details if not item["must_clarify"]),
        ),
    }


def _score_case(
    data: dict[str, Any],
    case: dict[str, Any],
    prediction: dict[str, Any],
    prediction_missing: bool,
) -> dict[str, Any]:
    expected_intents = set(case["expected_intents"])
    predicted_intents = set(prediction.get("intents", []))
    required = set(expected_modules(data, case))
    predicted = set(prediction.get("modules", []))
    forbidden = set(case.get("forbidden_modules", []))
    expected_triggers = set(case["expected_triggers"])
    predicted_triggers = set(prediction.get("triggers", []))
    missing = sorted(required - predicted)
    forbidden_hits = sorted(predicted & forbidden)
    if case["must_clarify"]:
        clarify_correct = bool(prediction.get("must_clarify")) and not predicted
    else:
        clarify_correct = not bool(prediction.get("must_clarify"))
    intent_exact = predicted_intents == expected_intents
    module_exact = predicted == required
    critical_miss = bool(missing) or prediction_missing
    return {
        "id": case["id"],
        "difficulty": case["difficulty"],
        "must_clarify": case["must_clarify"],
        "intents": sorted(predicted_intents),
        "expected_intents": sorted(expected_intents),
        "modules": sorted(predicted),
        "required_modules": sorted(required),
        "missing_modules": missing,
        "extra_modules": sorted(predicted - required),
        "forbidden_hits": forbidden_hits,
        "triggers": sorted(predicted_triggers),
        "expected_triggers": sorted(expected_triggers),
        "missing_triggers": sorted(expected_triggers - predicted_triggers),
        "extra_triggers": sorted(predicted_triggers - expected_triggers),
        "intent_exact": intent_exact,
        "module_exact": module_exact,
        "prediction_missing": prediction_missing,
        "critical_miss": critical_miss,
        "misroute": critical_miss or bool(forbidden_hits),
        "case_pass": intent_exact and module_exact and clarify_correct and not prediction_missing,
        "clarify_correct": clarify_correct,
        "required_count": len(required),
        "predicted_count": len(predicted),
        "module_hits": len(required & predicted),
        "intent_expected_count": len(expected_intents),
        "intent_predicted_count": len(predicted_intents),
        "intent_hits": len(expected_intents & predicted_intents),
        "trigger_expected_count": len(expected_triggers),
        "trigger_predicted_count": len(predicted_triggers),
        "trigger_hits": len(expected_triggers & predicted_triggers),
    }


def score_cases(data: dict[str, Any], predictions: dict[str, Any]) -> dict[str, Any]:
    prediction_map = {item["id"]: item for item in predictions["predictions"]}
    details = [
        _score_case(
            data,
            case,
            prediction_map.get(case["id"], {
                "intents": [], "modules": [], "triggers": [], "must_clarify": False,
            }),
            case["id"] not in prediction_map,
        )
        for case in data["cases"]
    ]
    by_difficulty = {
        difficulty: _aggregate([item for item in details if item["difficulty"] == difficulty])
        for difficulty in sorted({item["difficulty"] for item in details})
    }
    return {
        "predictor": predictions.get("predictor", "unknown"),
        "model": predictions.get("model"),
        "missing_prediction_ids": sorted(
            {case["id"] for case in data["cases"]} - set(prediction_map)
        ),
        "summary": _aggregate(details),
        "by_difficulty": by_difficulty,
        "details": details,
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def format_summary(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"意图路由基线：{result['predictor']}",
        f"用例数: {summary['case_count']}",
        f"意图完全匹配: {_pct(summary['intent_exact_rate'])}",
        f"模块完全匹配: {_pct(summary['module_exact_rate'])}",
        f"模块召回: {_pct(summary['module_recall'])}",
        f"模块精确: {_pct(summary['module_precision'])}",
        f"关键漏配率: {_pct(summary['critical_miss_rate'])}",
        f"错配率: {_pct(summary['misroute_rate'])}",
        f"澄清判断正确率: {_pct(summary['clarify_accuracy'])}",
        f"触发项召回: {_pct(summary['trigger_recall'])}",
        f"触发项精确: {_pct(summary['trigger_precision'])}",
    ]
    if result["missing_prediction_ids"]:
        lines.append(f"缺失预测: {', '.join(result['missing_prediction_ids'])}")
    lines.append("")
    lines.append("id | intents | modules | missing | forbidden | misroute")
    for item in result["details"]:
        lines.append(
            f"{item['id']} | {','.join(item['intents']) or '-'} | "
            f"{','.join(item['modules']) or '-'} | {','.join(item['missing_modules']) or '-'} | "
            f"{','.join(item['forbidden_hits']) or '-'} | {'yes' if item['misroute'] else 'no'}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="意图路由基线评分器")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--predictor", choices=("rules",))
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--write-predictions", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.predictor and args.predictions:
        parser.error("--predictor 与 --predictions 不能同时使用")
    try:
        data = load_dataset(args.cases)
        if args.predictions:
            predictions = load_predictions(args.predictions)
        else:
            predictions = predictions_from_rules(data)
        validate_predictions(data, predictions)
        if args.write_predictions:
            args.write_predictions.parent.mkdir(parents=True, exist_ok=True)
            args.write_predictions.write_text(
                json.dumps(predictions, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        result = score_cases(data, predictions)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
