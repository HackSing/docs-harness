"""Plan v3 治理：acceptance 反向登记、knowledge 结算与跨资产声明一致性。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class PlanGovernanceTest(HarnessTestBase):
    def test_plan_v3_acceptance_backref_and_governance_settlement(self) -> None:
        plan_path = self.create_full_plan(
            acceptance_required=True,
            knowledge_impact="unchanged",
        )
        frozen = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(frozen["schema_version"], "docs-harness/plan/v3")
        self.assertEqual(frozen["acceptance_refs"], [])
        self.assertTrue(frozen["governance"]["acceptance_required"])

        target = self.acceptance_target("contract_check")
        target["plan_ref"] = "docs/plans/governed.json"
        acceptance_input = self.write_json("inputs/governed-acceptance.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(acceptance_input.relative_to(self.project)),
            "--output", "docs/acceptance/governed.json",
        )
        frozen = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(frozen["acceptance_refs"], ["docs/acceptance/governed.json"])
        markdown = plan_path.with_suffix(".md").read_text(encoding="utf-8")
        self.assertIn("docs/acceptance/governed.json", markdown)

        governance_input = self.write_json(
            "inputs/governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "unchanged_reason": "本次只改变资产治理流程，不产生新的项目事实。",
            },
        )
        rejected = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/governed.json", "--status", "implemented",
            "--governance-input", str(governance_input.relative_to(self.project)),
            expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_plan_governance")
        self.assertIn("acceptance", rejected["message"])

        evidence = self.project / "contract-evidence.txt"
        evidence.write_text("contract passed\n", encoding="utf-8")
        record = self.write_json(
            "inputs/governed-record.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "method": "检查治理合同",
                "evidence_refs": ["contract-evidence.txt"],
            },
        )
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/governed.json",
        )
        self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/governed.json", "--status", "passed",
        )
        settled = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/governed.json", "--status", "implemented",
            "--governance-input", str(governance_input.relative_to(self.project)),
        )
        self.assertEqual(settled["warnings"], [])
        frozen = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertTrue(frozen["governance"]["governance_settled_at"])
        self.assertEqual(
            frozen["governance"]["unchanged_reason"],
            "本次只改变资产治理流程，不产生新的项目事实。",
        )
    def test_plan_v3_updated_knowledge_requires_active_refs(self) -> None:
        self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="updated",
            basename="knowledge-updated",
        )
        missing = self.write_json(
            "inputs/missing-knowledge-governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "updated_knowledge_refs": [],
            },
        )
        rejected = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/knowledge-updated.json", "--status", "implemented",
            "--governance-input", str(missing.relative_to(self.project)), expected=2,
        )
        self.assertIn("updated_knowledge_refs", rejected["message"])
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("KnowledgeOwner owns the runtime.\n", encoding="utf-8")
        value = self.write_json(
            "inputs/knowledge.json",
            self.knowledge_input("运行时所有权", "KnowledgeOwner 拥有运行时。"),
        )
        self.run_cli(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(value.relative_to(self.project)),
            "--output", "docs/knowledge/runtime-owner.json",
        )
        valid = self.write_json(
            "inputs/valid-knowledge-governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "updated_knowledge_refs": ["docs/knowledge/runtime-owner.json"],
            },
        )
        settled = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/knowledge-updated.json", "--status", "implemented",
            "--governance-input", str(valid.relative_to(self.project)),
        )
        self.assertEqual(settled["status"], "implemented")
    def test_plan_v3_allows_failed_terminal_acceptance_with_warning(self) -> None:
        self.create_full_plan(
            acceptance_required=True,
            knowledge_impact="unchanged",
            basename="failed-acceptance",
        )
        target = self.acceptance_target("contract_check")
        target["plan_ref"] = "docs/plans/failed-acceptance.json"
        target_input = self.write_json("inputs/failed-target.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/failed-target.json",
        )
        evidence = self.project / "failed-contract.txt"
        evidence.write_text("contract failed\n", encoding="utf-8")
        record = self.write_json(
            "inputs/failed-record.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "contract_check",
                "status": "failed",
                "layer": "L1",
                "reason": "治理合同未通过",
                "next_action": "收尾报告说明失败结果",
                "failure_attributions": [{
                    "category": "change_related",
                    "summary": "合同结果不符合预期",
                    "blocking": True,
                    "evidence_refs": ["failed-contract.txt"]
                }]
            },
        )
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/failed-target.json", expected=3,
        )
        self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/failed-target.json", "--status", "failed",
        )
        governance_input = self.write_json(
            "inputs/failed-governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "unchanged_reason": "失败验收不产生 Knowledge 更新。",
            },
        )
        settled = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/failed-acceptance.json", "--status", "implemented",
            "--governance-input", str(governance_input.relative_to(self.project)),
        )
        self.assertTrue(any("failed" in item for item in settled["warnings"]))
    def test_acceptance_supersede_removes_plan_backref(self) -> None:
        plan_path = self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="unchanged",
            basename="supersede-backref",
        )
        for name in ("old", "new"):
            target = self.acceptance_target("contract_check")
            target["plan_ref"] = "docs/plans/supersede-backref.json"
            target_input = self.write_json(f"inputs/{name}-target.json", target)
            self.run_cli(
                "acceptance", "create", "--target", str(self.project),
                "--input", str(target_input.relative_to(self.project)),
                "--output", f"docs/acceptance/{name}.json",
            )
        self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/old.json", "--status", "superseded",
            "--replacement", "docs/acceptance/new.json",
        )
        frozen = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(frozen["acceptance_refs"], ["docs/acceptance/new.json"])
    def test_assets_check_warns_when_plan_declaration_conflicts_with_refs(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="unchanged",
            basename="declaration-conflict",
        )
        target = self.acceptance_target("contract_check")
        target["plan_ref"] = "docs/plans/declaration-conflict.json"
        target_input = self.write_json("inputs/conflict-target.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/declaration-conflict.json",
        )
        payload = self.run_cli("assets-check", "--target", str(self.project), "--fast")
        self.assertTrue(any("acceptance_required=false" in item for item in payload["warnings"]))
        strict = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", "--strict",
            expected=1,
        )
        self.assertEqual(strict["status"], "failed")
    def test_assets_check_fails_when_settled_knowledge_is_archived(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="updated",
            basename="archived-knowledge",
        )
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("KnowledgeOwner owns the runtime.\n", encoding="utf-8")
        value = self.write_json(
            "inputs/archived-knowledge.json",
            self.knowledge_input("运行时所有权", "KnowledgeOwner 拥有运行时。"),
        )
        self.run_cli(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(value.relative_to(self.project)),
            "--output", "docs/knowledge/archive-me.json",
        )
        governance = self.write_json(
            "inputs/archive-governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "updated_knowledge_refs": ["docs/knowledge/archive-me.json"],
            },
        )
        self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/archived-knowledge.json", "--status", "implemented",
            "--governance-input", str(governance.relative_to(self.project)),
        )
        self.run_cli(
            "knowledge", "settle", "--target", str(self.project),
            "--knowledge", "docs/knowledge/archive-me.json", "--status", "deprecated",
        )
        payload = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", expected=1
        )
        self.assertTrue(any("结算 Knowledge" in item for item in payload["failures"]))

    def test_acceptance_supersede_unlinks_archived_plan_backref(self) -> None:
        self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="unchanged",
            basename="archived-plan",
        )
        for name in ("old", "new"):
            target = self.acceptance_target("contract_check")
            target["plan_ref"] = "docs/plans/archived-plan.json"
            target_input = self.write_json(f"inputs/{name}-target.json", target)
            self.run_cli(
                "acceptance", "create", "--target", str(self.project),
                "--input", str(target_input.relative_to(self.project)),
                "--output", f"docs/acceptance/{name}.json",
            )
        # Plan 被 settle deprecated 移入 archive/ 后，acceptance_refs 仍指向两个验收资产。
        self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/archived-plan.json", "--status", "deprecated",
        )
        archived_plan = self.project / "docs/plans/archive/archived-plan.json"
        self.assertTrue(archived_plan.is_file())
        frozen = json.loads(archived_plan.read_text(encoding="utf-8"))
        self.assertEqual(
            frozen["acceptance_refs"],
            ["docs/acceptance/old.json", "docs/acceptance/new.json"],
        )
        # superseded 必须按归档位置回退解析 plan_ref 并退出反向登记。
        self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/old.json", "--status", "superseded",
            "--replacement", "docs/acceptance/new.json",
        )
        frozen = json.loads(archived_plan.read_text(encoding="utf-8"))
        self.assertEqual(frozen["acceptance_refs"], ["docs/acceptance/new.json"])

    def test_acceptance_supersede_backref_failure_leaves_no_partial_state(self) -> None:
        plan_path = self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="unchanged",
            basename="vanished-plan",
        )
        for name in ("old", "new"):
            target = self.acceptance_target("contract_check")
            target["plan_ref"] = "docs/plans/vanished-plan.json"
            target_input = self.write_json(f"inputs/vanished-{name}-target.json", target)
            self.run_cli(
                "acceptance", "create", "--target", str(self.project),
                "--input", str(target_input.relative_to(self.project)),
                "--output", f"docs/acceptance/{name}.json",
            )
        # 物理删除 Plan（活路径与归档均不存在）：supersede 解析失败必须中止且零副作用。
        plan_path.unlink()
        plan_path.with_suffix(".md").unlink()
        before = self.snapshot_project()
        rejected = self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/old.json", "--status", "superseded",
            "--replacement", "docs/acceptance/new.json",
            expected=1,
        )
        self.assertEqual(rejected["code"], "acceptance_plan_ref_invalid")
        self.assertEqual(self.snapshot_project(), before)

if __name__ == "__main__":
    unittest.main()
