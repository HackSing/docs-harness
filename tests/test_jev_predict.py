"""Jev 适配器的离线契约测试：请求形状、阈值策略与错误处理，不发网络请求。"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import ROOT  # noqa: E402

JEV_PATH = ROOT / "evals" / "intent_routing" / "jev_predict.py"
CASES_PATH = ROOT / "evals" / "intent_routing" / "cases.json"

SPEC = importlib.util.spec_from_file_location("intent_routing_jev", JEV_PATH)
assert SPEC and SPEC.loader
jev_predict = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jev_predict)

INTENTS = (
    "answer_only", "code_task", "bug_fix", "plan_decision",
    "asset_lifecycle", "release", "docs_change",
)


def jev_response(
    primary: str,
    confidence: float,
    scores: dict[str, float],
    *,
    clarify: float = 0.1,
    direct_override: float = 0.02,
    code_verify: float = 0.02,
) -> dict:
    values = {intent: 0.01 for intent in INTENTS}
    values.update(scores)
    answers = {
        "primary_intent": {
            "type": "choice",
            "choice": primary,
            "confidence": confidence,
            "probabilities": {primary: confidence},
        },
        "clarify_required": {"type": "noul", "noul": clarify},
        "direct_override": {"type": "noul", "noul": direct_override},
        "code_verify": {"type": "noul", "noul": code_verify},
    }
    for intent, value in values.items():
        answers[f"intent_{intent}"] = {"type": "noul", "noul": value}
    return {"model": "jev-test", "answers": answers, "usage": {"input_tokens": 10, "output_tokens": 2}}


class JevPredictTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = jev_predict._load_cases(CASES_PATH)

    def case(self, case_id: str) -> dict:
        return next(item for item in self.dataset["cases"] if item["id"] == case_id)

    def test_payload_has_primary_intent_nouls_and_aux_questions(self) -> None:
        case = self.case("code-rename-slugify")
        payload = jev_predict.build_payload(case, "jev-test")
        self.assertEqual(payload["model"], "jev-test")
        self.assertEqual(payload["state"]["user_request"], case["prompt"])
        self.assertEqual(payload["questions"]["primary_intent"]["type"], "choice")
        for intent in INTENTS:
            self.assertEqual(payload["questions"][f"intent_{intent}"]["type"], "noul")
        for name in ("clarify_required", "direct_override", "code_verify"):
            self.assertEqual(payload["questions"][name]["type"], "noul")

    def test_vague_change_clarifies_and_keeps_tentative_intent(self) -> None:
        response = jev_response("unclear", 0.52, {"code_task": 0.95}, clarify=0.96)
        prediction = jev_predict.interpret_response(
            self.case("ambiguous-change-scope"), response, self.dataset
        )
        self.assertTrue(prediction["must_clarify"])
        self.assertEqual(prediction["modules"], [])
        self.assertEqual(prediction["intents"], ["code_task"])
        self.assertEqual(prediction["triggers"], ["clarify_required"])

    def test_secondary_intent_above_threshold_adds_modules(self) -> None:
        response = jev_response(
            "release", 0.92, {"release": 0.98, "bug_fix": 0.85}, clarify=0.2
        )
        prediction = jev_predict.interpret_response(
            self.case("release-after-bugfix"), response, self.dataset
        )
        self.assertEqual(prediction["intents"], ["bug_fix", "release"])
        self.assertEqual(prediction["modules"], ["bugfix", "code", "release"])
        self.assertFalse(prediction["must_clarify"])

    def test_borderline_secondary_is_excluded(self) -> None:
        response = jev_response(
            "release", 0.92, {"release": 0.98, "bug_fix": 0.76}, clarify=0.2
        )
        prediction = jev_predict.interpret_response(
            self.case("release-after-bugfix"), response, self.dataset
        )
        self.assertEqual(prediction["intents"], ["release"])
        self.assertEqual(prediction["modules"], ["release"])

    def test_answer_only_is_dropped_when_action_intent_is_selected(self) -> None:
        response = jev_response(
            "answer_only", 0.9, {"answer_only": 0.9, "code_task": 0.9}, clarify=0.1
        )
        prediction = jev_predict.interpret_response(
            self.case("ambiguous-review-login"), response, self.dataset
        )
        self.assertEqual(prediction["intents"], ["code_task"])
        self.assertEqual(prediction["modules"], ["code"])

    def test_low_primary_confidence_clarifies(self) -> None:
        response = jev_response("code_task", 0.4, {"code_task": 0.6}, clarify=0.2)
        prediction = jev_predict.interpret_response(
            self.case("code-rename-slugify"), response, self.dataset
        )
        self.assertTrue(prediction["must_clarify"])
        self.assertEqual(prediction["modules"], [])
        self.assertEqual(prediction["intents"], ["code_task"])

    def test_cli_without_api_key_fails_before_network(self) -> None:
        env = {key: value for key, value in os.environ.items() if key != "TYPESAFE_API_KEY"}
        result = subprocess.run(
            [sys.executable, str(JEV_PATH), "--limit", "1"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("TYPESAFE_API_KEY 未设置", result.stderr)


if __name__ == "__main__":
    unittest.main()
