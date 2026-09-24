"""evals/evals.json 中 kind=cli 用例的聚焦测试。

只补现有领域测试未断言到的行为；每个测试方法对应 evals.json 某条用例的 covered_by，
改名或删除时须同步 evals.json（tests.test_evals 会机械校验引用可解析）。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, MANAGED_MODULES  # noqa: E402

KNOWLEDGE_QUERY_KEYS = {
    "mode", "facts", "refs", "constraints", "conflicts",
    "conflict_check", "omitted", "source_priority",
}
SOURCE_PRIORITY = "current_source_and_runtime_remain_authoritative"


class EvalKnowledgeCaseTest(HarnessTestBase):
    def create_knowledge(self, name: str, statement: str) -> None:
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("KnowledgeOwner source\n", encoding="utf-8")
        input_path = self.write_json(f"inputs/{name}.json", self.knowledge_input(name, statement))
        self.run_cli(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(input_path.relative_to(self.project)),
            "--output", f"docs/knowledge/{name}.json",
        )

    def test_query_payload_shape_managed_first_budget_and_no_write(self) -> None:
        self.create_knowledge("owner", "KnowledgeOwner 拥有运行时。")
        docs = self.project / "docs"
        (docs / "notes.md").write_text(
            "# 笔记\n\n" + "填充" * 100 + "KnowledgeOwner 在文档里也出现。" + "尾部" * 600 + "\n",
            encoding="utf-8",
        )
        for index in range(3):
            (docs / f"extra-{index}.md").write_text(
                f"# 额外 {index}\n\nKnowledgeOwner 附带说明 {index}。\n", encoding="utf-8"
            )
        before = self.snapshot_project()
        payload = self.run_cli(
            "knowledge", "query", "--target", str(self.project),
            "--query", "KnowledgeOwner", "--limit", "2", "--max-chars", "500",
        )
        # query-no-write：查询不改动项目任何文件。
        self.assertEqual(self.snapshot_project(), before)
        self.assertEqual(set(payload), KNOWLEDGE_QUERY_KEYS)
        self.assertEqual(payload["constraints"], [])
        self.assertEqual(payload["source_priority"], SOURCE_PRIORITY)
        # managed-assets-first：受管 Knowledge 事实排在文档片段之前。
        self.assertEqual(payload["facts"][0]["fact_id"], "runtime.owner")
        self.assertEqual(len(payload["facts"]), 2)
        self.assertEqual(payload["refs"], [item["ref"] for item in payload["facts"]])
        # character-budget：事实文本总长不超过 --max-chars，超出部分计入 omitted。
        self.assertLessEqual(sum(len(item["text"]) for item in payload["facts"]), 500)
        self.assertGreater(payload["omitted"]["count"], 0)
        self.assertEqual(payload["omitted"]["reason"], "limit_or_character_budget")

    def test_query_surfaces_same_fact_id_conflicts_without_runtime_proof(self) -> None:
        self.create_knowledge("owner-a", "KnowledgeOwner A 拥有运行时。")
        self.create_knowledge("owner-b", "KnowledgeOwner B 拥有运行时。")
        payload = self.run_cli(
            "knowledge", "query", "--target", str(self.project), "--query", "KnowledgeOwner",
        )
        self.assertEqual(payload["conflict_check"], "managed_knowledge_assets_evaluated")
        self.assertEqual([item["fact_id"] for item in payload["conflicts"]], ["runtime.owner"])
        self.assertEqual(payload["source_priority"], SOURCE_PRIORITY)


class EvalPlanSelectCaseTest(HarnessTestBase):
    def select(self, *args: str) -> dict[str, object]:
        return self.run_cli("plan", "select", "--target", str(self.project), *args)

    def field_ids(self, selection: dict[str, object]) -> set[str]:
        fields = selection["fields"]
        assert isinstance(fields, list)
        return {item["id"] for item in fields}

    def test_simple_task_selects_none_general_without_plan_file(self) -> None:
        payload = self.select()
        self.assertEqual(payload["plan_level"], "none")
        self.assertEqual(payload["plan_profile"], "general")
        self.assertEqual(payload["fields"], [])
        self.assertFalse((self.project / "docs" / "plans").exists())

    def test_brief_carries_core_fields_without_domain_fields(self) -> None:
        payload = self.select("--level", "brief", "--profile", "frontend_ui")
        self.assertEqual(
            self.field_ids(payload),
            {"title", "key_symbols", "objective", "scope", "steps", "acceptance"},
        )

    def test_full_frontend_merges_secondary_into_one_main_plan(self) -> None:
        selection = self.select(
            "--level", "full", "--profile", "frontend_ui",
            "--secondary-profile", "backend_service",
        )
        self.assertEqual(selection["plan_profile"], "frontend_ui")
        self.assertEqual(selection["secondary_profiles"], ["backend_service"])
        ids = self.field_ids(selection)
        self.assertLessEqual(
            {"state_matrix", "components_interactions", "accessibility", "runtime_acceptance", "api_contract"},
            ids,
        )
        selection_path = self.write_json("inputs/frontend-selection.json", selection)
        content_path = self.write_json(
            "inputs/frontend-content.json",
            self.full_plan_content(selection, acceptance_required=False, knowledge_impact="unchanged"),
        )
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path.relative_to(self.project)),
            "--content", str(content_path.relative_to(self.project)),
            "--output", "docs/plans/frontend.json",
        )
        plans = sorted(path.name for path in (self.project / "docs" / "plans").glob("*.json"))
        self.assertEqual(plans, ["frontend.json"])

    def test_full_backend_carries_service_fields(self) -> None:
        ids = self.field_ids(self.select("--level", "full", "--profile", "backend_service"))
        self.assertLessEqual(
            {"api_contract", "data_model", "failure_retry", "concurrency_idempotency", "service_acceptance"},
            ids,
        )

    def test_full_bugfix_carries_reproduction_and_root_cause_fields(self) -> None:
        ids = self.field_ids(self.select("--level", "full", "--profile", "bugfix"))
        self.assertLessEqual(
            {
                "exact_reproduction", "event_timeline", "first_divergence",
                "root_cause_evidence", "regression_paths",
            },
            ids,
        )

    def test_full_architecture_carries_decision_and_adr_fields(self) -> None:
        ids = self.field_ids(self.select("--level", "full", "--profile", "architecture"))
        self.assertLessEqual(
            {
                "alternatives", "tradeoffs", "decision", "compatibility_migration",
                "rollback_strategy", "adr_decision",
            },
            ids,
        )

    def test_explicit_level_and_profile_override_effects_with_fingerprint(self) -> None:
        payload = self.select(
            "--level", "brief", "--complexity", "complex",
            "--profile", "bugfix", "--surface", "frontend_ui",
        )
        self.assertEqual(payload["plan_level"], "brief")
        self.assertEqual(payload["plan_profile"], "bugfix")
        self.assertIn("user_or_host_explicit", payload["reason"])
        self.assertIn("profile_explicit", payload["reason"])
        fingerprint = payload["selection_fingerprint"]
        self.assertTrue(str(fingerprint).startswith("sha256:"))
        self.assertEqual(payload["selection_ref"], fingerprint)
        repeated = self.select(
            "--level", "brief", "--complexity", "complex",
            "--profile", "bugfix", "--surface", "frontend_ui",
        )
        self.assertEqual(repeated["selection_fingerprint"], fingerprint)
        other = self.select("--level", "brief", "--profile", "general")
        self.assertNotEqual(other["selection_fingerprint"], fingerprint)


class EvalAcceptanceCaseTest(HarnessTestBase):
    def test_failure_attribution_requires_per_item_evidence(self) -> None:
        record = self.write_json(
            "failed-no-evidence.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "失败归因必须逐条带证据",
                "acceptance_type": "behavior_acceptance",
                "status": "failed",
                "layer": "L2",
                "evidence_layer": "focused_test",
                "reason": "聚焦测试失败",
                "next_action": "修复后重跑",
                "failure_attributions": [
                    {"category": "change_related", "summary": "本次改动引入", "blocking": True, "evidence_refs": []},
                ],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record), expected=2,
        )
        self.assertEqual(payload["code"], "invalid_acceptance_input")


class EvalInstallCaseTest(HarnessTestBase):
    LEGACY_RUNTIME_DIRS = ("runs", "knowledge", "knowledge-jobs", "background", "task-inputs")

    def test_init_installs_four_asset_scaffolds_without_generated_knowledge(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project), "--apply")
        config = json.loads(
            (self.project / ".docs-harness" / "config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v13")
        self.assertEqual(config["direct_mode"], {"default": True})
        for asset in ("plans", "knowledge", "acceptance", "adr"):
            self.assertTrue((self.project / "docs" / asset / "README.md").is_file(), asset)
        # 不生成事实或结果：无 Knowledge/Acceptance/ADR 资产、无旧知识地图。
        for asset in ("knowledge", "acceptance", "adr"):
            self.assertEqual(list((self.project / "docs" / asset).glob("*.json")), [], asset)
        self.assertFalse((self.project / "docs" / "knowledge-map.json").exists())
        # 不起后台知识任务，不装旧规则。
        for name in self.LEGACY_RUNTIME_DIRS:
            self.assertFalse((self.project / ".docs-harness" / name).exists(), name)
        self.assertFalse((self.project / ".docs-harness" / "harness-home").exists())
        for module in MANAGED_MODULES:
            self.assertTrue((self.project / "scripts" / module).is_file(), module)


if __name__ == "__main__":
    unittest.main()
