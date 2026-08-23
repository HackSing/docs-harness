from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "harness.py"


def _symlinks_supported() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "target").mkdir()
        try:
            (root / "link").symlink_to(root / "target", target_is_directory=True)
        except OSError:
            return False
    return True


# Windows 默认需要开发者模式或 SeCreateSymbolicLinkPrivilege 才能创建 symlink，
# 无权限环境下 symlink 安全测试无法搭建现场，只能跳过。
REQUIRES_SYMLINK = unittest.skipUnless(
    _symlinks_supported(),
    "当前环境无 symlink 创建权限（Windows 需开发者模式或 SeCreateSymbolicLinkPrivilege）",
)

# Windows 上 npm 是 npm.CMD，CreateProcess 不做 PATHEXT 解析，须经 cmd 调起。
NPM_COMMAND = ["cmd", "/c", "npm"] if os.name == "nt" else ["npm"]


class DocsHarnessV2DirectTest(unittest.TestCase):
    maxDiff = None

    CURRENT_CONFIG_KEYS = {
        "schema_version",
        "version",
        "installed_script_fingerprint",
        "installed_module_fingerprints",
        "installed_plan_template_fingerprints",
        "installed_githook_fingerprints",
        "direct_mode",
        "knowledge",
        "migration",
        "installed_at",
    }
    LEGACY_CONFIG_KEYS = {
        "rules_root",
        "installed_rule_fingerprints",
        "background_governance",
        "gate_path_rules",
    }

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, name: str, value: object) -> Path:
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def snapshot_project(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for path in sorted(self.project.rglob("*")):
            relative = path.relative_to(self.project).as_posix()
            if path.is_symlink():
                snapshot[relative] = f"symlink:{os.readlink(path)}"
            elif path.is_dir():
                snapshot[relative] = "directory"
            else:
                snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return snapshot

    def write_v5_install(
        self,
        *,
        installed_rules: dict[str, str],
        live_rules: dict[str, str] | None = None,
    ) -> dict[str, object]:
        rules_root = self.project / ".docs-harness" / "harness-home" / "rules"
        rules_root.mkdir(parents=True, exist_ok=True)
        current_rules = installed_rules if live_rules is None else live_rules
        for name, content in current_rules.items():
            (rules_root / name).write_bytes(content.encode("utf-8"))
        installed_fingerprints = {
            name: "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
            for name, content in installed_rules.items()
        }
        config: dict[str, object] = {
            "schema_version": "docs-harness/project-config/v5",
            "version": "1.8.2",
            "rules_root": ".docs-harness/harness-home/rules",
            "installed_rule_fingerprints": installed_fingerprints,
            "installed_script_fingerprint": "sha256:" + "0" * 64,
            "installed_plan_template_fingerprints": {},
            "direct_mode": {"default": False, "task_level_gates": True},
            "knowledge": {
                "mode": "managed",
                "bootstrap_async": True,
                "docs_preexisting_at_install": True,
            },
            "background_governance": {"enabled": True, "auto_dispatch": True},
            "gate_path_rules": [{"pattern": "**", "gates": ["code-edit"]}],
            "installed_at": "2026-08-08T00:00:00Z",
        }
        self.write_json(".docs-harness/config.json", config)
        return config

    def run_cli(self, *args: str, expected: int = 0) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(HARNESS), *args, "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, expected, f"{result.stdout}\n{result.stderr}")
        return json.loads(result.stdout)

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
            "assets-check", "self-test",
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

    def knowledge_input(self, title: str, statement: str) -> dict[str, object]:
        return {
            "schema_version": "docs-harness/knowledge-input/v1",
            "title": title,
            "key_symbols": ["KnowledgeOwner", "current_fact"],
            "summary": "当前项目事实。",
            "facts": [
                {
                    "id": "runtime.owner",
                    "statement": statement,
                    "source_refs": ["src/runtime.txt:1"],
                }
            ],
        }

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
        # 2.7.0 将资产领域逻辑拆到受管模块；控制器保留历史安装/迁移编排，
        # 继续设硬上限，新增领域模块各自遵守 500 行红线。
        # 2.7.1 把各输入 JSON 的 --help 示例常量下沉到控制器现场（单一真源），
        # 上限相应上调；真正的 anti-legacy 守卫是下方符号黑名单，不受体积影响。
        # settle --input 批量带入（acceptance-settle-input/v1）新增共用校验抽取与
        # 帮助示例，上限再次上调；受管模块红线同步由 400 行放宽至 500 行。
        # 2.8.0 接入第四类资产 ADR（命令组、config v10、项目文档脚手架与检查），
        # 上限随注册面上调。
        self.assertLess(HARNESS.stat().st_size, 175_000)
        self.assertLess(len(source.splitlines()), 4_200)
        for module in (
            "managed_assets.py", "asset_checks.py", "plan_governance.py",
            "knowledge_assets.py", "acceptance_assets.py", "adr_assets.py",
            "script_hygiene.py",
        ):
            self.assertLess(len((ROOT / "scripts" / module).read_text(encoding="utf-8").splitlines()), 500)
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

    def test_project_init_bootstraps_docs_system(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        payload = self.run_cli("plan", "check", "--target", str(self.project))
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["failures"], [])
        self.assertTrue((self.project / "docs/plans/README.md").is_file())
        self.assertTrue((self.project / "docs/plans/archive/.gitkeep").is_file())
        self.assertTrue((self.project / "docs/knowledge/README.md").is_file())
        self.assertTrue((self.project / "docs/acceptance/README.md").is_file())
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("docs-harness:plans-index:start", index)
        self.assertIn("docs-harness:plans-index:end", index)
        self.assertIn("docs-harness:knowledge-index:start", index)
        self.assertIn("docs-harness:acceptance-index:start", index)

    def test_plan_check_fails_when_docs_system_is_missing(self) -> None:
        payload = self.run_cli("plan", "check", "--target", str(self.project), expected=1)
        self.assertEqual(payload["status"], "failed")
        self.assertTrue(any("project init/upgrade" in item for item in payload["failures"]))

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

    def test_init_creates_project_doc_scaffolds_idempotently(self) -> None:
        (self.project / "README.md").write_text("# 我的项目\n\n自定义正文。\n", encoding="utf-8")
        self.run_cli("project", "init", "--target", str(self.project))
        self.assertEqual(
            (self.project / "README.md").read_text(encoding="utf-8"),
            "# 我的项目\n\n自定义正文。\n",
        )
        self.assertTrue((self.project / "CHANGELOG.md").is_file())
        self.assertTrue((self.project / "TODO.md").is_file())
        self.assertTrue((self.project / "docs/adr/README.md").is_file())
        before = self.snapshot_project()
        self.run_cli("project", "init", "--target", str(self.project))
        self.assertEqual(self.snapshot_project(), before)

    def test_project_check_flags_missing_and_malformed_project_docs(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        payload = self.run_cli("project", "check", "--target", str(self.project))
        self.assertNotIn("project_todo_missing", [f["code"] for f in payload["findings"]])
        (self.project / "TODO.md").unlink()
        payload = self.run_cli("project", "check", "--target", str(self.project), expected=1)
        self.assertIn("project_todo_missing", [f["code"] for f in payload["findings"]])
        (self.project / "TODO.md").write_text(
            "# TODO\n\n## 待办\n\n- [ ] 随便写的一条\n", encoding="utf-8"
        )
        payload = self.run_cli("project", "check", "--target", str(self.project))
        codes = {f["code"]: f["severity"] for f in payload["findings"]}
        self.assertEqual(codes.get("project_todo_format"), "yellow")

    def test_release_sync_strict_requires_changelog_top_version(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        (self.project / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts" / "harness.py", self.project / "scripts" / "harness.py")
        shutil.copytree(ROOT / "plan-templates", self.project / "plan-templates")
        (self.project / "evals").mkdir()
        shutil.copy2(ROOT / "evals" / "evals.json", self.project / "evals" / "evals.json")
        (self.project / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (self.project / "package.json").write_text(
            json.dumps({"version": version}) + "\n", encoding="utf-8"
        )
        (self.project / "SKILL.md").write_text(
            f"---\nmetadata:\n  version: {version}\n---\n", encoding="utf-8"
        )
        (self.project / "CHANGELOG.md").write_text(
            "# Changelog\n\n## 0.0.1 - 2026-01-01\n\n- 旧条目\n", encoding="utf-8"
        )
        relaxed = self.run_cli("release", "sync", "--target", str(self.project))
        self.assertEqual(relaxed["status"], "consistent")
        strict = self.run_cli(
            "release", "sync", "--target", str(self.project), "--strict", expected=1
        )
        self.assertEqual(strict["status"], "inconsistent")
        self.assertTrue(strict["strict_failures"])
        (self.project / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## {version} - 2026-08-16\n\n- 新条目\n", encoding="utf-8"
        )
        fixed = self.run_cli("release", "sync", "--target", str(self.project), "--strict")
        self.assertEqual(fixed["status"], "consistent")

    def test_assets_check_passes_for_initialized_zero_asset_project(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        payload = self.run_cli("assets-check", "--target", str(self.project))
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["checked"]["knowledge"], 0)
        self.assertEqual(payload["checked"]["acceptance"], 0)
        self.assertEqual(
            payload["checked"]["script_hygiene"], 0,
            "非 git 目标应跳过 ScriptHygiene（checked=0，不产生 WARN）",
        )

    def test_assets_check_rejects_tampered_knowledge_asset(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True)
        source.write_text("KnowledgeOwner owns the runtime.\n", encoding="utf-8")
        value = self.write_json(
            "inputs/knowledge.json",
            self.knowledge_input("运行时所有权", "KnowledgeOwner 拥有运行时。"),
        )
        self.run_cli(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(value.relative_to(self.project)),
            "--output", "docs/knowledge/runtime-owner.json",
        )
        asset_path = self.project / "docs/knowledge/runtime-owner.json"
        asset = json.loads(asset_path.read_text(encoding="utf-8"))
        asset["summary"] = "已被手工篡改"
        self.write_json("docs/knowledge/runtime-owner.json", asset)
        payload = self.run_cli(
            "assets-check", "--target", str(self.project), expected=1
        )
        self.assertTrue(any("资产指纹无效" in item for item in payload["failures"]))

    def test_assets_check_rejects_orphan_managed_index_entry(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        index_path = self.project / "docs/INDEX.md"
        index = index_path.read_text(encoding="utf-8")
        index = index.replace(
            "<!-- docs-harness:knowledge-index:end -->",
            "- [孤儿知识](knowledge/orphan.md) — 状态：有效；关键符号：`A`、`B`\n"
            "<!-- docs-harness:knowledge-index:end -->",
        )
        index_path.write_text(index, encoding="utf-8")
        payload = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", expected=1
        )
        self.assertTrue(any("没有对应活资产" in item for item in payload["failures"]))

    def test_assets_check_rejects_mixed_line_ending_script(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        (self.project / "deploy.sh").write_bytes(b"#!/bin/sh\r\necho mixed\n")
        (self.project / "clean.sh").write_bytes(b"#!/bin/sh\necho clean\n")
        for args in (("git", "init"), ("git", "add", "deploy.sh", "clean.sh")):
            subprocess.run(args, cwd=self.project, capture_output=True, check=True)
        payload = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", expected=1
        )
        self.assertTrue(
            any(
                "ScriptHygiene" in item and "deploy.sh" in item
                for item in payload["failures"]
            )
        )
        self.assertFalse(
            any("clean.sh" in item for item in payload["failures"]),
            "纯 LF 脚本不应被误判为混合行尾",
        )

    def test_assets_check_strict_blocks_slow_warning_but_fast_skips_it(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        selection_path = self.write_json("selection.json", selection)
        content_path = self.write_json(
            "content.json",
            {
                "title": "慢检查告警方案",
                "key_symbols": ["AbsentPlanSymbol", "AbsentPlanConsumer"],
                "objective": "验证 strict 与 fast 边界",
                "scope": ["scripts/harness.py"],
                "steps": ["创建", "结项"],
                "acceptance": ["strict 阻断慢检查 WARN"],
            },
        )
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/slow-warning.json",
        )
        selection_path.unlink()
        content_path.unlink()
        self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/slow-warning.json", "--status", "implemented",
        )
        normal = self.run_cli("assets-check", "--target", str(self.project))
        self.assertTrue(any("零命中" in item for item in normal["warnings"]))
        strict = self.run_cli(
            "assets-check", "--target", str(self.project), "--strict", expected=1
        )
        self.assertEqual(strict["status"], "failed")
        fast = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", "--strict"
        )
        self.assertEqual(fast["status"], "passed")

    def test_plan_check_reports_banner_and_stale_archive_reference(self) -> None:
        docs = self.project / "docs"
        plans = docs / "plans"
        archive = plans / "archive"
        archive.mkdir(parents=True)
        (docs / "INDEX.md").write_text(
            "# 索引\n\n- plans/no-banner.md（关键符号：无）\n"
            "- plans/archive/old-plan.md（已归档）\n",
            encoding="utf-8",
        )
        (plans / "no-banner.md").write_text("# 无横幅文档\n", encoding="utf-8")
        (archive / "old-plan.md").write_text(
            "> 状态：已废弃-被 no-banner.md 取代（2026-08-13 核对）\n\n旧文档。\n",
            encoding="utf-8",
        )
        (docs / "guide.md").write_text(
            "# 指南\n\n参见 docs/plans/old-plan.md 的旧路径。\n", encoding="utf-8"
        )
        payload = self.run_cli("plan", "check", "--target", str(self.project), expected=1)
        self.assertEqual(payload["status"], "failed")
        failures = payload["failures"]
        self.assertTrue(any("缺少状态横幅" in item for item in failures))
        self.assertTrue(any("引用已归档文档旧路径" in item for item in failures))

    def test_plan_select_uses_effects_not_task_text(self) -> None:
        none = self.run_cli("plan", "select", "--target", str(self.project))
        self.assertEqual(none["plan_level"], "none")
        full = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--complexity", "complex", "--surface", "architecture",
        )
        self.assertEqual(full["plan_level"], "full")
        self.assertEqual(full["plan_profile"], "architecture")
        field_ids = {item["id"] for item in full["fields"]}
        self.assertIn("adr_decision", field_ids)
        self.assertNotIn("state_matrix", field_ids)
        self.assertTrue(fields := {item["id"]: item for item in full["fields"]})
        self.assertTrue(fields["acceptance_required"]["guidance"])
        self.assertTrue(fields["knowledge_impact"]["guidance"])

    def full_plan_content(
        self,
        selection: dict[str, object],
        *,
        acceptance_required: bool,
        knowledge_impact: str,
    ) -> dict[str, object]:
        fields = selection["fields"]
        assert isinstance(fields, list)
        content: dict[str, object] = {
            item["id"]: f"已填写 {item['label']}"
            for item in fields
            if isinstance(item, dict)
        }
        content.update({
            "title": "三资产治理方案",
            "key_symbols": ["PlanGovernance", "AcceptanceBackref"],
            "acceptance_required": acceptance_required,
            "knowledge_impact": knowledge_impact,
        })
        return content

    def create_full_plan(
        self,
        *,
        acceptance_required: bool,
        knowledge_impact: str,
        basename: str = "governed",
    ) -> Path:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "full", "--profile", "general",
        )
        selection_path = self.write_json(f"inputs/{basename}-selection.json", selection)
        content_path = self.write_json(
            f"inputs/{basename}-content.json",
            self.full_plan_content(
                selection,
                acceptance_required=acceptance_required,
                knowledge_impact=knowledge_impact,
            ),
        )
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path.relative_to(self.project)),
            "--content", str(content_path.relative_to(self.project)),
            "--output", f"docs/plans/{basename}.json",
        )
        return self.project / f"docs/plans/{basename}.json"

    def test_plan_v3_acceptance_backref_and_governance_settlement(self) -> None:
        plan_path = self.create_full_plan(
            acceptance_required=True,
            knowledge_impact="unchanged",
        )
        frozen = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(frozen["schema_version"], "docs-harness/plan/v3")
        self.assertEqual(frozen["acceptance_refs"], [])
        self.assertTrue(frozen["governance"]["acceptance_required"])

        target = self.acceptance_target("contract_check")
        target["plan_ref"] = "docs/plans/governed.json"
        acceptance_input = self.write_json("inputs/governed-acceptance.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(acceptance_input.relative_to(self.project)),
            "--output", "docs/acceptance/governed.json",
        )
        frozen = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(frozen["acceptance_refs"], ["docs/acceptance/governed.json"])
        markdown = plan_path.with_suffix(".md").read_text(encoding="utf-8")
        self.assertIn("docs/acceptance/governed.json", markdown)

        governance_input = self.write_json(
            "inputs/governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "unchanged_reason": "本次只改变资产治理流程，不产生新的项目事实。",
            },
        )
        rejected = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/governed.json", "--status", "implemented",
            "--governance-input", str(governance_input.relative_to(self.project)),
            expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_plan_governance")
        self.assertIn("acceptance", rejected["message"])

        evidence = self.project / "contract-evidence.txt"
        evidence.write_text("contract passed\n", encoding="utf-8")
        record = self.write_json(
            "inputs/governed-record.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "method": "检查治理合同",
                "evidence_refs": ["contract-evidence.txt"],
            },
        )
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/governed.json",
        )
        self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/governed.json", "--status", "passed",
        )
        settled = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/governed.json", "--status", "implemented",
            "--governance-input", str(governance_input.relative_to(self.project)),
        )
        self.assertEqual(settled["warnings"], [])
        frozen = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertTrue(frozen["governance"]["governance_settled_at"])
        self.assertEqual(
            frozen["governance"]["unchanged_reason"],
            "本次只改变资产治理流程，不产生新的项目事实。",
        )

    def test_plan_v3_updated_knowledge_requires_active_refs(self) -> None:
        self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="updated",
            basename="knowledge-updated",
        )
        missing = self.write_json(
            "inputs/missing-knowledge-governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "updated_knowledge_refs": [],
            },
        )
        rejected = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/knowledge-updated.json", "--status", "implemented",
            "--governance-input", str(missing.relative_to(self.project)), expected=2,
        )
        self.assertIn("updated_knowledge_refs", rejected["message"])
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("KnowledgeOwner owns the runtime.\n", encoding="utf-8")
        value = self.write_json(
            "inputs/knowledge.json",
            self.knowledge_input("运行时所有权", "KnowledgeOwner 拥有运行时。"),
        )
        self.run_cli(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(value.relative_to(self.project)),
            "--output", "docs/knowledge/runtime-owner.json",
        )
        valid = self.write_json(
            "inputs/valid-knowledge-governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "updated_knowledge_refs": ["docs/knowledge/runtime-owner.json"],
            },
        )
        settled = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/knowledge-updated.json", "--status", "implemented",
            "--governance-input", str(valid.relative_to(self.project)),
        )
        self.assertEqual(settled["status"], "implemented")

    def test_plan_v3_allows_failed_terminal_acceptance_with_warning(self) -> None:
        self.create_full_plan(
            acceptance_required=True,
            knowledge_impact="unchanged",
            basename="failed-acceptance",
        )
        target = self.acceptance_target("contract_check")
        target["plan_ref"] = "docs/plans/failed-acceptance.json"
        target_input = self.write_json("inputs/failed-target.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/failed-target.json",
        )
        evidence = self.project / "failed-contract.txt"
        evidence.write_text("contract failed\n", encoding="utf-8")
        record = self.write_json(
            "inputs/failed-record.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "contract_check",
                "status": "failed",
                "layer": "L1",
                "reason": "治理合同未通过",
                "next_action": "收尾报告说明失败结果",
                "failure_attributions": [{
                    "category": "change_related",
                    "summary": "合同结果不符合预期",
                    "blocking": True,
                    "evidence_refs": ["failed-contract.txt"]
                }]
            },
        )
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/failed-target.json", expected=3,
        )
        self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/failed-target.json", "--status", "failed",
        )
        governance_input = self.write_json(
            "inputs/failed-governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "unchanged_reason": "失败验收不产生 Knowledge 更新。",
            },
        )
        settled = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/failed-acceptance.json", "--status", "implemented",
            "--governance-input", str(governance_input.relative_to(self.project)),
        )
        self.assertTrue(any("failed" in item for item in settled["warnings"]))

    def test_acceptance_supersede_removes_plan_backref(self) -> None:
        plan_path = self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="unchanged",
            basename="supersede-backref",
        )
        for name in ("old", "new"):
            target = self.acceptance_target("contract_check")
            target["plan_ref"] = "docs/plans/supersede-backref.json"
            target_input = self.write_json(f"inputs/{name}-target.json", target)
            self.run_cli(
                "acceptance", "create", "--target", str(self.project),
                "--input", str(target_input.relative_to(self.project)),
                "--output", f"docs/acceptance/{name}.json",
            )
        self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/old.json", "--status", "superseded",
            "--replacement", "docs/acceptance/new.json",
        )
        frozen = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(frozen["acceptance_refs"], ["docs/acceptance/new.json"])

    def test_assets_check_warns_when_plan_declaration_conflicts_with_refs(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="unchanged",
            basename="declaration-conflict",
        )
        target = self.acceptance_target("contract_check")
        target["plan_ref"] = "docs/plans/declaration-conflict.json"
        target_input = self.write_json("inputs/conflict-target.json", target)
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/declaration-conflict.json",
        )
        payload = self.run_cli("assets-check", "--target", str(self.project), "--fast")
        self.assertTrue(any("acceptance_required=false" in item for item in payload["warnings"]))
        strict = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", "--strict",
            expected=1,
        )
        self.assertEqual(strict["status"], "failed")

    def test_assets_check_fails_when_settled_knowledge_is_archived(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.create_full_plan(
            acceptance_required=False,
            knowledge_impact="updated",
            basename="archived-knowledge",
        )
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("KnowledgeOwner owns the runtime.\n", encoding="utf-8")
        value = self.write_json(
            "inputs/archived-knowledge.json",
            self.knowledge_input("运行时所有权", "KnowledgeOwner 拥有运行时。"),
        )
        self.run_cli(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(value.relative_to(self.project)),
            "--output", "docs/knowledge/archive-me.json",
        )
        governance = self.write_json(
            "inputs/archive-governance.json",
            {
                "schema_version": "docs-harness/plan-governance-input/v1",
                "updated_knowledge_refs": ["docs/knowledge/archive-me.json"],
            },
        )
        self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/archived-knowledge.json", "--status", "implemented",
            "--governance-input", str(governance.relative_to(self.project)),
        )
        self.run_cli(
            "knowledge", "settle", "--target", str(self.project),
            "--knowledge", "docs/knowledge/archive-me.json", "--status", "deprecated",
        )
        payload = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", expected=1
        )
        self.assertTrue(any("结算 Knowledge" in item for item in payload["failures"]))

    def test_bugfix_profile_requires_structured_verification_contract(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "full", "--profile", "bugfix",
        )
        fields = {item["id"]: item for item in selection["fields"]}
        for field_id in (
            "affected_modules",
            "verification_scope",
            "full_regression_trigger",
            "failure_attribution",
        ):
            self.assertIn(field_id, fields)
            self.assertTrue(fields[field_id]["required"])
            self.assertTrue(fields[field_id]["guidance"])

        content = {item["id"]: f"已填写 {item['label']}" for item in selection["fields"]}
        content.update(
            {
                "title": "Session Bugfix 方案",
                "key_symbols": ["SessionService", "SessionStore"],
                "acceptance_required": False,
                "knowledge_impact": "unchanged",
                "affected_modules": ["service/session", "tests/session"],
                "verification_scope": {
                    "mode": "affected_modules",
                    "commands": ["python -m unittest tests.test_session"],
                    "reused_passed_evidence": ["上一轮相同输入快照的类型检查"],
                },
                "full_regression_trigger": {
                    "required": False,
                    "reason_codes": [],
                    "rationale": "改动与调用链均限制在 session 模块",
                },
                "failure_attribution": {
                    "categories": [
                        "change_related",
                        "unrelated",
                        "pre_existing",
                        "environment",
                        "flaky",
                    ],
                    "separate_non_change_failures": True,
                    "evidence_required": True,
                },
            }
        )
        selection_path = self.write_json("bugfix-selection.json", selection)
        content_path = self.write_json("bugfix-content.json", content)
        payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/bugfix.json",
        )
        self.assertEqual(payload["execution_projection"]["affected_modules"], content["affected_modules"])
        self.assertEqual(
            payload["execution_projection"]["verification_scope"]["mode"],
            "affected_modules",
        )

        full_content = dict(content)
        full_content["verification_scope"] = {
            "mode": "repository_full",
            "commands": ["npm test"],
            "reused_passed_evidence": [],
        }
        full_content["full_regression_trigger"] = {
            "required": True,
            "reason_codes": ["public_contract_change"],
            "rationale": "验收输入 Schema 是对外公共契约",
        }
        full_content_path = self.write_json("bugfix-full-content.json", full_content)
        full_payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(full_content_path),
            "--output", "docs/plans/bugfix-full.json",
        )
        self.assertEqual(
            full_payload["execution_projection"]["full_regression_trigger"]["reason_codes"],
            ["public_contract_change"],
        )

        invalid = dict(content)
        invalid["verification_scope"] = {
            "mode": "repository_full",
            "commands": ["npm test"],
            "reused_passed_evidence": [],
        }
        invalid_path = self.write_json("bugfix-invalid.json", invalid)
        rejected = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(invalid_path),
            "--output", "docs/plans/bugfix-invalid.json", expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_plan_content")

    def test_plan_create_validates_and_freezes_only_selected_fields(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "frontend_ui",
        )
        selection_path = self.write_json("selection.json", selection)
        content = {
            "title": "前端确认状态修复方案",
            "key_symbols": ["ConfirmPage", "confirmState"],
            "objective": "修复前端确认状态",
            "scope": ["web/confirm.tsx"],
            "steps": ["复现", "修复", "走真实页面流程"],
            "acceptance": ["启动页面并完成确认流程"],
        }
        content_path = self.write_json("content.json", content)
        payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/fix.json",
        )
        self.assertEqual(payload["status"], "frozen")
        frozen = json.loads((self.project / "docs/plans/fix.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen["content"], content)
        self.assertNotIn("state_matrix", frozen["content"])
        document = self.project / "docs/plans/fix.md"
        self.assertIn("docs-harness:plan-document/v1", document.read_text(encoding="utf-8"))
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("plans/fix.md", index)
        self.assertIn("`ConfirmPage`", index)

        before = (self.project / "docs/plans/fix.json").read_bytes()
        repeated = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/fix.json",
        )
        self.assertEqual(repeated["status"], "frozen")
        self.assertEqual((self.project / "docs/plans/fix.json").read_bytes(), before)
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertEqual(index.count("plans/fix.md"), 1)

    def test_plan_settle_implements_and_archives_managed_plan(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        selection_path = self.write_json("selection.json", selection)
        content = {
            "title": "可归档任务方案",
            "key_symbols": ["PlanOwner", "PlanConsumer"],
            "objective": "验证方案生命周期",
            "scope": ["scripts/harness.py"],
            "steps": ["创建", "完成", "归档"],
            "acceptance": ["plan check 通过"],
        }
        content_path = self.write_json("content.json", content)
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/lifecycle.json",
        )
        implemented = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/lifecycle.json", "--status", "implemented",
        )
        self.assertEqual(implemented["status"], "implemented")
        document = self.project / "docs/plans/lifecycle.md"
        self.assertIn("已实施-仅追溯", document.read_text(encoding="utf-8"))
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("状态：已实施-仅追溯", index)

        deprecated = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/lifecycle.json", "--status", "deprecated",
            "--replacement", "next-plan.md",
        )
        self.assertEqual(deprecated["status"], "deprecated")
        self.assertFalse(document.exists())
        self.assertTrue((self.project / "docs/plans/archive/lifecycle.md").is_file())
        self.assertTrue((self.project / "docs/plans/archive/lifecycle.json").is_file())
        index = (self.project / "docs/INDEX.md").read_text(encoding="utf-8")
        self.assertNotIn("plans/lifecycle.md", index)
        checked = self.run_cli("plan", "check", "--target", str(self.project))
        self.assertEqual(checked["status"], "passed")

    def test_plan_settle_migrates_pre_250_frozen_identity(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        selection_path = self.write_json("selection.json", selection)
        content_path = self.write_json(
            "content.json",
            {
                "title": "旧冻结方案",
                "key_symbols": ["LegacyPlan", "PlanConsumer"],
                "objective": "兼容旧方案",
                "scope": ["scripts/harness.py"],
                "steps": ["迁移"],
                "acceptance": ["完成状态可写入"],
            },
        )
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/legacy.json",
        )
        frozen_path = self.project / "docs/plans/legacy.json"
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        frozen["schema_version"] = "docs-harness/plan/v2"
        frozen.pop("acceptance_refs")
        frozen.pop("governance", None)
        frozen["content"].pop("title")
        frozen["content"].pop("key_symbols")
        unsigned = dict(frozen)
        unsigned.pop("plan_fingerprint")
        frozen["plan_fingerprint"] = "sha256:" + hashlib.sha256(
            json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.write_json("docs/plans/legacy.json", frozen)
        payload = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/legacy.json", "--status", "implemented",
        )
        self.assertEqual(payload["status"], "implemented")
        self.assertIn(
            "已实施-仅追溯",
            (self.project / "docs/plans/legacy.md").read_text(encoding="utf-8"),
        )

    def test_plan_settle_rejects_tampered_frozen_fingerprint(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "general",
        )
        selection_path = self.write_json("selection.json", selection)
        content_path = self.write_json(
            "content.json",
            {
                "title": "指纹保护方案",
                "key_symbols": ["PlanFingerprint", "PlanConsumer"],
                "objective": "拒绝篡改",
                "scope": ["scripts/harness.py"],
                "steps": ["校验"],
                "acceptance": ["篡改被拒绝"],
            },
        )
        self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/tampered-fingerprint.json",
        )
        frozen_path = self.project / "docs/plans/tampered-fingerprint.json"
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        frozen["content"]["objective"] = "已被篡改"
        self.write_json("docs/plans/tampered-fingerprint.json", frozen)
        payload = self.run_cli(
            "plan", "settle", "--target", str(self.project),
            "--plan", "docs/plans/tampered-fingerprint.json",
            "--status", "implemented", expected=2,
        )
        self.assertEqual(payload["code"], "invalid_plan_ref")

    def test_plan_create_rejects_re_fingerprinted_unregistered_fields(self) -> None:
        selection = self.run_cli(
            "plan", "select", "--target", str(self.project),
            "--level", "brief", "--profile", "frontend_ui",
        )
        selection["fields"].append({"id": "controller_dump", "label": "控制器全集", "required": True})
        unsigned = {key: value for key, value in selection.items() if key != "selection_fingerprint"}
        selection["selection_fingerprint"] = "sha256:" + hashlib.sha256(
            json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        selection_path = self.write_json("tampered-selection.json", selection)
        content_path = self.write_json(
            "tampered-content.json",
            {
                "objective": "修复页面",
                "scope": ["web/page.tsx"],
                "steps": ["修复"],
                "acceptance": ["运行页面"],
                "controller_dump": "不应进入方案",
            },
        )
        payload = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/tampered.json", expected=2,
        )
        self.assertEqual(payload["code"], "invalid_plan_selection")

    def test_project_init_preserves_unowned_template_without_partial_install(self) -> None:
        template = self.project / "plan-templates" / "levels" / "brief.json"
        template.parent.mkdir(parents=True)
        template.write_text('{"owned_by":"user"}\n', encoding="utf-8")
        payload = self.run_cli("project", "init", "--target", str(self.project), expected=2)
        self.assertEqual(payload["code"], "install_conflict")
        self.assertEqual(template.read_text(encoding="utf-8"), '{"owned_by":"user"}\n')
        self.assertFalse((self.project / "scripts" / "harness.py").exists())
        self.assertFalse((self.project / ".docs-harness" / "config.json").exists())

    @REQUIRES_SYMLINK
    def test_project_init_rejects_external_scripts_parent_symlink(self) -> None:
        outside = Path(self.temp.name) / "outside-scripts"
        outside.mkdir()
        (self.project / "scripts").symlink_to(outside, target_is_directory=True)
        before = self.snapshot_project()
        payload = self.run_cli(
            "project", "init", "--target", str(self.project), expected=2
        )
        self.assertEqual(payload["code"], "install_conflict")
        self.assertEqual(self.snapshot_project(), before)
        self.assertEqual(list(outside.iterdir()), [])

    def test_project_init_installs_pure_v11_without_legacy_rules(self) -> None:
        payload = self.run_cli("project", "init", "--target", str(self.project))
        config = json.loads(
            (self.project / ".docs-harness" / "config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            payload["version"], (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        )
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v11")
        self.assertEqual(set(config), self.CURRENT_CONFIG_KEYS)
        self.assertTrue(self.LEGACY_CONFIG_KEYS.isdisjoint(config))
        self.assertEqual(config["direct_mode"], {"default": True})
        self.assertEqual(
            set(config["knowledge"]),
            {"mode", "query", "docs_preexisting_at_install"},
        )
        self.assertEqual(config["knowledge"]["mode"], "asset_lifecycle")
        self.assertEqual(config["knowledge"]["query"], "on_demand")
        self.assertFalse((self.project / ".docs-harness" / "harness-home" / "rules").exists())
        self.assertFalse(
            any("harness-home/rules" in item["path"] for item in payload["planned_changes"])
        )
        self.assertTrue((self.project / "docs/plans/README.md").is_file())
        self.assertTrue((self.project / "docs/plans/archive/.gitkeep").is_file())
        self.assertTrue((self.project / "docs/knowledge/archive/.gitkeep").is_file())
        self.assertTrue((self.project / "docs/acceptance/archive/.gitkeep").is_file())
        for module in (
            "managed_assets.py", "asset_checks.py", "plan_governance.py",
            "knowledge_assets.py", "acceptance_assets.py",
        ):
            self.assertTrue((self.project / "scripts" / module).is_file())

    def test_installed_controller_can_check_diff_and_self_test_itself(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        installed = self.project / "scripts" / "harness.py"
        for command in (
            [sys.executable, str(installed), "project", "check", "--target", str(self.project), "--json"],
            [sys.executable, str(installed), "project", "diff", "--target", str(self.project), "--json"],
            [sys.executable, str(installed), "self-test", "--target", str(self.project), "--json"],
        ):
            result = subprocess.run(
                command,
                cwd=self.project,
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(result.returncode, 0, f"{result.stdout}\n{result.stderr}")
            payload = json.loads(result.stdout)
            if command[2:4] == ["project", "diff"]:
                self.assertEqual(payload["changes"], [])
            if command[2] == "self-test":
                self.assertEqual(payload["status"], "passed")

    def test_installed_controller_runs_knowledge_and_acceptance_lifecycles(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        source = self.project / "src/owner.txt"
        source.parent.mkdir(parents=True)
        source.write_text("InstalledOwner owns lifecycle.\n", encoding="utf-8")
        knowledge = self.write_json(
            "inputs/installed-knowledge.json",
            {
                "schema_version": "docs-harness/knowledge-input/v1",
                "title": "安装副本知识",
                "key_symbols": ["InstalledOwner", "lifecycle_owner"],
                "summary": "安装副本可维护知识。",
                "facts": [
                    {
                        "id": "lifecycle.owner",
                        "statement": "InstalledOwner 拥有生命周期。",
                        "source_refs": ["src/owner.txt"],
                    }
                ],
            },
        )
        self.run_installed(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(knowledge.relative_to(self.project)),
            "--output", "docs/knowledge/installed.json",
        )
        acceptance = self.write_json(
            "inputs/installed-acceptance.json",
            {
                "schema_version": "docs-harness/acceptance-target-input/v1",
                "title": "安装副本验收",
                "key_symbols": ["InstalledOwner", "installed_acceptance"],
                "objective": "验证安装副本资产能力。",
                "knowledge_refs": ["docs/knowledge/installed.json"],
                "criteria": [
                    {
                        "id": "install.contract",
                        "title": "安装合同有效",
                        "acceptance_type": "contract_check",
                        "layer": "L1",
                    }
                ],
            },
        )
        self.run_installed(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(acceptance.relative_to(self.project)),
            "--output", "docs/acceptance/installed.json",
        )
        self.assertEqual(
            self.run_installed("knowledge", "check", "--target", str(self.project))["status"],
            "passed",
        )
        self.assertEqual(
            self.run_installed("acceptance", "check", "--target", str(self.project))["status"],
            "passed",
        )

    def run_installed(self, *args: str, expected: int = 0) -> dict[str, object]:
        installed = self.project / "scripts" / "harness.py"
        result = subprocess.run(
            [sys.executable, str(installed), *args, "--json"],
            cwd=self.project,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, expected, f"{result.stdout}\n{result.stderr}")
        return json.loads(result.stdout)

    def test_upgrade_source_flag_repairs_installed_copy(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        template = self.project / "plan-templates" / "levels" / "brief.json"
        template.unlink()
        payload = self.run_installed(
            "project", "upgrade", "--target", str(self.project), expected=2
        )
        self.assertEqual(payload["code"], "invalid_source")
        payload = self.run_installed(
            "project",
            "upgrade",
            "--target",
            str(self.project),
            "--source",
            str(ROOT),
            "--apply",
        )
        self.assertTrue(template.is_file())
        self.assertEqual(payload["source"], str(ROOT))
        self.assertFalse(payload["source_is_target"])
        self.assertIn("plan-templates/levels/brief.json", payload["changed"])
        payload = self.run_installed(
            "project", "upgrade", "--target", str(self.project)
        )
        self.assertTrue(payload["source_is_target"])
        payload = self.run_installed(
            "project",
            "check",
            "--target",
            str(self.project),
            "--source",
            str(ROOT),
            expected=2,
        )
        self.assertEqual(payload["code"], "invalid_request")
        payload = self.run_installed(
            "project",
            "upgrade",
            "--target",
            str(self.project),
            "--source",
            str(self.project / "missing-source"),
            expected=2,
        )
        self.assertEqual(payload["code"], "invalid_source")

    def test_upgrade_source_flag_rejects_version_mismatched_source(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        fake = Path(self.temp.name) / "fake-source"
        (fake / "scripts").mkdir(parents=True)
        shutil.copytree(ROOT / "plan-templates", fake / "plan-templates")
        shutil.copytree(ROOT / "scripts" / "githooks", fake / "scripts" / "githooks")
        for module in (
            "managed_assets.py", "asset_checks.py", "plan_governance.py",
            "knowledge_assets.py", "acceptance_assets.py", "adr_assets.py",
            "script_hygiene.py",
        ):
            shutil.copy2(ROOT / "scripts" / module, fake / "scripts" / module)
        script = (ROOT / "scripts" / "harness.py").read_text(encoding="utf-8")
        fake_script = re.sub(
            r'^VERSION = "[^"]+"',
            'VERSION = "0.0.0-fake"',
            script,
            count=1,
            flags=re.MULTILINE,
        )
        (fake / "scripts" / "harness.py").write_text(fake_script, encoding="utf-8")
        payload = self.run_installed(
            "project",
            "upgrade",
            "--target",
            str(self.project),
            "--source",
            str(fake),
            expected=2,
        )
        self.assertEqual(payload["code"], "source_version_mismatch")

    def test_unknown_legacy_config_schema_fails_before_install_writes(self) -> None:
        self.write_json(
            ".docs-harness/config.json",
            {
                "schema_version": "user/custom-config/v1",
                "version": "custom",
                "installed_rule_fingerprints": {},
            },
        )
        before = self.snapshot_project()
        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=3
        )
        self.assertEqual(payload["code"], "legacy_document_cleanup_conflict")
        self.assertEqual(self.snapshot_project(), before)

    def test_uninstall_removes_only_owned_install_and_preserves_project_docs(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        user_doc = self.project / "docs" / "product.md"
        user_doc.parent.mkdir(parents=True, exist_ok=True)
        user_doc.write_text("# 用户文档\n", encoding="utf-8")
        payload = self.run_cli(
            "project", "uninstall", "--target", str(self.project), "--apply"
        )
        self.assertTrue(payload["project_docs_preserved"])
        self.assertEqual(user_doc.read_text(encoding="utf-8"), "# 用户文档\n")
        self.assertFalse((self.project / "scripts" / "harness.py").exists())
        self.assertFalse((self.project / ".docs-harness" / "config.json").exists())
        self.assertFalse((self.project / "plan-templates").exists())

    def githook_digest(self, name: str) -> str:
        path = self.project / "scripts" / "githooks" / name
        # 与 file_fingerprint 同口径：autocrlf 环境下磁盘可能是 CRLF，按 LF 归一。
        data = path.read_bytes().replace(b"\r\n", b"\n")
        return "sha256:" + hashlib.sha256(data).hexdigest()

    def test_project_init_installs_githooks_with_activation_hint(self) -> None:
        payload = self.run_cli("project", "init", "--target", str(self.project))
        for name in ("pre-commit", "setup.sh"):
            installed = self.project / "scripts" / "githooks" / name
            self.assertTrue(installed.is_file())
            self.assertFalse(installed.is_symlink())
            self.assertEqual(
                installed.read_bytes(),
                (ROOT / "scripts" / "githooks" / name).read_bytes(),
            )
            self.assertIn(f"scripts/githooks/{name}", payload["changed"])
        config = json.loads(
            (self.project / ".docs-harness" / "config.json").read_text(encoding="utf-8")
        )
        fingerprints = config["installed_githook_fingerprints"]
        self.assertEqual(set(fingerprints), {"pre-commit", "setup.sh"})
        for name, fingerprint in fingerprints.items():
            self.assertEqual(fingerprint, self.githook_digest(name))
        self.assertIn("scripts/githooks/setup.sh", payload["githook_activation_hint"])
        pre_commit = (self.project / "scripts/githooks/pre-commit").read_text(encoding="utf-8")
        self.assertIn("assets-check --target . --fast", pre_commit)
        check = self.run_cli("project", "check", "--target", str(self.project))
        self.assertEqual(check["status"], "passed")

    def test_pre_commit_blocks_tampered_knowledge_asset(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        subprocess.run(
            ["git", "init"], cwd=self.project, capture_output=True, check=True
        )
        source = self.project / "src/runtime.txt"
        source.parent.mkdir(parents=True)
        source.write_text("KnowledgeOwner owns the runtime.\n", encoding="utf-8")
        value = self.write_json(
            "inputs/knowledge.json",
            self.knowledge_input("运行时所有权", "KnowledgeOwner 拥有运行时。"),
        )
        self.run_installed(
            "knowledge", "create", "--target", str(self.project),
            "--input", str(value.relative_to(self.project)),
            "--output", "docs/knowledge/runtime-owner.json",
        )
        asset_path = self.project / "docs/knowledge/runtime-owner.json"
        asset = json.loads(asset_path.read_text(encoding="utf-8"))
        asset["summary"] = "已被手工篡改"
        self.write_json("docs/knowledge/runtime-owner.json", asset)
        result = subprocess.run(
            ["sh", "scripts/githooks/pre-commit"],
            cwd=self.project,
            capture_output=True,
            check=False,
        )
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        self.assertEqual(result.returncode, 1, output)
        self.assertIn("assets-check", output)

    def test_upgrade_rejects_user_modified_githook_before_any_write(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        hook = self.project / "scripts" / "githooks" / "pre-commit"
        hook.write_bytes(hook.read_bytes() + b"# user tweak\n")
        before = self.snapshot_project()
        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=2
        )
        self.assertEqual(payload["code"], "install_conflict")
        self.assertEqual(self.snapshot_project(), before)

    def to_crlf(self, relative: str) -> None:
        path = self.project / relative
        data = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(data.replace(b"\n", b"\r\n"))

    def test_autocrlf_crlf_worktree_is_not_treated_as_user_modification(self) -> None:
        # Windows core.autocrlf=true 会把工作区文本检出为 CRLF；纯行尾差异不得
        # 阻断 check/upgrade/diff（真实事故：v1.2.0 项目升级被误判为用户修改）。
        self.run_cli("project", "init", "--target", str(self.project))
        for relative in (
            "scripts/harness.py",
            "scripts/knowledge_assets.py",
            "scripts/githooks/pre-commit",
            "plan-templates/levels/brief.json",
        ):
            self.to_crlf(relative)
        check = self.run_cli("project", "check", "--target", str(self.project))
        self.assertEqual(check["status"], "passed")
        diff = self.run_cli("project", "diff", "--target", str(self.project))
        self.assertEqual(diff["changes"], [])
        repeated = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )
        self.assertEqual(repeated["changed"], [])

    def test_autocrlf_crlf_worktree_still_rejects_real_modification(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.to_crlf("scripts/harness.py")
        script = self.project / "scripts" / "harness.py"
        script.write_bytes(script.read_bytes() + b"# user tweak\r\n")
        before = self.snapshot_project()
        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=2
        )
        self.assertEqual(payload["code"], "install_conflict")
        self.assertEqual(self.snapshot_project(), before)

    def test_project_check_and_upgrade_reject_asset_module_drift(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        module = self.project / "scripts" / "knowledge_assets.py"
        module.write_bytes(module.read_bytes() + b"# user tweak\n")
        checked = self.run_cli("project", "check", "--target", str(self.project), expected=1)
        self.assertIn("asset_module_drift", {item["code"] for item in checked["findings"]})
        before = self.snapshot_project()
        rejected = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=2
        )
        self.assertEqual(rejected["code"], "install_conflict")
        self.assertEqual(self.snapshot_project(), before)

    def test_upgrade_reports_all_modified_managed_files_at_once(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        for relative in ("scripts/harness.py", "scripts/acceptance_assets.py"):
            path = self.project / relative
            path.write_bytes(path.read_bytes() + b"# user tweak\n")
        before = self.snapshot_project()
        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=2
        )
        self.assertEqual(payload["code"], "install_conflict")
        conflicts = payload["install_conflicts"]
        self.assertEqual(len(conflicts), 2)
        self.assertEqual(
            {item["path"] for item in conflicts},
            {"scripts/harness.py", "scripts/acceptance_assets.py"},
        )
        for item in conflicts:
            self.assertEqual(item["reason"], "modified")
            self.assertTrue(item["actual_fingerprint"].startswith("sha256:"))
            self.assertEqual(
                item["allowed_fingerprints"], sorted(item["allowed_fingerprints"])
            )
        self.assertIn("scripts/harness.py", payload["message"])
        self.assertIn("scripts/acceptance_assets.py", payload["message"])
        self.assertEqual(self.snapshot_project(), before)

    def test_upgrade_reports_single_modified_managed_file(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        module = self.project / "scripts" / "acceptance_assets.py"
        module.write_bytes(module.read_bytes() + b"# user tweak\n")
        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=2
        )
        self.assertEqual(payload["code"], "install_conflict")
        conflicts = payload["install_conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["path"], "scripts/acceptance_assets.py")

    def test_upgrade_githooks_idempotent(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        repeated = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )
        self.assertEqual(repeated["changed"], [])
        diff = self.run_cli("project", "diff", "--target", str(self.project))
        self.assertEqual(diff["changes"], [])

    def test_uninstall_removes_only_unmodified_githooks(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        modified = self.project / "scripts" / "githooks" / "setup.sh"
        modified.write_bytes(modified.read_bytes() + b"# user tweak\n")
        preview = self.run_cli("project", "uninstall", "--target", str(self.project))
        self.assertIn("owned scripts/githooks files", preview["would_remove"])
        payload = self.run_cli(
            "project", "uninstall", "--target", str(self.project), "--apply"
        )
        self.assertIn("scripts/githooks/pre-commit", payload["removed"])
        self.assertNotIn("scripts/githooks/setup.sh", payload["removed"])
        self.assertFalse((self.project / "scripts" / "githooks" / "pre-commit").exists())
        self.assertTrue(modified.is_file())
        self.assertTrue((self.project / "scripts" / "githooks").is_dir())

    def test_upgrade_v6_config_is_smoothly_rewritten_to_v8(self) -> None:
        self.write_json(
            ".docs-harness/config.json",
            {
                "schema_version": "docs-harness/project-config/v6",
                "version": "2.3.0",
                "installed_script_fingerprint": "sha256:" + "0" * 64,
                "installed_plan_template_fingerprints": {},
                "direct_mode": {"default": True},
                "knowledge": {
                    "mode": "on_demand",
                    "read_only": True,
                    "docs_preexisting_at_install": False,
                },
                "migration": {"source_version": "2.2.0"},
                "installed_at": "2026-08-13T00:00:00Z",
            },
        )
        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )
        self.assertEqual(payload["from_version"], "2.3.0")
        config = json.loads(
            (self.project / ".docs-harness" / "config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v11")
        self.assertEqual(set(config), self.CURRENT_CONFIG_KEYS)
        self.assertTrue(self.LEGACY_CONFIG_KEYS.isdisjoint(config))
        self.assertEqual(config["migration"]["source_version"], "2.3.0")
        self.assertEqual(
            set(config["installed_githook_fingerprints"]), {"pre-commit", "setup.sh"}
        )
        for name in ("pre-commit", "setup.sh"):
            self.assertEqual(
                config["installed_githook_fingerprints"][name],
                self.githook_digest(name),
            )

    def test_upgrade_accepts_exact_241_templates_with_historical_bad_config_fingerprint(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        legacy_brief = (
            '{\n  "schema_version": "docs-harness/plan-template/v2",\n'
            '  "kind": "level",\n  "id": "brief",\n  "version": "2.4.1",\n'
            '  "fields": [\n'
            '    {"id": "objective", "label": "目标", "required": true},\n'
            '    {"id": "scope", "label": "范围", "required": true},\n'
            '    {"id": "steps", "label": "关键步骤", "required": true},\n'
            '    {"id": "acceptance", "label": "验收方案", "required": true}\n'
            '  ]\n}\n'
        )
        brief = self.project / "plan-templates" / "levels" / "brief.json"
        brief.write_text(legacy_brief, encoding="utf-8")
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["schema_version"] = "docs-harness/project-config/v7"
        config["version"] = "2.4.1"
        config["installed_plan_template_fingerprints"]["levels/brief.json"] = (
            "sha256:f3cbc14837d7c7f33a375a3ae91a24871f48ec5e064e976167709e46989ad1dd"
        )
        self.write_json(".docs-harness/config.json", config)

        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )

        self.assertEqual(payload["from_version"], "2.4.1")
        self.assertEqual(
            brief.read_bytes(),
            (ROOT / "plan-templates" / "levels" / "brief.json").read_bytes(),
        )

    def test_upgrade_still_rejects_modified_legacy_template(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        brief = self.project / "plan-templates" / "levels" / "brief.json"
        brief.write_bytes(brief.read_bytes() + b"\n")
        before = self.snapshot_project()

        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=2
        )

        self.assertEqual(payload["code"], "install_conflict")
        self.assertEqual(self.snapshot_project(), before)

    def test_upgrade_v5_preview_apply_cleanup_and_repeat_are_one_way(self) -> None:
        owned_rule = "---\nstatus: active\nrule_id: DH-LEGACY\n---\n\n# 旧规则\n"
        self.write_v5_install(installed_rules={"owned.md": owned_rule})
        docs = self.project / "docs"
        docs.mkdir(exist_ok=True)
        user_doc = docs / "product.md"
        user_doc.write_text("# 用户产品文档\n\n必须原样保留。\n", encoding="utf-8")
        managed_block = (
            "<!-- docs-harness:managed-version:start -->\n"
            "Docs Harness 当前版本：1.8.2\n"
            "<!-- docs-harness:managed-version:end -->"
        )
        (docs / "INDEX.md").write_text(
            f"# 用户索引\n\n{managed_block}\n\n用户索引正文。\n", encoding="utf-8"
        )
        modules_index = docs / "modules" / "INDEX.md"
        modules_index.parent.mkdir(parents=True)
        modules_index.write_text(
            f"# 用户模块索引\n\n{managed_block}\n\n模块正文。\n", encoding="utf-8"
        )
        self.write_json(
            "docs/knowledge-map.json",
            {"schema_version": "docs-harness/knowledge-map/v1", "features": []},
        )
        for relative in (
            ".docs-harness/runs/legacy-task/state.json",
            ".docs-harness/knowledge/cache.json",
            ".docs-harness/knowledge-jobs/job.json",
            ".docs-harness/background/legacy.json",
            ".docs-harness/task-inputs/facts.json",
        ):
            self.write_json(relative, {"legacy": True})

        before_preview = self.snapshot_project()
        preview = self.run_cli("project", "upgrade", "--target", str(self.project))
        self.assertEqual(preview["mode"], "preview")
        self.assertTrue(preview["apply_completion_possible"])
        self.assertEqual(self.snapshot_project(), before_preview)
        actions = {(item["path"], item["action"]) for item in preview["changes"]}
        self.assertIn(
            (".docs-harness/harness-home/rules/owned.md", "remove_owned_legacy"),
            actions,
        )
        self.assertIn(("docs/knowledge-map.json", "remove_owned_legacy"), actions)
        self.assertIn(("docs/INDEX.md", "remove_legacy_managed_block"), actions)
        self.assertIn(("docs/modules/INDEX.md", "remove_legacy_managed_block"), actions)
        for relative in (
            ".docs-harness/runs",
            ".docs-harness/knowledge",
            ".docs-harness/knowledge-jobs",
            ".docs-harness/background",
            ".docs-harness/task-inputs",
        ):
            self.assertIn((relative, "remove_legacy_runtime"), actions)

        applied = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )
        self.assertEqual(applied["mode"], "apply")
        self.assertFalse((self.project / ".docs-harness" / "harness-home" / "rules").exists())
        self.assertFalse((docs / "knowledge-map.json").exists())
        for relative in ("runs", "knowledge", "knowledge-jobs", "background", "task-inputs"):
            self.assertFalse((self.project / ".docs-harness" / relative).exists())
        self.assertEqual(user_doc.read_text(encoding="utf-8"), "# 用户产品文档\n\n必须原样保留。\n")
        for path, expected_text in (
            (docs / "INDEX.md", ("# 用户索引", "用户索引正文。")),
            (modules_index, ("# 用户模块索引", "模块正文。")),
        ):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("docs-harness:managed-version", text)
            for expected in expected_text:
                self.assertIn(expected, text)
        config = json.loads(
            (self.project / ".docs-harness" / "config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v11")
        self.assertEqual(set(config), self.CURRENT_CONFIG_KEYS)
        self.assertTrue(self.LEGACY_CONFIG_KEYS.isdisjoint(config))
        self.assertEqual(config["direct_mode"], {"default": True})
        self.assertEqual(config["knowledge"]["mode"], "asset_lifecycle")
        self.assertEqual(config["knowledge"]["query"], "on_demand")

        repeated = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )
        self.assertEqual(repeated["changed"], [])

    def test_git_upgrade_cleans_actual_git_runtime_and_preserves_quality_ledger(self) -> None:
        initialized = subprocess.run(
            ["git", "init", str(self.project)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        owned_rule = "# 旧规则\n"
        self.write_v5_install(installed_rules={"owned.md": owned_rule})
        self.write_json(".docs-harness/task-inputs/legacy-facts.json", {"legacy": True})
        self.write_json(".git/docs-harness/runs/legacy/state.json", {"legacy": True})
        self.write_json(
            ".git/docs-harness/quality-ledger/records/keep.json",
            {"user_review": True},
        )

        preview = self.run_cli("project", "upgrade", "--target", str(self.project))
        actions = {(item["path"], item["action"]) for item in preview["changes"]}
        self.assertIn((".docs-harness/task-inputs", "remove_legacy_runtime"), actions)
        self.assertIn((".git/docs-harness/runs", "remove_legacy_runtime"), actions)

        applied = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=3
        )
        self.assertEqual(applied["status"], "needs_delivery")
        self.assertFalse((self.project / ".docs-harness" / "task-inputs").exists())
        self.assertFalse((self.project / ".git" / "docs-harness" / "runs").exists())
        self.assertTrue(
            (
                self.project
                / ".git"
                / "docs-harness"
                / "quality-ledger"
                / "records"
                / "keep.json"
            ).is_file()
        )

    def test_upgrade_preserves_modified_and_unowned_rules_but_detaches_config(self) -> None:
        installed = "# Docs Harness 安装的旧规则\n"
        modified = "# 用户修改后的旧规则\n"
        extra = "# 用户自有规则\n"
        self.write_v5_install(
            installed_rules={"modified.md": installed},
            live_rules={"modified.md": modified, "extra.md": extra},
        )

        self.run_cli("project", "upgrade", "--target", str(self.project), "--apply")

        rules_root = self.project / ".docs-harness" / "harness-home" / "rules"
        self.assertEqual((rules_root / "modified.md").read_text(encoding="utf-8"), modified)
        self.assertEqual((rules_root / "extra.md").read_text(encoding="utf-8"), extra)
        config = json.loads(
            (self.project / ".docs-harness" / "config.json").read_text(encoding="utf-8")
        )
        self.assertTrue(self.LEGACY_CONFIG_KEYS.isdisjoint(config))
        self.assertEqual(
            set(config["migration"]["preserved_paths"]),
            {
                ".docs-harness/harness-home/rules/modified.md",
                ".docs-harness/harness-home/rules/extra.md",
            },
        )

    @REQUIRES_SYMLINK
    def test_upgrade_rejects_unsafe_legacy_rule_symlink_before_any_write(self) -> None:
        self.write_v5_install(installed_rules={})
        outside = Path(self.temp.name) / "outside-rule.md"
        outside.write_text("# 根外内容\n", encoding="utf-8")
        unsafe = self.project / ".docs-harness" / "harness-home" / "rules" / "unsafe.md"
        unsafe.symlink_to(outside)
        before = self.snapshot_project()

        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=3
        )

        self.assertEqual(payload["code"], "legacy_document_cleanup_conflict")
        self.assertEqual(self.snapshot_project(), before)
        self.assertEqual(outside.read_text(encoding="utf-8"), "# 根外内容\n")
        self.assertFalse((self.project / "scripts" / "harness.py").exists())
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / "plan-templates").exists())

    @REQUIRES_SYMLINK
    def test_upgrade_rejects_symlinked_runtime_root_before_any_write(self) -> None:
        initialized = subprocess.run(
            ["git", "init", str(self.project)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.write_v5_install(installed_rules={})
        outside = Path(self.temp.name) / "outside-runtime"
        (outside / "runs").mkdir(parents=True)
        marker = outside / "runs" / "keep.json"
        marker.write_text('{"outside":true}\n', encoding="utf-8")
        (self.project / ".git" / "docs-harness").symlink_to(
            outside,
            target_is_directory=True,
        )
        before = self.snapshot_project()

        payload = self.run_cli(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=3
        )

        self.assertEqual(payload["code"], "legacy_document_cleanup_conflict")
        conflicts = payload["legacy_document_cleanup"]["conflicts"]
        self.assertIn("legacy_runtime_root_unsafe", {item["reason_code"] for item in conflicts})
        self.assertEqual(self.snapshot_project(), before)
        self.assertEqual(marker.read_text(encoding="utf-8"), '{"outside":true}\n')
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / "scripts" / "harness.py").exists())

    def test_contract_check_cannot_claim_behavior(self) -> None:
        record = self.write_json(
            "contract.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "验证退出流程",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "method": "检查范围与格式",
                "evidence_refs": ["contract.json"],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record)
        )
        self.assertEqual(payload["status"], "contract_checked")
        self.assertFalse(payload["behavior_verified"])
        self.assertIsNone(payload["accepted_layer"])

    def test_contract_check_cannot_pass_without_method_and_evidence(self) -> None:
        record = self.write_json(
            "empty-contract.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "不能空验收",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "evidence_refs": [],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record), expected=2,
        )
        self.assertEqual(payload["code"], "invalid_acceptance_input")

    def test_git_project_acceptance_uses_actual_git_metadata_runtime(self) -> None:
        initialized = subprocess.run(
            ["git", "init", str(self.project)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        record = self.write_json(
            "git-contract.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "验证 Git Runtime 定位",
                "acceptance_type": "contract_check",
                "status": "passed",
                "layer": "L1",
                "method": "检查实际 Git 元数据路径",
                "evidence_refs": ["git-contract.json"],
            },
        )
        self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record)
        )
        records = list(
            (self.project / ".git" / "docs-harness" / "v2" / "acceptance").glob("*.json")
        )
        self.assertEqual(len(records), 1)
        self.assertFalse((self.project / ".docs-harness" / "v2").exists())

    def test_behavior_failure_returns_structured_attributions(self) -> None:
        (self.project / "failure.log").write_text(
            "current change failure\npre-existing warning\n", encoding="utf-8"
        )
        record = self.write_json(
            "failed.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "退出后不重复注入",
                "acceptance_type": "behavior_acceptance",
                "status": "failed",
                "layer": "L3",
                "evidence_layer": "local_runtime",
                "reason": "退出托盘后旧文本再次注入",
                "next_action": "修复重复 finalize 后重跑同一流程",
                "failure_attributions": [
                    {
                        "category": "change_related",
                        "summary": "退出流程仍重复 finalize",
                        "blocking": True,
                        "evidence_refs": ["failure.log"],
                    },
                    {
                        "category": "pre_existing",
                        "summary": "启动阶段存在既有警告",
                        "blocking": False,
                        "evidence_refs": ["failure.log"],
                    },
                    {
                        "category": "unrelated",
                        "summary": "无关模块存在独立告警",
                        "blocking": False,
                        "evidence_refs": ["failure.log"],
                    },
                    {
                        "category": "environment",
                        "summary": "测试环境缺少可选设备",
                        "blocking": False,
                        "evidence_refs": ["failure.log"],
                    },
                    {
                        "category": "flaky",
                        "summary": "相同输入下偶发超时",
                        "blocking": True,
                        "evidence_refs": ["failure.log"],
                    },
                ],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record), expected=3
        )
        self.assertEqual(
            set(payload),
            {
                "status",
                "layer",
                "evidence_layer",
                "reason",
                "next_action",
                "failure_attributions",
            },
        )
        self.assertEqual(payload["layer"], "local_runtime")
        self.assertEqual(payload["evidence_layer"], "local_runtime")
        self.assertEqual(
            [item["category"] for item in payload["failure_attributions"]],
            ["change_related", "pre_existing", "unrelated", "environment", "flaky"],
        )

    def test_failed_acceptance_requires_structured_attribution(self) -> None:
        record = self.write_json(
            "failed-without-attribution.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "验证失败必须归因",
                "acceptance_type": "behavior_acceptance",
                "status": "failed",
                "layer": "L2",
                "evidence_layer": "focused_test",
                "reason": "聚焦测试失败",
                "next_action": "分析失败来源",
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record), expected=2,
        )
        self.assertEqual(payload["code"], "invalid_acceptance_input")

    def test_behavior_evidence_layers_are_distinct_and_fixed(self) -> None:
        (self.project / "acceptance.log").write_text("passed\n", encoding="utf-8")
        cases = {
            "focused_test": "L2",
            "repository_full_test": "L2",
            "local_runtime": "L3",
            "package_or_install": "L4",
            "real_device": "L5",
        }
        for evidence_layer, layer in cases.items():
            with self.subTest(evidence_layer=evidence_layer):
                record = self.write_json(
                    f"{evidence_layer}.json",
                    {
                        "schema_version": "docs-harness/acceptance-input/v3",
                        "objective": f"验证 {evidence_layer}",
                        "acceptance_type": "behavior_acceptance",
                        "status": "passed",
                        "layer": layer,
                        "evidence_layer": evidence_layer,
                        "method": f"执行 {evidence_layer} 验收",
                        "evidence_refs": ["acceptance.log"],
                    },
                )
                payload = self.run_cli(
                    "acceptance", "record", "--target", str(self.project),
                    "--input", str(record),
                )
                self.assertEqual(payload["accepted_layer"], layer)
                self.assertEqual(payload["evidence_layer"], evidence_layer)

        mismatch = self.write_json(
            "mismatched-layer.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "不得用全量测试冒充包验收",
                "acceptance_type": "behavior_acceptance",
                "status": "passed",
                "layer": "L4",
                "evidence_layer": "repository_full_test",
                "method": "运行仓库全量测试",
                "evidence_refs": ["acceptance.log"],
            },
        )
        rejected = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(mismatch), expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_acceptance_input")

    def test_l1_cannot_claim_behavior_acceptance(self) -> None:
        record = self.write_json(
            "static-only.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "验证退出流程",
                "acceptance_type": "behavior_acceptance",
                "status": "passed",
                "layer": "L1",
                "evidence_layer": "focused_test",
                "method": "静态检查",
                "evidence_refs": ["type-check.txt"],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record), expected=2
        )
        self.assertEqual(payload["code"], "invalid_acceptance_input")

    def test_behavior_acceptance_cannot_reference_missing_evidence(self) -> None:
        record = self.write_json(
            "behavior-passed.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "验证退出流程",
                "acceptance_type": "behavior_acceptance",
                "status": "passed",
                "layer": "L2",
                "evidence_layer": "focused_test",
                "method": "运行聚焦回归",
                "evidence_refs": ["missing-test-result.txt"],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record), expected=2
        )
        self.assertEqual(payload["code"], "acceptance_evidence_missing")

    def init_git_project(self) -> None:
        initialized = subprocess.run(
            ["git", "init", str(self.project)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)

    def behavior_passed_input(self, name: str, evidence_refs: list[str]) -> Path:
        return self.write_json(
            name,
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "验证证据准入",
                "acceptance_type": "behavior_acceptance",
                "status": "passed",
                "layer": "L2",
                "evidence_layer": "focused_test",
                "method": "运行聚焦回归",
                "evidence_refs": evidence_refs,
            },
        )

    def test_behavior_acceptance_rejects_evidence_under_git_ignored_path(self) -> None:
        self.init_git_project()
        (self.project / ".gitignore").write_text("build/\n", encoding="utf-8")
        build_dir = self.project / "build"
        build_dir.mkdir()
        (build_dir / "pack.log").write_text("passed\n", encoding="utf-8")
        record = self.behavior_passed_input("ignored-evidence.json", ["build/pack.log"])
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record), expected=2
        )
        self.assertEqual(payload["code"], "acceptance_evidence_ignored")

    def test_behavior_acceptance_allows_evidence_under_committed_docs_path(self) -> None:
        self.init_git_project()
        (self.project / ".gitignore").write_text("build/\n", encoding="utf-8")
        evidence_dir = self.project / "docs" / "acceptance" / "evidence" / "pack-check"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "proof.log").write_text("passed\n", encoding="utf-8")
        record = self.behavior_passed_input(
            "committed-evidence.json", ["docs/acceptance/evidence/pack-check/proof.log"]
        )
        self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record)
        )
        records = list(
            (self.project / ".git" / "docs-harness" / "v2" / "acceptance").glob("*.json")
        )
        self.assertEqual(len(records), 1)

    def test_behavior_acceptance_missing_evidence_still_reported_in_git_project(self) -> None:
        self.init_git_project()
        (self.project / ".gitignore").write_text("build/\n", encoding="utf-8")
        record = self.behavior_passed_input("missing-evidence.json", ["build/missing.log"])
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record), expected=2
        )
        self.assertEqual(payload["code"], "acceptance_evidence_missing")

    def test_behavior_acceptance_non_git_target_is_not_locked_by_ignore_check(self) -> None:
        (self.project / ".gitignore").write_text("build/\n", encoding="utf-8")
        build_dir = self.project / "build"
        build_dir.mkdir()
        (build_dir / "pack.log").write_text("passed\n", encoding="utf-8")
        record = self.behavior_passed_input("non-git-evidence.json", ["build/pack.log"])
        self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record)
        )
        records = list(
            (self.project / ".docs-harness" / "v2" / "acceptance").glob("*.json")
        )
        self.assertEqual(len(records), 1)

    def test_user_pending_requires_ready_environment_and_short_handoff(self) -> None:
        record = self.write_json(
            "pending.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "验证麦克风权限体验",
                "acceptance_type": "user_acceptance",
                "status": "user_pending",
                "layer": "L5",
                "automatically_verified": ["应用已启动"],
                "user_checks": ["权限提示是否正确"],
                "steps": ["点击麦克风并观察提示"],
                "environment_ready": True,
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record), expected=3
        )
        self.assertEqual(payload["status"], "user_pending")
        self.assertTrue(payload["user_handoff"]["environment_ready"])

    def test_cli_cannot_self_declare_user_acceptance(self) -> None:
        record = self.write_json(
            "user-accepted.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "objective": "确认麦克风体验",
                "acceptance_type": "user_acceptance",
                "status": "passed",
                "layer": "L5",
                "method": "声称用户确认",
                "evidence_refs": ["missing-user-proof.txt"],
            },
        )
        payload = self.run_cli(
            "acceptance", "record", "--target", str(self.project), "--input", str(record), expected=3
        )
        self.assertEqual(payload["code"], "user_confirmation_required")

    def acceptance_target(self, acceptance_type: str = "behavior_acceptance") -> dict[str, object]:
        layer = {
            "contract_check": "L1",
            "behavior_acceptance": "L2",
            "user_acceptance": "L5",
        }[acceptance_type]
        criterion: dict[str, object] = {
            "id": "flow.result",
            "title": "功能流程结果符合预期",
            "acceptance_type": acceptance_type,
            "layer": layer,
        }
        if acceptance_type == "behavior_acceptance":
            criterion["evidence_layer"] = "focused_test"
        return {
            "schema_version": "docs-harness/acceptance-target-input/v1",
            "title": "功能流程验收",
            "key_symbols": ["AcceptanceOwner", "flow_result"],
            "objective": "逐条记录功能流程证据。",
            "criteria": [criterion],
        }

    def acceptance_record_input(
        self,
        name: str,
        evidence_refs: list[str],
        *,
        acceptance_type: str = "behavior_acceptance",
        method: str = "运行聚焦测试",
    ) -> Path:
        record: dict[str, object] = {
            "schema_version": "docs-harness/acceptance-input/v3",
            "criterion_id": "flow.result",
            "objective": "逐条记录功能流程证据。",
            "acceptance_type": acceptance_type,
            "status": "passed",
            "layer": {"behavior_acceptance": "L2", "user_acceptance": "L5"}[acceptance_type],
            "method": method,
            "evidence_refs": evidence_refs,
        }
        if acceptance_type == "behavior_acceptance":
            record["evidence_layer"] = "focused_test"
        else:
            record["confirmation"] = "用户确认功能流程符合预期。"
        return self.write_json(name, record)

    def test_acceptance_asset_create_record_reaccept_settle_and_check(self) -> None:
        target_input = self.write_json("inputs/acceptance-target.json", self.acceptance_target())
        created = self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/flow.json",
        )
        self.assertEqual(created["criteria"], 1)
        evidence = self.project / "focused-test.log"
        evidence.write_text("passed\n", encoding="utf-8")
        passed_input = self.write_json(
            "inputs/acceptance-passed.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "behavior_acceptance",
                "status": "passed",
                "layer": "L2",
                "evidence_layer": "focused_test",
                "method": "运行聚焦测试",
                "evidence_refs": ["focused-test.log"],
            },
        )
        recorded = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(passed_input.relative_to(self.project)),
            "--acceptance", "docs/acceptance/flow.json",
        )
        self.assertEqual(recorded["status"], "passed")
        settled = self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", "docs/acceptance/flow.json", "--status", "passed",
        )
        self.assertEqual(settled["status"], "passed")

        failed_input = self.write_json(
            "inputs/acceptance-failed.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "behavior_acceptance",
                "status": "failed",
                "layer": "L2",
                "evidence_layer": "focused_test",
                "reason": "回归失败",
                "next_action": "修复后重验",
                "failure_attributions": [
                    {
                        "category": "change_related",
                        "summary": "功能结果不符合预期",
                        "blocking": True,
                        "evidence_refs": ["focused-test.log"],
                    }
                ],
            },
        )
        rejected = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(failed_input.relative_to(self.project)),
            "--acceptance", "docs/acceptance/flow.json", expected=1,
        )
        self.assertEqual(rejected["code"], "acceptance_reaccept_required")
        reaccepted = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(failed_input.relative_to(self.project)),
            "--acceptance", "docs/acceptance/flow.json", "--reaccept", expected=3,
        )
        self.assertEqual(reaccepted["status"], "failed")
        self.assertEqual(
            self.run_cli("acceptance", "check", "--target", str(self.project))["status"],
            "passed",
        )

    def test_user_acceptance_pass_requires_explicit_confirmation_gate(self) -> None:
        target_input = self.write_json("inputs/user-target.json", self.acceptance_target("user_acceptance"))
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/user-flow.json",
        )
        record = self.write_json(
            "inputs/user-passed.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.result",
                "objective": "逐条记录功能流程证据。",
                "acceptance_type": "user_acceptance",
                "status": "passed",
                "layer": "L5",
                "method": "用户明确确认",
                "evidence_refs": [],
                "confirmation": "用户确认功能流程符合预期。",
            },
        )
        rejected = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/user-flow.json", expected=3,
        )
        self.assertEqual(rejected["code"], "user_confirmation_required")
        accepted = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/user-flow.json", "--user-confirmed",
        )
        self.assertEqual(accepted["status"], "passed")

    def test_acceptance_check_only_validates_latest_record_evidence(self) -> None:
        target_input = self.write_json("inputs/latest-target.json", self.acceptance_target())
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/latest.json",
        )
        (self.project / "old-evidence.log").write_text("old\n", encoding="utf-8")
        old_record = self.acceptance_record_input("inputs/latest-old.json", ["old-evidence.log"])
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(old_record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/latest.json",
        )
        (self.project / "new-evidence.log").write_text("new\n", encoding="utf-8")
        new_record = self.acceptance_record_input(
            "inputs/latest-new.json", ["new-evidence.log"], method="重验取代旧记录"
        )
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(new_record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/latest.json",
        )
        # 被最新记录取代的旧记录证据已清理，不再卡住 check
        (self.project / "old-evidence.log").unlink()
        self.assertEqual(
            self.run_cli("acceptance", "check", "--target", str(self.project))["status"],
            "passed",
        )

    def test_acceptance_check_fails_when_latest_record_evidence_missing(self) -> None:
        target_input = self.write_json("inputs/missing-target.json", self.acceptance_target())
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/missing.json",
        )
        (self.project / "stale-evidence.log").write_text("passed\n", encoding="utf-8")
        record = self.acceptance_record_input("inputs/missing-record.json", ["stale-evidence.log"])
        self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(record.relative_to(self.project)),
            "--acceptance", "docs/acceptance/missing.json",
        )
        (self.project / "stale-evidence.log").unlink()
        checked = self.run_cli("acceptance", "check", "--target", str(self.project), expected=1)
        self.assertEqual(checked["status"], "failed")
        self.assertTrue(
            any("stale-evidence.log" in failure for failure in checked["failures"]),
            checked["failures"],
        )

    def test_user_acceptance_confirmation_checked_only_on_latest_record(self) -> None:
        target_input = self.write_json(
            "inputs/user-latest-target.json", self.acceptance_target("user_acceptance")
        )
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(target_input.relative_to(self.project)),
            "--output", "docs/acceptance/user-latest.json",
        )
        for name in ("inputs/user-latest-old.json", "inputs/user-latest-new.json"):
            record = self.acceptance_record_input(name, [], acceptance_type="user_acceptance")
            self.run_cli(
                "acceptance", "record", "--target", str(self.project),
                "--input", str(record.relative_to(self.project)),
                "--acceptance", "docs/acceptance/user-latest.json", "--user-confirmed",
            )

        sys.path.insert(0, str(ROOT / "scripts"))
        import managed_assets

        asset_path = self.project / "docs" / "acceptance" / "user-latest.json"

        def strip_confirmation(index: int) -> None:
            asset = json.loads(asset_path.read_text(encoding="utf-8"))
            # 模拟旧版本写入的缺确认记录，重封指纹保持资产完整
            del asset["criteria"][0]["records"][index]["user_confirmation"]
            asset["asset_fingerprint"] = managed_assets.fingerprint(asset)
            asset_path.write_text(
                json.dumps(asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

        # 被取代的旧记录缺确认不再卡 check
        strip_confirmation(0)
        self.assertEqual(
            self.run_cli("acceptance", "check", "--target", str(self.project))["status"],
            "passed",
        )
        # 最新记录缺确认仍 FAIL
        strip_confirmation(1)
        checked = self.run_cli("acceptance", "check", "--target", str(self.project), expected=1)
        self.assertEqual(checked["status"], "failed")
        self.assertTrue(
            any("用户验收记录缺少明确确认" in failure for failure in checked["failures"]),
            checked["failures"],
        )

if __name__ == "__main__":
    unittest.main()
