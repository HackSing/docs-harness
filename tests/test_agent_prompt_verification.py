"""受管入口「验证默认后台」与合同文本的确定性守卫。"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

import asset_checks  # noqa: E402
import harness  # noqa: E402

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

    def test_live_e2e_rule_present_in_prompt_and_agents(self) -> None:
        prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
        agents_text = AGENTS_PATH.read_text(encoding="utf-8")
        for phrase in (
            "大任务全量实机闭环",
            "live_e2e",
            "pass_criteria",
            "fail_criteria",
            "默认停下等用户确认",
            "禁 mock",
            "deploy_ref",
            "熔断",
            "acceptance_ref",
        ):
            self.assertIn(phrase, prompt_text)
            self.assertIn(phrase, agents_text)

    def test_managed_agent_block_stays_within_budget(self) -> None:
        block = harness.managed_agent_block(ROOT)
        lf_bytes = len(block.encode("utf-8"))
        crlf_bytes = len(block.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
        self.assertLessEqual(lf_bytes, asset_checks.MANAGED_PROMPT_MAX_BYTES)
        self.assertLessEqual(crlf_bytes, asset_checks.MANAGED_PROMPT_MAX_BYTES)
        self.assertLessEqual(AGENTS_PATH.stat().st_size, asset_checks.AGENTS_FILE_MAX_BYTES)

    def test_cli_help_covers_offloaded_guidance(self) -> None:
        cases = {
            "plan": (
                "process_flowchart",
                "ux_journey",
                "Knowledge → Acceptance → Plan",
                "可修改 acceptance_required/knowledge_impact",
            ),
            "knowledge": ("不得全量加载 docs/", "settle --status deprecated|superseded"),
            "acceptance": (
                "docs/acceptance/evidence/",
                "persisted_to=runtime, linked=false",
                "--user-confirmed",
                "live_e2e",
                "pass_criteria",
                "confirm_before_run",
            ),
            "adr": ("adr amend --input", "adr settle --status deprecated|superseded"),
            "runtime": (
                "docs/runtime-verification/<task>/packet.json",
                "ui.viewports",
                "acceptance_ref",
                "deploy_ref",
                "rechecked_criteria",
            ),
            "checklist": ("改动文件与符号", "plan_linked", ".docs-harness/tasks/"),
            "report": ("focused_test", ".docs-harness/reports/", "runtime check 退出码"),
        }
        env = {**os.environ, "PYTHONUTF8": "1"}
        harness_script = str(ROOT / "scripts" / "harness.py")
        for command, needles in cases.items():
            result = subprocess.run(
                [sys.executable, harness_script, command, "--help"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{command}: {result.stderr}")
            for needle in needles:
                self.assertIn(needle, result.stdout, f"{command} --help 缺少 {needle}")


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
