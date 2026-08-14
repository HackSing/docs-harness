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


class DocsHarnessV2DirectTest(unittest.TestCase):
    maxDiff = None

    CURRENT_CONFIG_KEYS = {
        "schema_version",
        "version",
        "installed_script_fingerprint",
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
            (rules_root / name).write_text(content, encoding="utf-8", newline="")
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
        public_commands = {"knowledge", "plan", "acceptance", "project", "release", "docs-check", "self-test"}
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
        packed = subprocess.run(
            ["npm", "pack", "--dry-run", "--json"],
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
        # docs-check 常驻能力进控制器后单文件分发体积上浮；红线随 2.3.0 调整，
        # 拆分独立模块会破坏单文件安装指纹模型。
        self.assertLess(HARNESS.stat().st_size, 120_000)
        self.assertLess(len(source.splitlines()), 3_000)
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

    def test_docs_check_skips_without_docs_system(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        payload = self.run_cli("docs-check", "--target", str(self.project))
        self.assertEqual(payload["status"], "skipped")
        self.assertEqual(payload["failures"], [])

    def test_docs_check_reports_banner_and_stale_archive_reference(self) -> None:
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
        payload = self.run_cli("docs-check", "--target", str(self.project), expected=1)
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

        before = (self.project / "docs/plans/fix.json").read_bytes()
        repeated = self.run_cli(
            "plan", "create", "--target", str(self.project),
            "--selection", str(selection_path), "--content", str(content_path),
            "--output", "docs/plans/fix.json",
        )
        self.assertEqual(repeated["status"], "frozen")
        self.assertEqual((self.project / "docs/plans/fix.json").read_bytes(), before)

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

    def test_project_init_installs_pure_v7_without_legacy_rules(self) -> None:
        payload = self.run_cli("project", "init", "--target", str(self.project))
        config = json.loads(
            (self.project / ".docs-harness" / "config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            payload["version"], (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        )
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v7")
        self.assertEqual(set(config), self.CURRENT_CONFIG_KEYS)
        self.assertTrue(self.LEGACY_CONFIG_KEYS.isdisjoint(config))
        self.assertEqual(config["direct_mode"], {"default": True})
        self.assertEqual(
            set(config["knowledge"]),
            {"mode", "read_only", "docs_preexisting_at_install"},
        )
        self.assertEqual(config["knowledge"]["mode"], "on_demand")
        self.assertTrue(config["knowledge"]["read_only"])
        self.assertFalse((self.project / ".docs-harness" / "harness-home" / "rules").exists())
        self.assertFalse(
            any("harness-home/rules" in item["path"] for item in payload["planned_changes"])
        )

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
        script = (ROOT / "scripts" / "harness.py").read_text(encoding="utf-8")
        fake_script = re.sub(
            r'^VERSION = "[^"]+"',
            'VERSION = "0.0.0-fake"',
            script,
            count=1,
            flags=re.MULTILINE,
        )
        (fake / "scripts" / "harness.py").write_text(
            fake_script, encoding="utf-8", newline=""
        )
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
        user_doc.parent.mkdir(parents=True)
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
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

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
        check = self.run_cli("project", "check", "--target", str(self.project))
        self.assertEqual(check["status"], "passed")

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

    def test_upgrade_v6_config_is_smoothly_rewritten_to_v7(self) -> None:
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
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v7")
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
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v7")
        self.assertEqual(set(config), self.CURRENT_CONFIG_KEYS)
        self.assertTrue(self.LEGACY_CONFIG_KEYS.isdisjoint(config))
        self.assertEqual(config["direct_mode"], {"default": True})
        self.assertEqual(config["knowledge"]["mode"], "on_demand")
        self.assertTrue(config["knowledge"]["read_only"])

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

if __name__ == "__main__":
    unittest.main()
