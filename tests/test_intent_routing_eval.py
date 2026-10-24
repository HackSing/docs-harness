"""意图路由基线的数据集契约与评分器测试。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import ROOT  # noqa: E402

SCORE_PATH = ROOT / "evals" / "intent_routing" / "score.py"
CASES_PATH = ROOT / "evals" / "intent_routing" / "cases.json"
HELD_OUT_CASES_PATH = ROOT / "evals" / "intent_routing" / "held_out_cases.json"
HELD_OUT_2_CASES_PATH = ROOT / "evals" / "intent_routing" / "held_out_cases_2.json"

SPEC = importlib.util.spec_from_file_location("intent_routing_score", SCORE_PATH)
assert SPEC and SPEC.loader
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def synthetic_dataset() -> dict:
    return {
        "schema_version": score.DATASET_SCHEMA,
        "dataset_version": "test",
        "labels": {
            "intents": ["answer_only", "code_task"],
            "modules": ["code", "plan"],
            "triggers": ["read_only", "code_edit", "clarify_required"],
        },
        "intent_modules": {"answer_only": [], "code_task": ["code"]},
        "cases": [
            {
                "id": "case-code",
                "difficulty": "explicit",
                "setup": "x",
                "prompt": "改代码",
                "expected_intents": ["code_task"],
                "expected_triggers": ["code_edit"],
                "forbidden_modules": ["plan"],
                "must_clarify": False,
                "notes": "x",
            },
            {
                "id": "case-answer",
                "difficulty": "trap",
                "setup": "x",
                "prompt": "看看",
                "expected_intents": ["answer_only"],
                "expected_triggers": ["read_only"],
                "forbidden_modules": ["code", "plan"],
                "must_clarify": False,
                "notes": "x",
            },
        ],
    }


def assert_case_mapping(test_case: unittest.TestCase, data: dict) -> None:
    modules = set(data["labels"]["modules"])
    for case in data["cases"]:
        with test_case.subTest(case=case["id"]):
            expected = score.expected_modules(data, case)
            if case["must_clarify"]:
                test_case.assertEqual(expected, [])
                test_case.assertIn("clarify_required", case["expected_triggers"])
            else:
                derived = sorted({
                    module
                    for intent in case["expected_intents"]
                    for module in data["intent_modules"][intent]
                })
                test_case.assertEqual(expected, derived)
                test_case.assertNotIn("clarify_required", case["expected_triggers"])
            test_case.assertEqual(set(case["forbidden_modules"]), modules - set(expected))


class IntentRoutingDatasetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = score.load_dataset(CASES_PATH)

    def test_dataset_has_20_unique_cases(self) -> None:
        ids = [case["id"] for case in self.data["cases"]]
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(ids), len(set(ids)))

    def test_expected_modules_follow_mapping_and_clarify_rule(self) -> None:
        assert_case_mapping(self, self.data)


class HeldOutDatasetsTest(unittest.TestCase):
    EXPECTED_DIFFICULTY = {
        HELD_OUT_CASES_PATH: {"explicit": 29, "trap": 9, "ambiguous": 6, "multi_intent": 6},
        HELD_OUT_2_CASES_PATH: {"explicit": 27, "trap": 10, "ambiguous": 6, "multi_intent": 7},
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.main = score.load_dataset(CASES_PATH)
        cls.datasets = {
            path: score.load_dataset(path) for path in cls.EXPECTED_DIFFICULTY
        }

    def test_each_held_out_dataset_has_50_unique_disjoint_cases(self) -> None:
        seen = {case["id"] for case in self.main["cases"]}
        for path, data in self.datasets.items():
            with self.subTest(dataset=path.name):
                ids = [case["id"] for case in data["cases"]]
                self.assertEqual(len(ids), 50)
                self.assertEqual(len(ids), len(set(ids)))
                self.assertFalse(set(ids) & seen)
                seen.update(ids)

    def test_each_held_out_taxonomy_matches_main_dataset(self) -> None:
        for path, data in self.datasets.items():
            with self.subTest(dataset=path.name):
                self.assertEqual(data["labels"], self.main["labels"])
                self.assertEqual(data["intent_modules"], self.main["intent_modules"])

    def test_each_held_out_expected_modules_and_forbidden_sets(self) -> None:
        for path, data in self.datasets.items():
            with self.subTest(dataset=path.name):
                assert_case_mapping(self, data)

    def test_each_held_out_difficulty_distribution(self) -> None:
        for path, data in self.datasets.items():
            with self.subTest(dataset=path.name):
                counts = Counter(case["difficulty"] for case in data["cases"])
                self.assertEqual(counts, self.EXPECTED_DIFFICULTY[path])

    def test_scorer_cli_runs_on_each_held_out_dataset(self) -> None:
        for path in self.EXPECTED_DIFFICULTY:
            with self.subTest(dataset=path.name):
                result = subprocess.run(
                    [sys.executable, str(SCORE_PATH), "--cases", str(path), "--json"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["summary"]["case_count"], 50)


class RulesPredictorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = score.load_dataset(CASES_PATH)

    def test_rule_predictions_are_deterministic(self) -> None:
        self.assertEqual(
            score.predictions_from_rules(self.data),
            score.predictions_from_rules(self.data),
        )

    def test_clear_code_change_selects_code_only(self) -> None:
        case = next(item for item in self.data["cases"] if item["id"] == "code-rename-slugify")
        prediction = score.predict_rules(case["prompt"], self.data)
        self.assertEqual(prediction["intents"], ["code_task"])
        self.assertEqual(prediction["modules"], ["code"])
        self.assertIn("code_edit", prediction["triggers"])

    def test_vague_change_requires_clarification_without_modules(self) -> None:
        case = next(item for item in self.data["cases"] if item["id"] == "ambiguous-change-scope")
        prediction = score.predict_rules(case["prompt"], self.data)
        self.assertTrue(prediction["must_clarify"])
        self.assertEqual(prediction["modules"], [])
        self.assertEqual(prediction["triggers"], ["clarify_required"])

    def test_direct_override_keeps_code_contract(self) -> None:
        case = next(item for item in self.data["cases"] if item["id"] == "direct-override-refactor")
        prediction = score.predict_rules(case["prompt"], self.data)
        self.assertEqual(prediction["modules"], ["code"])
        self.assertIn("direct_override", prediction["triggers"])


class ScoreMathTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = synthetic_dataset()
        score.validate_dataset(self.data)

    def test_score_math_on_synthetic_cases(self) -> None:
        predictions = {
            "schema_version": score.PREDICTION_SCHEMA,
            "predictor": "test",
            "predictions": [
                {"id": "case-code", "intents": ["code_task"], "modules": ["code"],
                 "triggers": ["code_edit"], "must_clarify": False},
                {"id": "case-answer", "intents": ["code_task"], "modules": ["code"],
                 "triggers": ["code_edit"], "must_clarify": False},
            ],
        }
        score.validate_predictions(self.data, predictions)
        result = score.score_cases(self.data, predictions)
        summary = result["summary"]
        self.assertEqual(summary["case_count"], 2)
        self.assertEqual(summary["intent_exact_rate"], 0.5)
        self.assertEqual(summary["module_exact_rate"], 0.5)
        self.assertEqual(summary["critical_miss_rate"], 0.0)
        self.assertEqual(summary["misroute_rate"], 0.5)
        self.assertEqual(summary["module_recall"], 1.0)
        self.assertEqual(summary["module_precision"], 0.5)
        self.assertEqual(summary["clarify_accuracy"], 1.0)
        self.assertEqual(result["missing_prediction_ids"], [])

    def test_missing_prediction_counts_as_critical_miss(self) -> None:
        predictions = {
            "schema_version": score.PREDICTION_SCHEMA,
            "predictor": "test",
            "predictions": [
                {"id": "case-code", "intents": ["code_task"], "modules": ["code"],
                 "triggers": ["code_edit"], "must_clarify": False},
            ],
        }
        result = score.score_cases(self.data, predictions)
        self.assertEqual(result["missing_prediction_ids"], ["case-answer"])
        detail = next(item for item in result["details"] if item["id"] == "case-answer")
        self.assertTrue(detail["prediction_missing"])
        self.assertTrue(detail["critical_miss"])
        self.assertTrue(detail["misroute"])
        self.assertFalse(detail["case_pass"])

    def test_unknown_prediction_id_is_rejected(self) -> None:
        predictions = {
            "schema_version": score.PREDICTION_SCHEMA,
            "predictor": "test",
            "predictions": [
                {"id": "unknown", "intents": ["code_task"], "modules": ["code"],
                 "triggers": ["code_edit"], "must_clarify": False},
            ],
        }
        with self.assertRaises(ValueError):
            score.validate_predictions(self.data, predictions)

    def test_unknown_module_is_rejected(self) -> None:
        predictions = {
            "schema_version": score.PREDICTION_SCHEMA,
            "predictor": "test",
            "predictions": [
                {"id": "case-code", "intents": ["code_task"], "modules": ["unknown"],
                 "triggers": ["code_edit"], "must_clarify": False},
            ],
        }
        with self.assertRaises(ValueError):
            score.validate_predictions(self.data, predictions)


class ScoreCliTest(unittest.TestCase):
    def test_rules_cli_emits_json_for_all_cases(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCORE_PATH), "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["case_count"], 20)
        self.assertGreater(payload["summary"]["misroute_rate"], 0)
        self.assertTrue(payload["by_difficulty"])


if __name__ == "__main__":
    unittest.main()
