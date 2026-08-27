"""project init/uninstall 与 git 钩子：安装边界、脚手架幂等、已装控制器自检。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT, REQUIRES_SYMLINK


class ProjectInstallTest(HarnessTestBase):
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
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v12")
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


if __name__ == "__main__":
    unittest.main()
