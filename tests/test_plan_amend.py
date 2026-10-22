"""Plan amend 受控修订。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase  # noqa: E402


class PlanAmendTest(HarnessTestBase):
    def test_plan_amend_updates_frozen_content_and_amend_log(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "full", "--profile", "general",
        )
        content = {item["id"]: f"初稿 {item['label']}" for item in selection["fields"]}
        content.update(
            {
                "title": "Amend 测试方案",
                "key_symbols": ["plan_amend", "apply_plan_amend"],
                "acceptance_required": False,
                "knowledge_impact": "unchanged",
            }
        )
        selection_path = self.write_json("amend-selection.json", selection)
        content_path = self.write_json("amend-content.json", content)
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/amend-test.json",
        )
        before = json.loads((self.project / "docs/plans/amend-test.json").read_text(encoding="utf-8"))
        revised = dict(content)
        revised["objective"] = "修订后的目标"
        revised_path = self.write_json("amend-revised.json", revised)
        payload = self.run_cli(
            "plan", "amend", "--target", str(self.project),
            "--plan", "docs/plans/amend-test.json",
            "--content", str(revised_path),
            "--reason", "实测后修正目标表述",
        )
        self.assertEqual(payload["status"], "amended")
        self.assertNotEqual(payload["plan_fingerprint"], before["plan_fingerprint"])
        after = json.loads((self.project / "docs/plans/amend-test.json").read_text(encoding="utf-8"))
        self.assertEqual(after["content"]["objective"], "修订后的目标")
        self.assertEqual(after["frozen_at"], before["frozen_at"])
        log = after["governance"]["amend_log"]
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["reason"], "实测后修正目标表述")
        self.assertEqual(log[0]["fingerprint_before"], before["plan_fingerprint"])
        md = (self.project / "docs/plans/amend-test.md").read_text(encoding="utf-8")
        self.assertIn("最近修订", md)
        self.assertIn("修订后的目标", md)

    def test_plan_amend_can_change_governance_with_reason(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "full", "--profile", "general",
        )
        content = {item["id"]: f"初稿 {item['label']}" for item in selection["fields"]}
        content.update(
            {
                "title": "治理修订方案",
                "key_symbols": ["GovernanceAmend", "apply_plan_amend"],
                "acceptance_required": False,
                "knowledge_impact": "unchanged",
            }
        )
        selection_path = self.write_json("governance-selection.json", selection)
        content_path = self.write_json("governance-content.json", content)
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/governance-amend.json",
        )
        revised = dict(content)
        revised["acceptance_required"] = True
        revised["knowledge_impact"] = "updated"
        revised_path = self.write_json("governance-revised.json", revised)
        payload = self.run_cli(
            "plan", "amend", "--target", str(self.project),
            "--plan", "docs/plans/governance-amend.json",
            "--content", str(revised_path),
            "--reason", "实施后发现需要验收与知识沉淀",
        )
        self.assertEqual(payload["status"], "amended")
        after = json.loads(
            (self.project / "docs/plans/governance-amend.json").read_text(encoding="utf-8")
        )
        self.assertTrue(after["governance"]["acceptance_required"])
        self.assertEqual(after["governance"]["knowledge_impact"], "updated")
        self.assertEqual(after["governance"]["updated_knowledge_refs"], [])
        self.assertIsNone(after["governance"]["unchanged_reason"])
        self.assertEqual(after["governance"]["amend_log"][0]["reason"], "实施后发现需要验收与知识沉淀")

    def test_plan_amend_patch_and_dry_run(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        content = {
            "title": "Patch Amend",
            "key_symbols": ["PatchAmend", "plan_amend"],
            "objective": "旧目标",
            "scope": "范围",
            "steps": "步骤",
            "acceptance": "验收",
        }
        selection_path = self.write_json("patch-selection.json", selection)
        content_path = self.write_json("patch-content.json", content)
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/patch-amend.json",
        )
        patch_path = self.write_json("patch.json", {"objective": "新目标"})
        dry = self.run_cli(
            "plan", "amend", "--target", str(self.project),
            "--plan", "docs/plans/patch-amend.json",
            "--patch", str(patch_path), "--reason", "只改目标", "--dry-run",
        )
        self.assertEqual(dry["status"], "dry_run_valid")
        before = json.loads((self.project / "docs/plans/patch-amend.json").read_text(encoding="utf-8"))
        self.assertEqual(before["content"]["objective"], "旧目标")
        applied = self.run_cli(
            "plan", "amend", "--target", str(self.project),
            "--plan", "docs/plans/patch-amend.json",
            "--patch", str(patch_path), "--reason", "只改目标",
        )
        self.assertEqual(applied["status"], "amended")
        self.assertEqual(applied["mode"], "patch")
        after = json.loads((self.project / "docs/plans/patch-amend.json").read_text(encoding="utf-8"))
        self.assertEqual(after["content"]["objective"], "新目标")

    def test_plan_amend_rejects_empty_reason_and_settled_plan(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        content = {
            "title": "Brief Amend",
            "key_symbols": ["BriefAmend", "plan_amend"],
            "objective": "目标",
            "scope": "范围",
            "steps": "步骤",
            "acceptance": "验收",
        }
        selection_path = self.write_json("brief-selection.json", selection)
        content_path = self.write_json("brief-content.json", content)
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/brief-amend.json",
        )
        self.run_cli(
            "plan", "amend", "--target", str(self.project),
            "--plan", "docs/plans/brief-amend.json",
            "--content", str(content_path),
            "--reason", "   ", expected=2,
        )
        self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/brief-amend.json", "--status", "implemented",
        )
        self.run_cli(
            "plan", "amend", "--target", str(self.project),
            "--plan", "docs/plans/brief-amend.json",
            "--content", str(content_path),
            "--reason", "不应成功", expected=2,
        )


if __name__ == "__main__":
    unittest.main()
