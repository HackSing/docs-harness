"""CLI 公开面与源码守卫：命令注册、包导出、提示词面同步。"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT, HARNESS, NPM_COMMAND

sys.path.insert(0, str(ROOT / "scripts"))

from harness import MANAGED_MODULE_RELATIVE_FILES  # noqa: E402

# CPython ≤3.9 把 .py 当脚本运行时，tokenizer 每次 fgets 只读 BUFSIZ-1 字节并逐块校验 UTF-8，
# 多字节字符跨读块边界就误报 "Non-UTF-8 code ... but no encoding declared"（2.20.0 起 macOS
# 系统 Python 3.9.6 运行 harness.py 即失败）。import 与 py_compile 整文件解码，不受影响。
# BUFSIZ 取常见平台最小值：macOS 1024（实测）、Windows MSVC 512、glibc 8192；含非 ASCII 的
# 物理行不超过 511 字节，任何读块都装得下整行。长正文在三引号内用行尾反斜杠续行，字符串值不变。
PY39_TOKENIZER_CHUNK_BYTES = 511


def _readme_minimum_python() -> tuple[int, int]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"Python (\d+)\.(\d+) 或更高版本", readme)
    if match is None:
        raise AssertionError("README.md 缺少「Python X.Y 或更高版本」的环境要求")
    return int(match.group(1)), int(match.group(2))


def _find_python(version: tuple[int, int]) -> str | None:
    """找本机该版本的解释器：PATH 上的 pythonX.Y，或 macOS 开发者工具自带的 python3。

    直接用开发者目录里的真身而不是 /usr/bin/python3 垫片：未装命令行工具时垫片会弹安装框。
    """
    candidates = [shutil.which(f"python{version[0]}.{version[1]}")]
    if sys.platform == "darwin":
        developer = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True, check=False)
        if developer.returncode == 0:
            candidates.append(str(Path(developer.stdout.strip()) / "usr" / "bin" / "python3"))
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        probe = subprocess.run(
            [candidate, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
            capture_output=True, text=True, check=False,
        )
        if probe.returncode == 0 and probe.stdout.strip() == f"{version[0]}.{version[1]}":
            return candidate
    return None


class CliSurfaceTest(HarnessTestBase):
    def test_script_sources_fit_py39_tokenizer_chunks(self) -> None:
        offenders = [
            f"{path.relative_to(ROOT)}:{number}（{len(line)} 字节）"
            for path in sorted((ROOT / "scripts").glob("*.py"))
            for number, line in enumerate(path.read_bytes().split(b"\n"), 1)
            if len(line) > PY39_TOKENIZER_CHUNK_BYTES and not line.isascii()
        ]
        self.assertEqual(
            offenders, [],
            f"含非 ASCII 的物理行超过 {PY39_TOKENIZER_CHUNK_BYTES} 字节，Python 3.9 运行脚本会误报 "
            "Non-UTF-8；三引号正文在中文标点后加行尾反斜杠续行拆短",
        )
    def test_harness_script_runs_under_minimum_python(self) -> None:
        minimum = _readme_minimum_python()
        interpreter = _find_python(minimum)
        if interpreter is None:
            self.skipTest(f"本机没有 Python {minimum[0]}.{minimum[1]} 解释器")
        result = subprocess.run(
            [interpreter, str(HARNESS), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"{interpreter}: {result.stderr}")
    def test_ci_matrix_starts_with_minimum_python(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "assets-check.yml").read_text(encoding="utf-8")
        match = re.search(r'python-version: \["(\d+)\.(\d+)"', workflow)
        self.assertIsNotNone(match, "assets-check.yml 的 matrix.python-version 首项应为最低版本")
        self.assertEqual((int(match.group(1)), int(match.group(2))), _readme_minimum_python())
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
            "assets-check", "structure", "usage", "view", "self-test",
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
    def test_package_files_cover_every_managed_module(self) -> None:
        """npm 包必须带齐全部受管模块。

        同类缺陷已出现三次：2.9.0 漏 script_hygiene.py、2.11.0 漏 structure_check.py、
        2.16.0 漏 usage_log.py 与 usage_report.py。手工维护的 files 清单与
        MANAGED_MODULE_RELATIVE_FILES 各自演进，漏项只在下游 npm 安装后炸成
        ModuleNotFoundError，本仓库测试全绿。此处按真源逐项比对，堵掉第四次。
        """
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        listed = set(package["files"])
        missing = [
            f"scripts/{name}"
            for name in MANAGED_MODULE_RELATIVE_FILES
            if f"scripts/{name}" not in listed
        ]
        self.assertEqual(missing, [], f"package.json files 缺少受管模块：{missing}")

    def test_package_files_entries_all_exist(self) -> None:
        """files 每一项都必须真实存在。

        与上一条守卫互补、不合并：那条防漏项（真源 → 清单），这条防死项（清单 → 磁盘）。
        2.16.1 发现 files 长期带着 tests/test_v2_direct.py 这个已删文件——npm pack 对
        不存在的条目静默跳过，清单因此可以无限期腐烂而无人察觉。
        """
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        dead = [
            entry
            for entry in package["files"]
            if not (
                (ROOT / entry.rstrip("/")).is_dir()
                if entry.endswith("/")
                else (ROOT / entry).exists()
            )
        ]
        self.assertEqual(dead, [], f"package.json files 含不存在的条目：{dead}")

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
        # 2.11.1 修复 git 钩子安装（shim 共存模式 + 钩子健康检查 + uninstall 清理），
        # 控制器只增钩子健康检查段，上限随之上调。
        # 2.13.0 创建体验优化（plan select 知识注入与 sha256 selection 缓存、
        # plan/acceptance create --dry-run 整体校验、结算泄漏 WARN），控制器只增
        # 命令面与校验编排，校验逻辑下沉在 plan_governance/acceptance_assets，上限随之上调。
        # 2.16.1 收尾四项（下游结构检查排除集与源包判定、usage 首开提示、inputs 目录
        # 约定），控制器只增判定与安装面接线，上限随之上调——第 7 次上调。
        # 2.18.0 命令摩擦治理（usage 错误码接线、plan check 部分交付第三态、手写方案结算分支），
        # 控制器只增判定与结算分支，聚合逻辑在 usage_report，行数与字节上限随之上调——第 8 次上调。
        # 2.23.0 安装器在 core.filemode=false 时登记钩子 100755（register_githook_index_mode，
        # 与同文件的 check_githook_health 同属钩子安装面），行数上限随之上调——第 9 次上调。
        # 2.27.0 归档移动后 Knowledge source_refs 跟随改写（逻辑在 knowledge_assets，控制器只增
        # plan settle 接线）与非 create 动作拒收 --dry-run，字节上限随之上调——第 10 次上调。
        # 2.28.0 view 命令（Mermaid → HTML，渲染/落盘/打开在 diagram_view，控制器只增注册面与错误码映射）
        # 与受管正文「呈现形式」出图条款重写（约 1.3 KB），行数与字节上限随之上调——第 11 次上调。
        # 两道体量闸的分工：本地由 Structure 增量 WARN 触发结构评估；CI 由本上限硬拦。
        # Structure 增量检查对比 HEAD，提交后增量恒为空，CI 的 assets-check --strict
        # 永远看不到 harness.py 的体量 WARN，所以本上限是 CI 中唯一拦得住 harness.py
        # 无限增长的硬闸，"每次上调都要动测试文件"正是它的守卫方式。
        # 上限的去留由 TODO.md 第 5 条登记的体量债整理任务决定，不在功能任务里处置。
        self.assertLess(HARNESS.stat().st_size, 225_000)
        self.assertLess(len(source.splitlines()), 5_050)
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
        # 规约只在 AGENTS.md 一份：CLAUDE.md 受管区块只导入它，不复制正文。
        self.assertEqual(harness.claude_block(ROOT),
                         f"{harness.CLAUDE_BEGIN}\n@AGENTS.md\n{harness.CLAUDE_END}")
        self.assertNotIn("## 工作流规则", claude)
        # 受管入口不再指向 SKILL.md，改为指向 --help（示例已下沉到 CLI 现场）。
        self.assertNotIn("输入形状见 SKILL.md", agents)
        self.assertIn("python3 scripts/harness.py <cmd> --help", agents)
        self.assertIn("超过 60 行、单个文件超过 600 行时必须进行结构评估", agents)
        self.assertIn("不得仅为满足行数阈值机械切割", agents)
        self.assertNotIn("超过 500 行时必须拆分", agents)
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
