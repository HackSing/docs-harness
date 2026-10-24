"""Shadow 指标聚合与覆盖率核对的合同测试。"""

from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harness_test_base import ROOT  # noqa: E402

import routing_contract as rc  # noqa: E402
import routing_metrics as rm  # noqa: E402
import routing_shadow as rs  # noqa: E402

REGISTRY_PATH = ROOT / "routing" / "registry.json"
NOW = dt.datetime(2026, 10, 23, 12, 0, tzinfo=dt.timezone.utc)


def profile(intents: list[str], triggers: list[str], *, confidence: float = 0.9, clarify: bool = False) -> dict:
    return {
        "intents": intents,
        "triggers": triggers,
        "must_clarify": clarify,
        "confidence": confidence,
    }


class MetricsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = rc.load_registry(REGISTRY_PATH)

    def event(
        self,
        task_id: str,
        profile_value: dict,
        actual: list[str],
        *,
        needed: list[str] | None = None,
        rework: list[str] | None = None,
        completed: bool = True,
        latency: float = 100,
        tokens_in: int = 10,
        tokens_out: int = 2,
        cost: float = 0.001,
        model: bool = True,
        cache_hit: bool = False,
    ) -> dict:
        return rs.build_shadow_event(
            task_id,
            profile_value,
            actual,
            {
                "clarify_asked": bool(profile_value["must_clarify"]),
                "rework": rework or [],
                "completed": completed,
            },
            registry=self.registry,
            needed_modules=needed,
            model=(
                {
                    "name": "strong-router",
                    "version": "1.0",
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "latency_ms": latency,
                    "cost_usd": cost,
                    "credits": 1.0,
                    "cache_hit": cache_hit,
                }
                if model
                else None
            ),
            now=NOW,
        )

    def fixture(self) -> list[dict]:
        return [
            self.event(
                "t1",
                profile(["code_task"], ["code_edit"]),
                ["code"],
                needed=["code"],
                latency=100,
            ),
            self.event(
                "t2",
                profile(["plan_decision"], ["plan_required"]),
                ["plan"],
                needed=["plan", "assets"],
                rework=["scope_correction"],
                latency=300,
            ),
            self.event(
                "t3",
                profile(["code_task", "docs_change"], ["code_edit", "docs_edit"]),
                ["code", "docs"],
                needed=["docs"],
                completed=False,
                latency=200,
            ),
            self.event(
                "t4",
                profile([], ["clarify_required"], confidence=0.4, clarify=True),
                [],
                needed=[],
                latency=50,
                tokens_in=5,
                tokens_out=1,
                cost=0.0005,
            ),
        ]

    def test_coverage_check_pass_and_fail(self) -> None:
        passed = rm.coverage_check(
            {"modules": ["code"], "must_clarify": False}, ["code"]
        )
        self.assertTrue(passed.ok)
        self.assertEqual(passed.missing_modules, ())
        self.assertEqual(passed.coverage_rate, 1.0)
        failed = rm.coverage_check(
            {"modules": ["code", "plan"], "must_clarify": False}, ["code"]
        )
        self.assertFalse(failed.ok)
        self.assertEqual(failed.missing_modules, ("plan",))
        self.assertEqual(failed.coverage_rate, 0.5)

    def test_coverage_check_clarify_and_invalid_input(self) -> None:
        clarify = rm.coverage_check({"modules": [], "must_clarify": True}, [])
        self.assertTrue(clarify.ok)
        with self.assertRaises(rm.RoutingMetricsError):
            rm.coverage_check({"modules": ["code"], "must_clarify": True}, ["code"])
        with self.assertRaises(rm.RoutingMetricsError):
            rm.coverage_check({"must_clarify": False}, ["code"])

    def test_summary_counts_rates_and_percentiles(self) -> None:
        summary = rm.summarize_shadow(self.fixture())
        overall = summary.overall
        self.assertEqual(summary.event_count, 4)
        self.assertEqual(overall["coverage_fail_count"], 0)
        self.assertEqual(overall["coverage_rate"], 1.0)
        self.assertEqual(overall["critical_miss_count"], 1)
        self.assertEqual(overall["critical_miss_rate"], 0.25)
        self.assertEqual(overall["over_routing_count"], 1)
        self.assertEqual(overall["over_routing_rate"], 0.25)
        self.assertEqual(overall["quality_verified_count"], 4)
        self.assertEqual(overall["clarify_rate"], 0.25)
        self.assertEqual(overall["rework_rate"], 0.25)
        self.assertEqual(overall["completed_rate"], 0.75)
        self.assertEqual(overall["latency_p50_ms"], 150.0)
        self.assertEqual(overall["latency_p95_ms"], 285.0)
        self.assertEqual(overall["tokens_in_total"], 35)
        self.assertEqual(overall["tokens_out_total"], 7)
        self.assertEqual(overall["tokens_per_task"], 10.5)
        self.assertEqual(overall["cost_usd_total"], 0.0035)
        self.assertEqual(overall["cost_per_task"], 0.000875)
        self.assertEqual(overall["credits_total"], 4.0)
        self.assertEqual(overall["credits_per_task"], 1.0)

    def test_groups_by_phase_risk_and_intent(self) -> None:
        summary = rm.summarize_shadow(self.fixture())
        self.assertEqual(summary.by_phase["shadow"]["event_count"], 4)
        self.assertEqual(summary.by_risk["low"]["event_count"], 2)
        self.assertEqual(summary.by_risk["high"]["event_count"], 1)
        self.assertEqual(summary.by_risk["unknown"]["event_count"], 1)
        self.assertEqual(summary.by_intent["code_task"]["event_count"], 2)
        self.assertEqual(summary.by_intent["docs_change"]["event_count"], 1)
        self.assertEqual(summary.by_intent["plan_decision"]["event_count"], 1)

    def test_coverage_failure_always_alerts(self) -> None:
        event = self.event(
            "bad",
            profile(["code_task"], ["code_edit"]),
            ["docs"],
            needed=["code"],
        )
        summary = rm.summarize_shadow([event])
        self.assertEqual(summary.overall["coverage_fail_count"], 1)
        self.assertEqual(summary.overall["critical_miss_rate"], 0.0)
        self.assertEqual(summary.alerts[0]["code"], "coverage_fail")
        self.assertEqual(summary.alerts[0]["severity"], "critical")

    def test_threshold_alerts(self) -> None:
        summary = rm.summarize_shadow(
            self.fixture(),
            thresholds={
                "critical_miss_rate_max": 0.0,
                "latency_p95_ms": 200,
                "tokens_per_task": 5,
                "cost_usd_per_task": 0.0001,
                "min_quality_verified_rate": 1.0,
                "rework_rate_max": 0.1,
            },
        )
        codes = {alert["code"] for alert in summary.alerts}
        self.assertTrue(
            {"critical_miss_rate", "latency_p95_ms", "tokens_per_task",
             "cost_per_task", "rework_rate"} <= codes
        )
        self.assertNotIn("quality_verified_rate", codes)

    def test_cache_hit_is_summarized(self) -> None:
        hit = self.event(
            "cache",
            profile(["code_task"], ["code_edit"]),
            ["code"],
            needed=["code"],
            cache_hit=True,
        )
        normal = self.event(
            "normal",
            profile(["code_task"], ["code_edit"]),
            ["code"],
            needed=["code"],
        )
        summary = rm.summarize_shadow([hit, normal])
        self.assertEqual(summary.overall["cache_hit_count"], 1)
        self.assertEqual(summary.overall["cache_hit_rate"], 0.5)

    def test_quality_unverified_events_do_not_fake_rates(self) -> None:
        event = self.event(
            "no-needed",
            profile(["code_task"], ["code_edit"]),
            ["code"],
            model=False,
        )
        summary = rm.summarize_shadow([event])
        self.assertEqual(summary.overall["quality_verified_count"], 0)
        self.assertIsNone(summary.overall["critical_miss_rate"])
        self.assertIsNone(summary.overall["over_routing_rate"])
        self.assertEqual(summary.overall["quality_unverified_count"], 1)
        self.assertIsNone(summary.overall["tokens_per_task"])

    def test_unknown_threshold_is_rejected(self) -> None:
        with self.assertRaises(rm.RoutingMetricsError):
            rm.summarize_shadow(self.fixture(), thresholds={"unknown": 1})

    def test_invalid_event_is_rejected(self) -> None:
        with self.assertRaises(rm.RoutingMetricsError) as caught:
            rm.summarize_shadow([{"schema_version": rs.SHADOW_SCHEMA}])
        self.assertEqual(caught.exception.code, "shadow_event_invalid")

    def test_summary_is_json_serializable(self) -> None:
        summary = rm.summarize_shadow(self.fixture())
        encoded = json.dumps(summary.to_dict(), ensure_ascii=False)
        self.assertIn("critical_miss_rate", encoded)


if __name__ == "__main__":
    unittest.main()
