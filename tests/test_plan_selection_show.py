"""Plan 选择合同、plan show 与 INDEX 投影检查。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class PlanSelectionShowTest(HarnessTestBase):
    def test_plan_select_contract_fingerprint_is_stable_across_equivalent_flags(self) -> None:
        by_complexity = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--complexity", "complex", "--surface", "architecture",
        )
        by_level = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "full", "--profile", "architecture",
        )
        self.assertEqual(by_complexity["plan_level"], "full")
        self.assertEqual(by_complexity["plan_profile"], "architecture")
        self.assertEqual(
            by_complexity["contract_fingerprint"],
            by_level["contract_fingerprint"],
        )
        self.assertNotEqual(
            by_complexity["selection_fingerprint"],
            by_level["selection_fingerprint"],
        )
        self.assertIn("architecture_acceptance", by_complexity["content_template"])
        self.assertEqual(by_complexity["content_template"]["key_symbols"], [])
    def test_plan_create_accepts_direct_level_and_profile(self) -> None:
        content = {
            "title": "直接选择方案",
            "key_symbols": ["DirectSelection", "plan_create"],
            "objective": "验证无 selection 文件也能创建方案",
            "scope": ["scripts/harness.py"],
            "steps": ["选择", "创建", "核对"],
            "acceptance": ["聚焦测试通过"],
        }
        content_path = self.write_json("direct-content.json", content)
        payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--level", "brief", "--profile", "frontend_ui",
            "--content", str(content_path),
            "--output", "docs/plans/direct-selection.json",
        )
        self.assertEqual(payload["status"], "frozen")
        self.assertEqual(payload["selection_source"], "direct")
        self.assertTrue(payload["selection_ref"].startswith("sha256:"))
        frozen = json.loads(
            (self.project / "docs/plans/direct-selection.json").read_text(encoding="utf-8")
        )
        self.assertEqual(frozen["plan_level"], "brief")
        self.assertEqual(frozen["plan_profile"], "frontend_ui")
    def test_plan_show_returns_frozen_content_and_full_projection(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "full", "--profile", "general",
        )
        content = {item["id"]: f"已填写 {item['label']}" for item in selection["fields"]}
        content.update(
            {
                "title": "Show 测试方案",
                "key_symbols": ["PlanShow", "execution_projection"],
                "acceptance_required": False,
                "knowledge_impact": "unchanged",
            }
        )
        selection_path = self.write_json("show-selection.json", selection)
        content_path = self.write_json("show-content.json", content)
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/show-test.json",
        )
        shown = self.run_cli(
            "plan", "show", "--target", str(self.project),
            "--plan", "docs/plans/show-test.json",
        )
        self.assertEqual(shown["status"], "shown")
        self.assertEqual(shown["plan_status"], "active")
        self.assertEqual(shown["content"], content)
        for field_id in ("process_flowchart", "ux_journey", "module_interfaces"):
            self.assertEqual(shown["execution_projection"][field_id], content[field_id])
    def test_secondary_profile_fields_are_optional(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "full", "--profile", "frontend_ui",
            "--secondary-profile", "backend_service",
        )
        fields = {item["id"]: item for item in selection["fields"]}
        self.assertTrue(fields["state_matrix"]["required"])
        self.assertFalse(fields["api_contract"]["required"])
        content = {
            item["id"]: f"已填写 {item['label']}"
            for item in selection["fields"]
            if item["required"]
        }
        content.update(
            {
                "title": "次级 Profile 可选字段",
                "key_symbols": ["SecondaryOptional", "plan_create"],
                "acceptance_required": False,
                "knowledge_impact": "unchanged",
            }
        )
        selection_path = self.write_json("optional-selection.json", selection)
        content_path = self.write_json("optional-content.json", content)
        payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/optional-secondary.json",
        )
        self.assertEqual(payload["status"], "frozen")
        frozen = json.loads(
            (self.project / "docs/plans/optional-secondary.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("api_contract", frozen["content"])

    def test_plan_progress_suppresses_c8_symbol_warning(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "full", "--profile", "general",
        )
        content = {
            item["id"]: f"已填写 {item['label']}"
            for item in selection["fields"]
            if item.get("required")
        }
        content.update(
            {
                "title": "进度方案",
                "key_symbols": ["ProgressAlpha", "ProgressBeta"],
                "acceptance_required": False,
                "knowledge_impact": "unchanged",
                "progress": {
                    "completed_steps": ["第一步"],
                    "remaining_steps": ["第二步"],
                },
            }
        )
        selection_path = self.write_json("progress-selection.json", selection)
        content_path = self.write_json("progress-content.json", content)
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/progress.json",
        )
        source = self.project / "src" / "progress.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("ProgressAlpha = 1\nProgressBeta = 2\n", encoding="utf-8")
        payload = self.run_cli("plan", "check", "--target", str(self.project))
        self.assertFalse(
            any("已全部在源码命中" in item for item in payload["warnings"]),
            payload["warnings"],
        )

    def test_plan_check_warns_when_index_status_drifts(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project), "--apply")
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project), "--level", "brief",
        )
        selection_path = self.write_json("inputs/index-drift-selection.json", selection)
        content_path = self.write_json("inputs/index-drift-content.json", {
            "title": "索引漂移方案",
            "key_symbols": ["IndexDriftAlpha", "IndexDriftBeta"],
            "objective": "目标",
            "scope": "范围",
            "steps": "步骤",
            "acceptance": "验收",
        })
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path.relative_to(self.project)),
            "--content", str(content_path.relative_to(self.project)),
            "--output", "docs/plans/index-drift.json",
        )
        index_path = self.project / "docs/INDEX.md"
        index_path.write_text(
            index_path.read_text(encoding="utf-8").replace(
                "plans/index-drift.md) — 状态：有效（实施中）",
                "plans/index-drift.md) — 状态：已实施-仅追溯（代码已是真源，2026-01-01 核对）",
            ),
            encoding="utf-8",
        )
        payload = self.run_cli("plan", "check", "--target", str(self.project))
        self.assertTrue(
            any("INDEX 状态" in item and "不一致" in item for item in payload["warnings"]),
            payload["warnings"],
        )



if __name__ == "__main__":
    unittest.main()
