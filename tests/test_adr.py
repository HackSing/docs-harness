"""ADR 域：创建/结项/检查生命周期、防篡改与 supersedes 引用校验。"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT, HARNESS


class AdrTest(HarnessTestBase):
    def _adr_input(self, title: str = "测试决策", **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": "docs-harness/adr-input/v1",
            "title": title,
            "key_symbols": ["ADR_SPEC", "adr_create"],
            "context": "背景",
            "decision": "决策",
            "consequences": "影响",
        }
        value.update(overrides)
        return value
    def test_adr_lifecycle_create_check_settle(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.assertTrue((self.project / "docs/adr/README.md").is_file())
        content = self.write_json("inputs/adr.json", self._adr_input())
        created = self.run_cli(
            "adr", "create", "--target", str(self.project),
            "--input", str(content), "--output", "docs/adr/first.json",
        )
        self.assertEqual(created["status"], "created")
        self.assertTrue((self.project / "docs/adr/first.md").is_file())
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("docs-harness:adr-index:start", index)
        self.assertIn("first.md", index)
        checked = self.run_cli("adr", "check", "--target", str(self.project))
        self.assertEqual(checked["status"], "passed")
        # 定稿不可改：同名输出拒绝
        self.run_cli(
            "adr", "create", "--target", str(self.project),
            "--input", str(content), "--output", "docs/adr/first.json", expected=1,
        )
        # superseded 必须提供 replacement
        self.run_cli(
            "adr", "settle", "--target", str(self.project),
            "--adr", "docs/adr/first.json", "--status", "superseded", expected=1,
        )
        second = self.write_json(
            "inputs/adr2.json",
            self._adr_input(title="第二决策", supersedes=["docs/adr/first.json"]),
        )
        self.run_cli(
            "adr", "create", "--target", str(self.project),
            "--input", str(second), "--output", "docs/adr/second.json",
        )
        settled = self.run_cli(
            "adr", "settle", "--target", str(self.project),
            "--adr", "docs/adr/first.json", "--status", "superseded",
            "--replacement", "docs/adr/second.json",
        )
        self.assertEqual(settled["status"], "superseded")
        self.assertTrue((self.project / "docs/adr/archive/first.json").is_file())
        self.assertNotIn(
            "adr/first.md",
            (self.project / "docs/INDEX.md").read_text(encoding="utf-8"),
        )
        checked = self.run_cli("adr", "check", "--target", str(self.project))
        self.assertEqual(checked["status"], "passed")
        assets = self.run_cli("assets-check", "--target", str(self.project))
        self.assertEqual(assets["status"], "passed")
        self.assertEqual(assets["checked"]["adr"], 2)
    def test_adr_rejects_tampered_asset(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        content = self.write_json("inputs/adr.json", self._adr_input())
        self.run_cli(
            "adr", "create", "--target", str(self.project),
            "--input", str(content), "--output", "docs/adr/first.json",
        )
        asset_path = self.project / "docs/adr/first.json"
        asset = json.loads(asset_path.read_text(encoding="utf-8"))
        asset["decision"] = "手工篡改的决策"
        asset_path.write_text(json.dumps(asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        payload = self.run_cli("adr", "check", "--target", str(self.project), expected=1)
        self.assertEqual(payload["status"], "failed")
        self.assertTrue(any("指纹" in item for item in payload["failures"]))
    def test_adr_rejects_unknown_supersedes_ref(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        content = self.write_json(
            "inputs/adr.json", self._adr_input(supersedes=["docs/adr/ghost.json"])
        )
        self.run_cli(
            "adr", "create", "--target", str(self.project),
            "--input", str(content), "--output", "docs/adr/first.json", expected=1,
        )
    def test_adr_check_ignores_preexisting_unmarked_documents(self) -> None:
        adr_dir = self.project / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "ADR-0001.md").write_text("# 既有手写决策\n", encoding="utf-8")
        (adr_dir / "INDEX.md").write_text("# 既有索引\n", encoding="utf-8")
        self.run_cli("project", "init", "--target", str(self.project))
        self.assertEqual(
            (adr_dir / "ADR-0001.md").read_text(encoding="utf-8"), "# 既有手写决策\n"
        )
        checked = self.run_cli("adr", "check", "--target", str(self.project))
        self.assertEqual(checked["status"], "passed")
        payload = self.run_cli("project", "check", "--target", str(self.project))
        self.assertNotIn("adr_assets_invalid", [f["code"] for f in payload["findings"]])

    def test_adr_epilog_note_line_is_not_split_into_chars(self) -> None:
        # 回归：裸字符串作为 notes 传入 _schema_example_block 会被逐字符 extend（2.8.0 起）。
        sys.path.insert(0, str(ROOT / "scripts"))
        import harness
        note = "ADR 定稿后不可更新；失效时 adr settle --status deprecated|superseded（superseded 需 --replacement）。"
        self.assertIn(note, harness.ADR_EPILOG.splitlines())
        result = subprocess.run(
            [sys.executable, str(HARNESS), "adr", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(note, result.stdout.splitlines())

if __name__ == "__main__":
    unittest.main()
