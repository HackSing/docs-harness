"""受管入口「呈现形式」与「收尾」的选型契约。

阶梯是提示词规则，确定性测试守住规则文本：每个形式分支、交叉优先级、四块顺序
与附件位置。模型实际选型由 evals/evals.json 的 behavior 用例人工运行。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import ROOT

PROMPT_PATH = ROOT / "scripts" / "agent_prompt.md"
DOC_PATH = ROOT / "docs" / "output-format-ladder.md"
SNAPSHOT_START = "<!-- docs-harness:output-format-snapshot:start -->"
SNAPSHOT_END = "<!-- docs-harness:output-format-snapshot:end -->"

EXPECTED_LADDER = (
    ("问答、只读检查，一句话能答完", "纯文字 1–3 行，不上工具"),
    ("有改动的任务收尾、进度播报", '收尾按"收尾"一节的四块；进度只写一行：现在做什么，下一步做什么'),
    ("要用户拍板", "编号选项，每项附推荐；宿主支持点选时用点选"),
    ("线性步骤", "编号列表，不画图"),
    ("对比几项", "表格"),
    ("逐条审一批、需要筛选", "交互网页，用户的选择存下来由 agent 读取"),
    ("用户要看命令输出或改动细节", "代码块、diff 视图、改前改后截图"),
    ("教会别人", "先出脚本给用户确认，报出预计花费，再生成视频"),
    ("问答或只读检查完成、不属于上面任一种", "短结论 + 必要的图、表格或编号列表，不套四块"),
)

CLOSING_HEADINGS = (
    "1. **结果**",
    "2. **要你定**",
    "3. **你没要求的改动**",
    "4. **局限**",
)


def prompt_text() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def section_text(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end < 0 else text[start:end]


def section(heading: str) -> str:
    return section_text(prompt_text(), heading)


def ladder_rows_from(section_body: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in section_body.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].isdigit():
            cells = cells[1:]
        if len(cells) != 2 or cells[0] in {"内容", "---"}:
            continue
        rows.append((cells[0], cells[1]))
    return rows


def ladder_rows() -> list[tuple[str, str]]:
    return ladder_rows_from(section("## 呈现形式"))


class FormatLadderTest(unittest.TestCase):
    def test_every_branch_keeps_its_priority_and_output_form(self) -> None:
        rows = ladder_rows()
        self.assertEqual(len(rows), len(EXPECTED_LADDER))
        for priority, expected in enumerate(EXPECTED_LADDER, start=1):
            with self.subTest(priority=priority, branch=expected[0]):
                self.assertEqual(rows[priority - 1], expected)

    def test_crossing_rows_resolve_by_specificity(self) -> None:
        text = section("## 呈现形式")
        self.assertIn("同一回复命中多行时，取更具体的一行。", text)
        self.assertIn("有改动的任务即使一句话能说清，收尾仍按「收尾」一节的四块。", text)

    def test_read_only_completion_skips_closing_template(self) -> None:
        text = section("## 收尾")
        self.assertIn("没有改动的回复（问答、只读检查）不套四块、不写记录", text)

    def test_diagram_trigger_stays_independent_of_ladder_order(self) -> None:
        text = section("## 呈现形式")
        self.assertIn("出图不受上表顺序限制。", text)
        self.assertIn("用户表示没看懂、想看整体或要通俗解释", text)
        self.assertIn("三方以上来回交互、分支或状态变化、或分阶段且各有进入条件", text)
        self.assertIn("线性步骤、少量对比、填写说明不出图。", text)
        self.assertIn("解释类请求以图为主答案：先给一句结论，再给图", text)
        self.assertIn("图后最多补 3 条图里放不下的前提、边界或证据，不写步骤清单，不逐节点复述。", text)

    def test_command_and_diff_output_requires_an_explicit_request(self) -> None:
        rows = dict(ladder_rows())
        self.assertEqual(rows["用户要看命令输出或改动细节"], "代码块、diff 视图、改前改后截图")
        self.assertNotIn("命令、代码改动、界面改动", rows)

    def test_closing_blocks_keep_order_and_attachment_slot(self) -> None:
        text = section("## 收尾")
        positions = [text.index(heading) for heading in CLOSING_HEADINGS]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("四块是摘要结构，不是回复的全部。", text)
        self.assertIn(
            "用户要看图、表格、命令输出、diff 或截图时，放在「结果」句之后；记录路径始终是最后一行。",
            text,
        )
        self.assertIn("回复最后一行给收尾记录的路径", text)

    def test_archive_snapshot_matches_prompt_sections(self) -> None:
        doc = DOC_PATH.read_text(encoding="utf-8")
        self.assertIn("scripts/agent_prompt.md", doc)
        self.assertEqual(doc.count(SNAPSHOT_START), 1)
        self.assertEqual(doc.count(SNAPSHOT_END), 1)
        start = doc.index(SNAPSHOT_START) + len(SNAPSHOT_START)
        end = doc.index(SNAPSHOT_END)
        archived = doc[start:end].strip()
        prompt = prompt_text()
        expected = "\n\n".join(
            (
                section_text(prompt, "## 呈现形式").strip(),
                section_text(prompt, "## 收尾").strip(),
            )
        )
        self.assertEqual(archived, expected)


if __name__ == "__main__":
    unittest.main()
