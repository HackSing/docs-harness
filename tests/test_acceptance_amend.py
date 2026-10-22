"""Acceptance 未关联记录与 amend 行为。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class AcceptanceAmendTest(HarnessTestBase):
    def test_acceptance_amend_dry_run_does_not_write(self) -> None:
        target = self.acceptance_target("contract_check")
        target_input = self.write_json("inputs/dry-amend-target.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/dry-amend.json",
        )
        revised = self.acceptance_target("contract_check")
        revised["title"] = "修订后的标题"
        revised_input = self.write_json("inputs/dry-amend-revised.json", revised)
        payload = self.run_cli(
            "acceptance", "amend", "--target", str(self.project),
            "--acceptance", "docs/acceptance/dry-amend.json",
            "--input", str(revised_input.relative_to(self.project)),
            "--reason", "预检", "--dry-run",
        )
        self.assertEqual(payload["status"], "dry_run_valid")
        self.assertEqual(payload["writes"], "none")
        asset = json.loads(
            (self.project / "docs/acceptance/dry-amend.json").read_text(encoding="utf-8")
        )
        self.assertEqual(asset["revision"], 1)
        self.assertEqual(asset["title"], "功能流程验收")

    def test_acceptance_record_dry_run_does_not_write(self) -> None:
        target = self.acceptance_target("contract_check")
        target_input = self.write_json("inputs/dry-record-target.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/dry-record.json",
        )
        evidence = self.project / "dry-record.txt"
        evidence.write_text("passed\n", encoding="utf-8")
        record = self.write_json(
            "inputs/dry-record.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "method": "检查合同",
                "evidence_refs": ["dry-record.txt"],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/dry-record.json", "--dry-run",
        )
        self.assertEqual(payload["status"], "dry_run_valid")
        asset = json.loads(
            (self.project / "docs/acceptance/dry-record.json").read_text(encoding="utf-8")
        )
        self.assertEqual(asset["revision"], 1)
        self.assertEqual(asset["criteria"][0]["records"], [])

    def test_acceptance_settle_dry_run_does_not_write(self) -> None:
        target = self.acceptance_target("contract_check")
        target_input = self.write_json("inputs/dry-settle-target.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/dry-settle.json",
        )
        evidence = self.project / "dry-settle.txt"
        evidence.write_text("passed\n", encoding="utf-8")
        record = self.write_json(
            "inputs/dry-settle-record.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "method": "检查合同",
                "evidence_refs": ["dry-settle.txt"],
            },
        )
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/dry-settle.json",
        )
        payload = self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/dry-settle.json",
            "--status", "passed", "--dry-run",
        )
        self.assertEqual(payload["status"], "dry_run_valid")
        asset = json.loads(
            (self.project / "docs/acceptance/dry-settle.json").read_text(encoding="utf-8")
        )
        self.assertIsNone(asset["settled_at"])

    def test_unlinked_record_with_criterion_is_rejected(self) -> None:
        evidence = self.project / "unlinked-evidence.txt"
        evidence.write_text("passed\n", encoding="utf-8")
        record = self.write_json(
            "unlinked-record.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "验证未关联记录",
                "criterion_id": "flow.result",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "method": "检查证据",
                "evidence_refs": ["unlinked-evidence.txt"],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record), expected=2,
        )
        self.assertEqual(payload["code"], "acceptance_link_required")
        self.assertIn("--acceptance", payload["message"])
    def test_unlinked_record_without_criterion_is_marked_runtime_only(self) -> None:
        evidence = self.project / "runtime-evidence.txt"
        evidence.write_text("passed\n", encoding="utf-8")
        record = self.write_json(
            "runtime-record.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "验证独立记录",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "method": "检查证据",
                "evidence_refs": ["runtime-evidence.txt"],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record),
        )
        self.assertEqual(payload["persisted_to"], "runtime")
        self.assertFalse(payload["linked"])
        self.assertIn("不进入 docs/acceptance", payload["warning"])
    def test_acceptance_amend_revises_pending_criteria_and_rejects_recorded(self) -> None:
        target = self.acceptance_target("contract_check")
        target_input = self.write_json("inputs/amend-target.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/amend.json",
        )
        revised = self.acceptance_target("contract_check")
        revised["criteria"].append(
            {
                "id": "flow.second",
                "title": "第二条合同检查",
                "acceptance_type": "contract_check",
                "layer": "L1",
            }
        )
        revised_input = self.write_json("inputs/amend-revised.json", revised)
        amended = self.run_cli(
            "acceptance", "amend", "--target", str(self.project),
            "--acceptance", "docs/acceptance/amend.json",
            "--input", str(revised_input.relative_to(self.project)),
            "--reason", "补充第二条验收标准",
        )
        self.assertEqual(amended["status"], "amended")
        self.assertEqual(amended["revision"], 2)
        self.assertEqual(amended["criteria"], 2)
        evidence = self.project / "amend-evidence.txt"
        evidence.write_text("passed\n", encoding="utf-8")
        record = self.write_json(
            "inputs/amend-record.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "method": "检查合同",
                "evidence_refs": ["amend-evidence.txt"],
            },
        )
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/amend.json", expected=3,
        )
        rejected = self.run_cli(
            "acceptance", "amend", "--target", str(self.project),
            "--acceptance", "docs/acceptance/amend.json",
            "--input", str(revised_input.relative_to(self.project)),
            "--reason", "已有记录后不应修改",
            expected=1,
        )
        self.assertEqual(rejected["code"], "acceptance_amend_recorded")


if __name__ == "__main__":
    unittest.main()
