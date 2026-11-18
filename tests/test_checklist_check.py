"""进度清单字段校验（checklist check）。"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HARNESS, HarnessTestBase


class ChecklistCheckTest(HarnessTestBase):
    def write_checklist(self, text: str, name: str = "task-sample.md") -> str:
        path = self.project / ".docs-harness" / "tasks" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path.relative_to(self.project).as_posix()

    def test_standalone_checklist_with_four_elements_and_checkbox_passes(self) -> None:
        relative = self.write_checklist(
            "# 任务进度：示例\n\n"
            "## 改动文件与符号\n- `scripts/harness.py`：`main`、`dispatch_command`\n\n"
            "## 禁碰边界与脏文件\n- 工作区干净，不触碰 `plan_selection.py`\n\n"
            "## 已知陷阱\n- Windows 注意 Python 3.9 行长上限\n\n"
            "## 验收命令与层级\n- 验证层级：focused_test\n- `python -m unittest tests.test_checklist_check`\n\n"
            "- [ ] B1 实现与自测\n"
        )
        payload = self.run_cli(
            "checklist", "check", "--target", str(self.project), "--path", relative
        )
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "standalone")
        self.assertEqual(payload["missing"], [])
        self.assertEqual(payload["checklist_ref"], relative)

    def test_standalone_checklist_missing_fields_fails_with_labels(self) -> None:
        relative = self.write_checklist(
            "# 任务进度：缺项\n\n## 改动文件与符号\n- `scripts/a.py`：`foo`\n\n- [ ] 完成第一批\n",
            "partial.md",
        )
        payload = self.run_cli(
            "checklist", "check", "--target", str(self.project),
            "--path", relative, expected=1,
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["mode"], "standalone")
        self.assertIn("禁碰边界与脏文件", payload["missing"])
        self.assertIn("已知陷阱", payload["missing"])
        self.assertIn("验收命令与层级", payload["missing"])
        self.assertIn("next_action", payload)

    def test_plan_linked_checklist_checks_plan_ref_and_checkbox_without_duplicating_plan(self) -> None:
        relative = self.write_checklist(
            "# 进度：架构重构\n\nPlan: docs/plans/arch.json\n\n- [x] B1 落骨架\n- [ ] B2 填充实现\n",
            "linked.md",
        )
        payload = self.run_cli(
            "checklist", "check", "--target", str(self.project), "--path", relative
        )
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "plan_linked")
        self.assertEqual(payload["missing"], [])

        no_boxes = self.write_checklist(
            "# 进度：缺少勾选项\n\nPlan: docs/plans/arch.json\n",
            "linked-empty.md",
        )
        failed = self.run_cli(
            "checklist", "check", "--target", str(self.project), "--path", no_boxes, expected=1
        )
        self.assertEqual(failed["mode"], "plan_linked")
        self.assertEqual(failed["missing"], ["进度勾选项"])

    def test_missing_checklist_is_a_structured_error(self) -> None:
        payload = self.run_cli(
            "checklist", "check", "--target", str(self.project),
            "--path", ".docs-harness/tasks/missing.md", expected=2,
        )
        self.assertEqual(payload["code"], "checklist_missing")

    def test_unsupported_flag_is_rejected(self) -> None:
        relative = self.write_checklist(
            "Plan: docs/plans/a.json\n- [ ] item\n", "flag-check.md"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(HARNESS),
                "checklist",
                "check",
                "--target",
                str(self.project),
                "--path",
                relative,
                "--strict",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--strict", result.stderr)

    def test_installed_controller_supports_checklist_check(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project), "--apply")
        relative = self.write_checklist(
            "Plan: docs/plans/installed.json\n- [ ] step 1\n", "installed.md"
        )
        payload = self.run_installed("checklist", "check", "--path", relative)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "plan_linked")


if __name__ == "__main__":
    unittest.main()
