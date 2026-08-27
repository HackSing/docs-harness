"""CLI 公开面与源码守卫：命令注册、包导出、提示词面同步。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT, HARNESS, NPM_COMMAND


class CliSurfaceTest(HarnessTestBase):
    def test_removed_v1_commands_are_absent_from_cli(self) -> None:
        help_result = subprocess.run(
            [sys.executable, str(HARNESS), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        public_commands = {
            "knowledge", "plan", "acceptance", "adr", "project", "release",
            "assets-check", "structure", "self-test",
        }
        for command in public_commands:
            self.assertIn(command, help_result.stdout)
        for command in ("run", "context", "progress", "verify", "task", "background", "authorization"):
            result = subprocess.run(
                [sys.executable, str(HARNESS), command],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2, f"{command}: {result.stdout}\n{result.stderr}")
            self.assertIn("invalid choice", result.stderr)
        self.assertNotIn("--legacy-opt-in", help_result.stdout)
        self.assertFalse((self.project / ".docs-harness").exists())
    def test_package_exposes_only_current_public_docs(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        files = package["files"]
        self.assertNotIn("docs/", files)
        self.assertFalse(any(item.startswith("docs/history/") for item in files))
        self.assertFalse(any("codex_host_adapter" in item for item in files))
        self.assertFalse(any(item == "harness-home" or item.startswith("harness-home/") for item in files))
        self.assertNotIn("tests/test_harness.py", files)
        self.assertTrue(
            {
                "docs/README.md",
                "docs/architecture.md",
                "docs/contracts.md",
                "docs/testing.md",
                "docs/migrations/v2.0.0.md",
                "docs/plans/docs-harness-v2.0.0-direct-first-plan.md",
            }
            <= set(files)
        )
        if shutil.which("npm") is None:
            self.skipTest("npm 不在 PATH 中")
        packed = subprocess.run(
            [*NPM_COMMAND, "pack", "--dry-run", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(packed.returncode, 0, f"{packed.stdout}\n{packed.stderr}")
        packed_paths = {item["path"] for item in json.loads(packed.stdout)[0]["files"]}
        self.assertFalse(any(path.startswith("harness-home/") for path in packed_paths))
        self.assertNotIn("tests/test_harness.py", packed_paths)
    def test_legacy_rule_assets_are_machine_marked_non_default(self) -> None:
        self.assertFalse((ROOT / "harness-home").exists())
    def test_controller_source_has_no_legacy_state_machine_implementation(self) -> None:
        source = HARNESS.read_text(encoding="utf-8")
        # 2.7.0 将资产领域逻辑拆到受管模块；控制器保留历史安装/迁移编排。
        # 2.7.1 把各输入 JSON 的 --help 示例常量下沉到控制器现场（单一真源），
        # 上限相应上调；真正的 anti-legacy 守卫是下方符号黑名单，不受体积影响。
        # settle --input 批量带入（acceptance-settle-input/v1）新增共用校验抽取与
        # 帮助示例，上限再次上调。
        # 2.8.0 接入第四类资产 ADR（命令组、config v10、项目文档脚手架与检查），
        # 上限随注册面上调。
        # 2.10.0 接入 Structure 结构护栏（structure 命令组、受管入口结构护栏段、
        # CODEMAP 脚手架接线），控制器只增注册面，上限上调。此处只守控制器不复活
        # 旧状态机；模块体量由 Structure WARN 触发结构评估，不再以测试硬失败处方。
        self.assertLess(HARNESS.stat().st_size, 180_000)
        self.assertLess(len(source.splitlines()), 4_200)
        for symbol in (
            "def command_run(",
            "def command_context(",
            "def command_progress(",
            "def command_verify(",
            "def command_task(",
            "def command_background(",
            "def load_active_rules(",
            "TASK_SCHEMA =",
            "BACKGROUND_JOB_SCHEMA =",
            "EVIDENCE_RECEIPT_SCHEMA =",
            "def legacy_tombstone(",
            "def add_legacy_tombstone_parser(",
            "--legacy-opt-in",
        ):
            self.assertNotIn(symbol, source)
    def test_prompt_surfaces_carry_input_schemas_and_managed_blocks_synced(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for schema in (
            "docs-harness/knowledge-input/v1",
            "docs-harness/acceptance-target-input/v1",
            "docs-harness/acceptance-input/v3",
            "docs-harness/plan-governance-input/v1",
        ):
            self.assertIn(schema, skill)
        sys.path.insert(0, str(ROOT / "scripts"))
        import harness
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(harness.managed_agent_block(ROOT), agents)
        self.assertIn(harness.claude_block(ROOT), claude)
        # 受管入口不再指向 SKILL.md，改为指向 --help（示例已下沉到 CLI 现场）。
        for surface in (agents, claude):
            self.assertNotIn("输入形状见 SKILL.md", surface)
            self.assertIn("python3 scripts/harness.py <cmd> --help", surface)
            self.assertIn("超过 60 行、单个文件超过 500 行时必须进行结构评估", surface)
            self.assertIn("不得仅为满足行数阈值机械切割", surface)
            self.assertNotIn("超过 500 行时必须拆分", surface)
    def test_cli_help_carries_input_schema_examples(self) -> None:
        cases = {
            ("knowledge", "create"): (
                "docs-harness/knowledge-input/v1",
                "key_symbols",
            ),
            ("acceptance", "record"): (
                "docs-harness/acceptance-input/v3",
                "docs-harness/acceptance-target-input/v1",
                "按状态必填",
            ),
            ("plan", "settle"): (
                "docs-harness/plan-governance-input/v1",
                "updated_knowledge_refs",
            ),
            ("plan", "create"): (
                "plan select 输出的 fields",
                "docs-harness/plan-governance-input/v1",
            ),
        }
        for (command, action), needles in cases.items():
            result = subprocess.run(
                [sys.executable, str(HARNESS), command, action, "--help"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{command} {action}: {result.stderr}")
            for needle in needles:
                self.assertIn(needle, result.stdout, f"{command} {action} 缺少 {needle}")
    def test_docs_check_command_removed(self) -> None:
        result = subprocess.run(
            [sys.executable, str(HARNESS), "docs-check", "--target", str(self.project)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
