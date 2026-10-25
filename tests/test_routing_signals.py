"""缓存绕过信号的独立合同测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import ROOT  # noqa: E402

sys.path.insert(0, str(ROOT / "routing" / "hosts" / "qoder"))

from route_signals import cache_bypass_reason  # noqa: E402

PLAN = {"intents": ["plan_decision"]}
CODE = {"intents": ["code_task"]}


class CacheBypassSignalTest(unittest.TestCase):
    def test_plan_cache_yields_to_execution_task(self) -> None:
        self.assertEqual(
            cache_bypass_reason("现在重启本地联调", PLAN),
            "plan_task_switch",
        )

    def test_plan_cache_yields_to_read_only_question(self) -> None:
        self.assertEqual(
            cache_bypass_reason("pptSlidesPanel 目前是开的还是关的", PLAN),
            "plan_task_switch",
        )

    def test_plan_cache_yields_to_bug_report(self) -> None:
        self.assertEqual(
            cache_bypass_reason("报错了", PLAN),
            "plan_task_switch",
        )

    def test_plan_cache_survives_design_continuation(self) -> None:
        self.assertIsNone(
            cache_bypass_reason(
                "这个已实现的功能依然保持关闭，继续按这个方向",
                PLAN,
            )
        )

    def test_code_cache_survives_bug_report(self) -> None:
        self.assertIsNone(cache_bypass_reason("报错了", CODE))

    def test_code_cache_survives_normal_followup(self) -> None:
        self.assertIsNone(cache_bypass_reason("继续把这个契约文案改短", CODE))

    def test_ack_does_not_bypass_plan_cache(self) -> None:
        self.assertIsNone(cache_bypass_reason("好，对的", PLAN))

    def test_invalid_cached_profile_is_ignored(self) -> None:
        self.assertIsNone(cache_bypass_reason("继续", {}))


if __name__ == "__main__":
    unittest.main()
