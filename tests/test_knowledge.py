"""Knowledge 域：按需 query 边界与资产生命周期（create/update/settle/check）。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, REQUIRES_SYMLINK
from knowledge_assets import render_markdown  # noqa: E402


class KnowledgeTest(HarnessTestBase):
    def _create_knowledge(self, name: str, fact_id: str, refs: list[str]) -> Path:
        value = {
            "schema_version": "docs-harness/knowledge-input/v1",
            "title": name,
            "key_symbols": ["KnowledgeOwner", fact_id],
            "summary": "引用其他资产的事实。",
            "facts": [{"id": fact_id, "statement": f"{name} 的事实。", "source_refs": refs}],
        }
        input_path = self.write_json(f"inputs/{name}.json", value)
        self.run_cli(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(input_path.relative_to(self.project)),
            "--output", f"docs/knowledge/{name}.json",
        )
        return self.project / f"docs/knowledge/{name}.json"
    def _refs(self, relative: str) -> list[str]:
        asset = json.loads((self.project / relative).read_text(encoding="utf-8"))
        document = (self.project / relative).with_suffix(".md").read_text(encoding="utf-8")
        self.assertEqual(document, render_markdown(asset), "Markdown 投影须与 JSON 一致")
        return asset["facts"][0]["source_refs"]
    def test_plan_deprecated_archive_follows_knowledge_source_refs(self) -> None:
        (self.project / "src").mkdir()
        (self.project / "src/runtime.txt").write_text("source\n", encoding="utf-8")
        self.create_full_plan(acceptance_required=False, knowledge_impact="unchanged", basename="moved")
        live = self._create_knowledge(
            "live", "plan.live", ["docs/plans/moved.json", "docs/plans/moved.md:3", "src/runtime.txt:1"]
        )
        self._create_knowledge("history", "plan.history", ["docs/plans/moved.md"])
        # 下游 2026-09-11 现场：引用方案的 Knowledge 已先被取代归档，归档资产不接受 knowledge update。
        self.run_cli(
            "knowledge", "settle", "--target", str(self.project),
            "--knowledge", "docs/knowledge/history.json",
            "--status", "superseded", "--replacement", "docs/knowledge/live.json",
        )
        unrelated = self._create_knowledge("unrelated", "plan.unrelated", ["src/runtime.txt"])
        before_live = json.loads(live.read_text(encoding="utf-8"))
        before_unrelated = unrelated.read_bytes()

        settled = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/moved.json", "--status", "deprecated",
        )

        self.assertIn("docs/knowledge/live.json", settled["changed"])
        self.assertIn("docs/knowledge/archive/history.json", settled["changed"])
        self.assertEqual(
            self._refs("docs/knowledge/live.json"),
            ["docs/plans/archive/moved.json", "docs/plans/archive/moved.md:3", "src/runtime.txt:1"],
        )
        self.assertEqual(self._refs("docs/knowledge/archive/history.json"), ["docs/plans/archive/moved.md"])
        after_live = json.loads(live.read_text(encoding="utf-8"))
        for key in ("revision", "revision_history", "updated_at", "status"):
            self.assertEqual(after_live[key], before_live[key], key)
        self.assertNotEqual(after_live["asset_fingerprint"], before_live["asset_fingerprint"])
        self.assertEqual(unrelated.read_bytes(), before_unrelated)
        self.assertEqual(self.run_cli("knowledge", "check", "--target", str(self.project))["status"], "passed")
    def test_plan_archive_does_not_reseal_tampered_knowledge(self) -> None:
        self.create_full_plan(acceptance_required=False, knowledge_impact="unchanged", basename="moved")
        live = self._create_knowledge("live", "plan.live", ["docs/plans/moved.md"])
        asset = json.loads(live.read_text(encoding="utf-8"))
        asset["facts"][0]["statement"] = "手工改过、未重封的事实。"
        live.write_text(json.dumps(asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tampered = live.read_bytes()

        failed = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/moved.json", "--status", "deprecated", expected=1,
        )

        self.assertEqual(failed["code"], "asset_fingerprint_invalid")
        self.assertIn("docs/knowledge/live.json", failed["message"])
        self.assertEqual(live.read_bytes(), tampered, "指纹无效的资产不得被重封")
        self.assertTrue((self.project / "docs/plans/archive/moved.json").is_file())
    def test_knowledge_adr_acceptance_archive_follow_knowledge_source_refs(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project), "--apply")
        adr_input = self.write_json("inputs/adr.json", {
            "schema_version": "docs-harness/adr-input/v1", "title": "决策",
            "key_symbols": ["ADR_SPEC", "adr_create"], "context": "背景", "decision": "决策", "consequences": "影响",
        })
        self.run_cli(
            "adr", "create", "--target", str(self.project),
            "--input", str(adr_input.relative_to(self.project)), "--output", "docs/adr/decision.json",
        )
        target_input = self.write_json("inputs/acceptance.json", self.acceptance_target())
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)), "--output", "docs/acceptance/flow.json",
        )
        self._create_knowledge("old-fact", "fact.old", ["docs/adr/decision.md"])
        self._create_knowledge(
            "witness", "fact.witness",
            ["docs/adr/decision.md", "docs/acceptance/flow.json:2", "docs/knowledge/old-fact.md"],
        )

        for command, flag, name in (
            ("adr", "--adr", "docs/adr/decision.json"),
            ("acceptance", "--acceptance", "docs/acceptance/flow.json"),
            ("knowledge", "--knowledge", "docs/knowledge/old-fact.json"),
        ):
            settled = self.run_cli(
                command, "settle", "--target", str(self.project), flag, name, "--status", "deprecated",
            )
            self.assertIn("docs/knowledge/witness.json", settled["rewritten_source_refs"], command)

        self.assertEqual(
            self._refs("docs/knowledge/witness.json"),
            ["docs/adr/archive/decision.md", "docs/acceptance/archive/flow.json:2", "docs/knowledge/archive/old-fact.md"],
        )
        self.assertEqual(self._refs("docs/knowledge/archive/old-fact.json"), ["docs/adr/archive/decision.md"])
        self.assertEqual(self.run_cli("knowledge", "check", "--target", str(self.project))["status"], "passed")
    def test_knowledge_query_is_explicit_bounded_and_stateless(self) -> None:
        docs = self.project / "docs"
        docs.mkdir()
        (docs / "architecture.md").write_text(
            "# 语音架构\n\n语音入口由 VoiceCoordinator 负责，退出时不得重复 finalize。\n",
            encoding="utf-8",
        )
        payload = self.run_cli(
            "knowledge", "query", "--target", str(self.project),
            "--query", "VoiceCoordinator 退出", "--limit", "1", "--max-chars", "500",
        )
        self.assertEqual(payload["mode"], "knowledge_assist")
        self.assertEqual(len(payload["facts"]), 1)
        self.assertIn("docs/architecture.md", payload["refs"][0])
        self.assertFalse((self.project / ".docs-harness").exists())
    def test_knowledge_query_excludes_history_by_default(self) -> None:
        current = self.project / "docs" / "architecture.md"
        current.parent.mkdir(parents=True)
        current.write_text("# 当前架构\n\n当前入口是 DirectExecutor。\n", encoding="utf-8")
        history = self.project / "docs" / "history" / "plans" / "old.md"
        history.parent.mkdir(parents=True)
        history.write_text("# 旧方案\n\nLegacyGateOnlyFact 只存在于历史方案。\n", encoding="utf-8")
        payload = self.run_cli(
            "knowledge", "query", "--target", str(self.project),
            "--query", "LegacyGateOnlyFact",
        )
        self.assertEqual(payload["facts"], [])
        self.assertFalse(any("docs/history/" in ref for ref in payload["refs"]))
    @REQUIRES_SYMLINK
    def test_knowledge_query_does_not_follow_external_docs_symlink(self) -> None:
        outside = Path(self.temp.name) / "outside-docs"
        outside.mkdir()
        (outside / "secret.md").write_text(
            "# 外部内容\nExternalSymlinkSecret 不得被读取。\n",
            encoding="utf-8",
        )
        (self.project / "docs").symlink_to(outside, target_is_directory=True)
        payload = self.run_cli(
            "knowledge", "query", "--target", str(self.project),
            "--query", "ExternalSymlinkSecret",
        )
        self.assertEqual(payload["facts"], [])
        self.assertEqual(payload["refs"], [])
    def test_knowledge_asset_create_update_query_and_check(self) -> None:
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True)
        source.write_text("KnowledgeOwner owns the runtime.\n", encoding="utf-8")
        first = self.write_json("inputs/knowledge.json", self.knowledge_input("运行时所有权", "KnowledgeOwner 拥有运行时。"))
        created = self.run_cli(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(first.relative_to(self.project)),
            "--output", "docs/knowledge/runtime-owner.json",
        )
        self.assertEqual(created["revision"], 1)
        self.assertTrue((self.project / "docs/knowledge/runtime-owner.md").is_file())
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("knowledge/runtime-owner.md", index)

        queried = self.run_cli(
            "knowledge", "query", "--target", str(self.project),
            "--query", "KnowledgeOwner",
        )
        self.assertEqual(queried["facts"][0]["fact_id"], "runtime.owner")
        self.assertEqual(len(queried["facts"]), 1)
        self.assertFalse(any(ref.startswith("docs/INDEX.md") for ref in queried["refs"]))
        self.assertEqual(queried["conflicts"], [])

        second = self.write_json("inputs/knowledge-v2.json", self.knowledge_input("运行时所有权", "KnowledgeOwner 是运行时唯一所有者。"))
        updated = self.run_cli(
            "knowledge", "update", "--target", str(self.project),
            "--input", str(second.relative_to(self.project)),
            "--knowledge", "docs/knowledge/runtime-owner.json",
        )
        self.assertEqual(updated["revision"], 2)
        checked = self.run_cli("knowledge", "check", "--target", str(self.project))
        self.assertEqual(checked["status"], "passed")
    def test_knowledge_conflict_is_visible_and_settle_archives(self) -> None:
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True)
        source.write_text("source\n", encoding="utf-8")
        for name, statement in (("owner-a", "A owns runtime."), ("owner-b", "B owns runtime.")):
            input_path = self.write_json(f"inputs/{name}.json", self.knowledge_input(name, statement))
            self.run_cli(
                "knowledge", "create", "--target", str(self.project),
                "--input", str(input_path.relative_to(self.project)),
                "--output", f"docs/knowledge/{name}.json",
            )
        checked = self.run_cli("knowledge", "check", "--target", str(self.project), expected=1)
        self.assertEqual(checked["conflicts"][0]["fact_id"], "runtime.owner")
        settled = self.run_cli(
            "knowledge", "settle", "--target", str(self.project),
            "--knowledge", "docs/knowledge/owner-a.json",
            "--status", "superseded",
            "--replacement", "docs/knowledge/owner-b.json",
        )
        self.assertEqual(settled["status"], "superseded")
        self.assertTrue((self.project / "docs/knowledge/archive/owner-a.json").is_file())
        self.assertEqual(
            self.run_cli("knowledge", "check", "--target", str(self.project))["status"],
            "passed",
        )


if __name__ == "__main__":
    unittest.main()
