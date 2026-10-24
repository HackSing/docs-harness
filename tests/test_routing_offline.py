"""路由注册表与离线评分器的复用测试。"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harness_test_base import ROOT  # noqa: E402

import routing_contract as rc  # noqa: E402

EVAL_DIR = ROOT / "evals" / "intent_routing"
REGISTRY_PATH = ROOT / "routing" / "registry.json"
DATASETS = {
    "diagnostic": EVAL_DIR / "cases.json",
    "held-out-1": EVAL_DIR / "held_out_cases.json",
    "held-out-2": EVAL_DIR / "held_out_cases_2.json",
}
LOCAL_STRONG = {
    "held-out-1": [
        ROOT / ".docs-harness" / "evals" / "strong-held-out-predictions.json",
        ROOT / ".docs-harness" / "evals" / "strong-held-out-predictions-2.json",
    ],
    "held-out-2": [
        ROOT / ".docs-harness" / "evals" / "strong-held-out-2-predictions-run1.json",
        ROOT / ".docs-harness" / "evals" / "strong-held-out-2-predictions-run2.json",
    ],
}

SPEC = importlib.util.spec_from_file_location("intent_routing_score", EVAL_DIR / "score.py")
assert SPEC and SPEC.loader
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def load_dataset(path: Path) -> dict:
    return score.load_dataset(path)


def gold_profile(data: dict, case: dict) -> dict:
    return {
        "intents": case["expected_intents"],
        "modules": score.expected_modules(data, case),
        "triggers": case["expected_triggers"],
        "must_clarify": case["must_clarify"],
        "confidence": 0.9,
    }


def registry_predictions(data: dict, registry: rc.Registry) -> dict:
    predictions = []
    for case in data["cases"]:
        result = rc.validate_profile(gold_profile(data, case), registry)
        if not result.ok:
            raise AssertionError(
                f"{case['id']} gold profile 未通过校验：{[issue.code for issue in result.errors]}"
            )
        predictions.append(
            {
                "id": case["id"],
                "intents": result.profile["intents"],
                "modules": list(result.modules),
                "triggers": result.profile["triggers"],
                "must_clarify": result.effective_clarify,
                "confidence": result.profile["confidence"],
            }
        )
    return {
        "schema_version": score.PREDICTION_SCHEMA,
        "predictor": "registry-gold",
        "predictions": predictions,
    }


class OfflineRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = rc.load_registry(REGISTRY_PATH)
        cls.datasets = {name: load_dataset(path) for name, path in DATASETS.items()}

    def test_taxonomy_parity_across_all_datasets(self) -> None:
        for name, data in self.datasets.items():
            with self.subTest(dataset=name):
                self.assertEqual(
                    sorted(self.registry.intents), sorted(data["labels"]["intents"])
                )
                self.assertEqual(
                    sorted(self.registry.modules), sorted(data["labels"]["modules"])
                )
                self.assertEqual(
                    sorted(self.registry.triggers), sorted(data["labels"]["triggers"])
                )
                self.assertEqual(
                    {
                        intent: sorted(modules)
                        for intent, modules in self.registry.intent_modules.items()
                    },
                    {
                        intent: sorted(modules)
                        for intent, modules in data["intent_modules"].items()
                    },
                )

    def test_gold_profiles_resolve_to_expected_modules(self) -> None:
        for name, data in self.datasets.items():
            for case in data["cases"]:
                with self.subTest(dataset=name, case=case["id"]):
                    result = rc.validate_profile(gold_profile(data, case), self.registry)
                    self.assertTrue(result.ok, [issue.code for issue in result.errors])
                    self.assertEqual(
                        list(result.modules), score.expected_modules(data, case)
                    )
                    self.assertEqual(result.effective_clarify, case["must_clarify"])

    def test_registry_predictions_score_perfectly_through_score_cases(self) -> None:
        for name, data in self.datasets.items():
            with self.subTest(dataset=name):
                predictions = registry_predictions(data, self.registry)
                score.validate_predictions(data, predictions)
                result = score.score_cases(data, predictions)
                self.assertEqual(result["summary"]["case_count"], len(data["cases"]))
                self.assertEqual(result["summary"]["case_pass_rate"], 1.0)
                self.assertEqual(result["summary"]["intent_exact_rate"], 1.0)
                self.assertEqual(result["summary"]["module_exact_rate"], 1.0)
                self.assertEqual(result["summary"]["critical_miss_rate"], 0.0)
                self.assertEqual(result["summary"]["misroute_rate"], 0.0)

    def test_rules_baseline_still_runs_through_score_cases(self) -> None:
        data = self.datasets["diagnostic"]
        predictions = score.predictions_from_rules(data)
        score.validate_predictions(data, predictions)
        result = score.score_cases(data, predictions)
        self.assertEqual(result["summary"]["case_count"], 20)
        self.assertIn("critical_miss_rate", result["summary"])

    def test_local_strong_predictions_validate_and_score(self) -> None:
        files = [
            path
            for paths in LOCAL_STRONG.values()
            for path in paths
            if path.is_file()
        ]
        if not files:
            self.skipTest("本地强模型预测未归档")
        for path in files:
            with self.subTest(path=path.name):
                predictions = score.load_predictions(path)
                dataset_name = (
                    "held-out-2" if "held-out-2" in path.name else "held-out-1"
                )
                data = self.datasets[dataset_name]
                score.validate_predictions(data, predictions)
                for item in predictions["predictions"]:
                    result = rc.validate_profile(
                        {
                            "intents": item["intents"],
                            "modules": item.get("modules", []),
                            "triggers": item["triggers"],
                            "must_clarify": item.get("must_clarify", False),
                            "confidence": item.get("confidence", 0.9),
                        },
                        self.registry,
                    )
                    self.assertTrue(
                        result.ok,
                        f"{item['id']}: {[issue.code for issue in result.errors]}",
                    )
                    self.assertEqual(
                        list(result.modules), sorted(item.get("modules", []))
                    )
                result = score.score_cases(data, predictions)
                self.assertEqual(result["summary"]["case_count"], 50)
                self.assertEqual(result["summary"]["case_pass_rate"], 1.0)
                self.assertEqual(result["summary"]["critical_miss_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
