"""收尾报告字段校验（report check）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class ReportCheckTest(HarnessTestBase):
    def write_report(self, text: str, name: str = "2026-10-22-check.md") -> str:
        path = self.project / ".docs-harness" / "reports" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path.relative_to(self.project).as_posix()

    def test_complete_report_passes(self) -> None:
        relative = self.write_report(
            "## 改动路径\n`src/a.py`\n\n## 验证\n"
            "`python -m unittest tests.test_a`；退出码 0；验证层级：focused_test\n\n"
            "## 未覆盖\n无\n"
        )
        payload = self.run_cli(
            "report", "check", "--target", str(self.project), "--path", relative
        )
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["missing"], [])
        self.assertEqual(payload["report_ref"], relative)

    def test_missing_fields_fail_with_labels(self) -> None:
        relative = self.write_report(
            "## 改动路径\n`src/a.py`\n\n## 验证\n已人工检查\n",
            "2026-10-22-partial.md",
        )
        payload = self.run_cli(
            "report", "check", "--target", str(self.project),
            "--path", relative, expected=1,
        )
        self.assertEqual(payload["status"], "failed")
        self.assertIn("验证命令", payload["missing"])
        self.assertIn("退出结果", payload["missing"])
        self.assertIn("验证层级（验收层）", payload["missing"])
        self.assertIn("未覆盖项", payload["missing"])
        self.assertIn("next_action", payload)

    def test_exit_evidence_accepts_common_phrasings(self) -> None:
        for wording in ("退出码 0", "退出 0", "exit=0"):
            with self.subTest(wording=wording):
                relative = self.write_report(
                    f"## 改动路径\n`src/a.py`\n## 验证\n`python -m unittest`；{wording}\n"
                    "验证层级：focused_test\n## 未覆盖\n无\n",
                    f"2026-10-22-{wording.replace(' ', '-').replace('=', '-')}.md",
                )
                payload = self.run_cli(
                    "report", "check", "--target", str(self.project), "--path", relative
                )
                self.assertEqual(payload["status"], "passed", payload)

    def test_missing_report_is_a_structured_error(self) -> None:
        payload = self.run_cli(
            "report", "check", "--target", str(self.project),
            "--path", ".docs-harness/reports/missing.md", expected=2,
        )
        self.assertEqual(payload["code"], "report_missing")


if __name__ == "__main__":
    unittest.main()
