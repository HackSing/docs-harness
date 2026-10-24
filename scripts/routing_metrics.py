"""Shadow 指标聚合与执行前覆盖率核对。

`coverage_check` 是宿主的阻断点：解析出的必需模块必须全部被实际加载。
`summarize_shadow` 只消费 `routing_shadow` 的事件，输出按阶段、风险级别和
意图分组的计数、比率、延迟分位与 token/cost 汇总，并按阈值生成告警。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from routing_shadow import (
    PHASES,
    RISK_LEVELS,
    RoutingShadowError,
    validate_shadow_event,
)

THRESHOLD_KEYS = frozenset(
    {
        "calibration",
        "critical_miss_rate_max",
        "over_routing_rate_max",
        "clarify_rate_max",
        "rework_rate_max",
        "latency_p95_ms",
        "tokens_per_task",
        "cost_usd_per_task",
        "min_quality_verified_rate",
    }
)


class RoutingMetricsError(Exception):
    """指标输入不满足合同时抛出。"""

    def __init__(
        self,
        message: str,
        code: str = "routing_metrics_invalid",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


@dataclass(frozen=True)
class CoverageResult:
    ok: bool
    required_modules: tuple[str, ...]
    loaded_modules: tuple[str, ...]
    missing_modules: tuple[str, ...]
    extra_modules: tuple[str, ...]
    coverage_rate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "required_modules": list(self.required_modules),
            "loaded_modules": list(self.loaded_modules),
            "missing_modules": list(self.missing_modules),
            "extra_modules": list(self.extra_modules),
            "coverage_rate": self.coverage_rate,
        }


@dataclass(frozen=True)
class ShadowSummary:
    event_count: int
    overall: Mapping[str, Any]
    by_phase: Mapping[str, Mapping[str, Any]]
    by_risk: Mapping[str, Mapping[str, Any]]
    by_intent: Mapping[str, Mapping[str, Any]]
    alerts: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "overall": dict(self.overall),
            "by_phase": {key: dict(value) for key, value in self.by_phase.items()},
            "by_risk": {key: dict(value) for key, value in self.by_risk.items()},
            "by_intent": {key: dict(value) for key, value in self.by_intent.items()},
            "alerts": [dict(alert) for alert in self.alerts],
        }


def coverage_check(
    profile: Mapping[str, Any], loaded_modules: Sequence[str]
) -> CoverageResult:
    if not isinstance(profile, Mapping):
        raise RoutingMetricsError("profile 必须是对象", code="invalid_profile")
    must_clarify = profile.get("must_clarify", False)
    if not isinstance(must_clarify, bool):
        raise RoutingMetricsError("must_clarify 必须是布尔值", code="invalid_profile")
    modules = profile.get("modules")
    if modules is None:
        if must_clarify:
            modules = []
        else:
            raise RoutingMetricsError(
                "profile.modules 缺失；请传入 validate_profile 的解析结果",
                code="profile_modules_required",
            )
    required = _labels(modules, "required_modules")
    if must_clarify and required:
        raise RoutingMetricsError(
            "澄清画像不能带必需模块", code="clarify_profile_has_modules"
        )
    loaded = _labels(loaded_modules, "loaded_modules")
    missing = sorted(set(required) - set(loaded))
    extra = sorted(set(loaded) - set(required))
    rate = (
        1.0
        if not required
        else round(len(set(required) & set(loaded)) / len(required), 4)
    )
    return CoverageResult(
        ok=not missing,
        required_modules=tuple(required),
        loaded_modules=tuple(loaded),
        missing_modules=tuple(missing),
        extra_modules=tuple(extra),
        coverage_rate=rate,
    )


def summarize_shadow(
    events: Sequence[Mapping[str, Any]],
    *,
    thresholds: Mapping[str, Any] | None = None,
) -> ShadowSummary:
    if not isinstance(events, (list, tuple)):
        raise RoutingMetricsError("events 必须是数组", code="invalid_events")
    validated = []
    for index, event in enumerate(events):
        try:
            validated.append(validate_shadow_event(event))
        except RoutingShadowError as exc:
            raise RoutingMetricsError(
                f"第 {index + 1} 个 shadow 事件不合法：{exc.message}",
                code="shadow_event_invalid",
                details={"index": index, **exc.to_dict()},
            ) from exc
    overall = _aggregate(validated)
    by_phase = {
        phase: _aggregate([event for event in validated if event["phase"] == phase])
        for phase in PHASES
        if any(event["phase"] == phase for event in validated)
    }
    by_risk = {
        risk: _aggregate([event for event in validated if event["risk_level"] == risk])
        for risk in RISK_LEVELS
        if any(event["risk_level"] == risk for event in validated)
    }
    intents = sorted(
        {intent for event in validated for intent in event["profile"]["intents"]}
    )
    by_intent = {
        intent: _aggregate(
            [event for event in validated if intent in event["profile"]["intents"]]
        )
        for intent in intents
    }
    return ShadowSummary(
        event_count=len(validated),
        overall=overall,
        by_phase=by_phase,
        by_risk=by_risk,
        by_intent=by_intent,
        alerts=tuple(_alerts(overall, thresholds or {})),
    )


def _aggregate(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    count = len(events)
    counters, coverage_rates, latencies, tokens_in, tokens_out, cost_total = (
        _collect_aggregate(events)
    )
    return _aggregate_result(
        count, counters, coverage_rates, latencies, tokens_in, tokens_out, cost_total
    )


def _collect_aggregate(
    events: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, int], list[float], list[float], int, int, float]:
    counters = {
        "coverage_fail_count": 0,
        "critical_miss_count": 0,
        "over_routing_count": 0,
        "quality_verified_count": 0,
        "quality_unverified_count": 0,
        "clarify_count": 0,
        "rework_count": 0,
        "completed_count": 0,
        "completed_known_count": 0,
        "latency_count": 0,
        "model_metadata_count": 0,
        "token_metadata_count": 0,
        "cost_metadata_count": 0,
    }
    coverage_rates: list[float] = []
    latencies: list[float] = []
    tokens_in = 0
    tokens_out = 0
    cost_total = 0.0
    for event in events:
        _count_event(event, counters, coverage_rates, latencies)
        tokens_in += _model_number(event, "tokens_in", integer=True)
        tokens_out += _model_number(event, "tokens_out", integer=True)
        cost_total += _model_number(event, "cost_usd")
    return counters, coverage_rates, latencies, tokens_in, tokens_out, cost_total


def _aggregate_result(
    count: int,
    counters: Mapping[str, int],
    coverage_rates: Sequence[float],
    latencies: Sequence[float],
    tokens_in: int,
    tokens_out: int,
    cost_total: float,
) -> dict[str, Any]:
    return {
        "event_count": count,
        "coverage_fail_count": counters["coverage_fail_count"],
        "coverage_fail_rate": _rate(counters["coverage_fail_count"], count),
        "coverage_rate": _mean(coverage_rates, count),
        "critical_miss_count": counters["critical_miss_count"],
        "critical_miss_rate": _rate(
            counters["critical_miss_count"], counters["quality_verified_count"]
        ),
        "over_routing_count": counters["over_routing_count"],
        "over_routing_rate": _rate(
            counters["over_routing_count"], counters["quality_verified_count"]
        ),
        "quality_verified_count": counters["quality_verified_count"],
        "quality_unverified_count": counters["quality_unverified_count"],
        "quality_verified_rate": _rate(counters["quality_verified_count"], count),
        "clarify_count": counters["clarify_count"],
        "clarify_rate": _rate(counters["clarify_count"], count),
        "rework_count": counters["rework_count"],
        "rework_rate": _rate(counters["rework_count"], count),
        "completed_count": counters["completed_count"],
        "completed_rate": _rate(
            counters["completed_count"], counters["completed_known_count"]
        ),
        "latency_count": counters["latency_count"],
        "latency_p50_ms": _percentile(latencies, 0.50),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "model_metadata_count": counters["model_metadata_count"],
        "tokens_in_total": tokens_in,
        "tokens_out_total": tokens_out,
        "tokens_per_task": _ratio(
            tokens_in + tokens_out, counters["token_metadata_count"], digits=1
        ),
        "cost_usd_total": round(cost_total, 6)
        if counters["cost_metadata_count"]
        else None,
        "cost_per_task": _ratio(
            cost_total, counters["cost_metadata_count"], digits=6
        ),
    }


def _count_event(
    event: Mapping[str, Any],
    counters: dict[str, int],
    coverage_rates: list[float],
    latencies: list[float],
) -> None:
    required = set(event["modules"])
    actual = set(event["actual_modules"])
    rate = 1.0 if not required else len(required & actual) / len(required)
    coverage_rates.append(rate)
    if required - actual:
        counters["coverage_fail_count"] += 1
    if "needed_modules" in event:
        needed = set(event["needed_modules"])
        counters["quality_verified_count"] += 1
        if needed - required:
            counters["critical_miss_count"] += 1
        if required - needed:
            counters["over_routing_count"] += 1
    else:
        counters["quality_unverified_count"] += 1
    if event["profile"]["must_clarify"]:
        counters["clarify_count"] += 1
    if event["outcome"]["rework"]:
        counters["rework_count"] += 1
    if event["outcome"]["completed"] is not None:
        counters["completed_known_count"] += 1
        if event["outcome"]["completed"]:
            counters["completed_count"] += 1
    model = event.get("model")
    if model:
        counters["model_metadata_count"] += 1
        latency = model.get("latency_ms")
        if isinstance(latency, (int, float)) and not isinstance(latency, bool):
            counters["latency_count"] += 1
            latencies.append(float(latency))
        if "tokens_in" in model or "tokens_out" in model:
            counters["token_metadata_count"] += 1
        if "cost_usd" in model:
            counters["cost_metadata_count"] += 1


def _alerts(
    overall: Mapping[str, Any], thresholds: Mapping[str, Any]
) -> list[dict[str, Any]]:
    unknown = sorted(set(thresholds) - THRESHOLD_KEYS)
    if unknown:
        raise RoutingMetricsError(
            f"thresholds 含未知键：{', '.join(unknown)}",
            code="invalid_thresholds",
        )
    alerts: list[dict[str, Any]] = []
    if overall["coverage_fail_count"]:
        alerts.append(
            _alert(
                "coverage_fail",
                "critical",
                "coverage_fail_count",
                overall["coverage_fail_count"],
                0,
            )
        )
    rules = (
        ("critical_miss_rate_max", "critical_miss_rate", "critical_miss_rate", "critical"),
        ("over_routing_rate_max", "over_routing_rate", "over_routing_rate", "warning"),
        ("clarify_rate_max", "clarify_rate", "clarify_rate", "warning"),
        ("rework_rate_max", "rework_rate", "rework_rate", "warning"),
        ("latency_p95_ms", "latency_p95_ms", "latency_p95_ms", "warning"),
        ("tokens_per_task", "tokens_per_task", "tokens_per_task", "warning"),
        ("cost_usd_per_task", "cost_per_task", "cost_per_task", "warning"),
        (
            "min_quality_verified_rate",
            "quality_verified_rate",
            "quality_verified_rate",
            "warning",
        ),
    )
    for key, metric, code, severity in rules:
        threshold = thresholds.get(key)
        value = overall.get(metric)
        if threshold is None or value is None:
            continue
        if key == "min_quality_verified_rate":
            triggered = value < threshold
        else:
            triggered = value > threshold
        if triggered:
            alerts.append(_alert(code, severity, metric, value, threshold))
    severity_order = {"critical": 0, "warning": 1}
    return sorted(alerts, key=lambda item: (severity_order[item["severity"]], item["code"]))


def _alert(
    code: str, severity: str, metric: str, value: Any, threshold: Any
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "metric": metric,
        "value": value,
        "threshold": threshold,
    }


def _model_number(
    event: Mapping[str, Any], field: str, *, integer: bool = False
) -> float | int:
    model = event.get("model")
    if not model:
        return 0
    value = model.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return 0
    return int(value) if integer else float(value)


def _labels(value: Any, field: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise RoutingMetricsError(f"{field} 必须是数组", code="invalid_modules")
    labels = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise RoutingMetricsError(
                f"{field} 只能包含非空字符串", code="invalid_modules"
            )
        labels.append(item)
    if len(labels) != len(set(labels)):
        raise RoutingMetricsError(f"{field} 不能重复", code="invalid_modules")
    return sorted(labels)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _ratio(numerator: float, denominator: int, *, digits: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, digits)


def _mean(values: Sequence[float], count: int) -> float | None:
    if count == 0:
        return None
    return round(sum(values) / count, 4)


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        result = ordered[lower]
    else:
        weight = position - lower
        result = ordered[lower] * (1 - weight) + ordered[upper] * weight
    return round(result, 1)
