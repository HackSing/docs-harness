"""意图路由注册表、profile schema 与纯校验函数的合同测试。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harness_test_base import ROOT  # noqa: E402

import routing_contract as rc  # noqa: E402

REGISTRY_PATH = ROOT / "routing" / "registry.json"
EVAL_DIR = ROOT / "evals" / "intent_routing"


def eval_datasets() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (
            EVAL_DIR / "cases.json",
            EVAL_DIR / "held_out_cases.json",
            EVAL_DIR / "held_out_cases_2.json",
        )
    ]


def payload() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def sealed(value: dict) -> dict:
    value["fingerprint"] = rc.registry_fingerprint(value)
    return value


def write_registry(directory: Path, value: dict) -> Path:
    path = directory / "registry.json"
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def profile(**overrides: object) -> dict:
    value = {
        "intents": ["code_task"],
        "triggers": ["code_edit"],
        "must_clarify": False,
        "confidence": 0.95,
    }
    value.update(overrides)
    return value


class RegistryContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = rc.load_registry(REGISTRY_PATH)

    def test_taxonomy_matches_all_eval_datasets(self) -> None:
        for dataset in eval_datasets():
            with self.subTest(dataset=dataset.get("dataset_version")):
                self.assertEqual(sorted(self.registry.intents), sorted(dataset["labels"]["intents"]))
                self.assertEqual(sorted(self.registry.modules), sorted(dataset["labels"]["modules"]))
                self.assertEqual(sorted(self.registry.triggers), sorted(dataset["labels"]["triggers"]))
                expected = {
                    intent: sorted(modules)
                    for intent, modules in self.registry.intent_modules.items()
                }
                self.assertEqual(
                    expected,
                    {
                        intent: sorted(modules)
                        for intent, modules in dataset["intent_modules"].items()
                    },
                )

    def test_v1_taxonomy_size_and_contract_coverage(self) -> None:
        self.assertEqual(len(self.registry.intents), 7)
        self.assertEqual(len(self.registry.modules), 6)
        self.assertEqual(len(self.registry.triggers), 10)
        self.assertEqual(set(self.registry.contracts), set(self.registry.modules))
        self.assertTrue(self.registry.kernel_contract["rules"])
        self.assertEqual(
            sorted(self.registry.module_order), sorted(self.registry.modules)
        )
        self.assertLess(
            self.registry.module_order.index("plan"),
            self.registry.module_order.index("code"),
        )

    def test_fingerprint_is_stable(self) -> None:
        value = payload()
        self.assertEqual(rc.registry_fingerprint(value), value["fingerprint"])

    def test_manual_edit_without_reseal_is_rejected(self) -> None:
        value = payload()
        value["contracts"]["code"]["rules"][0] = "被手工改写的规则"
        with tempfile.TemporaryDirectory() as tmp:
            path = write_registry(Path(tmp), value)
            with self.assertRaises(rc.RoutingContractError) as caught:
                rc.load_registry(path)
        self.assertEqual(caught.exception.code, "registry_fingerprint_mismatch")

    def test_resealed_edit_is_accepted(self) -> None:
        value = payload()
        value["contracts"]["code"]["rules"][0] = "合法的受控修订"
        sealed(value)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_registry(Path(tmp), value)
            loaded = rc.load_registry(path)
        self.assertEqual(loaded.contracts["code"]["rules"][0], "合法的受控修订")

    def test_unknown_mapped_module_is_rejected(self) -> None:
        value = payload()
        value["intent_modules"]["code_task"] = ["nope"]
        sealed(value)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_registry(Path(tmp), value)
            with self.assertRaises(rc.RoutingContractError) as caught:
                rc.load_registry(path)
        self.assertEqual(caught.exception.code, "registry_module_unknown")

    def test_missing_fingerprint_is_rejected(self) -> None:
        value = payload()
        value.pop("fingerprint")
        with tempfile.TemporaryDirectory() as tmp:
            path = write_registry(Path(tmp), value)
            with self.assertRaises(rc.RoutingContractError) as caught:
                rc.load_registry(path)
        self.assertEqual(caught.exception.code, "registry_fingerprint_missing")

    def test_unreadable_and_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            with self.assertRaises(rc.RoutingContractError) as caught:
                rc.load_registry(missing)
            self.assertEqual(caught.exception.code, "registry_unreadable")
            broken = Path(tmp) / "broken.json"
            broken.write_text("{", encoding="utf-8")
            with self.assertRaises(rc.RoutingContractError) as caught:
                rc.load_registry(broken)
            self.assertEqual(caught.exception.code, "registry_invalid_json")

    def test_profile_schema_uses_registry_labels(self) -> None:
        schema = rc.profile_schema(self.registry)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            sorted(schema["properties"]["intents"]["items"]["enum"]),
            sorted(self.registry.intents),
        )
        self.assertEqual(
            sorted(schema["properties"]["modules"]["items"]["enum"]),
            sorted(self.registry.modules),
        )
        self.assertEqual(
            sorted(schema["properties"]["triggers"]["items"]["enum"]),
            sorted(self.registry.triggers),
        )


class ProfileValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = rc.load_registry(REGISTRY_PATH)

    def validate(self, value: dict) -> rc.ValidationResult:
        return rc.validate_profile(value, self.registry)

    def codes(self, result: rc.ValidationResult) -> set[str]:
        return {issue.code for issue in result.errors}

    def test_code_task_resolves_code(self) -> None:
        result = self.validate(profile())
        self.assertTrue(result.ok)
        self.assertEqual(result.modules, ("code",))
        self.assertFalse(result.effective_clarify)

    def test_bug_fix_resolves_code_and_bugfix(self) -> None:
        result = self.validate(
            profile(intents=["bug_fix"], triggers=["bug_report"])
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.modules, ("bugfix", "code"))

    def test_answer_only_derives_read_only_and_no_modules(self) -> None:
        result = self.validate(
            profile(intents=["answer_only"], triggers=[])
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.modules, ())
        self.assertIn("read_only", result.profile["triggers"])

    def test_plan_and_code_coexist_with_plan_first(self) -> None:
        result = self.validate(
            profile(
                intents=["plan_decision", "code_task"],
                triggers=["plan_required", "code_edit"],
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.modules, ("code", "plan"))
        self.assertIn("plan_required", result.profile["triggers"])
        self.assertIn("code_edit", result.profile["triggers"])

    def test_answer_only_conflict_is_rejected(self) -> None:
        result = self.validate(
            profile(intents=["answer_only", "code_task"], triggers=["read_only", "code_edit"])
        )
        self.assertFalse(result.ok)
        self.assertIn("answer_only_conflict", self.codes(result))

    def test_unknown_and_duplicate_labels_are_collected(self) -> None:
        result = self.validate(
            profile(
                intents=["code_task", "code_task", "nope"],
                modules=["code", "code", "nope"],
                triggers=["code_edit", "code_edit", "nope"],
            )
        )
        self.assertFalse(result.ok)
        self.assertTrue({"duplicate_intent", "unknown_intent"} <= self.codes(result))
        self.assertTrue({"duplicate_module", "unknown_module"} <= self.codes(result))
        self.assertTrue({"duplicate_trigger", "unknown_trigger"} <= self.codes(result))

    def test_unknown_profile_field_is_rejected(self) -> None:
        value = profile()
        value["prompt"] = "不应进入路由合同"
        result = self.validate(value)
        self.assertFalse(result.ok)
        self.assertIn("unknown_profile_field", self.codes(result))

    def test_candidate_modules_must_stay_in_closure(self) -> None:
        extra = self.validate(profile(modules=["code", "plan"]))
        self.assertFalse(extra.ok)
        self.assertIn("module_not_implied_by_intent", self.codes(extra))
        subset = self.validate(profile(intents=["bug_fix"], triggers=["bug_report"], modules=["code"]))
        self.assertTrue(subset.ok)
        self.assertIn("candidate_modules_incomplete", {w.code for w in subset.warnings})
        self.assertEqual(subset.modules, ("bugfix", "code"))

    def test_explicit_clarify_requires_empty_modules_and_trigger(self) -> None:
        with_modules = self.validate(
            profile(intents=["code_task"], modules=["code"], must_clarify=True, triggers=["clarify_required"], confidence=0.9)
        )
        self.assertFalse(with_modules.ok)
        self.assertIn("clarify_with_modules", self.codes(with_modules))
        extra_trigger = self.validate(
            profile(intents=[], must_clarify=True, triggers=["clarify_required", "read_only"], confidence=0.9)
        )
        self.assertFalse(extra_trigger.ok)
        self.assertIn("clarify_trigger_mismatch", self.codes(extra_trigger))

    def test_low_confidence_is_downgraded_to_clarify(self) -> None:
        result = self.validate(profile(confidence=0.2))
        self.assertTrue(result.ok)
        self.assertTrue(result.effective_clarify)
        self.assertEqual(result.modules, ())
        self.assertEqual(result.profile["triggers"], ["clarify_required"])
        self.assertIn("low_confidence_clarify", {w.code for w in result.warnings})

    def test_trigger_conflicts_are_rejected(self) -> None:
        result = self.validate(
            profile(intents=["answer_only"], triggers=["read_only", "release"])
        )
        self.assertFalse(result.ok)
        self.assertIn("trigger_conflict", self.codes(result))

    def test_code_task_without_edit_or_verify_warns(self) -> None:
        result = self.validate(profile(triggers=[]))
        self.assertTrue(result.ok)
        self.assertIn("code_task_trigger_missing", {w.code for w in result.warnings})

    def test_invalid_types_are_rejected(self) -> None:
        result = self.validate(
            {
                "intents": "code_task",
                "modules": "code",
                "triggers": {"code_edit": True},
                "must_clarify": "false",
                "confidence": True,
            }
        )
        self.assertFalse(result.ok)
        self.assertTrue(
            {"invalid_intent_list", "invalid_module_list", "invalid_trigger_list",
             "invalid_must_clarify", "invalid_confidence"} <= self.codes(result)
        )

    def test_result_is_json_serializable(self) -> None:
        result = self.validate(profile())
        encoded = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertIn("registry_fingerprint", encoded)

    def test_resolve_modules_matches_validation(self) -> None:
        self.assertEqual(rc.resolve_modules(profile(), self.registry), ("code",))
        self.assertEqual(
            rc.resolve_modules(
                profile(intents=["bug_fix"], triggers=["bug_report"]), self.registry
            ),
            ("bugfix", "code"),
        )
        self.assertEqual(
            rc.resolve_modules(profile(confidence=0.1), self.registry), ()
        )
        self.assertEqual(
            rc.resolve_modules(
                profile(intents=[], must_clarify=True, confidence=0.9), self.registry
            ),
            (),
        )

    def test_resolve_modules_rejects_invalid_input(self) -> None:
        with self.assertRaises(rc.RoutingContractError):
            rc.resolve_modules(profile(intents=["nope"]), self.registry)
        with self.assertRaises(rc.RoutingContractError):
            rc.resolve_modules({"intents": ["code_task"], "must_clarify": False}, self.registry)

    def test_direct_override_detection(self) -> None:
        for text in (
            "这次不使用 Harness，直接改",
            "不用 harness 了",
            "Do not use harness for this",
            "在不使用Harness的前提下完成",
        ):
            with self.subTest(text=text):
                self.assertTrue(rc.direct_override_requested(text, self.registry))
        self.assertFalse(rc.direct_override_requested("按 Harness 流程走", self.registry))


if __name__ == "__main__":
    unittest.main()
