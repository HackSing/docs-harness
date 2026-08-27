"""Docs Harness 测试共享基建：临时项目、CLI 调用与跨领域输入构造器。

npm test / CI 经 unittest discover 把 tests/ 置入 sys.path，各领域测试文件直接
`from harness_test_base import ...`；每个领域文件另带 sys.path 兜底，支持
`python -m unittest tests.test_<domain>` 直呼。本文件不以 test_ 开头，不被 discover 收集。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "harness.py"
MANAGED_MODULES = (
    "managed_assets.py", "asset_checks.py", "plan_governance.py",
    "knowledge_assets.py", "acceptance_assets.py", "adr_assets.py",
    "script_hygiene.py", "structure_check.py",
)


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


class HarnessTestBase(unittest.TestCase):
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
    def structure_git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
            cwd=self.project, capture_output=True, check=True,
        )
    def structure_commit_all(self) -> None:
        self.structure_git("add", "-A")
        self.structure_git("commit", "-m", "base")
    def write_lines(self, name: str, lines: list[str]) -> None:
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def githook_digest(self, name: str) -> str:
        path = self.project / "scripts" / "githooks" / name
        # 与 file_fingerprint 同口径：autocrlf 环境下磁盘可能是 CRLF，按 LF 归一。
        data = path.read_bytes().replace(b"\r\n", b"\n")
        return "sha256:" + hashlib.sha256(data).hexdigest()
