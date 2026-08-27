"""project upgrade：来源包修复、版本/指纹拒绝、pre-2.0 单向迁移与清理。"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT, MANAGED_MODULES, REQUIRES_SYMLINK


class ProjectUpgradeTest(HarnessTestBase):
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
        for module in MANAGED_MODULES:
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
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v12")
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
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v12")
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

if __name__ == "__main__":
    unittest.main()
