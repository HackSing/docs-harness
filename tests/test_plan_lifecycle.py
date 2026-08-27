"""Plan 域生命周期：check/select/create/settle 机制与冻结指纹防线。"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class PlanLifecycleTest(HarnessTestBase):
    def test_plan_check_fails_when_docs_system_is_missing(self) -> None:
        payload = self.run_cli("plan", "check", "--target", str(self.project), expected=1)
        self.assertEqual(payload["status"], "failed")
        self.assertTrue(any("project init/upgrade" in item for item in payload["failures"]))
    def test_plan_check_reports_banner_and_stale_archive_reference(self) -> None:
        docs = self.project / "docs"
        plans = docs / "plans"
        archive = plans / "archive"
        archive.mkdir(parents=True)
        (docs / "INDEX.md").write_text(
            "# 索引\n\n- plans/no-banner.md（关键符号：无）\n"
            "- plans/archive/old-plan.md（已归档）\n",
            encoding="utf-8",
        )
        (plans / "no-banner.md").write_text("# 无横幅文档\n", encoding="utf-8")
        (archive / "old-plan.md").write_text(
            "> 状态：已废弃-被 no-banner.md 取代（2026-08-13 核对）\n\n旧文档。\n",
            encoding="utf-8",
        )
        (docs / "guide.md").write_text(
            "# 指南\n\n参见 docs/plans/old-plan.md 的旧路径。\n", encoding="utf-8"
        )
        payload = self.run_cli("plan", "check", "--target", str(self.project), expected=1)
        self.assertEqual(payload["status"], "failed")
        failures = payload["failures"]
        self.assertTrue(any("缺少状态横幅" in item for item in failures))
        self.assertTrue(any("引用已归档文档旧路径" in item for item in failures))
    def test_plan_select_uses_effects_not_task_text(self) -> None:
        none = self.run_cli("plan", "select", "--target", str(self.project))
        self.assertEqual(none["plan_level"], "none")
        full = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--complexity", "complex", "--surface", "architecture",
        )
        self.assertEqual(full["plan_level"], "full")
        self.assertEqual(full["plan_profile"], "architecture")
        field_ids = {item["id"] for item in full["fields"]}
        self.assertIn("adr_decision", field_ids)
        self.assertNotIn("state_matrix", field_ids)
        self.assertTrue(fields := {item["id"]: item for item in full["fields"]})
        self.assertTrue(fields["acceptance_required"]["guidance"])
        self.assertTrue(fields["knowledge_impact"]["guidance"])
    def test_bugfix_profile_requires_structured_verification_contract(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "full", "--profile", "bugfix",
        )
        fields = {item["id"]: item for item in selection["fields"]}
        for field_id in (
            "affected_modules",
            "verification_scope",
            "full_regression_trigger",
            "failure_attribution",
        ):
            self.assertIn(field_id, fields)
            self.assertTrue(fields[field_id]["required"])
            self.assertTrue(fields[field_id]["guidance"])

        content = {item["id"]: f"已填写 {item['label']}" for item in selection["fields"]}
        content.update(
            {
                "title": "Session Bugfix 方案",
                "key_symbols": ["SessionService", "SessionStore"],
                "acceptance_required": False,
                "knowledge_impact": "unchanged",
                "affected_modules": ["service/session", "tests/session"],
                "verification_scope": {
                    "mode": "affected_modules",
                    "commands": ["python -m unittest tests.test_session"],
                    "reused_passed_evidence": ["上一轮相同输入快照的类型检查"],
                },
                "full_regression_trigger": {
                    "required": False,
                    "reason_codes": [],
                    "rationale": "改动与调用链均限制在 session 模块",
                },
                "failure_attribution": {
                    "categories": [
                        "change_related",
                        "unrelated",
                        "pre_existing",
                        "environment",
                        "flaky",
                    ],
                    "separate_non_change_failures": True,
                    "evidence_required": True,
                },
            }
        )
        selection_path = self.write_json("bugfix-selection.json", selection)
        content_path = self.write_json("bugfix-content.json", content)
        payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/bugfix.json",
        )
        self.assertEqual(payload["execution_projection"]["affected_modules"], content["affected_modules"])
        self.assertEqual(
            payload["execution_projection"]["verification_scope"]["mode"],
            "affected_modules",
        )

        full_content = dict(content)
        full_content["verification_scope"] = {
            "mode": "repository_full",
            "commands": ["npm test"],
            "reused_passed_evidence": [],
        }
        full_content["full_regression_trigger"] = {
            "required": True,
            "reason_codes": ["public_contract_change"],
            "rationale": "验收输入 Schema 是对外公共契约",
        }
        full_content_path = self.write_json("bugfix-full-content.json", full_content)
        full_payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(full_content_path),
            "--output", "docs/plans/bugfix-full.json",
        )
        self.assertEqual(
            full_payload["execution_projection"]["full_regression_trigger"]["reason_codes"],
            ["public_contract_change"],
        )

        invalid = dict(content)
        invalid["verification_scope"] = {
            "mode": "repository_full",
            "commands": ["npm test"],
            "reused_passed_evidence": [],
        }
        invalid_path = self.write_json("bugfix-invalid.json", invalid)
        rejected = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(invalid_path),
            "--output", "docs/plans/bugfix-invalid.json", expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_plan_content")
    def test_plan_create_validates_and_freezes_only_selected_fields(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "frontend_ui",
        )
        selection_path = self.write_json("selection.json", selection)
        content = {
            "title": "前端确认状态修复方案",
            "key_symbols": ["ConfirmPage", "confirmState"],
            "objective": "修复前端确认状态",
            "scope": ["web/confirm.tsx"],
            "steps": ["复现", "修复", "走真实页面流程"],
            "acceptance": ["启动页面并完成确认流程"],
        }
        content_path = self.write_json("content.json", content)
        payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/fix.json",
        )
        self.assertEqual(payload["status"], "frozen")
        frozen = json.loads((self.project / "docs/plans/fix.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen["content"], content)
        self.assertNotIn("state_matrix", frozen["content"])
        document = self.project / "docs/plans/fix.md"
        self.assertIn("docs-harness:plan-document/v1", document.read_text(encoding="utf-8"))
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("plans/fix.md", index)
        self.assertIn("`ConfirmPage`", index)

        before = (self.project / "docs/plans/fix.json").read_bytes()
        repeated = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/fix.json",
        )
        self.assertEqual(repeated["status"], "frozen")
        self.assertEqual((self.project / "docs/plans/fix.json").read_bytes(), before)
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertEqual(index.count("plans/fix.md"), 1)
    def test_plan_settle_implements_and_archives_managed_plan(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        selection_path = self.write_json("selection.json", selection)
        content = {
            "title": "可归档任务方案",
            "key_symbols": ["PlanOwner", "PlanConsumer"],
            "objective": "验证方案生命周期",
            "scope": ["scripts/harness.py"],
            "steps": ["创建", "完成", "归档"],
            "acceptance": ["plan check 通过"],
        }
        content_path = self.write_json("content.json", content)
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/lifecycle.json",
        )
        implemented = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/lifecycle.json", "--status", "implemented",
        )
        self.assertEqual(implemented["status"], "implemented")
        document = self.project / "docs/plans/lifecycle.md"
        self.assertIn("已实施-仅追溯", document.read_text(encoding="utf-8"))
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("状态：已实施-仅追溯", index)

        deprecated = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/lifecycle.json", "--status", "deprecated",
            "--replacement", "next-plan.md",
        )
        self.assertEqual(deprecated["status"], "deprecated")
        self.assertFalse(document.exists())
        self.assertTrue((self.project / "docs/plans/archive/lifecycle.md").is_file())
        self.assertTrue((self.project / "docs/plans/archive/lifecycle.json").is_file())
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertNotIn("plans/lifecycle.md", index)
        checked = self.run_cli("plan", "check", "--target", str(self.project))
        self.assertEqual(checked["status"], "passed")
    def test_plan_settle_migrates_pre_250_frozen_identity(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        selection_path = self.write_json("selection.json", selection)
        content_path = self.write_json(
            "content.json",
            {
                "title": "旧冻结方案",
                "key_symbols": ["LegacyPlan", "PlanConsumer"],
                "objective": "兼容旧方案",
                "scope": ["scripts/harness.py"],
                "steps": ["迁移"],
                "acceptance": ["完成状态可写入"],
            },
        )
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/legacy.json",
        )
        frozen_path = self.project / "docs/plans/legacy.json"
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        frozen["schema_version"] = "docs-harness/plan/v2"
        frozen.pop("acceptance_refs")
        frozen.pop("governance", None)
        frozen["content"].pop("title")
        frozen["content"].pop("key_symbols")
        unsigned = dict(frozen)
        unsigned.pop("plan_fingerprint")
        frozen["plan_fingerprint"] = "sha256:" + hashlib.sha256(
            json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.write_json("docs/plans/legacy.json", frozen)
        payload = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/legacy.json", "--status", "implemented",
        )
        self.assertEqual(payload["status"], "implemented")
        self.assertIn(
            "已实施-仅追溯",
            (self.project / "docs/plans/legacy.md").read_text(encoding="utf-8"),
        )
    def test_plan_settle_rejects_tampered_frozen_fingerprint(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        selection_path = self.write_json("selection.json", selection)
        content_path = self.write_json(
            "content.json",
            {
                "title": "指纹保护方案",
                "key_symbols": ["PlanFingerprint", "PlanConsumer"],
                "objective": "拒绝篡改",
                "scope": ["scripts/harness.py"],
                "steps": ["校验"],
                "acceptance": ["篡改被拒绝"],
            },
        )
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/tampered-fingerprint.json",
        )
        frozen_path = self.project / "docs/plans/tampered-fingerprint.json"
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        frozen["content"]["objective"] = "已被篡改"
        self.write_json("docs/plans/tampered-fingerprint.json", frozen)
        payload = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/tampered-fingerprint.json",
            "--status", "implemented", expected=2,
        )
        self.assertEqual(payload["code"], "invalid_plan_ref")
    def test_plan_create_rejects_re_fingerprinted_unregistered_fields(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "frontend_ui",
        )
        selection["fields"].append({"id": "controller_dump", "label": "控制器全集", "required": True})
        unsigned = {key: value for key, value in selection.items() if key != "selection_fingerprint"}
        selection["selection_fingerprint"] = "sha256:" + hashlib.sha256(
            json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        selection_path = self.write_json("tampered-selection.json", selection)
        content_path = self.write_json(
            "tampered-content.json",
            {
                "objective": "修复页面",
                "scope": ["web/page.tsx"],
                "steps": ["修复"],
                "acceptance": ["运行页面"],
                "controller_dump": "不应进入方案",
            },
        )
        payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/tampered.json", expected=2,
        )
        self.assertEqual(payload["code"], "invalid_plan_selection")

    def test_plan_check_archived_same_name_acceptance_entry_is_not_leak(self) -> None:
        docs = self.project / "docs"
        archive = docs / "plans" / "archive"
        archive.mkdir(parents=True)
        (archive / "same-name.md").write_text(
            "> 状态：已废弃-被别的方案取代（2026-08-22 核对）\n\n旧文档。\n",
            encoding="utf-8",
        )
        # INDEX 验收区块存在同名文档：裸子串匹配会把该条目误判为归档泄漏，
        # 链接 token (plans/<basename>) 匹配则不会误伤。
        (docs / "INDEX.md").write_text(
            "# 索引\n\n## 验收\n\n"
            "- [同名验收](acceptance/same-name.md)（关键符号：`AcceptanceSettle`、`PlanBackref`）\n",
            encoding="utf-8",
        )
        payload = self.run_cli("plan", "check", "--target", str(self.project), "--fast")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["failures"], [])

    def test_plan_check_live_doc_entry_requires_plan_link_token(self) -> None:
        docs = self.project / "docs"
        plans = docs / "plans"
        plans.mkdir(parents=True)
        (plans / "live.md").write_text(
            "> 状态：有效（现行事实/实施中）\n\n# 活文档\n", encoding="utf-8"
        )
        # 验收区块的同名条目不能顶替 plans 区块的活文档条目。
        (docs / "INDEX.md").write_text(
            "# 索引\n\n## 验收\n\n"
            "- [同名验收](acceptance/live.md)（关键符号：`AcceptanceSettle`、`PlanBackref`）\n",
            encoding="utf-8",
        )
        payload = self.run_cli(
            "plan", "check", "--target", str(self.project), "--fast", expected=1
        )
        self.assertTrue(
            any("缺少 docs/plans/live.md 的条目" in item for item in payload["failures"])
        )

    def test_plan_check_accepts_backtick_table_index_entry(self) -> None:
        docs = self.project / "docs"
        plans = docs / "plans"
        plans.mkdir(parents=True)
        (plans / "table-entry.md").write_text(
            "> 状态：有效（现行事实/实施中）\n\n# 表格条目文档\n", encoding="utf-8"
        )
        # 表格式索引以反引号路径登记（ZBuddy 等存量项目格式），与链接形态语义等同。
        (docs / "INDEX.md").write_text(
            "# 索引\n\n## 方案\n\n"
            "| 文档 | 说明 |\n| --- | --- |\n"
            "| `plans/table-entry.md` | 表格条目；关键符号：`TokenA`、`TokenB` |\n",
            encoding="utf-8",
        )
        payload = self.run_cli("plan", "check", "--target", str(self.project), "--fast")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["failures"], [])

    def test_plan_check_backtick_archived_entry_is_leak(self) -> None:
        docs = self.project / "docs"
        archive = docs / "plans" / "archive"
        archive.mkdir(parents=True)
        (archive / "gone.md").write_text(
            "> 状态：已废弃-被别的方案取代（2026-08-23 核对）\n\n旧文档。\n",
            encoding="utf-8",
        )
        # 放宽到反引号形态后，真正的归档泄漏（反引号条目留在活索引）仍须被抓。
        (docs / "INDEX.md").write_text(
            "# 索引\n\n| 文档 | 说明 |\n| --- | --- |\n"
            "| `plans/gone.md` | 泄漏条目仍留在活索引 |\n",
            encoding="utf-8",
        )
        payload = self.run_cli(
            "plan", "check", "--target", str(self.project), "--fast", expected=1
        )
        self.assertTrue(
            any("归档文档 gone.md 仍出现在活索引" in item for item in payload["failures"])
        )

if __name__ == "__main__":
    unittest.main()
