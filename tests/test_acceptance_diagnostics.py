"""Acceptance 失败诊断：缺项、期望/实际与 pending 摘要。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class AcceptanceDiagnosticsTest(HarnessTestBase):
    def test_acceptance_settle_mismatch_reports_pending_criteria(self) -> None:
        target_input = self.write_json("inputs/pending-target.json", self.acceptance_target())
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/pending.json",
        )
        payload = self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/pending.json", "--status", "passed",
            expected=1,
        )
        self.assertEqual(payload["code"], "acceptance_settle_mismatch")
        self.assertEqual(payload["details"]["pending_criteria"], ["flow.result"])
        self.assertIn("acceptance record", payload["next_action"])

    def test_acceptance_record_mismatch_reports_expected_and_actual(self) -> None:
        target_input = self.write_json("inputs/layer-target.json", self.acceptance_target())
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/layer.json",
        )
        (self.project / "runtime.log").write_text("passed\n", encoding="utf-8")
        record = self.write_json(
            "inputs/layer-mismatch.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "behavior_acceptance",
                "status": "passed",
                "layer": "L3",
                "evidence_layer": "local_runtime",
                "method": "本地运行态验证",
                "evidence_refs": ["runtime.log"],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/layer.json", expected=1,
        )
        self.assertEqual(payload["code"], "acceptance_record_mismatch")
        self.assertEqual(payload["details"]["field"], "layer")
        self.assertEqual(payload["details"]["expected"], "L2")
        self.assertEqual(payload["details"]["actual"], "L3")
        self.assertIn("layer", payload["next_action"])

    def test_acceptance_list_includes_pending_summary(self) -> None:
        target_input = self.write_json("inputs/list-target.json", self.acceptance_target())
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/list.json",
        )
        payload = self.run_cli("acceptance", "list", "--target", str(self.project))
        item = next(item for item in payload["items"] if item["asset_ref"].endswith("list.json"))
        self.assertEqual(item["criteria_total"], 1)
        self.assertEqual(item["criteria_pending"], 1)
        self.assertEqual(item["pending_criteria"], ["flow.result"])


if __name__ == "__main__":
    unittest.main()
