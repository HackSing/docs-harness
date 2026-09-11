"""assets-check 统一编排与 release sync：聚合防线、指纹/索引/脚本卫生拦截。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT

sys.path.insert(0, str(ROOT / "scripts"))

from plan_governance import plan_fingerprint


class AssetsCheckTest(HarnessTestBase):
    def test_release_sync_strict_requires_changelog_top_version(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        (self.project / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts" / "harness.py", self.project / "scripts" / "harness.py")
        shutil.copytree(ROOT / "plan-templates", self.project / "plan-templates")
        (self.project / "evals").mkdir()
        shutil.copy2(ROOT / "evals" / "evals.json", self.project / "evals" / "evals.json")
        (self.project / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (self.project / "package.json").write_text(
            json.dumps({"version": version}) + "\n", encoding="utf-8"
        )
        (self.project / "SKILL.md").write_text(
            f"---\nmetadata:\n  version: {version}\n---\n", encoding="utf-8"
        )
        (self.project / "CHANGELOG.md").write_text(
            "# Changelog\n\n## 0.0.1 - 2026-01-01\n\n- 旧条目\n", encoding="utf-8"
        )
        relaxed = self.run_cli("release", "sync", "--target", str(self.project))
        self.assertEqual(relaxed["status"], "consistent")
        strict = self.run_cli(
            "release", "sync", "--target", str(self.project), "--strict", expected=1
        )
        self.assertEqual(strict["status"], "inconsistent")
        self.assertTrue(strict["strict_failures"])
        (self.project / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## {version} - 2026-08-16\n\n- 新条目\n", encoding="utf-8"
        )
        fixed = self.run_cli("release", "sync", "--target", str(self.project), "--strict")
        self.assertEqual(fixed["status"], "consistent")
    def test_assets_check_passes_for_initialized_zero_asset_project(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        payload = self.run_cli("assets-check", "--target", str(self.project))
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["checked"]["knowledge"], 0)
        self.assertEqual(payload["checked"]["acceptance"], 0)
        self.assertEqual(
            payload["checked"]["script_hygiene"], 0,
            "非 git 目标应跳过 ScriptHygiene（checked=0，不产生 WARN）",
        )
        self.assertEqual(
            payload["checked"]["structure"], 0,
            "非 git 目标应跳过 Structure（checked=0，不产生 WARN）",
        )
    def test_assets_check_rejects_tampered_knowledge_asset(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True)
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
        asset_path = self.project / "docs/knowledge/runtime-owner.json"
        asset = json.loads(asset_path.read_text(encoding="utf-8"))
        asset["summary"] = "已被手工篡改"
        self.write_json("docs/knowledge/runtime-owner.json", asset)
        payload = self.run_cli(
            "assets-check", "--target", str(self.project), expected=1
        )
        self.assertTrue(any("资产指纹无效" in item for item in payload["failures"]))
    def test_assets_check_rejects_orphan_managed_index_entry(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        index_path = self.project / "docs/INDEX.md"
        index = index_path.read_text(encoding="utf-8")
        index = index.replace(
            "<!-- docs-harness:knowledge-index:end -->",
            "- [孤儿知识](knowledge/orphan.md) — 状态：有效；关键符号：`A`、`B`\n"
            "<!-- docs-harness:knowledge-index:end -->",
        )
        index_path.write_text(index, encoding="utf-8")
        payload = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", expected=1
        )
        self.assertTrue(any("没有对应活资产" in item for item in payload["failures"]))
    def test_assets_check_rejects_mixed_line_ending_script(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        (self.project / "deploy.sh").write_bytes(b"#!/bin/sh\r\necho mixed\n")
        (self.project / "clean.sh").write_bytes(b"#!/bin/sh\necho clean\n")
        for args in (("git", "init"), ("git", "add", "deploy.sh", "clean.sh")):
            subprocess.run(args, cwd=self.project, capture_output=True, check=True)
        payload = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", expected=1
        )
        self.assertTrue(
            any(
                "ScriptHygiene" in item and "deploy.sh" in item
                for item in payload["failures"]
            )
        )
        self.assertFalse(
            any("clean.sh" in item for item in payload["failures"]),
            "纯 LF 脚本不应被误判为混合行尾",
        )
    def test_assets_check_strict_blocks_slow_warning_but_fast_skips_it(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        selection_path = self.write_json("selection.json", selection)
        content_path = self.write_json(
            "content.json",
            {
                "title": "慢检查告警方案",
                "key_symbols": ["AbsentPlanSymbol", "AbsentPlanConsumer"],
                "objective": "验证 strict 与 fast 边界",
                "scope": ["scripts/harness.py"],
                "steps": ["创建", "结项"],
                "acceptance": ["strict 阻断慢检查 WARN"],
            },
        )
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/slow-warning.json",
        )
        selection_path.unlink()
        content_path.unlink()
        self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/slow-warning.json", "--status", "implemented",
        )
        normal = self.run_cli("assets-check", "--target", str(self.project))
        self.assertTrue(any("零命中" in item for item in normal["warnings"]))
        strict = self.run_cli(
            "assets-check", "--target", str(self.project), "--strict", expected=1
        )
        self.assertEqual(strict["status"], "failed")
        fast = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", "--strict"
        )
        self.assertEqual(fast["status"], "passed")
    def test_assets_check_warns_when_acceptance_settled_but_plan_not(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.create_full_plan(
            acceptance_required=True, knowledge_impact="unchanged", basename="leak",
        )
        target = self.acceptance_target()
        target["plan_ref"] = "docs/plans/leak.json"
        target_input = self.write_json("inputs/acceptance-target.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/leak.json",
        )
        (self.project / "focused-test.log").write_text("passed\n", encoding="utf-8")
        record_input = self.write_json("inputs/record.json", {
            "schema_version": "docs-harness/acceptance-input/v3",
            "criterion_id": "flow.result",
            "objective": "逐条记录功能流程证据。",
            "acceptance_type": "behavior_acceptance",
            "status": "passed",
            "layer": "L2",
            "evidence_layer": "focused_test",
            "method": "运行聚焦测试",
            "evidence_refs": ["focused-test.log"],
        })
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record_input.relative_to(self.project)),
            "--acceptance", "docs/acceptance/leak.json",
        )
        self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/leak.json", "--status", "passed",
        )
        leaking = self.run_cli("assets-check", "--target", str(self.project), "--fast")
        self.assertTrue(
            any("已全部结项，Plan 仍未 settle" in item for item in leaking["warnings"]),
            leaking["warnings"],
        )
        governance = self.write_json("inputs/governance.json", {
            "schema_version": "docs-harness/plan-governance-input/v1",
            "unchanged_reason": "本测试不涉及可复用事实",
        })
        self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/leak.json", "--status", "implemented",
            "--governance-input", str(governance.relative_to(self.project)),
        )
        settled = self.run_cli("assets-check", "--target", str(self.project), "--fast")
        self.assertFalse(
            any("仍未 settle" in item for item in settled["warnings"]),
            settled["warnings"],
        )
    def test_assets_check_warns_when_plan_frozen_too_long_without_settle(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.create_full_plan(
            acceptance_required=False, knowledge_impact="unchanged", basename="stale",
        )
        fresh = self.run_cli("assets-check", "--target", str(self.project), "--fast")
        self.assertFalse(
            any("仍未 settle" in item for item in fresh["warnings"]),
            fresh["warnings"],
        )
        plan_path = self.project / "docs/plans/stale.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["frozen_at"] = "2026-01-01T00:00:00+00:00"
        plan["plan_fingerprint"] = plan_fingerprint(plan)
        self.write_json("docs/plans/stale.json", plan)
        stale = self.run_cli("assets-check", "--target", str(self.project), "--fast")
        self.assertTrue(
            any("冻结超过 90 天仍未 settle" in item for item in stale["warnings"]),
            stale["warnings"],
        )

if __name__ == "__main__":
    unittest.main()
