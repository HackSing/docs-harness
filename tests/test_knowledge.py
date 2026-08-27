"""Knowledge 域：按需 query 边界与资产生命周期（create/update/settle/check）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, REQUIRES_SYMLINK


class KnowledgeTest(HarnessTestBase):
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
