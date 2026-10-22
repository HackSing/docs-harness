"""只读 show/list 查询面。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class ShowListTest(HarnessTestBase):
    def test_knowledge_show(self) -> None:
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True)
        source.write_text("KnowledgeOwner owns the runtime.\n", encoding="utf-8")
        value = self.write_json("inputs/show-knowledge.json", self.knowledge_input("展示知识", "KnowledgeOwner 拥有运行时。"))
        self.run_cli(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(value.relative_to(self.project)),
            "--output", "docs/knowledge/show.json",
        )
        shown = self.run_cli(
            "knowledge", "show", "--target", str(self.project),
            "--knowledge", "docs/knowledge/show.json",
        )
        self.assertEqual(shown["status"], "shown")
        self.assertEqual(shown["kind"], "knowledge")
        self.assertEqual(shown["asset"]["title"], "展示知识")
        self.assertEqual(shown["asset"]["facts"][0]["id"], "runtime.owner")

    def test_acceptance_show_and_list(self) -> None:
        target = self.write_json("inputs/show-acceptance.json", self.acceptance_target("contract_check"))
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target.relative_to(self.project)),
            "--output", "docs/acceptance/show.json",
        )
        shown = self.run_cli(
            "acceptance", "show", "--target", str(self.project),
            "--acceptance", "docs/acceptance/show.json",
        )
        self.assertEqual(shown["asset"]["status"], "pending")
        self.assertEqual(len(shown["asset"]["criteria"]), 1)
        listed = self.run_cli("acceptance", "list", "--target", str(self.project))
        self.assertEqual(listed["kind"], "acceptance")
        self.assertTrue(
            any(item["asset_ref"] == "docs/acceptance/show.json" for item in listed["items"]),
            listed["items"],
        )

    def test_adr_show(self) -> None:
        value = self.write_json(
            "inputs/show-adr.json",
            {
                "schema_version": "docs-harness/adr-input/v1",
                "title": "展示决策",
                "key_symbols": ["ADR_SPEC", "adr_create"],
                "context": "背景",
                "decision": "采用只读查询。",
                "consequences": "影响",
            },
        )
        self.run_cli(
            "adr", "create", "--target", str(self.project),
            "--input", str(value.relative_to(self.project)),
            "--output", "docs/adr/show.json",
        )
        shown = self.run_cli(
            "adr", "show", "--target", str(self.project), "--adr", "docs/adr/show.json",
        )
        self.assertEqual(shown["asset"]["title"], "展示决策")
        self.assertEqual(shown["asset"]["decision"], "采用只读查询。")

    def test_plan_show_and_list(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project), "--level", "brief",
        )
        selection_path = self.write_json("inputs/show-plan-selection.json", selection)
        content_path = self.write_json(
            "inputs/show-plan-content.json",
            {
                "title": "展示方案",
                "key_symbols": ["ShowPlan", "plan_list"],
                "objective": "目标",
                "scope": "范围",
                "steps": "步骤",
                "acceptance": "验收",
            },
        )
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path.relative_to(self.project)),
            "--content", str(content_path.relative_to(self.project)),
            "--output", "docs/plans/show.json",
        )
        shown = self.run_cli(
            "plan", "show", "--target", str(self.project), "--plan", "docs/plans/show.json",
        )
        self.assertEqual(shown["plan_status"], "active")
        listed = self.run_cli("plan", "list", "--target", str(self.project))
        self.assertTrue(
            any(item.get("plan_ref") == "docs/plans/show.json" for item in listed["items"]),
            listed["items"],
        )
        self.assertTrue(
            any(item.get("title") == "展示方案" for item in listed["items"]),
            listed["items"],
        )


if __name__ == "__main__":
    unittest.main()
