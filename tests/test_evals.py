"""evals/evals.json 登记表的机械校验。

cli 用例：covered_by 中每个测试 id 必须能被 unittest 解析成真实测试；
behavior 用例：scenario/rubric 完整，rubric 键集合与 expected 一一对应。
behavior 用例的实际运行方式见 docs/testing.md「行为用例（evals behavior）手动运行」。
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals" / "evals.json"
SCHEMA_VERSION = "docs-harness/evals/v3"
KINDS = {"cli", "behavior"}
# 与 scripts/harness.py update_json_version 同口径：发版同步要求顶层 version 行恰好一处。
VERSION_LINE = re.compile(r'(?m)^[ \t]*"version"[ \t]*:[ \t]*"[0-9]+\.[0-9]+\.[0-9]+"')


def load_evals() -> dict:
    return json.loads(EVALS.read_text(encoding="utf-8"))


def count_resolved_tests(suite: unittest.TestSuite) -> tuple[int, list[str]]:
    """返回 (真实测试数, 加载失败描述)；_FailedTest 等加载失败占位不计为测试。"""
    count = 0
    failures: list[str] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            nested_count, nested_failures = count_resolved_tests(item)
            count += nested_count
            failures.extend(nested_failures)
        elif type(item).__name__ in {"_FailedTest", "ModuleImportFailure", "LoadTestsFailure"}:
            failures.append(item.id())
        else:
            count += 1
    return count, failures


class EvalsRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.evals = load_evals()
        self.cases = self.evals["cases"]

    def test_schema_version_and_single_release_version_line(self) -> None:
        self.assertEqual(self.evals["schema_version"], SCHEMA_VERSION)
        self.assertIsInstance(self.evals["version"], str)
        self.assertEqual(len(VERSION_LINE.findall(EVALS.read_text(encoding="utf-8"))), 1)

    def test_case_ids_unique_and_kind_known(self) -> None:
        ids = [case["id"] for case in self.cases]
        self.assertEqual(len(ids), len(set(ids)), "用例 id 重复")
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertIn(case.get("kind"), KINDS)
                expected = case.get("expected")
                self.assertIsInstance(expected, list)
                self.assertTrue(expected)
                self.assertEqual(len(expected), len(set(expected)), "expected 标签重复")

    def test_cli_cases_reference_resolvable_tests(self) -> None:
        loader = unittest.TestLoader()
        for case in self.cases:
            if case["kind"] != "cli":
                continue
            with self.subTest(case=case["id"]):
                covered_by = case.get("covered_by")
                self.assertIsInstance(covered_by, list)
                self.assertTrue(covered_by, "cli 用例 covered_by 不能为空")
                for test_id in covered_by:
                    self.assertIsInstance(test_id, str)
                    suite = loader.loadTestsFromName(test_id)
                    count, failures = count_resolved_tests(suite)
                    self.assertEqual(failures, [], f"{test_id} 无法解析")
                    self.assertGreaterEqual(count, 1, f"{test_id} 未解析出测试")

    def test_unresolvable_test_id_is_detected(self) -> None:
        # loadTestsFromName 对不存在的属性返回 _FailedTest 而不抛错，守住识别逻辑本身。
        suite = unittest.TestLoader().loadTestsFromName(
            "tests.test_evals.EvalsRegistryTest.test_missing_on_purpose"
        )
        count, failures = count_resolved_tests(suite)
        self.assertEqual(count, 0)
        self.assertTrue(failures)

    def test_behavior_cases_have_scenario_and_matching_rubric(self) -> None:
        for case in self.cases:
            if case["kind"] != "behavior":
                continue
            with self.subTest(case=case["id"]):
                scenario = case.get("scenario")
                self.assertIsInstance(scenario, dict)
                for key in ("setup", "prompt"):
                    value = scenario.get(key)
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip(), f"scenario.{key} 为空")
                rubric = case.get("rubric")
                self.assertIsInstance(rubric, dict)
                self.assertEqual(set(rubric), set(case["expected"]))
                for label, criterion in rubric.items():
                    self.assertIsInstance(criterion, str, label)
                    self.assertTrue(criterion.strip(), f"rubric[{label}] 为空")


if __name__ == "__main__":
    unittest.main()
