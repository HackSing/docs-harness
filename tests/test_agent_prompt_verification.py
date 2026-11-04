"""受管入口「验证默认后台」与合同文本的确定性守卫。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import ROOT

PROMPT_PATH = ROOT / "scripts" / "agent_prompt.md"
AGENTS_PATH = ROOT / "AGENTS.md"
CONTRACTS_PATH = ROOT / "docs" / "contracts.md"
TESTING_PATH = ROOT / "docs" / "testing.md"
RUNTIME_README_PATH = ROOT / "docs" / "runtime-verification" / "README.md"


class BackgroundVerificationPromptTest(unittest.TestCase):
    def test_default_route_is_background_and_interruption_is_forbidden(self) -> None:
        text = PROMPT_PATH.read_text(encoding="utf-8")
        self.assertIn("- 验证默认后台：", text)
        for phrase in (
            "后台进程",
            "隐藏窗口",
            "离屏渲染",
            "headless",
            "不得弹出可见窗口",
            "抢焦点",
            "不得自动打开资源管理器、图片查看器或文件夹",
        ):
            self.assertIn(phrase, text)

    def test_foreground_exception_requires_announcement_and_record(self) -> None:
        text = PROMPT_PATH.read_text(encoding="utf-8")
        for phrase in (
            "只有真实硬件、系统权限、原生弹窗等确实无法后台的验证才上前台",
            "会出现什么窗口、持续多久、为什么必须前台",
            "恢复用户原前台窗口",
            "未提前说明的前台验证视为未完成",
            "收尾写明前台/后台、显示了什么、持续多久",
        ):
            self.assertIn(phrase, text)

    def test_closeout_record_declares_interaction_mode(self) -> None:
        text = PROMPT_PATH.read_text(encoding="utf-8")
        self.assertIn("运行态任务另写证据包路径、runtime check 退出码与前台/后台验证说明", text)

    def test_managed_agents_block_carries_the_same_rule(self) -> None:
        self.assertIn("验证默认后台", AGENTS_PATH.read_text(encoding="utf-8"))


class BackgroundVerificationContractTest(unittest.TestCase):
    def test_contract_lists_background_layers(self) -> None:
        text = CONTRACTS_PATH.read_text(encoding="utf-8")
        self.assertIn("## 4c. 验证默认后台", text)
        for phrase in (
            "后台进程执行",
            "webContents.capturePage",
            "RenderTargetBitmap",
            "-no-window",
            "simctl io booted screenshot",
            "独立 profile",
            "真实硬件、系统权限、原生弹窗",
        ):
            self.assertIn(phrase, text)

    def test_contract_keeps_foreground_exception_protocol(self) -> None:
        text = CONTRACTS_PATH.read_text(encoding="utf-8")
        for phrase in (
            "先确认后台方案确实不可行",
            "会出现什么窗口、持续多久、为什么必须前台",
            "结束后关闭全部验证窗口，恢复用户原前台窗口",
            "用户正在工作时延后，攒到最后一次集中验证",
            "未提前说明的前台验证视为未完成",
            "全程后台，或已按前台例外协议执行",
        ):
            self.assertIn(phrase, text)

    def test_docs_point_to_the_contract(self) -> None:
        self.assertIn("第 4c 节", TESTING_PATH.read_text(encoding="utf-8"))
        self.assertIn("第 4c 节", RUNTIME_README_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
