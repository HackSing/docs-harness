from __future__ import annotations

import hashlib
import importlib.util
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "harness.py"
HARNESS_SPEC = importlib.util.spec_from_file_location("docs_harness_controller", HARNESS)
assert HARNESS_SPEC and HARNESS_SPEC.loader
HARNESS_MODULE = importlib.util.module_from_spec(HARNESS_SPEC)
HARNESS_SPEC.loader.exec_module(HARNESS_MODULE)
RULES = ROOT / "harness-home" / "rules"
CURRENT_VERSION = HARNESS_MODULE.VERSION
ACTIVE_RULE_FILES = {
    "api-compatibility.md",
    "external-input-security.md",
    "ui-complete-states.md",
    "testing-release.md",
    "release-authorization-rollback.md",
    "documentation-changes.md",
    "scope-change-readmission.md",
    "windows-powershell-compatibility.md",
}
ACTIVE_RULE_IDS = {
    "DH-API-COMPATIBILITY",
    "DH-DOCUMENTATION-CHANGES",
    "DH-EXTERNAL-INPUT-SECURITY",
    "DH-RELEASE-AUTHORIZATION-ROLLBACK",
    "DH-SCOPE-CHANGE-READMISSION",
    "DH-TESTING-RELEASE",
    "DH-UI-COMPLETE-STATES",
    "DH-WINDOWS-POWERSHELL-COMPATIBILITY",
}


class DocsHarnessContractTest(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp.name).resolve()
        self.project = self.temp_root / "project"
        self.project.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _inject_default_assessments(self, args: tuple[str, ...]) -> tuple[str, ...]:
        """历史合同用例由测试宿主补齐新声明；声明专项测试可显式关闭。"""
        if not args or args[0] != "run" or "--task" not in args or "--task-id" in args:
            return args
        mutable = list(args)
        task = mutable[mutable.index("--task") + 1]
        facts: dict[str, Any] = {}
        facts_index: int | None = None
        if "--facts" in mutable:
            facts_index = mutable.index("--facts") + 1
            try:
                loaded = json.loads(Path(mutable[facts_index]).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return args
            if not isinstance(loaded, dict):
                return args
            facts = loaded
        scopes = list(facts.get("write_scope") or facts.get("allowed_scope") or [])
        scope_positions = [index for index, value in enumerate(mutable) if value == "--scope"]
        scopes.extend(mutable[index + 1] for index in scope_positions if index + 1 < len(mutable))
        if "intent_assessment" not in facts and "task_intent" not in facts and "candidate_intents" not in facts:
            candidates, _, _ = HARNESS_MODULE.classify_task_intents(
                task, {}, has_declared_scope=bool(scopes)
            )
            facts["intent_assessment"] = {
                "intents": [item["intent"] for item in candidates],
                "rationale": "测试宿主按当前任务语义提交意图声明",
            }
        if "gate_assessment" not in facts:
            gates = list(facts.get("gates") or HARNESS_MODULE.infer_gates_from_paths(scopes))
            facts["gate_assessment"] = {
                "gates": gates,
                "rationale": "测试宿主按当前范围提交 Gate 声明",
            }
        injected = self.write_json(f"auto-assessment-{len(list(self.temp_root.glob('auto-assessment-*')))}.json", facts)
        if facts_index is None:
            mutable.extend(("--facts", str(injected)))
        else:
            mutable[facts_index] = str(injected)
        return tuple(mutable)

    def run_harness(
        self,
        *args: str,
        expected: int | None = 0,
        inject_assessments: bool = True,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
        effective_args = self._inject_default_assessments(args) if inject_assessments else args
        result = subprocess.run(
            [sys.executable, str(HARNESS), *effective_args, "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        payload = json.loads(result.stdout)
        if expected is not None:
            self.assertEqual(result.returncode, expected, f"{result.stdout}\n{result.stderr}")
        return result, payload

    def run_installed_harness(
        self, *args: str, expected: int | None = 0
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
        result = subprocess.run(
            [sys.executable, str(self.project / "scripts" / "harness.py"), *args, "--json"],
            cwd=self.project,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        payload = json.loads(result.stdout)
        if expected is not None:
            self.assertEqual(result.returncode, expected, f"{result.stdout}\n{result.stderr}")
        return result, payload

    def write_json(self, name: str, value: Any) -> Path:
        path = self.temp_root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def write_gate_facts(self, name: str, gates: list[str], **facts: Any) -> Path:
        facts["gate_assessment"] = {
            "gates": gates,
            "rationale": "测试显式声明任务所需 Gate",
        }
        return self.write_json(name, facts)

    def snapshot_tree(self, root: Path) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        if not root.exists():
            return snapshot
        for path in sorted(root.rglob("*")):
            relative = str(path.relative_to(root))
            if path.is_symlink():
                snapshot[relative] = f"symlink:{os.readlink(path)}"
            elif path.is_dir():
                snapshot[relative] = "directory"
            else:
                snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return snapshot

    def bootstrap_knowledge(self) -> None:
        feature_id = "project-core"
        feature_root = self.project / "docs" / "features" / feature_id
        feature_root.mkdir(parents=True, exist_ok=True)
        for category, title in (
            ("product", "产品"),
            ("development", "研发"),
            ("testing", "测试"),
            ("design", "设计"),
        ):
            (feature_root / f"{category}.md").write_text(
                f"# 项目核心：{title}事实\n\n## 当前状态\n\n已由测试项目确认的真实事实和当前边界。\n\n## 事实来源\n\nREADME.md 与测试固定装置。\n",
                encoding="utf-8",
            )
        for shared in ("architecture.md", "security.md", "design-system.md", "testing-strategy.md"):
            path = self.project / "docs" / "shared" / shared
            path.write_text(path.read_text(encoding="utf-8") + "\n已由测试项目确认的公共事实和当前边界。\n", encoding="utf-8")
        knowledge_map = {
            "schema_version": "docs-harness/knowledge-map/v1",
            "knowledge_level": "L2",
            "reviewed_revision": "test-fixture",
            "features": [
                {
                    "feature_id": feature_id,
                    "name": "项目核心",
                    "aliases": ["项目", "README"],
                    "feature_type": "platform_capability",
                    "status": "implemented",
                    "scope_patterns": ["**"],
                    "documents": {category: f"docs/features/{feature_id}/{category}.md" for category in ("product", "development", "testing", "design")},
                    "shared_refs": ["docs/shared/architecture.md", "docs/shared/security.md", "docs/shared/design-system.md", "docs/shared/testing-strategy.md"],
                    "dependencies": [],
                    "known_gaps": [],
                }
            ],
        }
        (self.project / "docs" / "knowledge-map.json").write_text(json.dumps(knowledge_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def init_project(self, *, expected: int = 0, bootstrap_knowledge: bool = True) -> dict[str, Any]:
        docs_preexisted = (self.project / "docs").is_dir()
        _, payload = self.run_harness(
            "project", "init", "--target", str(self.project), expected=expected
        )
        if bootstrap_knowledge:
            self.bootstrap_knowledge()
        if not docs_preexisted:
            # 通用测试固定装置声明一组已存在的治理真源；专门的路由测试会显式移除或改写它们。
            (self.project / "docs" / "adr").mkdir(parents=True, exist_ok=True)
            (self.project / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
            (self.project / "docs" / "todo.md").write_text("# TODO\n", encoding="utf-8")
            (self.project / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
            for job in HARNESS_MODULE.list_background_jobs(self.project):
                root, current = HARNESS_MODULE.read_knowledge_job(self.project, job["job_id"])
                HARNESS_MODULE.refresh_knowledge_job_baseline(self.project, current)
                HARNESS_MODULE.write_background_job(self.project, root, current)
        return payload

    def write_background_goal_artifacts(self, job_id: str) -> None:
        self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", job_id
        )

    def complete_background_work_packages(self, job_id: str) -> None:
        root = self.project / ".docs-harness" / "background" / "jobs" / job_id
        progress = json.loads((root / "progress.json").read_text(encoding="utf-8"))
        for item in progress["work_package_states"]:
            self.run_harness(
                "background", "progress", "--target", str(self.project), "--job-id", job_id,
                "--work-package-id", item["id"], "--work-package-status", "in_progress",
            )
            self.run_harness(
                "background", "progress", "--target", str(self.project), "--job-id", job_id,
                "--work-package-id", item["id"], "--work-package-status", "completed",
            )

    def force_complex_background_job(self, job_id: str, packages: list[str] | None = None, route: str = "background_goal") -> dict[str, Any]:
        job_path = self.project / ".docs-harness" / "background" / "jobs" / job_id / "job.json"
        job = json.loads(job_path.read_text(encoding="utf-8"))
        job["execution_route"] = route
        job["goal_contract"] = HARNESS_MODULE.goal_contract_for_estimate(
            {"execution_route": route}, "验证后台 Goal 宿主桥接"
        )
        job["work_packages"] = packages or ["准备控制面", "完成业务验收"]
        job["host_dispatch_contract"] = HARNESS_MODULE.host_dispatch_contract(
            self.project, job_id, route
        )
        job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return job

    def background_event_sequence(self, job_id: str) -> list[dict[str, Any]]:
        root = self.project / ".docs-harness" / "background" / "jobs" / job_id
        return [
            {key: value for key, value in item.items() if key not in {"at", "job_id", "attempt"}}
            for item in HARNESS_MODULE.read_jsonl(root / "events.jsonl")
        ]

    def start_complex_background_job(self, job_id: str) -> None:
        self.write_background_goal_artifacts(job_id)
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched"
        )
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running"
        )

    def cancel_background_job(self, job_id: str) -> None:
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "cancelled"
        )

    def commit_project(self, message: str = "install docs harness") -> None:
        subprocess.run(["git", "add", "-A"], cwd=self.project, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Docs Harness Test",
                "-c",
                "user.email=docs-harness-test@example.invalid",
                "commit",
                "-q",
                "-m",
                message,
            ],
            cwd=self.project,
            check=True,
        )

    def init_git_remote(self) -> Path:
        remote = self.temp_root / "remote.git"
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.project, check=True)
        self.commit_project("initial project")
        subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(remote)], check=True)
        subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=self.project, check=True)
        subprocess.run(["git", "push", "-q", "-u", "origin", "main"], cwd=self.project, check=True)
        return remote

    def make_project_facts_meaningful(self, *names: str) -> None:
        mapping = {
            "product.md": self.project / "docs" / "features" / "project-core" / "product.md",
            "architecture.md": self.project / "docs" / "features" / "project-core" / "development.md",
            "testing.md": self.project / "docs" / "features" / "project-core" / "testing.md",
            "design.md": self.project / "docs" / "features" / "project-core" / "design.md",
            "security.md": self.project / "docs" / "shared" / "security.md",
        }
        for name in names:
            path = mapping[name]
            path.write_text(path.read_text(encoding="utf-8") + "\n已由项目确认的真实事实。\n", encoding="utf-8")

    def plan_for(self, extra: dict[str, Any] | None = None) -> Path:
        value: dict[str, Any] = {
            "背景": "当前能力需要调整。",
            "目标": "交付可验证结果。",
            "非目标": "不改变未授权范围。",
            "成功标准": ["目标结果可验证"],
            "执行内容": ["按任务包执行"],
            "验收结果": ["按前置标准验收"],
        }
        value.update(extra or {})
        return self.write_json(f"plan-{len(list(self.temp_root.glob('plan-*')))}.json", value)

    def evidence(
        self,
        name: str,
        *,
        evidence_type: str,
        covers: str,
        changed_paths: list[str],
        read_set: list[dict[str, str]] | None = None,
        concurrent_drift: list[str] | None = None,
        producer: dict[str, str] | None = None,
        write_set: list[str] | None = None,
    ) -> Path:
        runs = HARNESS_MODULE.runtime_root(self.project)
        state: Path | None = None
        direct = runs / covers
        if direct.is_dir():
            state = direct
        else:
            for candidate in sorted(runs.iterdir() if runs.is_dir() else []):
                package_path = candidate / "task-package.json"
                if not package_path.is_file():
                    continue
                candidate_package = json.loads(package_path.read_text(encoding="utf-8"))
                work_ids = {item["work_package_id"] for item in candidate_package.get("work_packages", [])}
                if covers in work_ids:
                    state = candidate
                    break
        if state is None:
            raise AssertionError(f"无法为证据定位任务包：{covers}")
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        now = HARNESS_MODULE.utc_now()
        return self.write_json(
            f"evidence-{name}.json",
            {
                "schema_version": "docs-harness/evidence-receipt/v2",
                "id": name,
                "type": evidence_type,
                "result": "passed",
                "covers": [covers],
                "task_id": package["task_id"],
                "target_identity": HARNESS_MODULE.target_identity(self.project),
                "package_fingerprint": HARNESS_MODULE.package_fingerprint(package),
                "content_set_fingerprint": None,
                "producer": producer or {"adapter": "codex-host", "capability": "review_receipt"},
                "command_argv_digest": HARNESS_MODULE.sha256_text("test-receipt-command"),
                "cwd": str(self.project.resolve()),
                "started_at": now,
                "ended_at": now,
                "ttl": 3600,
                "exit_code": 0,
                "output_or_artifact_digest": HARNESS_MODULE.sha256_text(name),
                "changed_paths": changed_paths,
                "read_set": read_set or [],
                "write_set": write_set if write_set is not None else changed_paths,
                "concurrent_drift": concurrent_drift or [],
                "conclusion": "验收通过",
            },
        )

    def quality_review(self, name: str, extra: dict[str, Any] | None = None) -> Path:
        value: dict[str, Any] = {
            "schema_version": "docs-harness/quality-review/v1",
            "task_summary": "为项目补充可复用的质量经验。",
            "record_reason": "这次任务包含值得复用的决策。",
            "outcome_summary": "任务状态与验收事实已经形成快照。",
            "delivered_value": ["后续智能体可以复用本次经验。"],
            "issues_and_rework": ["首次方案需要收敛数据边界。"],
            "cost_observations": [
                {"description": "执行时间来自当前任务观察。", "source": "observed"}
            ],
            "lessons": ["先固定个人本地与一次性快照边界。"],
            "residual_risks": ["尚未经过大规模账本检索验证。"],
            "next_actions": ["在后续相似任务前按关键词读取。"],
        }
        value.update(extra or {})
        return self.write_json(f"quality-review-{name}.json", value)

    def complete_code_task(self, relative: str = "src/core.py") -> tuple[dict[str, Any], dict[str, Any]]:
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", f"实现项目核心 `{relative}` 代码", "--scope", relative
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = 1\n", encoding="utf-8")
        evidence = self.evidence(f"complete-{path.stem}", evidence_type="test_result", covers=task_id, changed_paths=[relative])
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        return routed, verified

    def test_shipped_rules_are_active_and_self_tested(self) -> None:
        self.assertEqual(
            {path.name for path in RULES.glob("*.md")} - {"INDEX.md", "_rule-template.md"},
            ACTIVE_RULE_FILES,
        )
        index = (RULES / "INDEX.md").read_text(encoding="utf-8")
        for rule_id in ACTIVE_RULE_IDS:
            self.assertIn(rule_id, index)
        for name in ACTIVE_RULE_FILES:
            content = (RULES / name).read_text(encoding="utf-8")
            self.assertIn("status: active", content)
            self.assertRegex(content, r"rule_id: DH-[A-Z-]+")
            self.assertRegex(content, r"content_fingerprint: sha256:[0-9a-f]{64}")
        _, result = self.run_harness("self-test", "--target", str(ROOT))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(set(result["rules"]), ACTIVE_RULE_IDS)

    def test_project_install_is_portable_and_missing_rules_fail_closed(self) -> None:
        self.init_project()
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertNotIn("source_root", config)
        self.assertNotIn("harness_home", config)
        self.assertEqual(config["rules_root"], ".docs-harness/harness-home/rules")
        local_rules = self.project / config["rules_root"]
        self.assertTrue(local_rules.is_dir())
        self.assertEqual(
            {path.name for path in local_rules.glob("*.md")} - {"INDEX.md", "_rule-template.md"},
            ACTIVE_RULE_FILES,
        )

        shutil.rmtree(local_rules.parent)
        _, checked = self.run_harness("project", "check", "--target", str(self.project), expected=1)
        self.assertEqual(checked["status"], "failed")
        self.assertTrue(
            any(item["severity"] == "red" and item["code"] == "missing_harness_home" for item in checked["findings"])
        )

    def test_new_project_install_creates_feature_knowledge_scaffold_without_claiming_ready(self) -> None:
        installed = self.init_project(bootstrap_knowledge=False)
        self.assertEqual(installed["status"], "installed")
        self.assertEqual(installed["knowledge_status"], "building")
        self.assertFalse(installed["knowledge_flow"]["blocking_install"])
        self.assertEqual(installed["knowledge_flow"]["dispatch_status"], "dispatch_required")
        self.assertEqual(installed["knowledge_flow"]["dispatch_contract"]["task_kind"], "knowledge_bootstrap")
        self.assertEqual(installed["knowledge_next_action"], "bootstrap_knowledge_base")
        self.assertFalse(installed["clone_ready"])
        self.assertTrue((self.project / "docs" / "shared" / "architecture.md").is_file())
        self.assertTrue((self.project / "docs" / "features" / "INDEX.md").is_file())
        knowledge_map = json.loads((self.project / "docs" / "knowledge-map.json").read_text(encoding="utf-8"))
        self.assertEqual(knowledge_map["schema_version"], "docs-harness/knowledge-map/v1")
        self.assertEqual(knowledge_map["features"], [])
        self.assertEqual(installed["knowledge_flow"]["mode"], "bootstrap_new")
        self.assertFalse(installed["knowledge_flow"]["requires_user_consent_before_update"])

    def test_existing_docs_are_audited_without_install_time_content_changes(self) -> None:
        docs = self.project / "docs"
        docs.mkdir()
        custom = docs / "existing-prd.md"
        custom.write_text("# 已有需求\n\n用户保留的真实内容。\n", encoding="utf-8")
        before = self.snapshot_tree(docs)
        installed = self.init_project(bootstrap_knowledge=False)
        self.assertEqual(installed["knowledge_status"], "needs_audit")
        self.assertEqual(installed["knowledge_next_action"], "audit_existing_docs")
        self.assertEqual(self.snapshot_tree(docs), before)
        self.assertFalse((docs / "knowledge-map.json").exists())
        self.assertEqual(installed["knowledge_flow"]["mode"], "audit_existing")
        self.assertTrue(installed["knowledge_flow"]["requires_user_consent_before_update"])

    def test_dynamic_context_resolves_feature_and_loads_only_gate_categories(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修复项目核心模块代码",
            "--scope",
            "src/core.py",
            "--feature",
            "project-core",
        )
        knowledge = routed["knowledge_context"]
        self.assertEqual(knowledge["selected_features"], ["project-core"])
        self.assertEqual(knowledge["categories"], ["development"])
        refs = routed["context_schedule"]["action"]["project_fact_refs"]
        self.assertIn("docs/features/project-core/development.md", refs)
        self.assertNotIn("docs/features/project-core/product.md", refs)
        self.assertNotIn("docs/features/project-core/design.md", refs)

    def test_v15_read_only_query_uses_v2_empty_write_contract(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "项目文档在哪，请解释现有内容",
        )
        self.assertEqual(routed["admission_status"], "ready_direct")
        self.assertEqual(routed["execution_route"], "direct")
        self.assertEqual(routed["task_intent"], "query")
        self.assertEqual(routed["mutation_profile"], "read_only")
        self.assertEqual(routed["write_scope"], [])
        self.assertEqual(routed["allowed_actions"], ["read"])
        self.assertNotIn("document-edit", routed["matched_gates"])
        package = json.loads(Path(routed["task_package_ref"]).read_text(encoding="utf-8"))
        self.assertEqual(package["schema_version"], "docs-harness/task-package/v2")
        self.assertEqual(package["semantic_evidence_requirements"], ["source_trace"])

    def test_v15_branch_delete_audit_stays_read_only(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "审计 feature 分支是否可删除",
        )
        self.assertEqual(routed["task_intent"], "audit")
        self.assertEqual(routed["mutation_profile"], "read_only")
        self.assertEqual(routed["write_scope"], [])
        self.assertTrue(
            any(item["intent"] == "git_inspect" for item in routed["candidate_intents"])
        )

    def test_v15_mixed_audit_fix_uses_highest_mutation_profile(self) -> None:
        self.init_project()
        facts = self.write_json("mixed-intent.json", {"write_scope": ["README.md"]})
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "先审计 README，如需要再修复",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["task_intent"], "audit")
        self.assertEqual(routed["mutation_profile"], "workspace_write")
        self.assertEqual(routed["write_scope"], ["README.md"])
        self.assertEqual(
            {item["intent"] for item in routed["candidate_intents"]},
            {"audit", "modify"},
        )

    def test_v15_natural_language_scope_fails_closed(self) -> None:
        self.init_project()
        facts = self.write_json(
            "invalid-read-scope.json",
            {"task_intent": "query", "read_scope": ["仅只读查询，不产生工作树变更"]},
        )
        _, rejected = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "查询项目状态",
            "--facts",
            str(facts),
            expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_scope_description")

    def test_v169_scope_rejects_json_array_string(self) -> None:
        self.init_project()
        _, rejected = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `a.ts` 与 `b.ts`",
            "--scope",
            '["a.ts", "b.ts"]',
            expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_scope_json")
        self.assertIn("suggested_fix", rejected)
        facts = self.write_json(
            "json-scope-facts.json",
            {"task_intent": "modify", "write_scope": ['["a.ts", "b.ts"]']},
        )
        _, rejected_facts = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `a.ts` 与 `b.ts`",
            "--facts",
            str(facts),
            expected=2,
        )
        self.assertEqual(rejected_facts["code"], "invalid_scope_json")
        self.assertIn("suggested_fix", rejected_facts)

    def test_v173_scope_rejects_semicolon_concatenated(self) -> None:
        self.init_project()
        _, rejected = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改多文件",
            "--scope",
            "src/a.ts; src/b.ts; src/c.ts",
            expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_scope_concatenated")
        self.assertIn("suggested_fix", rejected)

    def test_v173_scope_rejects_comma_concatenated(self) -> None:
        self.init_project()
        _, rejected = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改多文件",
            "--scope",
            "src/a.ts, src/b.ts",
            expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_scope_concatenated")

    def test_v169_windows_posix_path_hint_for_missing_facts_file(self) -> None:
        with mock.patch.object(HARNESS_MODULE.sys, "platform", "win32"):
            with self.assertRaises(HARNESS_MODULE.HarnessError) as ctx:
                HARNESS_MODULE.load_input_file(
                    "/tmp/dh-v169-nonexistent-facts.json",
                    argument="--facts",
                    max_bytes=1024,
                    error_code="invalid_facts",
                )
        self.assertEqual(ctx.exception.code, "invalid_facts")
        self.assertIsNotNone(ctx.exception.suggested_fix)
        self.assertIn("工作区相对路径", ctx.exception.suggested_fix)

    def test_v169_facts_ignored_warns_when_not_readmission(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 `README.md` 文档", "--scope", "README.md"
        )
        facts = self.write_json("late-facts.json", {"success_criteria": ["补充标准"]})
        _, result = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task-id",
            routed["task_id"],
            "--facts",
            str(facts),
        )
        self.assertTrue(result["facts_ignored"])
        self.assertIn("facts_effective_condition", result)

    def test_v169_blocked_readmission_response_includes_contract_snapshot(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 `README.md` 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("ok\n", encoding="utf-8")
        (self.project / "outside.txt").write_text("unexpected\n", encoding="utf-8")
        evidence = self.evidence(
            "scope169",
            evidence_type="document_review",
            covers=task_id,
            changed_paths=["README.md", "outside.txt"],
        )
        self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        facts = self.write_json("readmission-facts.json", {"allowed_scope": ["README.md", "outside.txt"]})
        _, result = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--facts",
            str(facts),
            expected=None,
        )
        snapshot = result["contract_snapshot"]
        self.assertEqual(snapshot["allowed_scope"], ["README.md", "outside.txt"])
        self.assertIn("write_scope", snapshot)
        self.assertIn("read_scope", snapshot)
        self.assertIn("plan_fields", snapshot)
        self.assertIn("evidence_types", snapshot)

    def test_v170_fast_track_ready_direct_minimal_evidence(self) -> None:
        self.init_project()
        facts = self.write_json(
            "fast-track.json",
            {"fast_track": True, "write_scope": ["README.md"]},
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `README.md` 文档",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["admission_status"], "ready_direct")
        self.assertTrue(routed["fast_track"])
        self.assertEqual(routed["evidence_profile"], "fast_track")
        manifest = routed["completion_manifest"]
        self.assertEqual(manifest["evidence_profile"], "fast_track")
        self.assertEqual(manifest["required_evidence_types"], ["code_diff"])
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("updated\n", encoding="utf-8")
        evidence = self.evidence(
            "ft170", evidence_type="code_diff", covers=task_id, changed_paths=["README.md"]
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(verified["control_status"], "complete")
        self.assertEqual(verified["evidence_profile"], "fast_track")

    def test_v170_fast_track_with_verification_command_requires_test_run(self) -> None:
        self.init_project()
        facts = self.write_json(
            "fast-track-verify.json",
            {
                "fast_track": True,
                "write_scope": ["README.md"],
                "verification_commands": [{"argv": [sys.executable, "-m", "unittest"], "produces": ["test_run"]}],
            },
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `README.md` 文档",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["admission_status"], "ready_direct")
        manifest = routed["completion_manifest"]
        self.assertEqual(manifest["evidence_profile"], "fast_track")
        self.assertEqual(manifest["required_evidence_types"], ["code_diff", "test_run"])
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("updated\n", encoding="utf-8")
        evidence = self.evidence(
            "ft170v", evidence_type="code_diff", covers=task_id, changed_paths=["README.md"]
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(verified["control_status"], "complete")

    def test_v170_fast_track_high_gate_denied(self) -> None:
        self.init_project()
        facts = self.write_json(
            "fast-track-denied.json",
            {"fast_track": True, "write_scope": ["docs/api.md"]},
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `docs/api.md` 接口文档",
            "--facts",
            str(facts),
            expected=None,
        )
        self.assertFalse(routed["fast_track"])
        self.assertEqual(routed["fast_track_denied_reason"], "high_gate_present")
        self.assertNotEqual(routed.get("evidence_profile"), "fast_track")
        self.assertNotEqual(routed["admission_status"], "ready_direct")
        self.assertIn("contract_acceptance", routed["completion_manifest"]["required_evidence_types"])
        bad_facts = self.write_json(
            "fast-track-non-bool.json",
            {"fast_track": "yes", "write_scope": ["README.md"]},
        )
        _, rejected = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `README.md` 文档",
            "--facts",
            str(bad_facts),
            expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_facts")

    def test_v170_fast_track_runtime_downgrade_on_new_risk_gate(self) -> None:
        self.init_project()
        (self.project / "guides").mkdir()
        (self.project / "guides" / "intro.md").write_text("# intro\n", encoding="utf-8")
        facts = self.write_json(
            "fast-track-downgrade.json",
            {"fast_track": True, "write_scope": ["guides/"]},
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修订 `guides/` 文档",
            "--facts",
            str(facts),
        )
        self.assertTrue(routed["fast_track"])
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        risky = self.project / "guides" / "api"
        risky.mkdir()
        (risky / "reference.md").write_text("# api\n", encoding="utf-8")
        evidence = self.evidence(
            "ft170d", evidence_type="code_diff", covers=task_id, changed_paths=["guides/api/reference.md"]
        )
        _, rejected = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--evidence",
            str(evidence),
            expected=4,
        )
        self.assertEqual(rejected["reason_code"], "new_risk_gate")
        self.assertTrue(rejected["fast_track_downgraded"])
        state = HARNESS_MODULE.runtime_root(self.project) / task_id
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertFalse(package["fast_track"])
        self.assertTrue(package["fast_track_downgraded"])
        self.assertNotEqual(package["completion_manifest"]["required_evidence_types"], ["code_diff"])
        events = [
            json.loads(line)
            for line in (state / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(any(item.get("event") == "fast_track_downgraded" for item in events))
        _, readmitted = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, expected=None
        )
        self.assertNotEqual(readmitted.get("evidence_profile"), "fast_track")
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertFalse(package["fast_track"])
        self.assertIn("document_review", package["completion_manifest"]["required_evidence_types"])

    def test_v170_non_fast_track_behavior_unchanged(self) -> None:
        self.init_project()
        facts = self.write_json("no-fast-track.json", {"write_scope": ["README.md"]})
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `README.md` 文档",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["admission_status"], "ready_direct")
        self.assertNotIn("fast_track", routed)
        self.assertNotIn("evidence_profile", routed)
        self.assertNotIn("fast_track_denied_reason", routed)
        self.assertIn("document_review", routed["completion_manifest"]["required_evidence_types"])
        package = json.loads(Path(routed["task_package_ref"]).read_text(encoding="utf-8"))
        self.assertFalse(package["fast_track"])

    def test_v170_fast_track_inline_note(self) -> None:
        self.init_project()
        note = "修正 README 中过时的安装命令说明，仅文档措辞调整。"
        facts = self.write_json(
            "fast-track-note.json",
            {"fast_track": True, "write_scope": ["README.md"], "inline_note": note},
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `README.md` 文档",
            "--facts",
            str(facts),
        )
        self.assertTrue(routed["fast_track"])
        self.assertEqual(routed["inline_note"], note)
        package = json.loads(Path(routed["task_package_ref"]).read_text(encoding="utf-8"))
        self.assertEqual(package["inline_note"], note)
        self.assertFalse((self.project / "docs" / "plans").exists())
        plain_facts = self.write_json(
            "plain-note.json",
            {"write_scope": ["CHANGELOG.md"], "inline_note": note},
        )
        _, plain = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `CHANGELOG.md` 文档",
            "--facts",
            str(plain_facts),
        )
        self.assertTrue(plain["inline_note_ignored"])
        oversized = self.write_json(
            "oversized-note.json",
            {"fast_track": True, "write_scope": ["README.md"], "inline_note": "长" * 201},
        )
        _, rejected = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `README.md` 文档",
            "--facts",
            str(oversized),
            expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_facts")

    def test_v170_task_status_overhead_summary(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 `README.md` 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        _, status = self.run_harness(
            "task", "status", "--target", str(self.project), "--task-id", task_id
        )
        summary = status["overhead_summary"]
        self.assertGreater(summary["harness_total_ms"], 0)
        self.assertGreaterEqual(summary["wall_clock_ms"], 0)
        self.assertIn("harness_share", summary)
        if summary["wall_clock_ms"] > 0:
            self.assertIsNotNone(summary["harness_share"])
        else:
            self.assertIsNone(summary["harness_share"])

    def make_release_source(self, *, version: str = "9.9.9", name: str = "release-src") -> Path:
        source = self.temp_root / name
        (source / "scripts").mkdir(parents=True, exist_ok=True)
        (source / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (source / "package.json").write_text(
            json.dumps({"name": "docs-harness", "version": version}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (source / "SKILL.md").write_text(
            f"---\nname: docs-harness\nmetadata:\n  version: {version}\n  status: active\n---\n\n# Docs Harness\n",
            encoding="utf-8",
        )
        (source / "scripts" / "harness.py").write_text(
            f'#!/usr/bin/env python3\nVERSION = "{version}"\n', encoding="utf-8"
        )
        (source / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## {version} - 2026-08-07\n\n- 条目\n", encoding="utf-8"
        )
        return source

    def rewrite_release_source_version(self, source: Path, relative: str, version: str) -> None:
        path = source / relative
        text = path.read_text(encoding="utf-8")
        updated = re.sub(r"[0-9]+\.[0-9]+\.[0-9]+", version, text, count=1)
        self.assertNotEqual(updated, text)
        path.write_text(updated, encoding="utf-8")

    def test_v171_release_sync_check_consistent(self) -> None:
        source = self.make_release_source()
        _, payload = self.run_harness("release", "sync", "--target", str(source))
        self.assertEqual(payload["status"], "consistent")
        self.assertEqual(payload["version_truth"], "9.9.9")
        self.assertEqual(payload["diffs"], [])
        self.assertEqual(payload["changelog_top_version"], "9.9.9")
        self.assertNotIn("changelog_hint", payload)

    def test_v171_release_sync_check_inconsistent_package(self) -> None:
        source = self.make_release_source()
        self.rewrite_release_source_version(source, "package.json", "9.9.8")
        _, payload = self.run_harness("release", "sync", "--target", str(source), expected=2)
        self.assertEqual(payload["status"], "inconsistent")
        self.assertEqual(
            payload["diffs"],
            [{"source": "package", "expected": "9.9.9", "actual": "9.9.8"}],
        )
        self.assertEqual(payload["version_truth"], "9.9.9")

    def test_v171_release_sync_apply_atomic_write(self) -> None:
        source = self.make_release_source()
        self.rewrite_release_source_version(source, "VERSION", "9.9.8")
        self.rewrite_release_source_version(source, "SKILL.md", "9.9.8")
        _, payload = self.run_harness("release", "sync", "--apply", "--target", str(source))
        self.assertEqual(payload["status"], "synced")
        self.assertEqual(payload["version"], "9.9.9")
        self.assertEqual(sorted(payload["changed"]), ["SKILL.md", "VERSION"])
        _, check = self.run_harness("release", "sync", "--target", str(source))
        self.assertEqual(check["status"], "consistent")
        self.assertEqual((source / "VERSION").read_text(encoding="utf-8"), "9.9.9\n")
        package = json.loads((source / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], "9.9.9")
        metadata, _ = HARNESS_MODULE.parse_frontmatter((source / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(metadata.get("version"), "9.9.9")
        _, again = self.run_harness("release", "sync", "--apply", "--target", str(source))
        self.assertEqual(again["status"], "already_consistent")
        self.assertEqual(again["changed"], [])

    def test_v171_release_sync_apply_rollback_no_partial_write(self) -> None:
        source = self.make_release_source(name="release-rollback")
        self.rewrite_release_source_version(source, "VERSION", "9.9.8")
        self.rewrite_release_source_version(source, "SKILL.md", "9.9.8")
        originals = {
            relative: (source / relative).read_bytes()
            for relative in ("VERSION", "package.json", "SKILL.md")
        }
        # 注入：破坏 SKILL.md 版本源可读性（macOS 上 chmod 无法阻止 os.replace，故改用内容破坏）
        (source / "SKILL.md").write_text("not a valid skill document\n", encoding="utf-8")
        try:
            _, payload = self.run_harness(
                "release", "sync", "--apply", "--target", str(source), expected=1
            )
            self.assertEqual(payload["code"], "release_source_unreadable")
        finally:
            (source / "SKILL.md").write_bytes(originals["SKILL.md"])
        for relative, content in originals.items():
            self.assertEqual(
                (source / relative).read_bytes(),
                content,
                f"{relative} 出现部分写入，原子性被破坏",
            )
        leftovers = [path.name for path in source.glob(".*.release-sync-*")]
        self.assertEqual(leftovers, [])

    def test_v171_release_sync_target_version_conflict(self) -> None:
        source = self.make_release_source()
        _, conflict = self.run_harness(
            "release", "sync", "--target-version", "9.9.8", "--target", str(source), expected=2
        )
        self.assertEqual(conflict["code"], "release_version_conflict")
        _, confirmed = self.run_harness(
            "release", "sync", "--apply", "--target-version", "9.9.9", "--target", str(source)
        )
        self.assertEqual(confirmed["status"], "already_consistent")

    def test_v171_layer_reuse_snapshot_cache(self) -> None:
        HARNESS_MODULE.reset_layer_reuse_cache()
        self.addCleanup(HARNESS_MODULE.reset_layer_reuse_cache)
        self.init_project()
        target_id = HARNESS_MODULE.target_identity(self.project)
        kwargs = {"contract_version": HARNESS_MODULE.VERSION, "target_id": target_id}
        first = HARNESS_MODULE.cached_workspace_snapshot(self.project, **kwargs)
        second = HARNESS_MODULE.cached_workspace_snapshot(self.project, **kwargs)
        self.assertEqual(first, second)
        stats = HARNESS_MODULE.layer_reuse_stats()
        self.assertEqual(stats["snapshot_hits"], 1)
        self.assertEqual(stats["snapshot_misses"], 1)
        # 合同版本变化 → 缓存失效重算
        third = HARNESS_MODULE.cached_workspace_snapshot(
            self.project, contract_version="0.0.0", target_id=target_id
        )
        self.assertEqual(third, first)
        self.assertEqual(HARNESS_MODULE.layer_reuse_stats()["snapshot_misses"], 2)
        # 工作区内容变化 → 清单摘要漂移，缓存失效重算
        (self.project / "README.md").write_text("changed\n", encoding="utf-8")
        fourth = HARNESS_MODULE.cached_workspace_snapshot(self.project, **kwargs)
        self.assertNotEqual(fourth, first)
        self.assertEqual(HARNESS_MODULE.layer_reuse_stats()["snapshot_misses"], 3)

    def test_v171_verify_response_reports_layer_reuse(self) -> None:
        self.init_project()
        facts = self.write_json(
            "ft171.json", {"fast_track": True, "write_scope": ["README.md"]}
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 `README.md` 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("updated\n", encoding="utf-8")
        evidence = self.evidence(
            "ft171", evidence_type="code_diff", covers=task_id, changed_paths=["README.md"]
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(verified["control_status"], "complete")
        reuse = verified["layer_reuse"]
        self.assertGreaterEqual(reuse["snapshot_hits"], 1)
        self.assertGreaterEqual(reuse["snapshot_misses"], 1)

    def test_v172_prepare_and_run_matches_stepwise_event_sequence(self) -> None:
        self.init_project()
        _, verified_a = self.complete_code_task("src/v172-stepwise.py")
        stepwise_id = verified_a["post_completion"]["job_id"]
        self.force_complex_background_job(stepwise_id, ["包一", "包二"])
        self.start_complex_background_job(stepwise_id)
        stepwise_events = self.background_event_sequence(stepwise_id)
        # 释放知识锁，避免后续 Job 的 running 闸门互斥
        self.cancel_background_job(stepwise_id)

        _, verified_b = self.complete_code_task("src/v172-merged.py")
        merged_id = verified_b["post_completion"]["job_id"]
        self.force_complex_background_job(merged_id, ["包一", "包二"])
        _, merged = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", merged_id,
            "--job-status", "running", "--prepare-and-run",
        )
        self.assertEqual(merged["status"], "running")
        self.assertTrue(merged["prepare_and_run"])
        self.assertEqual(merged["prepare_status"], "prepared")
        self.assertEqual(merged["dispatch_sequence"], ["prepare", "dispatched", "running"])
        self.assertEqual(merged["completed_steps"], ["prepare", "dispatched", "running"])
        self.assertEqual(self.background_event_sequence(merged_id), stepwise_events)
        self.cancel_background_job(merged_id)

        # 幂等：已分步 prepare 且指纹一致时合并命令复用 already_prepared，不重复写工件与事件
        _, verified_c = self.complete_code_task("src/v172-idempotent.py")
        idem_id = verified_c["post_completion"]["job_id"]
        self.force_complex_background_job(idem_id, ["包一", "包二"])
        self.write_background_goal_artifacts(idem_id)
        _, reused = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", idem_id,
            "--job-status", "running", "--prepare-and-run",
        )
        self.assertEqual(reused["status"], "running")
        self.assertEqual(reused["prepare_status"], "already_prepared")
        self.assertEqual(self.background_event_sequence(idem_id), stepwise_events)

    def test_v172_prepare_and_run_gate_failures_stop_at_matching_step(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/v172-gate.py")
        job_id = verified["post_completion"]["job_id"]
        self.force_complex_background_job(job_id, ["闸门包"])
        self.write_background_goal_artifacts(job_id)
        # prepare 闸门：工件指纹漂移时与分步 prepare 返回相同错误码
        root = self.project / ".docs-harness" / "background" / "jobs" / job_id
        plan_path = root / "plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["objective"] = "被篡改的目标"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _, stepwise_prepare = self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", job_id, expected=3
        )
        _, merged = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id,
            "--job-status", "running", "--prepare-and-run", expected=3,
        )
        self.assertEqual(merged["code"], stepwise_prepare["code"])
        self.assertEqual(merged["code"], "invalid_background_goal_artifacts")
        _, status = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", job_id
        )
        self.assertEqual(status["status"], "contract_ready")
        self.assertNotIn(
            "dispatched", [item["event"] for item in self.background_event_sequence(job_id)]
        )

        # running 闸门：知识基线漂移停在 running，与分步 dispatch running 返回相同结论
        _, verified_a = self.complete_code_task("src/v172-drift-stepwise.py")
        stepwise_id = verified_a["post_completion"]["job_id"]
        self.force_complex_background_job(stepwise_id, ["漂移包"])
        self.write_background_goal_artifacts(stepwise_id)
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", stepwise_id,
            "--job-status", "dispatched",
        )
        _, verified_b = self.complete_code_task("src/v172-drift-merged.py")
        merged_id = verified_b["post_completion"]["job_id"]
        self.force_complex_background_job(merged_id, ["漂移包"])
        (self.project / "docs" / "todo.md").write_text("# TODO\n\n- 外部改动\n", encoding="utf-8")
        _, stepwise_drift = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", stepwise_id,
            "--job-status", "running", expected=3,
        )
        _, merged_drift = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", merged_id,
            "--job-status", "running", "--prepare-and-run", expected=3,
        )
        self.assertEqual(merged_drift["status"], "needs_rebase")
        self.assertEqual(merged_drift["reason_code"], stepwise_drift["reason_code"])
        self.assertEqual(merged_drift["changed_paths"], stepwise_drift["changed_paths"])
        self.assertTrue(merged_drift["prepare_and_run"])
        self.assertEqual(merged_drift["completed_steps"], ["prepare", "dispatched"])
        self.assertEqual(
            [item["event"] for item in self.background_event_sequence(merged_id)],
            ["created", "prepared", "dispatched", "needs_rebase"],
        )

    def test_v172_progress_all_completed_batch_and_no_partial_commit(self) -> None:
        self.init_project()
        _, verified_a = self.complete_code_task("src/v172-all-stepwise.py")
        stepwise_id = verified_a["post_completion"]["job_id"]
        self.force_complex_background_job(stepwise_id, ["包一", "包二", "包三"])
        self.start_complex_background_job(stepwise_id)
        self.complete_background_work_packages(stepwise_id)
        stepwise_events = self.background_event_sequence(stepwise_id)
        stepwise_progress = json.loads(
            (self.project / ".docs-harness" / "background" / "jobs" / stepwise_id / "progress.json").read_text(encoding="utf-8")
        )
        # 释放知识锁，避免后续 Job 的 running 闸门互斥
        self.cancel_background_job(stepwise_id)

        _, verified_b = self.complete_code_task("src/v172-all-merged.py")
        merged_id = verified_b["post_completion"]["job_id"]
        self.force_complex_background_job(merged_id, ["包一", "包二", "包三"])
        self.start_complex_background_job(merged_id)
        _, batch = self.run_harness(
            "background", "progress", "--target", str(self.project), "--job-id", merged_id,
            "--all", "completed",
        )
        self.assertEqual(batch["remaining_work_packages"], [])
        self.assertEqual(len(batch["updated_work_packages"]), 3)
        self.assertEqual(batch["already_completed_work_packages"], [])
        self.assertEqual(batch["completed_work_packages"], stepwise_progress["completed_work_packages"])
        self.assertEqual(self.background_event_sequence(merged_id), stepwise_events)
        self.cancel_background_job(merged_id)

        # 非法前置态（blocked）→ 整体拒绝，不部分提交
        _, verified_c = self.complete_code_task("src/v172-all-blocked.py")
        blocked_id = verified_c["post_completion"]["job_id"]
        self.force_complex_background_job(blocked_id, ["包一", "包二"])
        self.start_complex_background_job(blocked_id)
        progress_path = self.project / ".docs-harness" / "background" / "jobs" / blocked_id / "progress.json"
        first = json.loads(progress_path.read_text(encoding="utf-8"))["work_package_states"][0]["id"]
        self.run_harness(
            "background", "progress", "--target", str(self.project), "--job-id", blocked_id,
            "--work-package-id", first, "--work-package-status", "blocked",
        )
        _, rejected = self.run_harness(
            "background", "progress", "--target", str(self.project), "--job-id", blocked_id,
            "--all", "completed", expected=3,
        )
        self.assertEqual(rejected["code"], "background_progress_all_blocked")
        self.assertEqual(rejected["blocking_work_packages"], [{"id": first, "status": "blocked"}])
        self.assertFalse(rejected["partial_commit"])
        states = {
            item["id"]: item["status"]
            for item in json.loads(progress_path.read_text(encoding="utf-8"))["work_package_states"]
        }
        self.assertEqual(states[first], "blocked")
        self.assertEqual(set(states.values()), {"blocked", "pending"})
        advanced = [
            item for item in self.background_event_sequence(blocked_id)
            if item.get("event") == "progress_updated" and item.get("work_package_status") != "blocked"
        ]
        self.assertEqual(advanced, [])

    def test_v172_prepare_and_run_rejects_ineligible_routes(self) -> None:
        self.init_project()
        # phased 路线拒绝
        _, verified_a = self.complete_code_task("src/v172-phased.py")
        phased_id = verified_a["post_completion"]["job_id"]
        self.force_complex_background_job(phased_id, ["阶段包"], route="background_goal_phased")
        _, phased = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", phased_id,
            "--job-status", "running", "--prepare-and-run", expected=3,
        )
        self.assertEqual(phased["code"], "background_prepare_and_run_not_eligible")
        self.assertEqual(phased["eligibility_reason_code"], "route_phased_oversized")
        _, phased_status = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", phased_id
        )
        self.assertEqual(phased_status["status"], "contract_ready")
        self.assertEqual(
            [item["event"] for item in self.background_event_sequence(phased_id)],
            ["created", "transition_rejected"],
        )

        # direct 路线拒绝（行为不变：本来就直达，不使用合并入口）
        _, verified_b = self.complete_code_task("src/v172-direct.py")
        direct_id = verified_b["post_completion"]["job_id"]
        _, direct = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", direct_id,
            "--job-status", "running", "--prepare-and-run", expected=3,
        )
        self.assertEqual(direct["code"], "background_prepare_and_run_not_eligible")
        self.assertEqual(direct["eligibility_reason_code"], "route_not_complex_goal")

        # change_scoped 分数 ≥60 拒绝
        _, verified_c = self.complete_code_task("src/v172-score.py")
        score_id = verified_c["post_completion"]["job_id"]
        self.force_complex_background_job(score_id, ["高分包"])
        _, score_status = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", score_id
        )
        estimate_path = Path(score_status["workload_estimate_ref"])
        estimate = json.loads(estimate_path.read_text(encoding="utf-8"))
        estimate["raw_score"] = 75
        estimate_path.write_text(json.dumps(estimate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _, scored = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", score_id,
            "--job-status", "running", "--prepare-and-run", expected=3,
        )
        self.assertEqual(scored["code"], "background_prepare_and_run_not_eligible")
        self.assertEqual(scored["eligibility_reason_code"], "score_not_below_60")

        # 声明制：未显式给出 --job-status running 失败关闭
        _, missing = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", score_id,
            "--prepare-and-run", expected=2,
        )
        self.assertEqual(missing["code"], "invalid_background_job_status")

    def test_v15_git_fetch_has_independent_metadata_contract(self) -> None:
        self.init_project()
        self.init_git_remote()
        facts = self.write_json(
            "git-fetch.json",
            {
                "task_intent": "git_fetch",
                "git_scope": [".git:refs/remotes/origin/*"],
            },
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "执行 git fetch 获取远端引用",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["admission_status"], "ready_direct")
        self.assertEqual(routed["mutation_profile"], "git_metadata_write")
        self.assertEqual(routed["write_scope"], [])
        self.assertEqual(routed["git_scope"], [".git:refs/remotes/origin/*"])
        self.assertIn("git_fetch", routed["allowed_actions"])
        _, verified = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            routed["task_id"],
        )
        self.assertEqual(verified["control_status"], "complete")
        self.assertTrue(verified["git_postcheck"]["passed"])
        self.assertIn("git_fetch_result", verified["evidence_types"])

    def test_v15_remote_identity_strips_credentials_and_query_material(self) -> None:
        clean = HARNESS_MODULE.sanitized_remote_fingerprint("https://example.com/repo.git")
        credentialed = HARNESS_MODULE.sanitized_remote_fingerprint(
            "https://user:token@example.com/repo.git?access_token=secret#fragment"
        )
        self.assertEqual(clean, credentialed)
        self.assertEqual(
            HARNESS_MODULE.sanitized_remote_fingerprint("git@example.com:team/repo.git"),
            HARNESS_MODULE.sanitized_remote_fingerprint("example.com:team/repo.git"),
        )

    def test_v15_git_fetch_allows_only_declared_remote_ref_change(self) -> None:
        self.init_project()
        remote = self.init_git_remote()
        other = self.temp_root / "fetch-source"
        subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        (other / "fetched.txt").write_text("remote\n", encoding="utf-8")
        subprocess.run(["git", "add", "fetched.txt"], cwd=other, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Remote Test", "-c", "user.email=remote@example.invalid", "commit", "-q", "-m", "fetch target"],
            cwd=other,
            check=True,
        )
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=other, check=True)
        facts = self.write_json(
            "git-fetch-ref-change.json",
            {"task_intent": "git_fetch", "git_scope": [".git:refs/remotes/origin/*"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "执行 git fetch 获取远端引用", "--facts", str(facts)
        )
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", routed["task_id"]
        )
        self.assertTrue(verified["git_postcheck"]["passed"])
        self.assertEqual(verified["git_postcheck"]["changed_refs"], ["refs/remotes/origin/main"])
        self.assertEqual(verified["git_postcheck"]["outside_refs"], [])

    def test_v15_git_inspect_is_read_only_direct(self) -> None:
        self.init_project()
        facts = self.write_json(
            "git-inspect.json",
            {"git_scope": [".git:history"]},
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "用 git log 查看提交历史",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["task_intent"], "git_inspect")
        self.assertEqual(routed["mutation_profile"], "read_only")
        self.assertEqual(routed["admission_status"], "ready_direct")
        self.assertIn("git_inspect", routed["allowed_actions"])

    def test_v15_git_sync_is_planned_without_manual_write_scope(self) -> None:
        self.init_project()
        self.init_git_remote()
        facts = self.write_json(
            "git-sync.json",
            {"git_scope": [".git:refs/remotes/origin/main"]},
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "执行 git pull 同步远端",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["task_intent"], "git_sync")
        self.assertEqual(routed["mutation_profile"], "workspace_write")
        self.assertEqual(routed["admission_status"], "needs_plan")
        self.assertEqual(routed["write_scope"], [])
        self.assertFalse(routed["plan_contract"]["scope_required"])
        self.assertIn("git_sync", routed["allowed_actions"])

    def test_v15_git_sync_remote_drift_forces_readmission(self) -> None:
        self.init_project()
        remote = self.init_git_remote()
        facts = self.write_json(
            "git-sync-drift.json",
            {"git_scope": [".git:refs/remotes/origin/main"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "执行 git pull 同步远端", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for()
        self.run_harness("run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan))

        other = self.temp_root / "other"
        subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        (other / "remote-change.txt").write_text("remote\n", encoding="utf-8")
        subprocess.run(["git", "add", "remote-change.txt"], cwd=other, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Remote Test", "-c", "user.email=remote@example.invalid", "commit", "-q", "-m", "remote drift"],
            cwd=other,
            check=True,
        )
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=other, check=True)
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=4
        )
        self.assertEqual(blocked["reason_code"], "git_remote_drift")
        self.assertFalse(blocked["git_postcheck"]["checks"]["remote_target_unchanged"])

    def test_v15_git_sync_preflight_scope_and_postcheck_complete(self) -> None:
        self.init_project()
        remote = self.init_git_remote()
        other = self.temp_root / "sync-source"
        subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        (other / "synced.txt").write_text("from remote\n", encoding="utf-8")
        subprocess.run(["git", "add", "synced.txt"], cwd=other, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Remote Test", "-c", "user.email=remote@example.invalid", "commit", "-q", "-m", "sync target"],
            cwd=other,
            check=True,
        )
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=other, check=True)
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        facts = self.write_json(
            "git-sync-complete.json",
            {"git_scope": [".git:refs/remotes/origin/main"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "执行 git pull 同步远端", "--facts", str(facts)
        )
        self.assertEqual(routed["write_scope"], ["synced.txt"])
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for()
        self.run_harness("run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan))
        subprocess.run(["git", "merge", "--ff-only", "origin/main"], cwd=self.project, check=True, capture_output=True)
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(verified["control_status"], "complete")
        self.assertEqual(verified["changed_paths"], ["synced.txt"])
        self.assertTrue(verified["git_postcheck"]["passed"])

    def test_v15_git_sync_dirty_overlap_is_blocked_in_preflight(self) -> None:
        self.init_project()
        remote = self.init_git_remote()
        other = self.temp_root / "dirty-source"
        subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        (other / "README.md").write_text("remote\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=other, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Remote Test", "-c", "user.email=remote@example.invalid", "commit", "-q", "-m", "remote readme"],
            cwd=other,
            check=True,
        )
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=other, check=True)
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        (self.project / "README.md").write_text("local dirty\n", encoding="utf-8")
        facts = self.write_json(
            "git-sync-dirty.json",
            {"git_scope": [".git:refs/remotes/origin/main"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "执行 git pull 同步远端", "--facts", str(facts), expected=3
        )
        self.assertEqual(routed["admission_status"], "blocked")
        self.assertTrue(any("脏工作区" in blocker for blocker in routed["blockers"]))

    def test_v15_git_sync_non_fast_forward_is_blocked_in_preflight(self) -> None:
        self.init_project()
        remote = self.init_git_remote()
        (self.project / "local.txt").write_text("local\n", encoding="utf-8")
        self.commit_project("local divergence")
        other = self.temp_root / "diverged-source"
        subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        (other / "remote.txt").write_text("remote\n", encoding="utf-8")
        subprocess.run(["git", "add", "remote.txt"], cwd=other, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Remote Test", "-c", "user.email=remote@example.invalid", "commit", "-q", "-m", "remote divergence"],
            cwd=other,
            check=True,
        )
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=other, check=True)
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        facts = self.write_json(
            "git-sync-diverged.json",
            {"git_scope": [".git:refs/remotes/origin/main"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "执行 git pull 同步远端", "--facts", str(facts), expected=3
        )
        self.assertEqual(routed["admission_status"], "blocked")
        self.assertTrue(any("fast-forward" in blocker for blocker in routed["blockers"]))

    def test_v15_git_preflight_fails_closed_when_lfs_or_submodule_unavailable(self) -> None:
        self.init_project()
        self.init_git_remote()
        (self.project / ".gitattributes").write_text("*.bin filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")
        (self.project / ".gitmodules").write_text("[submodule \"missing\"]\n\tpath = deps/missing\n\turl = ../missing.git\n", encoding="utf-8")
        original = HARNESS_MODULE.git_command

        def unavailable(target: Path, *arguments: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
            if arguments[:2] in {("lfs", "version"), ("submodule", "status")}:
                return subprocess.CompletedProcess(["git", *arguments], 1, "", "unavailable")
            return original(target, *arguments, timeout=timeout)

        with mock.patch.object(HARNESS_MODULE, "git_command", side_effect=unavailable):
            snapshot, _, blockers = HARNESS_MODULE.git_preflight_contract(
                self.project,
                "git_fetch",
                [".git:refs/remotes/origin/*"],
            )
        self.assertIsNotNone(snapshot)
        self.assertIn("Git LFS 不可用", blockers)
        self.assertIn("Git Submodule 状态不可验证", blockers)

    def test_v15_fetch_sync_mixed_intent_uses_workspace_safety_upper_bound(self) -> None:
        self.init_project()
        self.init_git_remote()
        facts = self.write_json(
            "fetch-sync.json",
            {"git_scope": [".git:refs/remotes/origin/main"]},
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "先 git fetch，再同步远端",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["task_intent"], "git_fetch")
        self.assertEqual(routed["mutation_profile"], "workspace_write")
        self.assertEqual(
            {item["intent"] for item in routed["candidate_intents"]},
            {"git_fetch", "git_sync"},
        )

    def test_v15_negated_write_does_not_upgrade_query(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "查询远端状态，不推送，也不要修改文件",
        )
        self.assertEqual(routed["task_intent"], "query")
        self.assertEqual(routed["mutation_profile"], "read_only")
        self.assertNotIn("external_write", {item["intent"] for item in routed["candidate_intents"]})
        self.assertNotIn("modify", {item["intent"] for item in routed["candidate_intents"]})

    def test_v15_read_only_security_audit_keeps_risk_gate(self) -> None:
        self.init_project()
        facts = self.write_gate_facts("read-only-security.json", ["security-sensitive"])
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "审计安全权限配置",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["mutation_profile"], "read_only")
        self.assertIn("security-sensitive", routed["matched_gates"])
        self.assertEqual(routed["admission_status"], "needs_plan")

    def test_v15_unrelated_unattributed_drift_warns_without_blocking_task_write(self) -> None:
        self.init_project()
        facts = self.write_json("drift-scope.json", {"write_scope": ["README.md"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("# Updated\n", encoding="utf-8")
        (self.project / "unrelated.txt").write_text("external\n", encoding="utf-8")
        evidence = self.evidence("drift-task", evidence_type="document_review", covers=task_id, changed_paths=["README.md"])
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        attribution = verified["workspace_attribution"]
        self.assertEqual(attribution["task_write_set"], ["README.md"])
        self.assertEqual(attribution["unattributed_drift"], ["unrelated.txt"])
        self.assertEqual(attribution["warnings"][0]["reason_code"], "unattributed_drift_unrelated")

    def test_v15_reported_concurrent_drift_is_not_promoted_to_verified(self) -> None:
        self.init_project()
        facts = self.write_json("concurrent-scope.json", {"write_scope": ["README.md"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("# Task\n", encoding="utf-8")
        (self.project / "external.txt").write_text("external\n", encoding="utf-8")
        evidence = self.evidence(
            "verified-concurrent",
            evidence_type="document_review",
            covers=task_id,
            changed_paths=["README.md"],
            concurrent_drift=["external.txt"],
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        attribution = verified["workspace_attribution"]
        self.assertEqual(attribution["concurrent_drift"], [])
        self.assertEqual(attribution["reported_concurrent_drift"], ["external.txt"])
        self.assertEqual(attribution["unattributed_drift"], ["external.txt"])
        self.assertEqual(attribution["warnings"][0]["reason_code"], "concurrent_drift_unverified_unrelated")

    def test_v15_high_risk_concurrent_drift_fails_closed(self) -> None:
        self.init_project()
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["gate_path_rules"] = [{"pattern": "security/**", "gates": ["security-sensitive"]}]
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        facts = self.write_json("risky-concurrent.json", {"write_scope": ["README.md"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("# Task\n", encoding="utf-8")
        risky = self.project / "security" / "secret.txt"
        risky.parent.mkdir()
        risky.write_text("external\n", encoding="utf-8")
        evidence = self.evidence(
            "risky-concurrent",
            evidence_type="document_review",
            covers=task_id,
            changed_paths=["README.md"],
            concurrent_drift=["security/secret.txt"],
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertEqual(blocked["reason_code"], "high_risk_drift")

    def test_v15_unattributed_overlap_fails_closed(self) -> None:
        self.init_project()
        # 关闭自动归因，保留 write_scope 内未归因写入的失败关闭行为覆盖
        self.disable_auto_attribution()
        facts = self.write_json("drift-overlap.json", {"write_scope": ["README.md"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("# Unattributed\n", encoding="utf-8")
        evidence = self.evidence("missing-write-receipt", evidence_type="document_review", covers=task_id, changed_paths=[])
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=3
        )
        self.assertEqual(pending["result"], "补充证据")
        self.assertEqual(pending["reason_code"], "unattributed_drift_overlap")
        self.assertEqual(pending["missing_attribution_paths"], ["README.md"])
        self.assertEqual(pending["next_action"], "provide_evidence")
        self.assertEqual(pending["workspace_attribution"]["attribution_quality"], "verified")
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["package_revision"], 1)
        receipt = self.evidence(
            "write-receipt", evidence_type="document_review", covers=task_id, changed_paths=["README.md"]
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(receipt)
        )
        self.assertEqual(verified["result"], "完成")

    def test_v15_read_set_fingerprint_drift_requires_reread(self) -> None:
        self.init_project()
        source = self.project / "source.txt"
        source.write_text("before\n", encoding="utf-8")
        facts = self.write_json(
            "read-set-drift.json",
            {"read_scope": ["source.txt"], "write_scope": ["README.md"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        before = HARNESS_MODULE.file_fingerprint(source)
        (self.project / "README.md").write_text("# Updated\n", encoding="utf-8")
        source.write_text("after\n", encoding="utf-8")
        evidence = self.evidence(
            "read-set",
            evidence_type="document_review",
            covers=task_id,
            changed_paths=["README.md"],
            read_set=[{"path": "source.txt", "fingerprint": before}],
        )
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=3
        )
        self.assertEqual(pending["result"], "补充证据")
        self.assertEqual(pending["reason_code"], "read_set_drift")
        self.assertEqual([item["action"] for item in pending["recovery_actions"]], ["refresh_evidence"])
        self.assertEqual(pending["refresh_paths"], ["source.txt"])
        self.assertEqual(pending["next_action"], "refresh_evidence")
        after = HARNESS_MODULE.file_fingerprint(source)
        refreshed = self.evidence(
            "read-set-refreshed",
            evidence_type="document_review",
            covers=task_id,
            changed_paths=["README.md"],
            read_set=[{"path": "source.txt", "fingerprint": after}],
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(refreshed)
        )
        self.assertEqual(verified["result"], "完成")

    def test_v15_context_content_set_is_loaded_once_per_stage(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        _, first = self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        _, second = self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        self.assertFalse(first["context_cache_hit"])
        self.assertTrue(second["context_cache_hit"])
        self.assertEqual(second["rules"], [])
        self.assertEqual(second["project_facts"], [])
        self.assertEqual(
            first["receipt"]["content_set_fingerprint"],
            second["receipt"]["content_set_fingerprint"],
        )
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        self.assertEqual(len(HARNESS_MODULE.read_jsonl(state / "context-receipts.jsonl")), 1)

    def test_v15_run_returns_fingerprinted_completion_manifest(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md"
        )
        manifest = routed["completion_manifest"]
        self.assertTrue(HARNESS_MODULE.completion_manifest_valid(manifest))
        self.assertEqual(manifest["completion_protocol"], "incremental_receipts_single_final")
        self.assertIn("write_set", manifest["required_receipts"])
        self.assertIn("document_review", manifest["required_evidence_types"])

    def test_v15_evidence_receipt_rejects_cross_package_and_untrusted_producer(self) -> None:
        self.init_project()
        _, first = self.run_harness(
            "run", "--target", str(self.project), "--task", "查询项目文档在哪"
        )
        _, second = self.run_harness(
            "run", "--target", str(self.project), "--task", "查询项目说明在哪"
        )
        receipt = self.evidence(
            "cross-package",
            evidence_type="source_trace",
            covers=first["task_id"],
            changed_paths=[],
            read_set=[{"path": "docs/INDEX.md", "fingerprint": HARNESS_MODULE.file_fingerprint(self.project / "docs" / "INDEX.md")}],
        )
        value = json.loads(receipt.read_text(encoding="utf-8"))
        value["covers"] = [second["task_id"]]
        receipt.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        _, rejected = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", second["task_id"], "--evidence", str(receipt), expected=2
        )
        self.assertEqual(rejected["code"], "evidence_binding_mismatch")

        untrusted = self.evidence(
            "untrusted",
            evidence_type="source_trace",
            covers=second["task_id"],
            changed_paths=[],
            read_set=[{"path": "docs/INDEX.md", "fingerprint": HARNESS_MODULE.file_fingerprint(self.project / "docs" / "INDEX.md")}],
            producer={"adapter": "unknown", "capability": "review_receipt"},
        )
        _, rejected = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", second["task_id"], "--evidence", str(untrusted), expected=2
        )
        self.assertEqual(rejected["code"], "untrusted_evidence_producer")

        expired = self.evidence(
            "expired",
            evidence_type="source_trace",
            covers=second["task_id"],
            changed_paths=[],
            read_set=[{"path": "docs/INDEX.md", "fingerprint": HARNESS_MODULE.file_fingerprint(self.project / "docs" / "INDEX.md")}],
        )
        expired_value = json.loads(expired.read_text(encoding="utf-8"))
        expired_value["started_at"] = "2000-01-01T00:00:00+00:00"
        expired_value["ended_at"] = "2000-01-01T00:00:00+00:00"
        expired_value["ttl"] = 1
        expired.write_text(json.dumps(expired_value, ensure_ascii=False), encoding="utf-8")
        _, rejected = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", second["task_id"], "--evidence", str(expired), expected=3
        )
        self.assertEqual(rejected["code"], "evidence_expired")

        legacy = self.write_json(
            "legacy-evidence.json",
            {
                "id": "legacy",
                "type": "source_trace",
                "result": "passed",
                "covers": [second["task_id"]],
                "changed_paths": [],
            },
        )
        _, rejected = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", second["task_id"], "--evidence", str(legacy), expected=2
        )
        self.assertEqual(rejected["code"], "legacy_evidence_not_accepted")

    def test_v15_v1_task_migration_is_explicit_transactional_and_recoverable(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "查询项目文档在哪"
        )
        task_id = routed["task_id"]
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        for key in (
            "task_intent", "candidate_intents", "mutation_profile", "read_scope", "write_scope",
            "git_scope", "external_scope", "git_operation", "git_state_snapshot", "git_sync_scope",
            "completion_manifest",
        ):
            package.pop(key, None)
        package["schema_version"] = "docs-harness/task-package/v1"
        package["package_revision"] = 1
        fingerprint = HARNESS_MODULE.package_fingerprint(package)
        compiled = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        compiled.update({"schema_version": "docs-harness/compiled-task/v1", "package_revision": 1, "package_fingerprint": fingerprint})
        freeze = json.loads((state / "freeze.json").read_text(encoding="utf-8"))
        freeze.update({"schema_version": "docs-harness/freeze/v1", "package_revision": 1, "package_fingerprint": fingerprint})
        (state / "task-package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        (state / "compiled-task.json").write_text(json.dumps(compiled, ensure_ascii=False, indent=2), encoding="utf-8")
        (state / "freeze.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")

        _, status = self.run_harness("task", "status", "--target", str(self.project), "--task-id", task_id)
        self.assertEqual(status["compatibility_mode"], "v1_read_only")
        self.assertTrue(status["migration_required"])
        _, rejected = self.run_harness("context", "--target", str(self.project), "--task-id", task_id, expected=3)
        self.assertEqual(rejected["code"], "legacy_task_requires_migration")

        objects = ["task-package.json", "compiled-task.json", "freeze.json", "evidence-index.json", "context-receipts.jsonl", "authorization-receipts.jsonl"]
        before = {name: HARNESS_MODULE.file_fingerprint(state / name) for name in objects}
        with self.assertRaises(HARNESS_MODULE.HarnessError) as raised:
            HARNESS_MODULE.migrate_v1_task_state(self.project, task_id, apply=True, fail_after=2)
        self.assertEqual(raised.exception.code, "migration_interrupted")
        self.assertEqual(before, {name: HARNESS_MODULE.file_fingerprint(state / name) for name in objects})
        journal = json.loads((state / "migration-v1-v2" / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(journal["status"], "rolled_back")

        _, preview = self.run_harness("task", "migrate", "--target", str(self.project), "--task-id", task_id)
        self.assertEqual(preview["status"], "migration_preview")
        _, migrated = self.run_harness("task", "migrate", "--target", str(self.project), "--task-id", task_id, "--apply")
        self.assertEqual(migrated["status"], "migrated_needs_readmission")
        migrated_package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(migrated_package["schema_version"], "docs-harness/task-package/v2")
        self.assertTrue((state / "package-history" / "task-package.v1.json").is_file())
        self.assertEqual(json.loads((state / "evidence-index.json").read_text(encoding="utf-8"))["legacy_evidence_read_only"], True)

    def test_v15_legacy_controller_fails_closed_on_v2_task(self) -> None:
        self.init_project()
        _, routed = self.run_harness("run", "--target", str(self.project), "--task", "查询项目文档在哪")
        legacy_script = self.temp_root / "legacy-controller.py"
        legacy_script.write_text(
            HARNESS.read_text(encoding="utf-8").replace(
                'TASK_SCHEMA = "docs-harness/task-package/v2"',
                'TASK_SCHEMA = "docs-harness/task-package/v1"',
                1,
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(legacy_script), "context", "--target", str(self.project), "--task-id", routed["task_id"], "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["code"], "invalid_state")

    def test_v15_telemetry_is_bounded_and_rollback_requires_no_active_v2_tasks(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "查询项目文档在哪"
        )
        task_id = routed["task_id"]
        _, blocked = self.run_harness(
            "project", "rollback-check", "--target", str(self.project), expected=3
        )
        self.assertFalse(blocked["rollback_allowed"])
        self.assertIn(task_id, blocked["active_v2_task_ids"])
        source = self.project / "docs" / "INDEX.md"
        evidence = self.evidence(
            "query-source",
            evidence_type="source_trace",
            covers=task_id,
            changed_paths=[],
            read_set=[{"path": "docs/INDEX.md", "fingerprint": HARNESS_MODULE.file_fingerprint(source)}],
        )
        self.run_harness("verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence))
        _, allowed = self.run_harness("project", "rollback-check", "--target", str(self.project))
        self.assertTrue(allowed["rollback_allowed"])
        events = HARNESS_MODULE.read_jsonl(HARNESS_MODULE.task_state_dir(self.project, task_id) / "events.jsonl")
        required = {
            "phase", "started_at", "duration_ms", "reason_code", "package_revision",
            "context_cache_hit", "context_load_count", "readmission_count", "evidence_round_count",
            "host_receipt_count", "business_action_count",
        }
        self.assertTrue(events)
        self.assertEqual([event["event"] for event in events], ["created", "verification_attempt"])
        attempt = events[-1]
        self.assertEqual(attempt["outcome_class"], "complete")
        self.assertEqual(attempt["reason_codes"], ["complete"])
        self.assertEqual(attempt["evidence_round_count"], 0)
        self.assertFalse(attempt["evidence_regeneration_required"])
        self.assertTrue(all(event["context_load_count"] == 0 for event in events))
        for event in events:
            self.assertTrue(required <= set(event))
            serialized = json.dumps(event, ensure_ascii=False)
            self.assertNotIn("查询项目文档在哪", serialized)
            self.assertNotIn("environment", serialized)

    def test_missing_required_feature_category_degrades_context_but_new_feature_is_allowed(self) -> None:
        self.init_project()
        design = self.project / "docs" / "features" / "project-core" / "design.md"
        design.write_text("# 项目核心：设计事实\n\n待确认。\n", encoding="utf-8")
        _, degraded = self.run_harness(
            "run", "--target", str(self.project), "--task", "修复项目核心 UI 交互", "--scope", "src/view.tsx"
        )
        self.assertEqual(degraded["admission_status"], "needs_plan")
        self.assertEqual(degraded["context_quality"], "degraded")
        self.assertEqual(degraded["knowledge_context"]["missing_categories"], ["design"])
        self.assertEqual(degraded["blockers"], [])

        fresh = self.temp_root / "new-feature-project"
        fresh.mkdir()
        old_project = self.project
        self.project = fresh
        try:
            self.init_project(bootstrap_knowledge=False)
            _, allowed = self.run_harness(
                "run", "--target", str(self.project), "--task", "新增功能：导出报告", "--scope", "src/export.py"
            )
            self.assertEqual(allowed["knowledge_context"]["status"], "new_feature")
            self.assertNotEqual(allowed["admission_status"], "blocked")
        finally:
            self.project = old_project

    def test_run_fails_closed_when_rules_are_missing_or_have_no_active_entries(self) -> None:
        self.init_project()
        rules_root = self.project / ".docs-harness" / "harness-home" / "rules"

        shutil.rmtree(rules_root)
        _, missing = self.run_installed_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 README 文档",
            "--scope",
            "README.md",
            expected=3,
        )
        self.assertEqual(missing["admission_status"], "blocked")
        self.assertTrue(any("规则目录" in item for item in missing["blockers"]))

        rules_root.mkdir(parents=True)
        _, empty = self.run_installed_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 README 文档",
            "--scope",
            "README.md",
            expected=3,
        )
        self.assertEqual(empty["admission_status"], "blocked")
        self.assertTrue(any("active 规则" in item for item in empty["blockers"]))

    def test_git_project_init_blocks_ignored_install_snapshot_before_writes(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        (self.project / ".gitignore").write_text("/.docs-harness/\n", encoding="utf-8")
        _, blocked = self.run_harness(
            "project", "init", "--target", str(self.project), expected=3
        )
        self.assertEqual(blocked["code"], "git_delivery_ignored")
        self.assertFalse((self.project / "scripts" / "harness.py").exists())
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / ".docs-harness").exists())

    def test_git_project_install_requires_current_head_before_clone_ready(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        installed = self.init_project(expected=3)
        self.assertEqual(installed["status"], "needs_delivery")
        self.assertEqual(installed["runtime_status"], "healthy")
        self.assertEqual(installed["delivery_status"], "pending_commit")
        self.assertFalse(installed["clone_ready"])
        self.assertIn("scripts/harness.py", installed["required_commit_paths"])
        self.assertIn(".docs-harness/config.json", installed["required_commit_paths"])

        _, pending = self.run_harness(
            "project", "check", "--target", str(self.project), expected=3
        )
        self.assertEqual(pending["status"], "needs_delivery")
        self.assertEqual(pending["delivery_status"], "pending_commit")
        self.assertFalse(pending["clone_ready"])

        subprocess.run(["git", "add", "-A"], cwd=self.project, check=True)
        _, staged = self.run_harness(
            "project", "check", "--target", str(self.project), expected=3
        )
        self.assertEqual(staged["delivery_status"], "pending_commit")
        self.assertFalse(staged["clone_ready"])

        self.commit_project()
        _, checked = self.run_harness("project", "check", "--target", str(self.project))
        self.assertEqual(checked["status"], "passed")
        self.assertEqual(checked["delivery_status"], "in_head")
        self.assertTrue(checked["clone_ready"])
        self.assertEqual(checked["required_commit_paths"], [])
        repeated = self.init_project()
        self.assertEqual(repeated["status"], "installed")
        self.assertTrue(repeated["clone_ready"])
        self.assertEqual(repeated["changed"], [])

    def test_install_delivery_status_tolerates_autocrlf_line_endings(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run(["git", "config", "core.autocrlf", "true"], cwd=self.project, check=True)
        self.init_project(expected=3)
        self.commit_project()
        script = self.project / "scripts" / "harness.py"
        script.write_bytes(script.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        clean = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", "scripts/harness.py"],
            cwd=self.project,
            check=False,
        )
        self.assertEqual(clean.returncode, 0, "固定装置失效：仅行尾差异时 git 应视为干净")
        _, checked = self.run_harness("project", "check", "--target", str(self.project))
        self.assertEqual(checked["delivery_status"], "in_head")
        self.assertTrue(checked["clone_ready"])

    def test_committed_git_install_survives_fresh_clone(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.init_project(expected=3)
        self.commit_project()
        clone = self.temp_root / "clone"
        subprocess.run(["git", "clone", "-q", str(self.project), str(clone)], check=True)

        checked = subprocess.run(
            [
                sys.executable,
                str(clone / "scripts" / "harness.py"),
                "project",
                "check",
                "--target",
                str(clone),
                "--json",
            ],
            cwd=clone,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        checked_payload = json.loads(checked.stdout)
        self.assertTrue(checked_payload["clone_ready"])
        self.assertEqual(checked_payload["knowledge_status"], "ready")
        self.assertEqual(checked_payload["knowledge_delivery_status"], "in_head")

        routed = subprocess.run(
            [
                sys.executable,
                str(clone / "scripts" / "harness.py"),
                "run",
                "--target",
                str(clone),
                "--task",
                "修改 README 文档",
                "--scope",
                "README.md",
                "--json",
            ],
            cwd=clone,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(routed.returncode, 0, routed.stdout + routed.stderr)
        self.assertEqual(
            json.loads(routed.stdout)["rules"], ["DH-DOCUMENTATION-CHANGES"]
        )

        feature_routed = subprocess.run(
            [
                sys.executable,
                str(clone / "scripts" / "harness.py"),
                "run",
                "--target",
                str(clone),
                "--task",
                "修改项目核心代码",
                "--scope",
                "src/core.py",
                "--feature",
                "project-core",
                "--json",
            ],
            cwd=clone,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(feature_routed.returncode, 0, feature_routed.stdout + feature_routed.stderr)
        feature_payload = json.loads(feature_routed.stdout)
        self.assertEqual(feature_payload["knowledge_context"]["selected_features"], ["project-core"])
        self.assertEqual(feature_payload["knowledge_context"]["categories"], ["development"])
        self.assertIn(
            "docs/features/project-core/development.md",
            feature_payload["context_schedule"]["action"]["project_fact_refs"],
        )

    def test_hidden_project_scope_keeps_leading_dot(self) -> None:
        self.init_project()
        facts = self.write_json("hidden-scope.json", {"allowed_scope": [".docs-harness/**"]})
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "审查隐藏目录范围",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["allowed_scope"], [".docs-harness/**"])

    def test_windows_powershell_task_normalizes_scope_and_loads_rule(self) -> None:
        self.init_project()
        facts = self.write_json("windows-scope.json", {"allowed_scope": [r"scripts\windows\tool.ps1"]})
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            r"修改 Windows PowerShell `scripts\windows\tool.ps1`",
            "--facts",
            str(facts),
        )
        self.assertEqual(routed["allowed_scope"], ["scripts/windows/tool.ps1"])
        self.assertIn("DH-WINDOWS-POWERSHELL-COMPATIBILITY", routed["rules"])
        self.assertIn("PowerShell 宿主与语法", routed["plan_fields"])

    def test_project_init_is_preserve_and_merge_and_check_passes(self) -> None:
        (self.project / "AGENTS.md").write_text("# Existing\n\n用户自己的规则。\n", encoding="utf-8")
        self.init_project()
        agents = (self.project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("用户自己的规则", agents)
        self.assertIn("docs-harness:managed-entry:start", agents)
        self.assertIn("同一行为快照最多一次完整回归", agents)
        self.assertIn("已有完整回归且行为快照未变时必须复用证据", agents)
        self.assertTrue((self.project / "scripts" / "harness.py").is_file())
        _, checked = self.run_harness("project", "check", "--target", str(self.project))
        self.assertEqual(checked["status"], "passed")
        self.assertEqual(checked["red"], 0)
        self.assertFalse(checked["empty_rules_legal"])
        _, diffed = self.run_harness("project", "diff", "--target", str(self.project))
        self.assertEqual(diffed["changes"], [])
        _, preview = self.run_harness("project", "upgrade", "--target", str(self.project))
        self.assertEqual(preview["changes"], [])
        _, repeated = self.run_harness("project", "init", "--target", str(self.project))
        self.assertEqual(repeated["changed"], [])
        installed = subprocess.run(
            [sys.executable, str(self.project / "scripts" / "harness.py"), "self-test", "--target", str(self.project), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout)
        self.assertEqual(json.loads(installed.stdout)["status"], "passed")

    def test_project_upgrade_syncs_owned_version_markers_and_is_idempotent(self) -> None:
        (self.project / "AGENTS.md").write_text(
            "# Existing\n\n用户自己的规则。\n", encoding="utf-8"
        )
        self.init_project()
        agents_path = self.project / "AGENTS.md"
        agents_path.write_text(
            agents_path.read_text(encoding="utf-8").replace(CURRENT_VERSION, "1.4.1"),
            encoding="utf-8",
        )
        index_path = self.project / "docs" / "INDEX.md"
        index_path.write_text(
            index_path.read_text(encoding="utf-8").replace(CURRENT_VERSION, "1.4.1")
            + "\n项目自有内容。\n",
            encoding="utf-8",
        )
        _, marker_check = self.run_harness(
            "project", "check", "--target", str(self.project), expected=1
        )
        marker_codes = {item["code"] for item in marker_check["findings"]}
        self.assertIn("managed_entry_version_mismatch", marker_codes)
        self.assertIn("knowledge_index_version_mismatch", marker_codes)
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["version"] = "1.4.1"
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        _, checked = self.run_harness(
            "project", "check", "--target", str(self.project), expected=1
        )
        finding_codes = {item["code"] for item in checked["findings"]}
        self.assertIn("controller_version_mismatch", finding_codes)

        _, preview = self.run_harness(
            "project", "upgrade", "--target", str(self.project)
        )
        changes = {item["path"]: item for item in preview["changes"]}
        self.assertEqual(changes["docs/INDEX.md"]["from_version"], "1.4.1")
        self.assertEqual(changes["docs/INDEX.md"]["to_version"], CURRENT_VERSION)
        self.assertTrue(preview["apply_completion_possible"])

        _, applied = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )
        self.assertEqual(applied["status"], "upgraded")
        self.assertIn(f"Docs Harness 当前版本：{CURRENT_VERSION}", agents_path.read_text(encoding="utf-8"))
        self.assertIn("用户自己的规则", agents_path.read_text(encoding="utf-8"))
        self.assertIn("项目自有内容", index_path.read_text(encoding="utf-8"))
        _, repeated = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )
        self.assertEqual(repeated["changed"], [])

    def test_project_upgrade_migrates_only_exact_legacy_version_template(self) -> None:
        self.init_project()
        legacy = self.project / "docs" / "modules" / "INDEX.md"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            "# 旧知识索引\n\nDocs Harness 当前版本：1.3.0\n\n- 保留此条目\n",
            encoding="utf-8",
        )
        _, preview = self.run_harness(
            "project", "upgrade", "--target", str(self.project)
        )
        item = next(
            item for item in preview["changes"] if item["path"] == "docs/modules/INDEX.md"
        )
        self.assertEqual(item["action"], "migrate_legacy_version_template")
        _, applied = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )
        self.assertEqual(applied["status"], "upgraded")
        text = legacy.read_text(encoding="utf-8")
        self.assertIn("docs-harness:managed-version:start", text)
        self.assertIn(f"Docs Harness 当前版本：{CURRENT_VERSION}", text)
        self.assertIn("保留此条目", text)

    def test_project_upgrade_reports_ambiguous_legacy_version_without_overwrite(self) -> None:
        self.init_project()
        legacy = self.project / "docs" / "modules" / "INDEX.md"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        original = "# 旧知识索引\n\n项目依据 Docs Harness v1.3.0 建立，其中保留项目事实。\n"
        legacy.write_text(original, encoding="utf-8")
        _, preview = self.run_harness(
            "project", "upgrade", "--target", str(self.project)
        )
        self.assertFalse(preview["apply_completion_possible"])
        self.assertEqual(
            preview["manual_migrations"][0]["reason_code"],
            "unowned_legacy_version_reference",
        )
        _, applied = self.run_harness(
            "project",
            "upgrade",
            "--target",
            str(self.project),
            "--apply",
            expected=3,
        )
        self.assertEqual(applied["status"], "needs_manual_migration")
        self.assertEqual(legacy.read_text(encoding="utf-8"), original)

    def test_source_version_truth_must_be_consistent(self) -> None:
        source = self.temp_root / "source"
        shutil.copytree(ROOT, source)
        (source / "VERSION").write_text("1.4.0\n", encoding="utf-8")
        with self.assertRaises(HARNESS_MODULE.HarnessError) as raised:
            HARNESS_MODULE.validate_project_source(source)
        self.assertEqual(raised.exception.code, "source_version_inconsistent")

    def test_git_project_uses_git_dir_for_runtime_state(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.init_project(expected=3)
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 `README.md` 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        self.assertTrue((self.project / ".git" / "docs-harness" / "runs" / task_id).is_dir())
        self.assertFalse((self.project / ".docs-harness" / "runs" / task_id).exists())

    def test_non_git_snapshot_tracks_install_snapshot_but_excludes_runtime_state(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "调整 `.docs-harness/config.json` 文档",
            "--scope",
            ".docs-harness/config.json",
        )
        task_id = routed["task_id"]
        state = self.project / ".docs-harness" / "runs" / task_id
        freeze = json.loads((state / "freeze.json").read_text(encoding="utf-8"))
        self.assertIn(".docs-harness/config.json", freeze["workspace_snapshot"])
        self.assertTrue(
            all(not path.startswith(".docs-harness/runs/") for path in freeze["workspace_snapshot"])
        )

        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["test_marker"] = "changed"
        # 关闭自动归因，保留 write_scope 内未归因写入的失败关闭行为覆盖
        config.setdefault("verification", {})["auto_attribute_in_scope"] = False
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        self.assertEqual(pending["changed_paths"], [".docs-harness/config.json"])
        self.assertEqual(pending["reason_code"], "unattributed_drift_overlap")

    def test_installed_controller_rejects_project_diff_without_source_rules(self) -> None:
        self.init_project()
        _, rejected = self.run_installed_harness(
            "project", "diff", "--target", str(self.project), expected=2
        )
        self.assertEqual(rejected["code"], "invalid_source")
        self.assertIn("来源包", rejected["message"])

    def test_direct_route_creates_independent_state_and_verifies(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 `README.md` 文档",
            "--scope",
            "README.md",
        )
        self.assertEqual(routed["admission_status"], "ready_direct")
        self.assertEqual(routed["rules"], ["DH-DOCUMENTATION-CHANGES"])
        task_id = routed["task_id"]
        state = self.project / ".docs-harness" / "runs" / task_id
        self.assertTrue((state / "task-package.json").is_file())
        self.assertFalse((self.project / ".git" / "agent-docs-harness").exists())
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("# 新文档\n", encoding="utf-8")
        evidence = self.evidence("direct", evidence_type="document_review", covers=task_id, changed_paths=["README.md"])
        _, verified = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--evidence",
            str(evidence),
        )
        self.assertEqual(verified["result"], "完成")
        self.assertEqual(verified["control_status"], "complete")
        post = verified["post_completion"]
        self.assertEqual(post["status"], "not_required")
        self.assertEqual(post["reason_code"], "no_background_deliverables")
        self.assertEqual(verified["background_jobs"], [])
        compiled = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        self.assertEqual(compiled["control_status"], "complete")

    def test_existing_incomplete_knowledge_requires_reported_consent_and_decline_is_local(self) -> None:
        self.init_project(bootstrap_knowledge=False)
        feature = {
            "feature_id": "report-export",
            "name": "导出报告",
            "aliases": ["报告导出"],
            "feature_type": "user_capability",
            "status": "partial",
            "scope_patterns": ["src/export/**"],
            "documents": {category: f"docs/features/report-export/{category}.md" for category in ("product", "development", "testing", "design")},
            "shared_refs": [],
            "dependencies": [],
            "known_gaps": ["四类功能知识待补全"],
        }
        assessment = self.write_json(
            "knowledge-partial.json",
            {
                "schema_version": "docs-harness/knowledge-assessment/v1",
                "status": "partial",
                "reviewed_revision": "workspace:test",
                "features": [feature],
                "gaps": ["report-export 四类知识不完整"],
            },
        )
        _, audited = self.run_harness(
            "knowledge", "audit", "--target", str(self.project), "--assessment", str(assessment), expected=3
        )
        self.assertEqual(audited["status"], "needs_confirmation")
        self.assertEqual(audited["next_action"], "request_knowledge_update_consent")
        declined = self.write_json(
            "knowledge-declined.json",
            {
                "schema_version": "docs-harness/knowledge-consent/v1",
                "approved": False,
                "authorized_scope": [],
            },
        )
        _, result = self.run_harness(
            "knowledge", "update", "--target", str(self.project), "--assessment", str(assessment), "--consent", str(declined)
        )
        self.assertEqual(result["status"], "declined")
        self.assertTrue((self.project / ".docs-harness" / "knowledge" / "declined.json").is_file())
        self.assertFalse((self.project / "docs" / "features" / "report-export").exists())

        allowed_scope = ["docs/INDEX.md", "docs/features/INDEX.md", "docs/knowledge-map.json"]
        allowed_scope.extend(feature["documents"].values())
        approved = self.write_json(
            "knowledge-approved.json",
            {
                "schema_version": "docs-harness/knowledge-consent/v1",
                "approved": True,
                "authorized_scope": allowed_scope,
            },
        )
        _, prepared = self.run_harness(
            "knowledge", "update", "--target", str(self.project), "--assessment", str(assessment), "--consent", str(approved)
        )
        self.assertEqual(prepared["status"], "contract_ready")
        self.assertEqual(set(prepared["dispatch_contract"]["allowed_write_scope"]), set(allowed_scope))
        job_id = prepared["job_id"]
        self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running"
        )
        feature_root = self.project / "docs" / "features" / "report-export"
        feature_root.mkdir(parents=True)
        for category in ("product", "development", "testing", "design"):
            (feature_root / f"{category}.md").write_text(
                f"# 导出报告：{category}\n\n## 当前状态\n\n已从当前代码和测试确认的功能事实与边界。\n\n## 事实来源\n\nsrc/export/ 与当前验收证据。\n",
                encoding="utf-8",
            )
        feature["status"] = "implemented"
        feature["known_gaps"] = []
        ready_assessment = self.write_json(
            "knowledge-ready.json",
            {
                "schema_version": "docs-harness/knowledge-assessment/v1",
                "status": "ready",
                "reviewed_revision": "workspace:ready",
                "features": [feature],
                "gaps": [],
            },
        )
        _, updated = self.run_harness(
            "knowledge", "verify", "--target", str(self.project), "--job-id", job_id, "--assessment", str(ready_assessment)
        )
        self.assertEqual(updated["result"], "updated")
        self.assertEqual(updated["knowledge_status"]["status"], "ready")

    def test_new_project_bootstrap_update_does_not_require_second_consent(self) -> None:
        self.init_project(bootstrap_knowledge=False)
        feature = {
            "feature_id": "project-core",
            "name": "项目核心",
            "aliases": ["核心"],
            "feature_type": "internal_capability",
            "status": "partial",
            "scope_patterns": ["src/**"],
            "documents": {
                category: f"docs/features/project-core/{category}.md"
                for category in ("product", "development", "testing", "design")
            },
            "shared_refs": ["docs/shared/architecture.md"],
            "dependencies": [],
            "known_gaps": ["首次遍历待补全"],
        }
        assessment = self.write_json(
            "bootstrap-assessment.json",
            {
                "schema_version": "docs-harness/knowledge-assessment/v1",
                "status": "partial",
                "reviewed_revision": "workspace:bootstrap",
                "features": [feature],
                "gaps": ["首次遍历待补全"],
            },
        )
        _, prepared = self.run_harness(
            "knowledge", "update", "--target", str(self.project), "--assessment", str(assessment)
        )
        self.assertEqual(prepared["status"], "contract_ready")
        self.assertEqual(prepared["dispatch_contract"]["authorization_basis"], "project_init_bootstrap")
        self.assertIsNone(prepared["dispatch_contract"]["consent_ref"])

    def test_background_knowledge_job_detects_pre_dispatch_drift_and_out_of_scope_write(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        source = self.project / "src" / "core.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("VALUE = 2\n", encoding="utf-8")
        evidence = self.evidence("drift", evidence_type="test_result", covers=task_id, changed_paths=["src/core.py"])
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        job_id = verified["post_completion"]["job_id"]
        product = self.project / "docs" / "features" / "project-core" / "product.md"
        product.write_text(product.read_text(encoding="utf-8") + "\n外部并发更新。\n", encoding="utf-8")
        _, drifted = self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running", expected=3
        )
        self.assertEqual(drifted["status"], "needs_rebase")
        self.assertEqual(drifted["reason_code"], "knowledge_changed_before_dispatch")
        self.run_harness("knowledge", "retry", "--target", str(self.project), "--job-id", job_id)
        self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running"
        )
        design = self.project / "docs" / "features" / "project-core" / "design.md"
        design.write_text(design.read_text(encoding="utf-8") + "\n越界更新。\n", encoding="utf-8")
        _, outside = self.run_harness(
            "knowledge", "verify", "--target", str(self.project), "--job-id", job_id, "--result", "no_change", expected=3
        )
        self.assertEqual(outside["status"], "needs_rebase")
        self.assertEqual(outside["reason_code"], "knowledge_write_outside_allowed_scope")
        compiled = json.loads(
            (self.project / ".docs-harness" / "runs" / task_id / "compiled-task.json").read_text(encoding="utf-8")
        )
        self.assertEqual(compiled["control_status"], "complete")

    def test_post_completion_job_creation_failure_does_not_rollback_parent_completion(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        source = self.project / "src" / "core.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("VALUE = 3\n", encoding="utf-8")
        jobs_root = self.project / ".docs-harness" / "knowledge-jobs"
        jobs_root.write_text("模拟 Runtime 路径故障\n", encoding="utf-8")
        evidence = self.evidence("dispatch-failed", evidence_type="test_result", covers=task_id, changed_paths=["src/core.py"])
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(verified["result"], "完成")
        self.assertEqual(verified["control_status"], "complete")
        self.assertEqual(verified["post_completion"]["status"], "dispatch_failed")
        compiled = json.loads(
            (self.project / ".docs-harness" / "runs" / task_id / "compiled-task.json").read_text(encoding="utf-8")
        )
        self.assertEqual(compiled["control_status"], "complete")
        self.assertEqual(compiled["post_completion"]["status"], "dispatch_failed")

    def test_background_knowledge_jobs_serialize_per_feature_and_retry_without_touching_parent(self) -> None:
        self.init_project()
        job_ids: list[str] = []
        for suffix in ("a", "b"):
            relative = f"src/{suffix}.py"
            _, routed = self.run_harness(
                "run", "--target", str(self.project), "--task", f"实现项目核心 `{relative}` 代码", "--scope", relative
            )
            task_id = routed["task_id"]
            self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("VALUE = 1\n", encoding="utf-8")
            evidence = self.evidence(f"code-{suffix}", evidence_type="test_result", covers=task_id, changed_paths=[relative])
            _, verified = self.run_harness(
                "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
            )
            job_ids.append(verified["post_completion"]["job_id"])

        self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_ids[0], "--job-status", "running"
        )
        _, locked = self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_ids[1], "--job-status", "running", expected=3
        )
        self.assertEqual(locked["code"], "knowledge_feature_locked")
        self.run_harness(
            "knowledge", "verify", "--target", str(self.project), "--job-id", job_ids[0], "--result", "no_change"
        )
        _, running = self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_ids[1], "--job-status", "running"
        )
        self.assertEqual(running["status"], "running")
        self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_ids[1], "--job-status", "failed"
        )
        _, retried = self.run_harness(
            "knowledge", "retry", "--target", str(self.project), "--job-id", job_ids[1]
        )
        self.assertEqual(retried["status"], "contract_ready")
        self.assertEqual(retried["attempt"], 2)

    def test_workload_estimate_preserves_raw_route_when_candidate_forces_goal(self) -> None:
        self.project.joinpath("src").mkdir()
        self.project.joinpath("src", "main.py").write_text("VALUE = 1\n", encoding="utf-8")
        candidate = self.write_json(
            "background-candidate.json",
            {"schema_version": "docs-harness/background-candidate/v1", "requires_plan": True},
        )
        _, estimate = self.run_harness(
            "background", "estimate", "--target", str(self.project), "--candidate", str(candidate)
        )
        self.assertEqual(estimate["schema_version"], "docs-harness/workload-estimate/v1")
        self.assertEqual(estimate["score_route"], "background_direct")
        self.assertEqual(estimate["execution_route"], "background_goal")
        self.assertEqual(estimate["route_override_reason"], "candidate_requires_plan")
        self.assertFalse(estimate["blocking_main_task"])
        self.assertTrue(Path(estimate["estimate_ref"]).is_file())

    def test_workload_score_boundaries_and_scan_limit_hard_upgrade(self) -> None:
        self.assertEqual(
            [HARNESS_MODULE.score_bucket(value, ((150, 0), (800, 8), (3000, 16)), 24) for value in (150, 151, 800, 801, 3000, 3001)],
            [0, 8, 8, 16, 16, 24],
        )
        inventory = [{"path": f"file-{index}.py", "size": 10, "extension": ".py"} for index in range(10)]
        with mock.patch.object(HARNESS_MODULE, "bounded_project_inventory", return_value=(inventory, True)):
            with mock.patch.object(HARNESS_MODULE, "knowledge_status", return_value={"status": "ready", "features": 0, "gaps": []}):
                with mock.patch.object(HARNESS_MODULE, "read_knowledge_map", return_value=None):
                    estimate = HARNESS_MODULE.workload_estimate(self.project)
        self.assertEqual(estimate["score_route"], "background_direct")
        self.assertEqual(estimate["execution_route"], "background_goal_phased")
        self.assertEqual(estimate["route_override_reason"], "scan_file_limit_exceeded")
        self.assertTrue(estimate["scan_truncated"])

    def test_document_delivery_classification_keeps_user_document_blocking(self) -> None:
        self.init_project()
        facts = self.write_json(
            "deliverables.json",
            {
                "allowed_scope": ["docs/api-migration.md", "src/api.py"],
                "background_deliverables": ["版本复盘"],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现 API 并交付迁移文档", "--facts", str(facts)
        )
        blocking = {item["deliverable"] for item in routed["blocking_deliverables"]}
        background = {item["deliverable"] for item in routed["background_deliverables"]}
        self.assertIn("docs/api-migration.md", blocking)
        self.assertIn("required_contract_and_recovery_evidence", blocking)
        self.assertIn("版本复盘", background)
        self.assertNotIn("docs/api-migration.md", background)

    def test_unified_background_alias_and_host_capability_degradation_are_explicit(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/alias.py")
        job = verified["post_completion"]["dispatch_contract"]
        self.assertEqual(job["schema_version"], "docs-harness/background-job/v2")
        self.assertFalse(job["may_spawn_child_jobs"])
        self.assertFalse(job["may_mutate_parent"])
        self.assertIn(job["execution_route"], {"background_direct", "background_goal", "background_goal_phased"})
        _, legacy = self.run_harness(
            "knowledge", "job-status", "--target", str(self.project), "--job-id", job["job_id"]
        )
        self.assertTrue(legacy["deprecated_alias"])
        self.assertEqual(legacy["replacement_command"], "background status")
        _, queued = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job["job_id"], "--job-status", "queued_manual"
        )
        self.assertEqual(queued["status"], "queued_manual")
        _, status = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", job["job_id"]
        )
        self.assertEqual(status["execution_route"], job["execution_route"])
        self.assertFalse(status["host_dispatch_contract"]["silent_route_downgrade_allowed"])

    def test_background_retry_stops_at_max_attempts(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/retry.py")
        governance = next(job for job in verified["background_jobs"] if job["task_kind"] == "delivery_governance")
        job_id = governance["job_id"]
        for expected_attempt in (2, 3):
            self.run_harness(
                "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "queued_manual"
            )
            _, retried = self.run_harness(
                "background", "retry", "--target", str(self.project), "--job-id", job_id
            )
            self.assertEqual(retried["attempt"], expected_attempt)
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "queued_manual"
        )
        _, exhausted = self.run_harness(
            "background", "retry", "--target", str(self.project), "--job-id", job_id, expected=3
        )
        self.assertEqual(exhausted["status"], "failed")
        self.assertEqual(exhausted["reason_code"], "max_attempts_reached")

    def test_bootstrap_serializes_incremental_job_and_rebuilds_its_baseline(self) -> None:
        installed = self.init_project(bootstrap_knowledge=False)
        bootstrap_id = installed["knowledge_flow"]["job_id"]
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", bootstrap_id, "--job-status", "dispatched"
        )
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", bootstrap_id, "--job-status", "running"
        )
        routed, verified = self.complete_code_task("src/during-bootstrap.py")
        incremental_id = verified["post_completion"]["job_id"]
        _, waiting = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", incremental_id
        )
        self.assertEqual(waiting["status"], "waiting_for_bootstrap_merge")
        self.assertEqual(waiting["dependency_job_ids"], [bootstrap_id])

        self.bootstrap_knowledge()
        knowledge_map = json.loads((self.project / "docs" / "knowledge-map.json").read_text(encoding="utf-8"))
        assessment = self.write_json(
            "bootstrap-ready-assessment.json",
            {
                "schema_version": "docs-harness/knowledge-assessment/v1",
                "status": "ready",
                "reviewed_revision": "test-bootstrap-ready",
                "features": knowledge_map["features"],
                "gaps": [],
            },
        )
        _, completed = self.run_harness(
            "background", "verify", "--target", str(self.project), "--job-id", bootstrap_id, "--assessment", str(assessment)
        )
        self.assertIn(incremental_id, completed["released_waiting_jobs"])
        _, released = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", incremental_id
        )
        self.assertEqual(released["status"], "contract_ready")
        self.assertTrue(released["baseline_rebuilt_after_bootstrap"])
        compiled = json.loads(
            (self.project / ".docs-harness" / "runs" / routed["task_id"] / "compiled-task.json").read_text(encoding="utf-8")
        )
        self.assertEqual(compiled["control_status"], "complete")

    def test_critical_finding_creates_one_followup_without_rewriting_parent(self) -> None:
        self.init_project()
        routed, verified = self.complete_code_task("src/finding.py")
        job_id = verified["post_completion"]["job_id"]
        self.force_complex_background_job(job_id, ["核实重大发现"])
        self.write_background_goal_artifacts(job_id)
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched"
        )
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running"
        )
        self.run_harness(
            "background", "progress", "--target", str(self.project), "--job-id", job_id,
            "--work-package-id", "wp-01", "--work-package-status", "blocked",
            "--reason-code", "critical_contract_conflict",
        )
        finding = self.write_json(
            "critical-finding.json",
            {
                "schema_version": "docs-harness/background-assessment/v1",
                "critical_finding": {"code": "implementation_document_conflict", "summary": "实现与知识边界冲突"},
            },
        )
        _, result = self.run_harness(
            "background", "verify", "--target", str(self.project), "--job-id", job_id,
            "--result", "completed_with_finding", "--assessment", str(finding)
        )
        self.assertEqual(result["blocked_work_package_ids"], ["wp-01"])
        followup_id = result["critical_followup_job_id"]
        _, followup = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", followup_id
        )
        self.assertEqual(followup["task_kind"], "critical_followup")
        self.assertEqual(followup["parent_task_id"], routed["task_id"])
        self.assertEqual(followup["parent_job_id"], job_id)
        self.assertFalse(followup["may_mutate_parent"])
        compiled = json.loads(
            (self.project / ".docs-harness" / "runs" / routed["task_id"] / "compiled-task.json").read_text(encoding="utf-8")
        )
        self.assertEqual(compiled["control_status"], "complete")

    def test_background_goal_requires_bound_plan_and_progress_before_running(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/goal-artifacts.py")
        job_id = verified["post_completion"]["job_id"]
        self.force_complex_background_job(job_id, ["验证复杂后台工作包"])
        _, blocked = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id,
            "--job-status", "dispatched", expected=3
        )
        self.assertEqual(blocked["code"], "missing_background_goal_artifacts")
        self.write_background_goal_artifacts(job_id)
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched"
        )
        _, running = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running"
        )
        self.assertEqual(running["status"], "running")
        _, status = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", job_id
        )
        self.assertEqual(
            Path(status["goal_artifacts"]["plan_ref"]),
            (self.project / ".docs-harness" / "background" / "jobs" / job_id / "plan.json").resolve(),
        )

    def test_v161_prepare_progress_tamper_repair_and_verify_closed_loop(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/v161-loop.py")
        job_id = verified["post_completion"]["job_id"]
        job = self.force_complex_background_job(job_id)
        contract = job["host_dispatch_contract"]
        self.assertEqual(contract["required_preparation"], "background_goal_artifacts")
        self.assertEqual(contract["control_plane_write_policy"], "harness_cli_only")
        self.assertEqual(contract["dispatch_sequence"], ["prepare", "create_host_goal", "dispatched", "running"])
        self.assertIsInstance(contract["manual_resume_argv"], list)
        self.assertTrue(all(isinstance(item, list) for item in contract["manual_resume_argv"]))

        for _ in range(2):
            _, rejected = self.run_harness(
                "background", "dispatch", "--target", str(self.project), "--job-id", job_id,
                "--job-status", "dispatched", expected=3,
            )
            self.assertEqual(rejected["reason_code"], "missing_background_goal_artifacts")
            self.assertEqual(rejected["next_action"], "prepare_background_goal")
        root = self.project / ".docs-harness" / "background" / "jobs" / job_id
        rejected_events = [
            item for item in HARNESS_MODULE.read_jsonl(root / "events.jsonl")
            if item.get("event") == "transition_rejected" and item.get("reason_code") == "missing_background_goal_artifacts"
        ]
        self.assertEqual(len(rejected_events), 1)
        self.assertEqual(
            set(rejected_events[0]),
            {"event", "job_id", "attempt", "from_status", "requested_status", "reason_code", "at"},
        )
        self.assertNotIn(str(self.temp_root), json.dumps(rejected_events[0], ensure_ascii=False))

        _, prepared = self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", job_id
        )
        self.assertEqual(prepared["status"], "prepared")
        plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
        progress = json.loads((root / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["artifact_revision"], 2)
        self.assertEqual(progress["attempt"], 1)
        self.assertEqual([item["id"] for item in plan["work_packages"]], ["wp-01", "wp-02"])
        before = self.snapshot_tree(root)
        _, repeated = self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", job_id
        )
        self.assertEqual(repeated["status"], "already_prepared")
        self.assertEqual(self.snapshot_tree(root), before)

        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id,
            "--job-status", "dispatched",
        )
        _, early = self.run_harness(
            "background", "progress", "--target", str(self.project), "--job-id", job_id,
            "--work-package-id", "wp-01", "--work-package-status", "in_progress", expected=3,
        )
        self.assertEqual(early["code"], "invalid_background_job_transition")
        plan["objective"] = "外部篡改"
        (root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _, tampered = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id,
            "--job-status", "running", expected=3,
        )
        self.assertEqual(tampered["reason_code"], "background_goal_artifacts_tampered")
        _, repaired = self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", job_id, "--repair"
        )
        self.assertEqual(repaired["status"], "repaired")
        self.assertTrue((root / "attempts" / "attempt-001" / "archive-001" / "plan.json").is_file())
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id,
            "--job-status", "running",
        )
        _, unsafe_reason = self.run_harness(
            "background", "progress", "--target", str(self.project), "--job-id", job_id,
            "--work-package-id", "wp-01", "--work-package-status", "in_progress",
            "--reason-code", "自由 文本", expected=2,
        )
        self.assertEqual(unsafe_reason["code"], "invalid_background_reason_code")
        _, skipped = self.run_harness(
            "background", "progress", "--target", str(self.project), "--job-id", job_id,
            "--work-package-id", "wp-01", "--work-package-status", "completed", expected=3,
        )
        self.assertEqual(skipped["code"], "invalid_background_progress_transition")
        _, incomplete = self.run_harness(
            "background", "verify", "--target", str(self.project), "--job-id", job_id,
            "--result", "no_change", expected=3,
        )
        self.assertEqual(incomplete["reason_code"], "incomplete_background_work_packages")
        self.complete_background_work_packages(job_id)
        _, completed = self.run_harness(
            "background", "verify", "--target", str(self.project), "--job-id", job_id,
            "--result", "no_change",
        )
        self.assertEqual(completed["result"], "no_change")
        self.assertEqual(completed["blocked_work_package_ids"], [])

    def test_v161_prepare_rejects_partial_artifacts_and_direct_is_not_required(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/v161-partial.py")
        direct_id = verified["post_completion"]["job_id"]
        _, direct = self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", direct_id
        )
        self.assertEqual(direct["status"], "not_required")
        direct_root = self.project / ".docs-harness" / "background" / "jobs" / direct_id
        self.assertFalse((direct_root / "plan.json").exists())

        job = self.force_complex_background_job(direct_id, ["部分工件检查"])
        plan, _ = HARNESS_MODULE.background_goal_artifact_values(job)
        (direct_root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before = (direct_root / "plan.json").read_bytes()
        _, partial = self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", direct_id, expected=3
        )
        self.assertEqual(partial["code"], "partial_background_goal_artifacts")
        self.assertEqual((direct_root / "plan.json").read_bytes(), before)
        self.assertFalse((direct_root / "progress.json").exists())
        _, repaired = self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", direct_id, "--repair"
        )
        self.assertEqual(repaired["status"], "repaired")

    def test_v161_retry_archives_attempt_and_summary_index_keeps_each_attempt(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/v161-retry.py")
        job_id = verified["post_completion"]["job_id"]
        self.force_complex_background_job(job_id, ["单一工作包"])
        self.write_background_goal_artifacts(job_id)
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched")
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running")
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "failed")
        _, retried = self.run_harness("background", "retry", "--target", str(self.project), "--job-id", job_id)
        self.assertEqual(retried["attempt"], 2)
        self.assertTrue(retried["requires_prepare"])
        root = self.project / ".docs-harness" / "background" / "jobs" / job_id
        self.assertFalse((root / "plan.json").exists())
        self.assertTrue((root / "attempts" / "attempt-001" / "archive-001" / "progress.json").is_file())
        self.write_background_goal_artifacts(job_id)
        progress = json.loads((root / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(progress["attempt"], 2)
        self.assertEqual(progress["work_package_states"], [{"id": "wp-01", "status": "pending"}])
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched")
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running")
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "failed")
        summaries = [item for item in HARNESS_MODULE.read_jsonl(HARNESS_MODULE.background_index_path(self.project)) if item["job_id"] == job_id]
        self.assertEqual([(item["attempt"], item["status"]) for item in summaries], [(1, "failed"), (2, "failed")])

    def test_v161_complex_knowledge_alias_cannot_bypass_prepare_or_running_gate(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/v161-alias.py")
        job_id = verified["post_completion"]["job_id"]
        self.force_complex_background_job(job_id)
        _, jump = self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_id,
            "--job-status", "running", expected=3,
        )
        self.assertEqual(jump["reason_code"], "invalid_background_job_transition")
        self.assertTrue(jump["deprecated_alias"])
        self.write_background_goal_artifacts(job_id)
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched")
        root = self.project / ".docs-harness" / "background" / "jobs" / job_id
        (root / "progress.json").unlink()
        _, missing = self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_id,
            "--job-status", "running", expected=3,
        )
        self.assertEqual(missing["reason_code"], "missing_background_goal_artifacts")

    def test_v161_change_scoped_estimate_ignores_project_size_but_preserves_source_identity(self) -> None:
        inventory = [
            {"path": f"packages/p{i % 8}/file{i}.py", "extension": ".py", "size": 10}
            for i in range(5000)
        ]
        with mock.patch.object(HARNESS_MODULE, "bounded_project_inventory", return_value=(inventory, True)):
            project_wide = HARNESS_MODULE.workload_estimate(self.project)
            change_scoped = HARNESS_MODULE.workload_estimate(
                self.project,
                candidate={
                    "estimate_basis": "change_scoped",
                    "changed_paths": ["packages/p1/one.py"],
                    "selected_features": ["p1"],
                    "deliverables": ["feature_knowledge_incremental_sync"],
                    "allowed_write_scope": ["docs/**"],
                },
            )
        self.assertEqual(project_wide["execution_route"], "background_goal_phased")
        self.assertNotEqual(change_scoped["execution_route"], "background_goal_phased")
        self.assertEqual(change_scoped["estimate_basis"], "change_scoped")
        self.assertTrue(change_scoped["project_scale_context"]["scan_truncated"])
        # v1.6.4：change-scoped 去重指纹只绑定变化路径、功能、交付物与写入范围，
        # 不再与 project-wide 全量 inventory 指纹相同。
        self.assertNotEqual(project_wide["source_fingerprint"], change_scoped["source_fingerprint"])
        self.assertTrue(change_scoped["change_scope_fingerprint"])

    def test_v161_control_plane_scope_guard_and_git_runtime_prepare(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        self.init_project(expected=3)
        estimate = HARNESS_MODULE.workload_estimate(self.project, candidate={"requires_plan": True})
        with self.assertRaises(HARNESS_MODULE.HarnessError) as blocked:
            HARNESS_MODULE.create_background_job(
                self.project, task_kind="delivery_governance", estimate=estimate,
                parent_task_id=None, allowed_write_scope=(".docs-harness/**",),
            )
        self.assertEqual(blocked.exception.code, "invalid_background_scope")
        with self.assertRaises(HARNESS_MODULE.HarnessError) as git_blocked:
            HARNESS_MODULE.create_background_job(
                self.project, task_kind="delivery_governance", estimate=estimate,
                parent_task_id=None, allowed_write_scope=(".git/**",),
            )
        self.assertEqual(git_blocked.exception.code, "invalid_background_scope")
        job, _ = HARNESS_MODULE.create_background_job(
            self.project, task_kind="delivery_governance", estimate=estimate,
            parent_task_id=None, allowed_write_scope=("docs/reviews/**",),
            route_base_key=HARNESS_MODULE.sha256_text("control-plane-route"),
            document_route_contract=HARNESS_MODULE.resolve_document_routes(
                self.project, required_kinds=("reviews_root",)
            ),
        )
        self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", job["job_id"]
        )
        plan_path = self.project / ".git" / "docs-harness" / "background" / "jobs" / job["job_id"] / "plan.json"
        self.assertTrue(plan_path.is_file())
        self.assertFalse((self.project / ".docs-harness" / "background" / "jobs" / job["job_id"]).exists())
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job["job_id"],
            "--job-status", "dispatched",
        )
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job["job_id"],
            "--job-status", "running",
        )
        progress = json.loads(plan_path.with_name("progress.json").read_text(encoding="utf-8"))
        for item in progress["work_package_states"]:
            self.run_harness(
                "background", "progress", "--target", str(self.project), "--job-id", job["job_id"],
                "--work-package-id", item["id"], "--work-package-status", "in_progress",
            )
            self.run_harness(
                "background", "progress", "--target", str(self.project), "--job-id", job["job_id"],
                "--work-package-id", item["id"], "--work-package-status", "completed",
            )
        _, verified = self.run_harness(
            "background", "verify", "--target", str(self.project), "--job-id", job["job_id"],
            "--result", "no_change",
        )
        self.assertEqual(verified["result"], "no_change")

    def test_v161_running_legacy_artifacts_receive_one_attempt_verify_compatibility(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/v161-legacy.py")
        job_id = verified["post_completion"]["job_id"]
        self.force_complex_background_job(job_id, ["旧格式工作包"])
        self.write_background_goal_artifacts(job_id)
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched")
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running")
        root = self.project / ".docs-harness" / "background" / "jobs" / job_id
        plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
        progress = json.loads((root / "progress.json").read_text(encoding="utf-8"))
        for value in (plan, progress):
            value.pop("artifact_revision", None)
            value.pop("generated_by", None)
        progress.pop("attempt", None)
        progress.pop("work_package_states", None)
        (root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / "progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        job_path = root / "job.json"
        job = json.loads(job_path.read_text(encoding="utf-8"))
        job["goal_artifacts"] = {
            "artifact_revision": 1,
            "attempt": 1,
            "plan_ref": str((root / "plan.json").resolve()),
            "plan_fingerprint": HARNESS_MODULE.file_fingerprint(root / "plan.json"),
            "progress_ref": str((root / "progress.json").resolve()),
            "progress_fingerprint": HARNESS_MODULE.file_fingerprint(root / "progress.json"),
        }
        job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _, accepted = self.run_harness(
            "background", "verify", "--target", str(self.project), "--job-id", job_id, "--result", "no_change"
        )
        self.assertEqual(accepted["result"], "no_change")
        events = HARNESS_MODULE.read_jsonl(root / "events.jsonl")
        self.assertEqual(sum(item.get("event") == "legacy_goal_artifacts_accepted" for item in events), 1)

    def test_delivery_receipt_proves_parent_persisted_before_background_contracts(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/timeline.py")
        parent_time = verified["parent_completed_at"]
        created = verified["background"]["job_created_at"]
        self.assertTrue(created)
        self.assertTrue(all(parent_time <= value for value in created.values()))
        self.assertEqual(verified["known_limit_codes"], [])
        self.assertEqual(verified["delivery_layers"]["remote_delivery"]["expectation"], "not_requested")
        self.assertEqual(verified["background"]["status"], "dispatch_required")

    def test_background_prune_is_dry_run_first_and_requires_terminal_summary(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/prune.py")
        job_id = verified["post_completion"]["job_id"]
        self.run_harness(
            "knowledge", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running"
        )
        self.run_harness(
            "knowledge", "verify", "--target", str(self.project), "--job-id", job_id, "--result", "no_change"
        )
        _, preview = self.run_harness(
            "background", "prune", "--target", str(self.project), "--older-than", "0"
        )
        self.assertEqual(preview["mode"], "dry_run")
        self.assertIn(job_id, [item["job_id"] for item in preview["candidates"]])
        self.assertTrue((self.project / ".docs-harness" / "background" / "jobs" / job_id).is_dir())
        _, applied = self.run_harness(
            "background", "prune", "--target", str(self.project), "--older-than", "0", "--apply"
        )
        self.assertIn(job_id, applied["removed"])
        self.assertFalse((self.project / ".docs-harness" / "background" / "jobs" / job_id).exists())

    def test_consent_receipt_fingerprint_drift_is_rejected(self) -> None:
        self.init_project(bootstrap_knowledge=False)
        feature = {
            "feature_id": "consent-feature",
            "name": "同意边界",
            "aliases": [],
            "feature_type": "user_capability",
            "status": "partial",
            "scope_patterns": ["src/**"],
            "documents": {category: f"docs/features/consent-feature/{category}.md" for category in ("product", "development", "testing", "design")},
            "shared_refs": [],
            "dependencies": [],
            "known_gaps": ["待补全"],
        }
        assessment = self.write_json(
            "consent-assessment.json",
            {"schema_version": "docs-harness/knowledge-assessment/v1", "status": "partial", "reviewed_revision": "test", "features": [feature], "gaps": ["待补全"]},
        )
        _, audited = self.run_harness(
            "knowledge", "audit", "--target", str(self.project), "--assessment", str(assessment), expected=3
        )
        consent = self.write_json(
            "stale-consent.json",
            {
                "schema_version": "docs-harness/knowledge-consent/v1",
                "approved": True,
                "authorized_scope": audited["authorized_scope"],
                "assessment_fingerprint": "sha256:" + "0" * 64,
                "inventory_fingerprint": audited["inventory_fingerprint"],
            },
        )
        _, rejected = self.run_harness(
            "knowledge", "update", "--target", str(self.project), "--assessment", str(assessment), "--consent", str(consent), expected=3
        )
        self.assertEqual(rejected["code"], "knowledge_consent_stale")

    def test_planned_route_requires_context_and_accepts_complete_plan(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("product.md", "design.md", "architecture.md")
        facts = self.write_json(
            "facts-ui.json",
            {"allowed_scope": ["src/view.tsx"], "success_criteria": ["页面完整状态可验收"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现 UI 页面", "--facts", str(facts)
        )
        self.assertEqual(routed["admission_status"], "needs_plan")
        task_id = routed["task_id"]
        plan = self.plan_for({"设计状态": "覆盖空、加载、成功和失败状态。", "真实页面验收": "从真实入口验收。"})
        _, blocked = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        self.assertEqual(blocked["admission_status"], "blocked")
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        runs_root = self.project / ".docs-harness" / "runs"
        task_ids_before_readmission = {path.name for path in runs_root.iterdir() if path.is_dir()}
        _, admitted = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan)
        )
        self.assertEqual(admitted["task_id"], task_id)
        self.assertEqual(
            {path.name for path in runs_root.iterdir() if path.is_dir()},
            task_ids_before_readmission,
        )
        self.assertEqual(admitted["admission_status"], "ready_planned")
        self.assertEqual(admitted["next_action"], "load_action_context")
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        path = self.project / "src" / "view.tsx"
        path.parent.mkdir()
        path.write_text("export const View = () => null;\n", encoding="utf-8")
        evidence = self.evidence("ui", evidence_type="ui_acceptance", covers=task_id, changed_paths=["src/view.tsx"])
        test_evidence = self.evidence("ui-test", evidence_type="test_result", covers=task_id, changed_paths=["src/view.tsx"])
        _, verified = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--evidence",
            str(evidence),
            "--evidence",
            str(test_evidence),
        )
        self.assertEqual(verified["control_status"], "complete")

    def test_release_requires_structured_authorization(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "testing.md")
        facts = self.write_gate_facts(
            "facts-release.json",
            ["release-external"],
            allowed_scope=["dist/app.zip"],
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "发布 release", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for({"外部目标": "测试发布目标。", "发布与回滚": "失败时撤回。"})
        _, pending = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        self.assertEqual(pending["admission_status"], "needs_authorization")
        auth = self.write_json(
            "authorization.json",
            {
                "approved": True,
                "authorized_actions": ["external_write"],
                "authorized_scope": ["dist/app.zip"],
                "external_target": "test-release",
            },
        )
        _, admitted = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--authorization",
            str(auth),
        )
        self.assertEqual(admitted["admission_status"], "ready_planned")
        self.assertEqual(admitted["authorization_status"], "reported")
        auth.unlink()
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        self.assertNotEqual(blocked.get("reason_code"), "authorization_contract_drift")
        self.assertNotIn("授权", str(blocked.get("reason", "")))

    def test_missing_project_fact_can_recompile_after_fact_is_filled(self) -> None:
        self.init_project()
        required = self.project / "docs" / "explicit-required.md"
        facts = self.write_json(
            "missing-facts.json",
            {"allowed_scope": ["src/a.py"], "required_fact_refs": ["docs/explicit-required.md"]},
        )
        _, blocked = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "实现 `src/a.py` 代码",
            "--facts",
            str(facts),
            expected=3,
        )
        self.assertEqual(blocked["admission_status"], "blocked")
        task_id = blocked["task_id"]
        required.write_text("# 显式必要事实\n\n这是本任务明确要求的当前项目事实与可验证边界。\n", encoding="utf-8")
        _, recompiled = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(recompiled["admission_status"], "ready_direct")
        state = self.project / ".docs-harness" / "runs" / task_id
        current = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(current["package_revision"], 2)

    def test_unsafe_verification_command_is_rejected(self) -> None:
        self.init_project()
        facts = self.write_json(
            "unsafe-command.json",
            {
                "allowed_scope": ["README.md"],
                "verification_commands": [["python3", "-c", "print('unsafe')"]],
            },
        )
        _, rejected = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts), expected=2
        )
        self.assertEqual(rejected["code"], "unsafe_verification_command")

    def test_safe_local_verification_command_runs(self) -> None:
        self.init_project()
        (self.project / "test_smoke.py").write_text(
            "import unittest\n\n\n"
            "class SmokeTest(unittest.TestCase):\n"
            "    def test_pass(self):\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        facts = self.write_json(
            "safe-command.json",
            {
                "allowed_scope": ["README.md"],
                "verification_commands": [
                    {"argv": ["python3", "-m", "unittest"], "produces": ["test_result"]}
                ],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("# README\n", encoding="utf-8")
        evidence = self.evidence("safe-command", evidence_type="document_review", covers=task_id, changed_paths=["README.md"])
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(verified["result"], "完成")
        self.assertEqual(verified["verification_commands"][0]["result"], "passed")
        self.assertEqual(verified["verification_commands"][0]["produces"], ["test_result"])
        self.assertEqual(verified["verification_receipts"][0]["schema_version"], "docs-harness/evidence-receipt/v2")
        self.assertEqual(verified["verification_receipts"][0]["producer"]["capability"], "verification_command")

    def write_verification_byproduct_test(self, *, write_real_file: bool, write_configured_volatile: bool) -> None:
        lines = [
            "import pathlib",
            "import unittest",
            "",
            "",
            "class VerificationByproductTest(unittest.TestCase):",
            "    def test_byproducts(self):",
            "        root = pathlib.Path.cwd()",
            "        cache = root / '__pycache__'",
            "        cache.mkdir(exist_ok=True)",
            "        (cache / 'cached.txt').write_text('x', encoding='utf-8')",
            "        pytest_cache = root / '.pytest_cache' / 'v' / 'cache'",
            "        pytest_cache.mkdir(parents=True, exist_ok=True)",
            "        (pytest_cache / 'lastfailed').write_text('{}', encoding='utf-8')",
            "        (root / '.coverage').write_text('coverage', encoding='utf-8')",
            "        (root / 'report.log').write_text('log', encoding='utf-8')",
        ]
        if write_real_file:
            lines.append("        (root / 'EXTRA_OUTPUT.md').write_text('# 额外写入', encoding='utf-8')")
        if write_configured_volatile:
            lines.append("        scratch = root / 'scratch'")
            lines.append("        scratch.mkdir(exist_ok=True)")
            lines.append("        (scratch / 'report.txt').write_text('scratch', encoding='utf-8')")
        (self.project / "test_verification_byproducts.py").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run_verification_byproduct_flow(self) -> tuple[int, dict[str, Any]]:
        facts = self.write_json(
            "byproduct-command.json",
            {
                "allowed_scope": ["README.md"],
                "verification_commands": [
                    {"argv": ["python3", "-m", "unittest"], "produces": ["test_result"]}
                ],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("# README\n", encoding="utf-8")
        evidence = self.evidence("byproduct-command", evidence_type="document_review", covers=task_id, changed_paths=["README.md"])
        result, payload = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=None
        )
        return result.returncode, payload

    def test_volatile_verification_byproducts_do_not_block_completion(self) -> None:
        self.init_project()
        self.write_verification_byproduct_test(write_real_file=False, write_configured_volatile=False)
        code, verified = self.run_verification_byproduct_flow()
        self.assertEqual(code, 0, json.dumps(verified, ensure_ascii=False))
        self.assertEqual(verified["result"], "完成")
        command_result = verified["verification_commands"][0]
        self.assertEqual(command_result["result"], "passed")
        self.assertEqual(command_result["produces"], ["test_result"])
        self.assertNotIn("unexpected_write_set", command_result)
        self.assertIn("__pycache__/cached.txt", command_result["volatile_write_set"])
        self.assertIn(".pytest_cache/v/cache/lastfailed", command_result["volatile_write_set"])
        self.assertIn(".coverage", command_result["volatile_write_set"])
        self.assertIn("report.log", command_result["volatile_write_set"])
        self.assertEqual(verified["verification_receipts"][0]["producer"]["capability"], "verification_command")

    def test_verification_command_real_workspace_write_still_rejected(self) -> None:
        self.init_project()
        self.write_verification_byproduct_test(write_real_file=True, write_configured_volatile=False)
        code, blocked = self.run_verification_byproduct_flow()
        self.assertEqual(code, 3)
        self.assertEqual(blocked["result"], "补充证据")
        command_result = blocked["verification_commands"][0]
        self.assertEqual(command_result["result"], "failed")
        self.assertEqual(command_result["reason_code"], "verification_command_workspace_write")
        self.assertEqual(command_result["unexpected_write_set"], ["EXTRA_OUTPUT.md"])
        self.assertEqual(command_result["produces"], [])
        self.assertIn(".coverage", command_result["volatile_write_set"])

    def test_existing_volatile_named_file_modification_is_still_rejected(self) -> None:
        self.init_project()
        self.write_verification_byproduct_test(write_real_file=False, write_configured_volatile=False)
        (self.project / "report.log").write_text("preexisting\n", encoding="utf-8")
        code, blocked = self.run_verification_byproduct_flow()
        self.assertEqual(code, 3)
        command_result = blocked["verification_commands"][0]
        self.assertEqual(command_result["reason_code"], "verification_command_workspace_write")
        self.assertEqual(command_result["unexpected_write_set"], ["report.log"])
        self.assertNotIn("report.log", command_result["volatile_write_set"])

    def test_configured_volatile_paths_extend_verification_tolerance(self) -> None:
        self.init_project()
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["verification"] = {"volatile_paths": ["scratch/*"]}
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.write_verification_byproduct_test(write_real_file=False, write_configured_volatile=True)
        code, verified = self.run_verification_byproduct_flow()
        self.assertEqual(code, 0, json.dumps(verified, ensure_ascii=False))
        self.assertEqual(verified["result"], "完成")
        command_result = verified["verification_commands"][0]
        self.assertEqual(command_result["result"], "passed")
        self.assertIn("scratch/report.txt", command_result["volatile_write_set"])

    def test_volatile_verification_path_builtin_and_configured_patterns(self) -> None:
        module = HARNESS_MODULE
        for relative in (
            "__pycache__/mod.cpython-312.pyc",
            "tests/__pycache__/mod.cpython-312.pyc",
            ".pytest_cache/v/cache/nodeids",
            ".mypy_cache/3.12/mod.json",
            "htmlcov/index.html",
            ".coverage",
            ".coverage.worker-1",
            "reports/run.log",
            "build/output.tmp",
            ".DS_Store",
        ):
            self.assertTrue(module.volatile_verification_path(relative), relative)
        for relative in (
            "README.md",
            "src/app.py",
            "coverage.xml",
            "docs/notes.md",
            "scratch/report.txt",
        ):
            self.assertFalse(module.volatile_verification_path(relative), relative)
        self.assertTrue(module.volatile_verification_path("scratch/report.txt", ["scratch/*"]))
        self.assertFalse(module.volatile_verification_path("src/app.py", ["scratch/*"]))

    def test_configured_volatile_paths_reject_global_or_escaping_patterns(self) -> None:
        for pattern in ("*", "**", "src?/*", "../scratch/*", "/scratch/*", ".git/tmp/*"):
            with self.subTest(pattern=pattern):
                with self.assertRaises(HARNESS_MODULE.HarnessError) as raised:
                    HARNESS_MODULE.validate_volatile_verification_paths([pattern])
                self.assertEqual(raised.exception.code, "invalid_project_config")

    def test_project_upgrade_fails_before_writes_for_invalid_volatile_pattern(self) -> None:
        self.init_project()
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["verification"] = {"volatile_paths": ["*"]}
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        script = self.project / "scripts" / "harness.py"
        before = HARNESS_MODULE.file_fingerprint(script)
        _, rejected = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=2
        )
        self.assertEqual(rejected["code"], "invalid_project_config")
        self.assertEqual(HARNESS_MODULE.file_fingerprint(script), before)

    def test_project_upgrade_preserves_verification_volatile_paths(self) -> None:
        self.init_project()
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["verification"] = {"volatile_paths": ["scratch/*"]}
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.run_harness("project", "upgrade", "--target", str(self.project), "--apply")
        upgraded = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(upgraded["verification"], {"volatile_paths": ["scratch/*"]})
        _, repeated = self.run_harness("project", "upgrade", "--target", str(self.project), "--apply")
        self.assertEqual(repeated["changed"], [])
        self.assertEqual(
            json.loads(config_path.read_text(encoding="utf-8"))["verification"],
            {"volatile_paths": ["scratch/*"]},
        )

    def test_plan_contract_is_shared_with_context_and_has_executable_next_step(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力"
        )
        self.assertEqual(routed["admission_status"], "needs_plan")
        self.assertIn("执行范围", routed["plan_fields"])
        self.assertEqual(routed["plan_contract"]["plan_fields"], routed["plan_fields"])
        self.assertTrue(routed["plan_contract"]["scope_required"])
        self.assertEqual(routed["reason_code"], "scope_required")

        task_id = routed["task_id"]
        suggested = self.project.resolve() / ".docs-harness" / "runs" / task_id / "plan.json"
        self.assertEqual(routed["artifact_ref"], str(suggested))
        self.assertIn(task_id, routed["next_command_argv"])
        self.assertIn("context", routed["next_command_argv"])

        _, context = self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        self.assertEqual(context["plan_contract"], routed["plan_contract"])
        self.assertEqual(context["artifact_ref"], str(suggested))
        self.assertEqual(context["reason_code"], "plan_submission_required")
        self.assertIn(task_id, context["next_command_argv"])
        self.assertIn(str(suggested), context["next_command_argv"])

    def test_scope_from_plan_recompiles_path_gates_before_plan_readmission(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力"
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        plan = self.plan_for({"执行范围": ["src/api/client.py"]})
        _, revised = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--plan",
            str(plan),
            expected=3,
        )
        self.assertEqual(revised["reason_code"], "scope_gate_plan_amendment_required")
        self.assertEqual(revised["next_action"], "complete_plan_delta")
        self.assertFalse(revised["plan_regeneration_required"])
        self.assertFalse(revised["source_execution_allowed"])
        self.assertEqual(revised["missing_plan_fields"], revised["added_plan_fields"])
        self.assertIn("兼容策略", revised["missing_plan_fields"])
        self.assertNotIn("背景", revised["missing_plan_fields"])
        self.assertIn(task_id, revised["next_command_argv"])

        state = self.project / ".docs-harness" / "runs" / task_id
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["package_revision"], 2)
        self.assertEqual(package["allowed_scope"], ["src/api/client.py"])
        self.assertIn("architecture-contract", package["matched_gates"])
        self.assertIn("code-edit", package["matched_gates"])
        self.assertIn("兼容策略", package["plan_fields"])

        _, refreshed = self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        self.assertEqual(refreshed["plan_contract"]["plan_fields"], package["plan_fields"])
        self.assertFalse(refreshed["plan_contract"]["scope_required"])

        contract = revised["plan_delta_contract"]
        self.assertEqual(contract["schema_version"], "docs-harness/plan-delta-contract/v1")
        self.assertEqual(contract["frozen_scope"], ["src/api/client.py"])
        plan.unlink()
        patch = self.write_json(
            "plan-delta.json",
            {field: f"{field}的受控说明" for field in contract["missing_plan_fields"]},
        )
        _, frozen = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(patch)
        )
        self.assertEqual(frozen["admission_status"], "ready_planned")
        compiled = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        self.assertIsNone(compiled["plan_delta_contract"])
        self.assertTrue(Path(compiled["plan_ref"]).is_file())
        self.assertTrue(str(compiled["plan_ref"]).startswith(str(state / "artifacts" / "plans")))
        events = [item["event"] for item in HARNESS_MODULE.read_jsonl(state / "events.jsonl")]
        self.assertEqual(events.count("plan_frozen"), 1)
        self.assertEqual(
            json.loads((state / "task-package.json").read_text(encoding="utf-8"))["package_revision"], 2
        )

    def test_v164_scope_gate_compilation_only_requires_added_plan_fields(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "security.md", "testing.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力"
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        plan = self.plan_for(
            {"执行范围": ["src/auth/authService.ts", "src/auth/authService.test.ts"]}
        )
        _, amended = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--plan",
            str(plan),
            expected=3,
        )
        self.assertEqual(amended["result"], "补充计划")
        self.assertEqual(amended["reason_code"], "scope_gate_plan_amendment_required")
        self.assertEqual(amended["next_action"], "complete_plan_delta")
        self.assertIn("security-sensitive", amended["added_gates"])
        self.assertIn("testing-acceptance", amended["added_gates"])
        self.assertEqual(amended["missing_plan_fields"], ["安全边界", "负向路径"])
        self.assertEqual(amended["added_plan_fields"], ["安全边界", "负向路径"])
        self.assertIn("security_acceptance", amended["added_evidence_types"])
        self.assertFalse(amended["plan_regeneration_required"])
        self.assertFalse(amended["source_execution_allowed"])

        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        contract = amended["plan_delta_contract"]
        self.assertEqual(
            contract["frozen_plan_fields"],
            ["背景", "目标", "非目标", "成功标准", "执行内容", "验收结果"],
        )
        self.assertTrue(Path(contract["base_plan_ref"]).is_file())
        # 受管计划副本让调用者临时文件删除后仍能合并补丁。
        plan.unlink()
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        patch = self.write_json(
            "security-plan-delta.json",
            {
                "task_id": task_id,
                "base_plan_fingerprint": contract["base_plan_fingerprint"],
                "plan_contract_fingerprint": contract["plan_contract_fingerprint"],
                "安全边界": "只改认证模块，不改变权限模型。",
                "负向路径": ["非法凭证被拒绝"],
            },
        )
        _, frozen = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(patch)
        )
        self.assertEqual(frozen["admission_status"], "ready_planned")
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["package_revision"], 2)
        merged = json.loads(
            Path(
                json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))["plan_ref"]
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(merged["背景"], "当前能力需要调整。")
        self.assertEqual(merged["安全边界"], "只改认证模块，不改变权限模型。")
        self.assertEqual(merged["执行范围"], package["allowed_scope"])
        events = [item["event"] for item in HARNESS_MODULE.read_jsonl(state / "events.jsonl")]
        self.assertEqual(events.count("plan_frozen"), 1)
        self.assertEqual(events.count("scope_bound_readmission"), 1)

    def test_v164_complete_plan_draft_freezes_once_after_scope_compilation(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力"
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        plan = self.plan_for({"执行范围": ["src/helper.py"]})
        _, admitted = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan)
        )
        self.assertEqual(admitted["admission_status"], "ready_planned")
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["package_revision"], 2)
        self.assertIn("code-edit", package["matched_gates"])
        self.assertNotIn("执行范围", package["plan_fields"])
        events = HARNESS_MODULE.read_jsonl(state / "events.jsonl")
        frozen_events = [item for item in events if item["event"] == "plan_frozen"]
        self.assertEqual(len(frozen_events), 1)
        self.assertEqual(frozen_events[0]["reason_code"], "scope_bound_plan_adopted")
        self.assertFalse(frozen_events[0]["plan_regeneration_required"])
        self.assertNotIn("plan_amendment_required", [item["event"] for item in events])

    def test_v164_plan_delta_patch_cannot_change_frozen_fields(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "security.md", "testing.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力"
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        plan = self.plan_for({"执行范围": ["src/auth/authService.ts"]})
        _, amended = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        self.assertEqual(amended["next_action"], "complete_plan_delta")
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        conflicting = self.write_json(
            "frozen-field-delta.json",
            {
                "安全边界": "只改认证模块。",
                "负向路径": ["非法凭证被拒绝"],
                "背景": "重写已冻结的背景。",
            },
        )
        result, refused = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--plan",
            str(conflicting),
            expected=None,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(refused["code"], "plan_delta_conflict")
        patch = self.write_json(
            "scope-changing-delta.json",
            {
                "安全边界": "只改认证模块。",
                "负向路径": ["非法凭证被拒绝"],
                "执行范围": ["src/auth/authService.ts", "src/payment/refund.ts"],
            },
        )
        # 严格超集：控制器自动重编译并合并补丁，不再强制完整重新准入
        _, expanded = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(patch)
        )
        self.assertEqual(expanded["admission_status"], "ready_planned")
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["allowed_scope"], ["src/auth/authService.ts", "src/payment/refund.ts"])

    def test_v164_identical_plan_and_action_context_delivers_content_once(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "security.md", "testing.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力"
        )
        task_id = routed["task_id"]
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        plan = self.plan_for({"执行范围": ["src/auth/authService.ts"]})
        _, amended = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        _, plan_context = self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        self.assertGreater(plan_context["loaded_content_count"], 0)
        patch = self.write_json(
            "context-delta.json",
            {field: f"{field}的受控说明" for field in amended["missing_plan_fields"]},
        )
        self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(patch)
        )
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(
            package["context_schedule"]["action"], package["context_schedule"]["plan"]
        )
        _, action_context = self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        self.assertEqual(action_context["loaded_content_count"], 0)
        self.assertEqual(action_context["rules"], [])
        self.assertEqual(action_context["project_facts"], [])
        self.assertEqual(
            action_context["reused_content_count"], plan_context["loaded_content_count"]
        )
        self.assertTrue(action_context["context_delta"])
        self.assertFalse(action_context["context_cache_hit"])
        receipts = HARNESS_MODULE.read_jsonl(state / "context-receipts.jsonl")
        stages = [item["stage"] for item in receipts]
        self.assertEqual(stages.count("action"), 1)
        action_receipt = next(item for item in receipts if item["stage"] == "action")
        self.assertEqual(action_receipt["delivered_content_fingerprints"], [])
        self.assertEqual(
            action_receipt["content_set_fingerprint"],
            next(
                item["content_set_fingerprint"]
                for item in receipts
                if item["stage"] == "plan" and item["package_revision"] == 2
            ),
        )

    def test_path_gate_inference_recognizes_common_test_file_patterns(self) -> None:
        gates = HARNESS_MODULE.infer_gates_from_paths(
            [
                "src/agentStream.test.ts",
                "src/pptContent.spec.ts",
                "src/对应测试文件",
            ]
        )
        self.assertIn("testing-acceptance", gates)
        self.assertIn("code-edit", gates)

    def test_verify_incrementally_admits_additive_gate_and_reuses_receipt(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        source = self.project / "src" / "helper.py"
        source.parent.mkdir(parents=True)
        source.write_text("before\n", encoding="utf-8")
        facts = self.write_json("incremental-gate.json", {"allowed_scope": ["src/**"]})
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "调整现有能力",
            "--facts",
            str(facts),
        )
        task_id = routed["task_id"]
        self.assertNotIn("code-edit", routed["matched_gates"])
        source.write_text("after\n", encoding="utf-8")
        receipt = self.evidence(
            "incremental-gate-test",
            evidence_type="test_result",
            covers=task_id,
            changed_paths=["src/helper.py"],
        )
        original_receipt = json.loads(receipt.read_text(encoding="utf-8"))

        _, pending = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--evidence",
            str(receipt),
            expected=3,
        )
        self.assertEqual(pending["reason_code"], "incremental_gate_context_required")
        self.assertEqual([item["action"] for item in pending["recovery_actions"]], ["incremental_admission"])
        self.assertEqual(pending["added_gates"], ["code-edit"])
        self.assertFalse(pending["evidence_regeneration_required"])

        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["package_revision"], 2)
        self.assertIn("code-edit", package["matched_gates"])
        indexed = json.loads((state / "evidence-index.json").read_text(encoding="utf-8"))["evidence"]
        self.assertEqual(len(indexed), 1)
        self.assertEqual(indexed[0]["origin_package_fingerprint"], original_receipt["package_fingerprint"])
        self.assertEqual(indexed[0]["package_fingerprint"], HARNESS_MODULE.package_fingerprint(package))
        self.assertEqual(indexed[0]["adoption_reason"], "additive_gate_only")

        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        change_review = self.write_json(
            "incremental-change-review.json",
            {
                "schema_version": "docs-harness/evidence-declaration/v1",
                "type": "change_review",
                "write_set": ["src/helper.py"],
                "conclusion": "增量 Gate 准入后变更仍符合原任务意图",
            },
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(change_review)
        )
        self.assertEqual(verified["result"], "完成")
        events = HARNESS_MODULE.read_jsonl(state / "events.jsonl")
        self.assertIn("incremental_gate_readmission", [event["event"] for event in events])

    def test_v164_every_verify_attempt_is_recorded_as_bounded_event(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "testing.md")
        facts = self.write_json(
            "verify-attempt.json",
            {"allowed_scope": ["src/**"], "gates": ["code-edit"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        for _ in range(2):
            self.run_harness(
                "verify", "--target", str(self.project), "--task-id", task_id, expected=3
            )
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        attempts = [
            item
            for item in HARNESS_MODULE.read_jsonl(state / "events.jsonl")
            if item.get("event") == "verification_attempt"
        ]
        self.assertEqual(len(attempts), 2)
        self.assertEqual([item["outcome_class"] for item in attempts], ["provide_evidence"] * 2)
        self.assertEqual([item["evidence_round_count"] for item in attempts], [0, 1])
        for item in attempts:
            self.assertEqual(item["exit_code"], 3)
            self.assertTrue(item["reason_codes"])
            self.assertTrue(
                {
                    "command_executed_count",
                    "command_cache_hit_count",
                    "context_full_load_count",
                    "context_delta_load_count",
                    "evidence_regeneration_required",
                }
                <= set(item)
            )
            serialized = json.dumps(item, ensure_ascii=False)
            self.assertNotIn("调整现有能力", serialized)
            self.assertNotIn("environment", serialized)

    def test_v164_authorization_contract_survives_incremental_gate_admission(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "testing.md", "security.md")
        facts = self.write_gate_facts(
            "auth-incremental.json",
            ["release-external"],
            allowed_scope=["dist/**", "src/**"],
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "发布 release", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for({"外部目标": "测试发布目标。", "发布与回滚": "失败时回退到上一个版本。"})
        _, pending = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        self.assertEqual(pending["admission_status"], "needs_authorization")
        auth = self.write_json(
            "auth-incremental-receipt.json",
            {
                "approved": True,
                "authorized_actions": ["external_write"],
                "authorized_scope": ["dist/**", "src/**"],
                "external_target": "test-release",
            },
        )
        _, admitted = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--authorization", str(auth)
        )
        self.assertEqual(admitted["admission_status"], "ready_planned")
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        original_package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        original_fingerprint = HARNESS_MODULE.package_fingerprint(original_package)
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        source = self.project / "src" / "helper.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("released\n", encoding="utf-8")
        receipt = self.evidence(
            "auth-incremental-test",
            evidence_type="test_result",
            covers=task_id,
            changed_paths=["src/helper.py"],
        )
        _, incremental = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--evidence",
            str(receipt),
            expected=3,
        )
        self.assertEqual(incremental["missing_evidence_types"], ["external_state"])
        adoptions = [
            item
            for item in HARNESS_MODULE.read_jsonl(state / "authorization-receipts.jsonl")
            if item.get("schema_version") == "docs-harness/authorization-adoption/v1"
        ]
        self.assertEqual(len(adoptions), 1)
        adopted_package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(adopted_package["package_revision"], 2)
        self.assertIn("code-edit", adopted_package["matched_gates"])
        self.assertIn("release-external", adopted_package["matched_gates"])
        self.assertEqual(
            adoptions[0]["package_fingerprint"],
            HARNESS_MODULE.package_fingerprint(adopted_package),
        )
        self.assertEqual(adoptions[0]["adopted_from_package_fingerprint"], original_fingerprint)
        self.assertEqual(adoptions[0]["adoption_reason"], "authorization_contract_unchanged")
        self.assertEqual(adoptions[0]["external_target"], "test-release")
        self.assertTrue(adoptions[0]["artifact_ref"])
        self.assertTrue(Path(adoptions[0]["artifact_ref"]).is_file())
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        result, second = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=None
        )
        self.assertNotEqual(second.get("reason_code"), "authorization_contract_drift")
        self.assertNotIn("授权", str(second.get("reason", "")))
        self.assertNotEqual(result.returncode, 4)
        events = HARNESS_MODULE.read_jsonl(state / "events.jsonl")
        readmission = [item for item in events if item.get("event") == "incremental_gate_readmission"]
        self.assertEqual(len(readmission), 1)
        self.assertTrue(readmission[0]["authorization_adopted"])
        self.assertEqual(readmission[0]["disposition"], "incremental_admission")
        self.assertEqual(events[-1]["readmission_count"], 1)

    def test_v164_authorization_adoption_is_refused_when_any_scope_changes(self) -> None:
        previous = {
            "task_id": "t-1",
            "package_revision": 1,
            "authorization_requirements": ["external_write"],
            "allowed_scope": ["dist/**"],
            "write_scope": ["dist/**"],
            "git_scope": [],
            "external_scope": ["dist/**"],
        }
        candidate = {**previous, "package_revision": 2, "external_scope": ["dist/**", "release/**"]}
        self.assertNotEqual(
            HARNESS_MODULE.authorization_contract_fingerprint(previous),
            HARNESS_MODULE.authorization_contract_fingerprint(candidate),
        )
        state = self.temp_root / "adoption-state"
        state.mkdir()
        self.assertIsNone(HARNESS_MODULE.authorization_adoption_record(state, previous, candidate))

    def test_v164_evidence_managed_copy_survives_source_deletion(self) -> None:
        self.init_project()
        facts = self.write_json(
            "facts-evmanaged.json",
            {"allowed_scope": ["src/helper.py", "README.md"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        (self.project / "src").mkdir(parents=True, exist_ok=True)
        (self.project / "src" / "helper.py").write_text("value = 1\n", encoding="utf-8")
        (self.project / "README.md").write_text("# README\n", encoding="utf-8")
        doc_evidence = self.evidence(
            "ev-managed-doc",
            evidence_type="document_review",
            covers=task_id,
            changed_paths=["src/helper.py", "README.md"],
        )
        _, first = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(doc_evidence), expected=3
        )
        self.assertIn("test_result", first["missing_evidence_types"])
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        managed_dir = state / "artifacts" / "evidence"
        self.assertTrue(any(managed_dir.iterdir()), "首次校验通过的证据必须摄取到受管副本")
        doc_evidence.unlink()
        test_evidence = self.evidence(
            "ev-managed-test", evidence_type="test_result", covers=task_id, changed_paths=["src/helper.py"]
        )
        _, second = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(test_evidence)
        )
        self.assertEqual(second["result"], "完成")
        self.assertNotIn("ev-managed-doc", second.get("stale_evidence", []))

    def test_v164_passed_verification_command_not_rerun_when_supplying_evidence(self) -> None:
        self.init_project()
        (self.project / "test_smoke_cache.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_pass(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        facts = self.write_json(
            "cache-command.json",
            {
                "allowed_scope": ["src/helper.py", "README.md"],
                "verification_commands": [
                    {"argv": ["python3", "-m", "unittest", "test_smoke_cache"], "produces": ["test_result"]}
                ],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        (self.project / "src").mkdir(parents=True, exist_ok=True)
        (self.project / "src" / "helper.py").write_text("value = 1\n", encoding="utf-8")
        (self.project / "README.md").write_text("# README\n", encoding="utf-8")
        changed = ["src/helper.py", "README.md"]
        test_evidence = self.evidence(
            "cache-test", evidence_type="test_result", covers=task_id, changed_paths=changed
        )
        _, first = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(test_evidence), expected=3
        )
        self.assertIn("document_review", first["missing_evidence_types"])
        self.assertEqual(first["verification_commands"][0]["result"], "passed")
        self.assertFalse(first["verification_commands"][0].get("cache_hit"))
        evidence = self.evidence(
            "cache-doc", evidence_type="document_review", covers=task_id, changed_paths=changed
        )
        _, second = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(second["result"], "完成")
        self.assertTrue(second["verification_commands"][0]["cache_hit"])
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        attempts = [
            item
            for item in HARNESS_MODULE.read_jsonl(state / "events.jsonl")
            if item.get("event") == "verification_attempt"
        ]
        self.assertEqual(attempts[-1]["command_executed_count"], 0)
        self.assertEqual(attempts[-1]["command_cache_hit_count"], 1)

    def test_v164_only_failed_verification_command_is_rerun(self) -> None:
        self.init_project()
        passing = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_pass(self):\n        self.assertTrue(True)\n"
        (self.project / "test_pass_a.py").write_text(passing, encoding="utf-8")
        (self.project / "test_pass_b.py").write_text(passing, encoding="utf-8")
        (self.project / "test_flag.py").write_text(
            "import pathlib\nimport unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def test_flag(self):\n        self.assertTrue(pathlib.Path('flag.log').is_file())\n",
            encoding="utf-8",
        )
        facts = self.write_json(
            "multi-command.json",
            {
                "allowed_scope": ["README.md"],
                "verification_commands": [
                    {"argv": ["python3", "-m", "unittest", "test_pass_a"], "produces": ["test_result"]},
                    {"argv": ["python3", "-m", "unittest", "test_flag"], "produces": ["test_result"]},
                    {"argv": ["python3", "-m", "unittest", "test_pass_b"], "produces": ["test_result"]},
                ],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        (self.project / "README.md").write_text("# README\n", encoding="utf-8")
        evidence = self.evidence(
            "multi-doc", evidence_type="document_review", covers=task_id, changed_paths=["README.md"]
        )
        _, first = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=3
        )
        by_command = {tuple(item["command"]): item for item in first["verification_commands"]}
        self.assertEqual(by_command[("python3", "-m", "unittest", "test_pass_a")]["result"], "passed")
        self.assertEqual(by_command[("python3", "-m", "unittest", "test_pass_b")]["result"], "passed")
        self.assertEqual(by_command[("python3", "-m", "unittest", "test_flag")]["result"], "failed")
        (self.project / "flag.log").write_text("ready\n", encoding="utf-8")
        _, second = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(second["result"], "完成")
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        attempts = [
            item
            for item in HARNESS_MODULE.read_jsonl(state / "events.jsonl")
            if item.get("event") == "verification_attempt"
        ]
        self.assertEqual(attempts[-1]["command_executed_count"], 1)
        self.assertEqual(attempts[-1]["command_cache_hit_count"], 2)

    def test_v164_blocking_write_only_flips_its_own_verification_command(self) -> None:
        self.init_project()
        passing = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_pass(self):\n        self.assertTrue(True)\n"
        (self.project / "test_pass_keep.py").write_text(passing, encoding="utf-8")
        (self.project / "test_write_extra.py").write_text(
            "import pathlib\nimport unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def test_write(self):\n"
            "        pathlib.Path('EXTRA_OUTPUT.md').write_text('# 额外写入', encoding='utf-8')\n",
            encoding="utf-8",
        )
        facts = self.write_json(
            "blocking-write-command.json",
            {
                "allowed_scope": ["README.md"],
                "verification_commands": [
                    {"argv": ["python3", "-m", "unittest", "test_write_extra"], "produces": ["test_result"]},
                    {"argv": ["python3", "-m", "unittest", "test_pass_keep"], "produces": ["test_result"]},
                ],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        (self.project / "README.md").write_text("# README\n", encoding="utf-8")
        evidence = self.evidence(
            "blocking-write-doc", evidence_type="document_review", covers=task_id, changed_paths=["README.md"]
        )
        _, first = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=3
        )
        by_command = {tuple(item["command"]): item for item in first["verification_commands"]}
        writer = by_command[("python3", "-m", "unittest", "test_write_extra")]
        keeper = by_command[("python3", "-m", "unittest", "test_pass_keep")]
        self.assertEqual(writer["result"], "failed")
        self.assertEqual(writer["reason_code"], "verification_command_workspace_write")
        self.assertEqual(keeper["result"], "passed")
        self.assertFalse(keeper.get("cache_hit"))
        (self.project / "EXTRA_OUTPUT.md").unlink()
        _, second = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        by_command = {tuple(item["command"]): item for item in second["verification_commands"]}
        self.assertEqual(by_command[("python3", "-m", "unittest", "test_write_extra")]["result"], "failed")
        self.assertTrue(by_command[("python3", "-m", "unittest", "test_pass_keep")]["cache_hit"])
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        attempts = [
            item
            for item in HARNESS_MODULE.read_jsonl(state / "events.jsonl")
            if item.get("event") == "verification_attempt"
        ]
        self.assertEqual(attempts[-1]["command_executed_count"], 1)
        self.assertEqual(attempts[-1]["command_cache_hit_count"], 1)

    def test_v164_workspace_input_change_invalidates_command_cache(self) -> None:
        self.init_project()
        (self.project / "test_smoke_inv.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_pass(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        facts = self.write_json(
            "invalidate-command.json",
            {
                "allowed_scope": ["src/helper.py", "README.md"],
                "verification_commands": [
                    {"argv": ["python3", "-m", "unittest", "test_smoke_inv"], "produces": ["test_result"]}
                ],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        (self.project / "src").mkdir(parents=True, exist_ok=True)
        (self.project / "src" / "helper.py").write_text("value = 1\n", encoding="utf-8")
        (self.project / "README.md").write_text("# README v1\n", encoding="utf-8")
        changed = ["src/helper.py", "README.md"]
        test_evidence = self.evidence(
            "invalidate-test", evidence_type="test_result", covers=task_id, changed_paths=changed
        )
        _, first = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(test_evidence), expected=3
        )
        self.assertFalse(first["verification_commands"][0].get("cache_hit"))
        (self.project / "README.md").write_text("# README v2 已更新\n", encoding="utf-8")
        evidence = self.evidence(
            "invalidate-doc", evidence_type="document_review", covers=task_id, changed_paths=changed
        )
        _, second = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(second["result"], "完成")
        self.assertFalse(second["verification_commands"][0].get("cache_hit"))
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        attempts = [
            item
            for item in HARNESS_MODULE.read_jsonl(state / "events.jsonl")
            if item.get("event") == "verification_attempt"
        ]
        self.assertEqual(attempts[-1]["command_executed_count"], 1)
        self.assertEqual(attempts[-1]["command_cache_hit_count"], 0)

    def test_v164_command_cache_can_be_disabled_by_project_config(self) -> None:
        self.init_project()
        (self.project / "test_smoke_off.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_pass(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["verification"] = {"command_cache_enabled": False}
        config_path.write_text(json.dumps(config), encoding="utf-8")
        facts = self.write_json(
            "cache-off-command.json",
            {
                "allowed_scope": ["src/helper.py", "README.md"],
                "verification_commands": [
                    {"argv": ["python3", "-m", "unittest", "test_smoke_off"], "produces": ["test_result"]}
                ],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        (self.project / "src").mkdir(parents=True, exist_ok=True)
        (self.project / "src" / "helper.py").write_text("value = 1\n", encoding="utf-8")
        (self.project / "README.md").write_text("# README\n", encoding="utf-8")
        changed = ["src/helper.py", "README.md"]
        test_evidence = self.evidence(
            "cache-off-test", evidence_type="test_result", covers=task_id, changed_paths=changed
        )
        _, first = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(test_evidence), expected=3
        )
        self.assertEqual(first["verification_commands"][0]["result"], "passed")
        self.assertFalse(first["verification_commands"][0].get("cache_hit"))
        doc_evidence = self.evidence(
            "cache-off-doc", evidence_type="document_review", covers=task_id, changed_paths=changed
        )
        _, second = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(doc_evidence)
        )
        self.assertEqual(second["result"], "完成")
        self.assertFalse(second["verification_commands"][0].get("cache_hit"))
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        attempts = [
            item
            for item in HARNESS_MODULE.read_jsonl(state / "events.jsonl")
            if item.get("event") == "verification_attempt"
        ]
        self.assertEqual(attempts[-1]["command_executed_count"], 1)
        self.assertEqual(attempts[-1]["command_cache_hit_count"], 0)
        self.assertFalse(attempts[-1]["command_cache_enabled"])
        cache_index = state / "artifacts" / "verification" / "command-receipts.jsonl"
        self.assertFalse(cache_index.exists(), "关闭缓存后不得写入验证命令收据")

    def test_v164_same_active_task_key_returns_existing_task(self) -> None:
        self.init_project()
        facts = self.write_json("idem-facts.json", {"allowed_scope": ["README.md"]})
        _, first = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        _, second = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        self.assertEqual(second["task_id"], first["task_id"])
        self.assertTrue(second["active_task_reused"])
        self.assertEqual(second["reason_code"], "active_task_reused")
        self.assertEqual(second["admission_status"], first["admission_status"])
        runs_root = self.project / ".docs-harness" / "runs"
        task_dirs = [path for path in runs_root.iterdir() if path.is_dir()]
        self.assertEqual(len(task_dirs), 1)
        _, forced = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 README 文档",
            "--facts",
            str(facts),
            "--new-task",
        )
        self.assertNotEqual(forced["task_id"], first["task_id"])
        self.assertNotIn("active_task_reused", forced)

    def test_v164_different_initial_workspace_creates_new_task(self) -> None:
        self.init_project()
        facts = self.write_json("idem-ws-facts.json", {"allowed_scope": ["README.md"]})
        _, first = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        (self.project / "README.md").write_text("# 已存在\n", encoding="utf-8")
        _, second = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        self.assertNotEqual(second["task_id"], first["task_id"])
        self.assertNotIn("active_task_reused", second)

    def test_v164_change_scoped_estimate_ignores_unrelated_workspace_changes(self) -> None:
        self.init_project()
        (self.project / "src").mkdir(parents=True, exist_ok=True)
        (self.project / "src" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
        candidate = {
            "estimate_basis": "change_scoped",
            "changed_paths": ["src/core.py"],
            "allowed_write_scope": ["docs/**"],
            "selected_features": ["src/core"],
            "deliverables": ["feature_knowledge_incremental_sync"],
        }
        first = HARNESS_MODULE.workload_estimate(self.project, candidate=candidate)
        (self.project / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
        second = HARNESS_MODULE.workload_estimate(self.project, candidate=candidate)
        self.assertEqual(first["source_fingerprint"], second["source_fingerprint"])
        (self.project / "src" / "core.py").write_text("VALUE = 2\n", encoding="utf-8")
        third = HARNESS_MODULE.workload_estimate(self.project, candidate=candidate)
        self.assertNotEqual(third["source_fingerprint"], first["source_fingerprint"])

    def write_repowiki_fixture(self) -> None:
        root = self.project / ".qoder" / "repowiki" / "knowledge" / "zh"
        (root / "核心模块").mkdir(parents=True, exist_ok=True)
        (root / "核心模块" / "核心模块.md").write_text(
            "---\nkind: module\nname: 核心模块\ncategory: architecture\nscope:\n    - 'src/**'\nsource_files:\n    - src/core.py\n---\n\n### 1. 概述\n\n核心模块负责业务编排与状态流转，已由测试项目确认的真实事实和当前边界。\n",
            encoding="utf-8",
        )
        (root / "文档体系").mkdir(parents=True, exist_ok=True)
        (root / "文档体系" / "文档体系.md").write_text(
            "---\nkind: documentation\nname: 文档体系\ncategory: docs\nscope:\n    - 'docs/**'\n---\n\n### 1. 概述\n\n文档体系描述项目文档结构与写作约束，已由测试项目确认的真实事实和当前边界。\n",
            encoding="utf-8",
        )
        (root / "_index.yaml").write_text("schema_version: 1\nmodules: {}\n", encoding="utf-8")
        wiki_root = self.project / ".qoder" / "repowiki" / "zh" / "content"
        wiki_root.mkdir(parents=True, exist_ok=True)
        (wiki_root / "架构概览.md").write_text(
            "# 架构概览\n\n测试项目由核心模块与文档体系组成。\n",
            encoding="utf-8",
        )

    def test_v177_repowiki_guidance_depends_on_directory_presence(self) -> None:
        self.assertEqual(HARNESS_MODULE.repowiki_context_guidance(self.project), {})
        self.write_repowiki_fixture()
        guidance = HARNESS_MODULE.repowiki_context_guidance(self.project)
        self.assertEqual(
            guidance["instructions"],
            [HARNESS_MODULE.REPOWIKI_ARCHITECTURE_INSTRUCTION],
        )
        self.assertEqual(
            guidance["preferred_read_roots"],
            [
                ".qoder/repowiki/zh/content/",
                ".qoder/repowiki/knowledge/zh/",
            ],
        )

    def test_v166_repowiki_init_consumes_without_scaffold_or_bootstrap(self) -> None:
        self.write_repowiki_fixture()
        _, payload = self.run_harness("project", "init", "--target", str(self.project))
        self.assertFalse((self.project / "docs").exists())
        self.assertEqual(payload["knowledge_flow"]["mode"], "external_consume_only")
        self.assertEqual(
            payload["knowledge_flow"]["context_instructions"],
            [HARNESS_MODULE.REPOWIKI_ARCHITECTURE_INSTRUCTION],
        )
        self.assertEqual(payload["knowledge_status"], "ready")
        self.assertIn(
            HARNESS_MODULE.REPOWIKI_ARCHITECTURE_INSTRUCTION,
            (self.project / "AGENTS.md").read_text(encoding="utf-8"),
        )
        bootstraps = [
            job
            for job in HARNESS_MODULE.list_background_jobs(self.project)
            if job.get("task_kind") == "knowledge_bootstrap"
        ]
        self.assertEqual(bootstraps, [])

    def test_v166_repowiki_status_is_ready_with_source_marker(self) -> None:
        self.write_repowiki_fixture()
        status = HARNESS_MODULE.knowledge_status(self.project)
        self.assertEqual(status["status"], "ready")
        self.assertEqual(status["source"], "repowiki")
        self.assertEqual(status["features"], 2)
        self.assertEqual(status["total_cards"], 2)
        self.assertFalse(status["truncated"])
        self.assertEqual(
            status["context_instructions"],
            [HARNESS_MODULE.REPOWIKI_ARCHITECTURE_INSTRUCTION],
        )

    def test_v167_repowiki_truncation_is_observable(self) -> None:
        self.write_repowiki_fixture()
        root = self.project / ".qoder" / "repowiki" / "knowledge" / "zh"
        overflow = root / "溢出模块"
        overflow.mkdir(parents=True, exist_ok=True)
        for index in range(3):
            (overflow / f"卡片{index}.md").write_text(
                f"---\nkind: module\nname: 卡片{index}\ncategory: architecture\nscope:\n    - 'src/**'\n---\n\n### 1. 概述\n\n溢出卡片，已由测试项目确认的真实事实和当前边界。\n",
                encoding="utf-8",
            )
        os.environ["DOCS_HARNESS_REPOWIKI_CARD_LIMIT"] = "2"
        try:
            status = HARNESS_MODULE.knowledge_status(self.project)
            self.assertEqual(status["features"], 2)
            self.assertEqual(status["total_cards"], 5)
            self.assertTrue(status["truncated"])
            self.init_project(bootstrap_knowledge=False)
            _, routed = self.run_harness(
                "run", "--target", str(self.project), "--task", "调整核心模块的处理逻辑", "--scope", "src/core.py"
            )
            package_path = self.project / ".docs-harness" / "runs" / routed["task_id"] / "task-package.json"
            context = json.loads(package_path.read_text(encoding="utf-8"))["knowledge_context"]
            self.assertTrue(context["truncated"])
            self.assertEqual(context["total_cards"], 5)
            self.assertEqual(context["context_quality"], "complete")
        finally:
            os.environ.pop("DOCS_HARNESS_REPOWIKI_CARD_LIMIT", None)

    def test_v166_repowiki_run_consumes_cards_without_governance_deliverables(self) -> None:
        self.write_repowiki_fixture()
        self.init_project(bootstrap_knowledge=False)
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整核心模块的处理逻辑", "--scope", "src/core.py"
        )
        package_path = self.project / ".docs-harness" / "runs" / routed["task_id"] / "task-package.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        context = package["knowledge_context"]
        self.assertEqual(context["source"], "repowiki")
        self.assertEqual(context["context_quality"], "complete")
        self.assertEqual(
            routed["context_instructions"],
            [HARNESS_MODULE.REPOWIKI_ARCHITECTURE_INSTRUCTION],
        )
        self.assertEqual(
            context["instructions"],
            [HARNESS_MODULE.REPOWIKI_ARCHITECTURE_INSTRUCTION],
        )
        self.assertEqual(
            context["preferred_read_roots"],
            [
                ".qoder/repowiki/zh/content/",
                ".qoder/repowiki/knowledge/zh/",
            ],
        )
        self.assertEqual(context["selected_features"], ["核心模块"])
        card_refs = [ref for refs in context["category_refs"].values() for ref in refs]
        self.assertIn(".qoder/repowiki/knowledge/zh/核心模块/核心模块.md", card_refs)
        declared = {item["deliverable"] for item in package["background_deliverables"]}
        self.assertNotIn("feature_knowledge_incremental_sync", declared)
        self.assertNotIn("adr_changelog_todo_review", declared)
        _, status = self.run_harness(
            "task", "status", "--target", str(self.project), "--task-id", routed["task_id"]
        )
        self.assertEqual(
            status["context_instructions"],
            [HARNESS_MODULE.REPOWIKI_ARCHITECTURE_INSTRUCTION],
        )

    def test_v166_repowiki_bootstrap_fails_closed(self) -> None:
        self.write_repowiki_fixture()
        self.init_project(bootstrap_knowledge=False)
        _, payload = self.run_harness("knowledge", "bootstrap", "--target", str(self.project), expected=3)
        self.assertEqual(payload["code"], "knowledge_external_consume_only")

    def test_v166_repowiki_verify_creates_no_knowledge_job(self) -> None:
        self.write_repowiki_fixture()
        self.init_project(bootstrap_knowledge=False)
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现核心模块的 `src/core.py` 代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "src").mkdir(parents=True, exist_ok=True)
        (self.project / "src" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
        evidence = self.evidence(
            "repowiki-complete-core",
            evidence_type="test_result",
            covers=task_id,
            changed_paths=["src/core.py"],
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(verified["result"], "完成")
        knowledge_jobs = [
            job
            for job in HARNESS_MODULE.list_background_jobs(self.project)
            if str(job.get("task_kind", "")).startswith("knowledge_")
        ]
        self.assertEqual(knowledge_jobs, [])

    def test_v164_completion_without_workspace_change_creates_zero_background_jobs(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "testing.md")
        facts = self.write_json(
            "no-change-facts.json",
            {"allowed_scope": ["src/**"], "gates": ["code-edit"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.assertIn(
            "feature_knowledge_incremental_sync",
            [item["deliverable"] for item in routed["background_deliverables"]],
        )
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        source = self.project / "docs" / "INDEX.md"
        jobs_before = [job["job_id"] for job in HARNESS_MODULE.list_background_jobs(self.project)]
        receipt = self.evidence(
            "no-change-test",
            evidence_type="test_result",
            covers=task_id,
            changed_paths=[],
            read_set=[{"path": "docs/INDEX.md", "fingerprint": HARNESS_MODULE.file_fingerprint(source)}],
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(receipt)
        )
        self.assertEqual(verified["control_status"], "complete")
        self.assertEqual(verified["changed_paths"], [])
        self.assertEqual(verified["post_completion"]["reason_code"], "no_write_no_sync")
        self.assertEqual(verified["post_completion"]["status"], "not_required")
        self.assertEqual(verified["background"]["jobs"], [])
        self.assertEqual(
            [job["job_id"] for job in HARNESS_MODULE.list_background_jobs(self.project)],
            jobs_before,
        )

    def test_incremental_gate_context_returns_only_new_content(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "testing.md")
        source = self.project / "src" / "helper.test.ts"
        source.parent.mkdir(parents=True)
        source.write_text("before\n", encoding="utf-8")
        facts = self.write_json(
            "incremental-context.json",
            {"allowed_scope": ["src/**"], "gates": ["code-edit"]},
        )
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "调整现有能力",
            "--facts",
            str(facts),
        )
        task_id = routed["task_id"]
        _, initial_context = self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        initial_refs = {
            item["ref"] for item in [*initial_context["rules"], *initial_context["project_facts"]]
        }
        self.assertTrue(initial_refs)

        source.write_text("after\n", encoding="utf-8")
        receipt = self.evidence(
            "incremental-context-test",
            evidence_type="test_result",
            covers=task_id,
            changed_paths=["src/helper.test.ts"],
        )
        _, pending = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--evidence",
            str(receipt),
            expected=3,
        )
        self.assertEqual(pending["added_gates"], ["testing-acceptance"])

        _, delta = self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        self.assertTrue(delta["context_delta"])
        self.assertGreater(delta["reused_content_count"], 0)
        self.assertGreater(delta["loaded_content_count"], 0)
        delta_refs = {item["ref"] for item in [*delta["rules"], *delta["project_facts"]]}
        self.assertTrue(delta_refs.isdisjoint(initial_refs))
        self.assertIn("rule:DH-TESTING-RELEASE", delta_refs)
        self.assertEqual(delta["next_action"], "verify")
        self.assertIn("verify", delta["next_command_argv"])

        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(verified["result"], "完成")

    def test_verify_keeps_full_readmission_for_gate_that_changes_route(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "security.md")
        source = self.project / "src" / "auth.py"
        source.parent.mkdir(parents=True)
        source.write_text("before\n", encoding="utf-8")
        facts = self.write_json("high-risk-gate.json", {"allowed_scope": ["src/**"]})
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "调整现有能力",
            "--facts",
            str(facts),
        )
        task_id = routed["task_id"]
        source.write_text("after\n", encoding="utf-8")
        receipt = self.evidence(
            "high-risk-gate-test",
            evidence_type="test_result",
            covers=task_id,
            changed_paths=["src/auth.py"],
        )
        _, blocked = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--evidence",
            str(receipt),
            expected=4,
        )
        self.assertEqual(blocked["result"], "重新准入")
        self.assertEqual(blocked["reason_code"], "new_risk_gate")
        self.assertIn("security-sensitive", blocked["new_gates"])

    def test_file_arguments_reject_inline_content_with_safe_structured_errors(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "testing.md")

        _, plan_task = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力"
        )
        self.run_harness(
            "context",
            "--target",
            str(self.project),
            "--task-id",
            plan_task["task_id"],
            "--stage",
            "plan",
        )

        facts = self.write_gate_facts(
            "release-facts.json",
            ["release-external"],
            allowed_scope=["dist/app.zip"],
        )
        _, release_task = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "发布产物",
            "--facts",
            str(facts),
        )
        self.run_harness(
            "context",
            "--target",
            str(self.project),
            "--task-id",
            release_task["task_id"],
            "--stage",
            "plan",
        )
        release_plan = self.plan_for(
            {field: "已覆盖" for field in release_task["plan_fields"]}
        )
        self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task-id",
            release_task["task_id"],
            "--plan",
            str(release_plan),
            expected=3,
        )

        readme = self.project / "README.md"
        readme.write_text("before\n", encoding="utf-8")
        _, evidence_task = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 README 文档",
            "--scope",
            "README.md",
        )
        self.run_harness(
            "context",
            "--target",
            str(self.project),
            "--task-id",
            evidence_task["task_id"],
            "--stage",
            "action",
        )

        secret_marker = "MUST_NOT_LEAK_" + ("x" * 4096)
        inline = json.dumps({"secret": secret_marker})
        cases = (
            ("facts", ["run", "--target", str(self.project), "--task", "测试", "--facts", inline]),
            (
                "plan",
                [
                    "run",
                    "--target",
                    str(self.project),
                    "--task-id",
                    plan_task["task_id"],
                    "--plan",
                    inline,
                ],
            ),
            (
                "authorization",
                [
                    "run",
                    "--target",
                    str(self.project),
                    "--task-id",
                    release_task["task_id"],
                    "--authorization",
                    inline,
                ],
            ),
            (
                "evidence",
                [
                    "verify",
                    "--target",
                    str(self.project),
                    "--task-id",
                    evidence_task["task_id"],
                    "--evidence",
                    inline,
                ],
            ),
        )
        for name, args in cases:
            with self.subTest(argument=name):
                runs_root = self.project / ".docs-harness" / "runs"
                state_before = self.snapshot_tree(runs_root)
                result = subprocess.run(
                    [sys.executable, str(HARNESS), *args, "--json"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                self.assertEqual(result.returncode, 2)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["code"], "inline_input_not_supported")
                self.assertNotIn(secret_marker, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.snapshot_tree(runs_root), state_before)

    def test_plan_file_input_boundaries_are_structured_and_do_not_mutate_state(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力"
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        runs_root = self.project / ".docs-harness" / "runs"
        state_before = self.snapshot_tree(runs_root)

        missing = self.temp_root / "missing-plan.json"
        oversized = self.temp_root / "oversized-plan.md"
        oversized.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        non_utf8 = self.temp_root / "non-utf8-plan.md"
        non_utf8.write_bytes(b"\xff\xfe\x80")

        cases = (
            ("short_inline", json.dumps({"secret": "SHORT_INLINE_MUST_NOT_LEAK"}), "inline_input_not_supported"),
            ("missing", str(missing), "invalid_plan"),
            ("oversized", str(oversized), "invalid_plan"),
            ("non_utf8", str(non_utf8), "invalid_plan"),
        )
        for name, plan_input, expected_code in cases:
            with self.subTest(boundary=name):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(HARNESS),
                        "run",
                        "--target",
                        str(self.project),
                        "--task-id",
                        task_id,
                        "--plan",
                        plan_input,
                        "--json",
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                self.assertEqual(result.returncode, 2, f"{result.stdout}\n{result.stderr}")
                payload = json.loads(result.stdout)
                self.assertEqual(payload["code"], expected_code)
                self.assertNotIn("SHORT_INLINE_MUST_NOT_LEAK", result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertNotIn("OSError", result.stderr)
                self.assertEqual(self.snapshot_tree(runs_root), state_before)

    def test_file_argument_help_exposes_file_contract_and_existing_task_continuation(self) -> None:
        result = subprocess.run(
            [sys.executable, str(HARNESS), "run", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--facts FACTS_FILE", result.stdout)
        self.assertIn("--plan PLAN_FILE", result.stdout)
        self.assertIn("--authorization AUTHORIZATION_FILE", result.stdout)
        self.assertIn("继续已有任务", result.stdout)
        self.assertIn("不接受内联内容", result.stdout)

    def test_verify_blocker_uses_the_shared_executable_next_step_contract(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 README 文档",
            "--scope",
            "README.md",
        )
        _, blocked = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            routed["task_id"],
            expected=3,
        )
        self.assertEqual(blocked["next_action"], "load_action_context")
        self.assertEqual(blocked["reason_code"], "action_context_missing")
        self.assertIn("context", blocked["next_command_argv"])
        self.assertIn(routed["task_id"], blocked["next_command_argv"])

    def test_invalid_active_rule_fails_project_check(self) -> None:
        self.init_project()
        invalid_rule = self.project / ".docs-harness" / "harness-home" / "rules" / "invalid.md"
        invalid_rule.write_text(
            "---\nstatus: active\nrule_id: R-1\ncontent_fingerprint: sha256:bad\n---\n\n# Invalid\n",
            encoding="utf-8",
        )
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["installed_rule_fingerprints"]["invalid.md"] = "sha256:" + hashlib.sha256(invalid_rule.read_bytes()).hexdigest()
        config_path.write_text(json.dumps(config), encoding="utf-8")
        _, checked = self.run_harness(
            "project", "check", "--target", str(self.project), expected=1
        )
        self.assertEqual(checked["status"], "failed")
        self.assertTrue(any(item["code"] == "invalid_active_rule" for item in checked["findings"]))

    def test_upgrade_refuses_to_overwrite_user_modified_controller(self) -> None:
        self.init_project()
        installed = self.project / "scripts" / "harness.py"
        installed.write_text(installed.read_text(encoding="utf-8") + "\n# 用户本地修改\n", encoding="utf-8")
        _, rejected = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=2
        )
        self.assertEqual(rejected["code"], "install_conflict")
        self.assertIn("用户本地修改", installed.read_text(encoding="utf-8"))

    def test_upgrade_preview_reports_outdated_managed_entry(self) -> None:
        self.init_project()
        agents = self.project / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8").replace(
                "只有用户明确要求“添加到质量账本”或同义写入动作时",
                "旧版入口尚未包含质量账本触发规则时",
            ),
            encoding="utf-8",
        )
        _, preview = self.run_harness(
            "project", "upgrade", "--target", str(self.project)
        )
        self.assertIn(
            {"path": "AGENTS.md", "action": "update_managed_block"},
            preview["changes"],
        )

    def test_git_delivery_requires_current_managed_entry_content_in_head(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        self.init_project(expected=3)
        self.commit_project()
        agents = self.project / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8").replace(
                "只有用户明确要求“添加到质量账本”或同义写入动作时",
                "旧版入口尚未包含质量账本触发规则时",
            ),
            encoding="utf-8",
        )
        self.commit_project("commit outdated managed entry")
        _, checked = self.run_harness(
            "project", "check", "--target", str(self.project), expected=3
        )
        self.assertEqual(checked["delivery_status"], "pending_commit")
        self.assertFalse(checked["clone_ready"])
        self.assertIn("AGENTS.md", checked["required_commit_paths"])

    def test_plan_scope_change_creates_new_package_revision_and_reloads_context(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("product.md", "design.md", "architecture.md")
        _, routed = self.run_harness("run", "--target", str(self.project), "--task", "实现 UI 页面")
        task_id = routed["task_id"]
        self.assertEqual(routed["allowed_scope"], [])
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for(
            {
                "设计状态": "覆盖完整状态。",
                "真实页面验收": "从真实入口验收。",
                "执行范围": ["src/view.tsx"],
            }
        )
        _, revised = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan)
        )
        self.assertEqual(revised["admission_status"], "ready_planned")
        state = self.project / ".docs-harness" / "runs" / task_id
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["package_revision"], 2)
        self.assertTrue((state / "package-history" / "task-package.v1.json").is_file())
        compiled = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        self.assertEqual(compiled["next_action"], "load_action_context")
        events = HARNESS_MODULE.read_jsonl(state / "events.jsonl")
        frozen_events = [item for item in events if item["event"] == "plan_frozen"]
        self.assertEqual(len(frozen_events), 1)
        self.assertEqual(frozen_events[0]["reason_code"], "scope_bound_plan_adopted")
        _, reloaded = self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "action"
        )
        self.assertEqual(reloaded["stage"], "action")
        receipts = HARNESS_MODULE.read_jsonl(state / "context-receipts.jsonl")
        self.assertEqual(receipts[-1]["package_revision"], 2)

    def test_plan_scope_superset_recompiles_and_non_superset_forces_readmission(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("product.md", "design.md", "architecture.md")
        facts = self.write_json("plan-scope-facts.json", {"allowed_scope": ["src/view.tsx"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现 UI 页面", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for(
            {
                "设计状态": "覆盖完整状态。",
                "真实页面验收": "从真实入口验收。",
                "执行范围": ["src/view.tsx", "src/style.css"],
            }
        )
        # 严格超集：控制器自动重编译并采用方案，不再要求完整重新准入
        _, adopted = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan)
        )
        self.assertEqual(adopted["admission_status"], "ready_planned")
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["package_revision"], 2)
        self.assertEqual(package["allowed_scope"], ["src/view.tsx", "src/style.css"])

        # 非超集冲突仍然强制完整重新准入
        facts2 = self.write_json("plan-scope-facts-2.json", {"allowed_scope": ["src/view.tsx", "src/style.css"]})
        _, routed2 = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现 UI 页面", "--facts", str(facts2)
        )
        task_id2 = routed2["task_id"]
        self.assertNotEqual(task_id2, task_id)
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id2, "--stage", "plan")
        conflicting_plan = self.plan_for(
            {
                "设计状态": "覆盖完整状态。",
                "真实页面验收": "从真实入口验收。",
                "执行范围": ["src/view.tsx", "src/other.ts"],
            }
        )
        _, readmission = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id2, "--plan", str(conflicting_plan), expected=4
        )
        self.assertEqual(readmission["result"], "重新准入")
        self.assertEqual(readmission["reason_code"], "plan_scope_mismatch")
        self.assertEqual(readmission["task_scope"], ["src/view.tsx", "src/style.css"])
        self.assertEqual(readmission["plan_scope"], ["src/view.tsx", "src/other.ts"])
        self.assertEqual(readmission["next_action"], "rerun_harness_for_readmission")

    def test_readmission_preserves_original_task_change_baseline(self) -> None:
        self.init_project()
        # 关闭自动归因，保留 write_scope 内未归因写入的失败关闭行为覆盖
        self.disable_auto_attribution()
        readme = self.project / "README.md"
        readme.write_text("before\n", encoding="utf-8")
        facts = self.write_json("initial-scope.json", {"allowed_scope": ["README.md"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        readme.write_text("after\n", encoding="utf-8")
        extra = self.project / "docs" / "extra.md"
        extra.write_text("# Extra\n", encoding="utf-8")
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        self.assertEqual(pending["result"], "补充证据")
        self.assertEqual(pending["outside_scope"], [])
        self.assertEqual(pending["reason_code"], "unattributed_drift_overlap")
        self.assertEqual(pending["missing_attribution_paths"], ["README.md"])
        self.assertEqual(
            pending["workspace_attribution"]["unattributed_drift"],
            ["README.md", "docs/extra.md"],
        )

        receipt = self.evidence(
            "baseline-preserved",
            evidence_type="document_review",
            covers=task_id,
            changed_paths=["README.md"],
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(receipt)
        )
        self.assertEqual(verified["changed_paths"], ["README.md", "docs/extra.md"])
        self.assertEqual(verified["control_status"], "complete")

    def test_non_git_snapshot_limit_fails_closed_without_partial_task_state(self) -> None:
        self.init_project()
        bulk = self.project / "bulk"
        bulk.mkdir()
        for index in range(4100):
            (bulk / f"item-{index:04d}.txt").write_text("x", encoding="utf-8")
        _, blocked = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "修改 README 文档",
            "--scope",
            "README.md",
            expected=3,
        )
        self.assertEqual(blocked["code"], "workspace_snapshot_truncated")
        self.assertFalse((self.project / ".docs-harness" / "runs").exists())

    def test_changed_plan_or_context_fails_closed(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("product.md", "design.md", "architecture.md")
        facts = self.write_json("freshness-facts.json", {"allowed_scope": ["src/view.tsx"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现 UI 页面", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        (self.project / "docs" / "features" / "project-core" / "design.md").write_text("# 设计事实\n\n事实已经变化。\n", encoding="utf-8")
        plan = self.plan_for({"设计状态": "完整。", "真实页面验收": "真实入口。"})
        _, blocked = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        self.assertEqual(blocked["next_action"], "load_plan_context")
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        self.run_harness("run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan))
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        plan.write_text(plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        state = self.project / ".docs-harness" / "runs" / task_id
        compiled = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        managed_plan = Path(compiled["plan_ref"])
        self.assertEqual(managed_plan.parent, state / "artifacts" / "plans")
        managed_plan.write_text(managed_plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        _, readmission = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=4
        )
        self.assertEqual(readmission["result"], "重新准入")
        self.assertIn("方案", readmission["reason"])

    def test_extended_progress_replays_events_and_enforces_dependencies(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_json(
            "facts-extended.json",
            {
                "execution_route": "extended",
                "allowed_scope": ["docs/a.md", "docs/b.md"],
                "work_packages": [
                    {
                        "id": "wp-a",
                        "goal": "交付 A",
                        "scope": ["docs/a.md"],
                        "dependencies": [],
                        "owner": "owner-a",
                        "success_criteria": ["A 完成"],
                        "acceptance": ["A 有证据"],
                    },
                    {
                        "id": "wp-b",
                        "goal": "交付 B",
                        "scope": ["docs/b.md"],
                        "dependencies": ["wp-a"],
                        "owner": "owner-b",
                        "success_criteria": ["B 完成"],
                        "acceptance": ["B 有证据"],
                    },
                ],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现多工作包文档", "--facts", str(facts)
        )
        self.assertEqual(routed["execution_topology"], "multi_owner")
        state_path = Path(routed["task_package_ref"])
        packet = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(len(packet["dispatch_contracts"]), 2)
        self.assertEqual({item["role"] for item in packet["dispatch_contracts"]}, {"implementation_owner"})
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for({"文档真源": "根项目文档地图。", "索引与残留": "同步索引并清除旧引用。"})
        _, admitted = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan)
        )
        self.assertEqual(admitted["admission_status"], "ready_extended")
        _, dependency_block = self.run_harness(
            "progress",
            "begin",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--work-package",
            "wp-b",
            expected=3,
        )
        self.assertEqual(dependency_block["code"], "dependency_blocked")

        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--work-package", "wp-a")
        self.run_harness("progress", "begin", "--target", str(self.project), "--task-id", task_id, "--work-package", "wp-a")
        (self.project / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
        evidence_a = self.evidence("wp-a", evidence_type="document_review", covers="wp-a", changed_paths=["docs/a.md"])
        self.run_harness(
            "progress", "submit", "--target", str(self.project), "--task-id", task_id, "--work-package", "wp-a", "--evidence", str(evidence_a)
        )
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--work-package", "wp-b")
        self.run_harness("progress", "begin", "--target", str(self.project), "--task-id", task_id, "--work-package", "wp-b")
        (self.project / "docs" / "b.md").write_text("# B\n", encoding="utf-8")
        evidence_b = self.evidence("wp-b", evidence_type="document_review", covers="wp-b", changed_paths=["docs/b.md"])
        self.run_harness(
            "progress", "submit", "--target", str(self.project), "--task-id", task_id, "--work-package", "wp-b", "--evidence", str(evidence_b)
        )
        _, status = self.run_harness(
            "progress", "status", "--target", str(self.project), "--task-id", task_id, "--handoff"
        )
        self.assertEqual(status["work_package_states"], {"wp-a": "verified", "wp-b": "verified"})
        self.assertEqual(status["next_action"], "verify")
        task_evidence = self.evidence(
            "extended-test",
            evidence_type="test_result",
            covers=task_id,
            changed_paths=["docs/a.md", "docs/b.md"],
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(task_evidence)
        )
        self.assertEqual(verified["result"], "完成")

    def test_out_of_scope_change_forces_readmission(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 `README.md` 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("ok\n", encoding="utf-8")
        (self.project / "outside.txt").write_text("unexpected\n", encoding="utf-8")
        evidence = self.evidence("scope", evidence_type="document_review", covers=task_id, changed_paths=["README.md", "outside.txt"])
        _, result = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertEqual(result["result"], "重新准入")
        self.assertEqual(result["outside_scope"], ["outside.txt"])

    def test_git_ignored_artifact_does_not_force_readmission(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        (self.project / ".gitignore").write_text("smartclaw/dist/\n", encoding="utf-8")
        (self.project / "README.md").write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore", "README.md"], cwd=self.project, check=True)
        self.init_project(expected=3)
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 `README.md` 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        (self.project / "README.md").write_text("after\n", encoding="utf-8")
        ignored = self.project / "smartclaw" / "dist" / "generated.bin"
        ignored.parent.mkdir(parents=True)
        ignored.write_bytes(b"generated")
        evidence = self.evidence("ignored-artifact", evidence_type="document_review", covers=task_id, changed_paths=["README.md"])
        _, result = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(result["result"], "完成")

    def test_quality_ledger_add_and_read_non_git_snapshot(self) -> None:
        self.init_project()
        ledger = self.project / ".docs-harness" / "quality-ledger"
        self.assertFalse(ledger.exists())
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 `README.md` 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        review = self.quality_review("add-read")
        _, added = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", task_id, "--review", str(review)
        )
        record_path = ledger / "records" / f"{task_id}.json"
        self.assertEqual(added["status"], "recorded")
        self.assertEqual(added["record_ref"], str(record_path.resolve()))
        record = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(record["schema_version"], "docs-harness/quality-record/v1")
        self.assertEqual(record["task_id"], task_id)
        self.assertEqual(record["trigger_source"], "reported_user_explicit")
        self.assertEqual(record["package_revision"], 1)
        self.assertEqual(record["task_status_at_recording"]["control_status"], "ready_direct")
        self.assertEqual(record["review"]["lessons"], ["先固定个人本地与一次性快照边界。"])
        self.assertNotIn("original_task", record["task_facts"])

        _, exact = self.run_harness(
            "ledger", "read", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(exact["status"], "ok")
        self.assertEqual([item["task_id"] for item in exact["records"]], [task_id])
        _, queried = self.run_harness(
            "ledger", "read", "--target", str(self.project), "--query", "一次性快照", "--limit", "5"
        )
        self.assertEqual([item["task_id"] for item in queried["records"]], [task_id])

    def test_quality_ledger_is_idempotent_and_conflict_never_overwrites(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 `README.md` 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        review = self.quality_review("stable")
        _, first = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", task_id, "--review", str(review)
        )
        record_path = Path(first["record_ref"])
        before = record_path.read_bytes()
        _, repeated = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", task_id, "--review", str(review)
        )
        self.assertEqual(repeated["status"], "already_recorded")
        self.assertFalse(repeated["changed"])
        conflicting = self.quality_review("conflict", {"outcome_summary": "不同的复盘内容。"})
        _, conflict = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", task_id, "--review", str(conflicting), expected=2
        )
        self.assertEqual(conflict["code"], "record_conflict")
        self.assertEqual(record_path.read_bytes(), before)

    def test_quality_ledger_invalid_review_has_zero_writes(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 `README.md` 文档", "--scope", "README.md"
        )
        invalid = self.quality_review("invalid", {"unexpected": "raw tool output"})
        _, blocked = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", routed["task_id"], "--review", str(invalid), expected=2
        )
        self.assertEqual(blocked["code"], "invalid_quality_review")
        self.assertFalse((self.project / ".docs-harness" / "quality-ledger").exists())

    def test_quality_ledger_is_excluded_from_non_git_workspace_snapshot(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 `README.md` 文档", "--scope", "README.md"
        )
        review = self.quality_review("snapshot")
        self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", routed["task_id"], "--review", str(review)
        )
        _, second = self.run_harness(
            "run", "--target", str(self.project), "--task", "再次审查 `README.md` 文档", "--scope", "README.md"
        )
        freeze = json.loads(
            (self.project / ".docs-harness" / "runs" / second["task_id"] / "freeze.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            all(not path.startswith(".docs-harness/quality-ledger/") for path in freeze["workspace_snapshot"])
        )

    def test_quality_ledger_uses_current_recompiled_package_revision(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力"
        )
        task_id = routed["task_id"]
        self.run_harness(
            "context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan"
        )
        plan = self.plan_for({"执行范围": ["src/api/client.py"]})
        self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        review = self.quality_review("revision")
        _, added = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", task_id, "--review", str(review)
        )
        record = json.loads(Path(added["record_ref"]).read_text(encoding="utf-8"))
        self.assertEqual(record["package_revision"], 2)
        self.assertEqual(record["task_facts"]["allowed_scope"], ["src/api/client.py"])
        self.assertIn("architecture-contract", record["task_facts"]["matched_gates"])

    def test_quality_ledger_git_storage_and_purge_runtime_preserve_record(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        (self.project / "README.md").write_text("before\n", encoding="utf-8")
        self.init_project(expected=3)
        self.commit_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 `README.md` 文档", "--scope", "README.md"
        )
        review = self.quality_review("git")
        _, added = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", routed["task_id"], "--review", str(review)
        )
        git_record = self.project / ".git" / "docs-harness" / "quality-ledger" / "records" / f"{routed['task_id']}.json"
        self.assertEqual(added["record_ref"], str(git_record.resolve()))
        self.assertTrue(git_record.is_file())
        self.run_harness(
            "project", "uninstall", "--target", str(self.project), "--apply", "--purge-runtime"
        )
        self.assertFalse((self.project / ".git" / "docs-harness" / "runs").exists())
        self.assertTrue(git_record.is_file())

    def test_quality_ledger_read_reports_corrupt_records(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 `README.md` 文档", "--scope", "README.md"
        )
        review = self.quality_review("corrupt")
        _, added = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", routed["task_id"], "--review", str(review)
        )
        record_path = Path(added["record_ref"])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["review"]["outcome_summary"] = "被篡改但未更新指纹。"
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        _, result = self.run_harness(
            "ledger", "read", "--target", str(self.project), "--task-id", routed["task_id"], expected=1
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["invalid_records"][0]["reason_code"], "invalid_quality_record")

    def test_quality_ledger_rejects_inline_and_obvious_secret_input(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 `README.md` 文档", "--scope", "README.md"
        )
        inline = json.dumps({"schema_version": "docs-harness/quality-review/v1"})
        _, rejected_inline = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", routed["task_id"], "--review", inline, expected=2
        )
        self.assertEqual(rejected_inline["code"], "inline_input_not_supported")
        secret = self.quality_review(
            "secret", {"outcome_summary": "请求包含 Bearer abcdefghijklmnopqrstuvwxyz012345"}
        )
        _, rejected_secret = self.run_harness(
            "ledger", "add", "--target", str(self.project), "--task-id", routed["task_id"], "--review", str(secret), expected=2
        )
        self.assertEqual(rejected_secret["code"], "invalid_quality_review")
        self.assertFalse((self.project / ".docs-harness" / "quality-ledger").exists())

    def test_quality_ledger_managed_entry_is_manual_and_agent_readable(self) -> None:
        self.init_project()
        agents = (self.project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("只有用户明确要求“添加到质量账本”", agents)
        self.assertIn("不得自动记录", agents)
        self.assertIn("ledger add", agents)
        self.assertIn("ledger read", agents)

    def test_quality_ledger_concurrent_add_creates_one_record(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 `README.md` 文档", "--scope", "README.md"
        )
        review = self.quality_review("concurrent")
        command = [
            sys.executable,
            str(HARNESS),
            "ledger",
            "add",
            "--target",
            str(self.project),
            "--task-id",
            routed["task_id"],
            "--review",
            str(review),
            "--json",
        ]
        processes = [
            subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            for _ in range(2)
        ]
        results = [process.communicate(timeout=30) for process in processes]
        payloads = [json.loads(stdout) for stdout, _ in results]
        self.assertEqual(sum(payload.get("status") == "recorded" for payload in payloads), 1)
        for process, payload in zip(processes, payloads):
            if payload.get("status") == "recorded":
                self.assertEqual(process.returncode, 0)
            elif payload.get("status") == "already_recorded":
                self.assertEqual(process.returncode, 0)
            else:
                self.assertEqual(process.returncode, 2)
                self.assertEqual(payload.get("code"), "state_locked")
        records = list(
            (self.project / ".docs-harness" / "quality-ledger" / "records").glob("*.json")
        )
        self.assertEqual(len(records), 1)

    def test_uninstall_preview_and_apply_preserve_project_docs(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 `README.md` 文档", "--scope", "README.md"
        )
        state = self.project / ".docs-harness" / "runs" / routed["task_id"]
        self.assertTrue(state.is_dir())
        _, preview = self.run_harness("project", "uninstall", "--target", str(self.project))
        self.assertEqual(preview["mode"], "preview")
        self.assertTrue((self.project / "scripts" / "harness.py").is_file())
        self.run_harness("project", "uninstall", "--target", str(self.project), "--apply")
        self.assertFalse((self.project / "scripts" / "harness.py").exists())
        self.assertTrue((self.project / "docs" / "features" / "project-core" / "product.md").is_file())
        self.assertTrue(state.is_dir())
        self.assertNotIn("docs-harness:managed-entry:start", (self.project / "AGENTS.md").read_text(encoding="utf-8"))

    def test_v16_contract_ready_bootstrap_blocks_incremental_until_ready(self) -> None:
        installed = self.init_project(bootstrap_knowledge=False)
        bootstrap_id = installed["knowledge_flow"]["job_id"]
        _, verified = self.complete_code_task("src/contract-ready.py")
        job = verified["post_completion"]["dispatch_contract"]
        self.assertEqual(job["status"], "waiting_for_bootstrap_merge")
        self.assertEqual(job["dependency_job_ids"], [bootstrap_id])
        _, rejected = self.run_harness(
            "background", "verify", "--target", str(self.project), "--job-id", job["job_id"], "--result", "no_change", expected=2
        )
        self.assertEqual(rejected["code"], "invalid_background_job_transition")

    def test_v16_failed_bootstrap_blocks_waiter(self) -> None:
        installed = self.init_project(bootstrap_knowledge=False)
        bootstrap_id = installed["knowledge_flow"]["job_id"]
        _, verified = self.complete_code_task("src/waiter.py")
        incremental_id = verified["post_completion"]["job_id"]
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", bootstrap_id, "--job-status", "cancelled"
        )
        _, waiter = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", incremental_id
        )
        self.assertEqual(waiter["status"], "needs_user_input")
        self.assertEqual(waiter["dependency_reason_code"], "bootstrap_dependency_not_ready")

    def test_v16_incremental_no_change_requires_ready_knowledge(self) -> None:
        self.init_project()
        _, verified = self.complete_code_task("src/readiness.py")
        job_id = verified["post_completion"]["job_id"]
        (self.project / "docs" / "knowledge-map.json").unlink()
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched"
        )
        job_contract = json.loads(
            (self.project / ".docs-harness" / "background" / "jobs" / job_id / "job.json").read_text(encoding="utf-8")
        )
        if job_contract["execution_route"] != "background_direct":
            self.write_background_goal_artifacts(job_id)
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running", expected=3
        )
        self.run_harness("background", "retry", "--target", str(self.project), "--job-id", job_id)
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched")
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running")
        _, blocked = self.run_harness(
            "background", "verify", "--target", str(self.project), "--job-id", job_id, "--result", "no_change", expected=3
        )
        self.assertEqual(blocked["status"], "needs_user_input")
        self.assertEqual(blocked["reason_code"], "knowledge_no_change_without_ready_knowledge")

    def test_v16_upgrade_existing_docs_returns_audit_handoff_without_content_write(self) -> None:
        docs = self.project / "docs"
        docs.mkdir()
        existing = docs / "project.md"
        existing.write_text("# 项目事实\n\n用户已有内容。\n", encoding="utf-8")
        before = existing.read_text(encoding="utf-8")
        _, upgraded = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=3
        )
        self.assertEqual(upgraded["status"], "upgraded_knowledge_pending")
        self.assertEqual(upgraded["knowledge_flow"]["mode"], "audit_existing")
        self.assertTrue(upgraded["knowledge_flow"]["requires_user_consent_before_update"])
        self.assertEqual(existing.read_text(encoding="utf-8"), before)
        self.assertIsNone(upgraded["knowledge_flow"]["job_id"])

    def test_v16_upgrade_without_docs_creates_one_bootstrap(self) -> None:
        (self.project / "README.md").write_text("# Legacy\n", encoding="utf-8")
        _, upgraded = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=3
        )
        self.assertEqual(upgraded["knowledge_flow"]["mode"], "bootstrap_new")
        self.assertTrue((self.project / "docs" / "knowledge-map.json").is_file())
        jobs = [job for job in HARNESS_MODULE.list_background_jobs(self.project) if job.get("task_kind") == "knowledge_bootstrap"]
        self.assertEqual(len(jobs), 1)

    def test_v16_intent_time_and_path_boundaries(self) -> None:
        self.init_project()
        _, deferred = self.run_harness(
            "run", "--target", str(self.project), "--task", "本次只排查，后面另开任务实现"
        )
        self.assertEqual(deferred["mutation_profile"], "read_only")
        self.assertEqual(deferred["deferred_intents"], [{"intent": "modify", "mutation_profile": "workspace_write"}])
        self.assertIn("future_clause_deferred", deferred["intent_boundary_reason_codes"])
        _, review = self.run_harness(
            "run", "--target", str(self.project), "--task", "只读审查 `docs/reviews/x.md`", "--scope", "docs/reviews/x.md"
        )
        self.assertNotIn("frontend-design", review["matched_gates"])
        self.assertNotIn("code-edit", review["matched_gates"])
        facts = self.write_json("boundary-write.json", {"write_scope": ["src/views/Home.tsx"]})
        _, frontend = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整当前页面", "--facts", str(facts)
        )
        self.assertIn("frontend-design", frontend["matched_gates"])
        self.assertNotIn("security-sensitive", HARNESS_MODULE.infer_gates_from_paths(["src/authors/latest.ts"], mutation_profile="workspace_write"))
        self.assertNotIn("architecture-contract", HARNESS_MODULE.infer_gates_from_paths(["src/rapid/latest.ts"], mutation_profile="workspace_write"))
        self.assertNotIn("code-edit", HARNESS_MODULE.infer_gates("使用 Claude Code 审查方案", mutation_profile="read_only"))

    def test_v16_inventory_filters_runtime_generated_and_binary_assets(self) -> None:
        self.project.joinpath("src").mkdir()
        self.project.joinpath("src", "main.py").write_text("VALUE = 1\n", encoding="utf-8")
        for relative in (".playwright-cli/state.json", "zbuddy-output/run.log", "dist/app.js", "slides/demo.pptx"):
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture")
        inventory, summary, _ = HARNESS_MODULE.knowledge_scan_inventory_details(self.project)
        self.assertIn("src/main.py", inventory)
        self.assertNotIn(".playwright-cli/state.json", inventory)
        self.assertNotIn("zbuddy-output/run.log", inventory)
        self.assertNotIn("dist/app.js", inventory)
        self.assertNotIn("slides/demo.pptx", inventory)
        self.assertTrue(summary)

    def test_v16_candidate_ready_claim_is_recomputed_before_map_write(self) -> None:
        installed = self.init_project(bootstrap_knowledge=False)
        job_id = installed["knowledge_flow"]["job_id"]
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "dispatched")
        self.run_harness("background", "dispatch", "--target", str(self.project), "--job-id", job_id, "--job-status", "running")
        feature_root = self.project / "docs" / "features" / "project-core"
        feature_root.mkdir(parents=True)
        documents = {}
        for category in ("product", "development", "testing", "design"):
            relative = f"docs/features/project-core/{category}.md"
            documents[category] = relative
            (self.project / relative).write_text(f"# {category}\n\n待确认。\n", encoding="utf-8")
        assessment = self.write_json(
            "false-ready.json",
            {
                "schema_version": "docs-harness/knowledge-assessment/v1",
                "status": "ready",
                "reviewed_revision": "claim-only",
                "features": [{
                    "feature_id": "project-core", "name": "项目核心", "aliases": [],
                    "feature_type": "internal_capability", "status": "implemented",
                    "scope_patterns": ["src/**"], "documents": documents, "shared_refs": [],
                    "dependencies": [], "known_gaps": [],
                }],
                "gaps": [],
            },
        )
        _, blocked = self.run_harness(
            "background", "verify", "--target", str(self.project), "--job-id", job_id, "--assessment", str(assessment), expected=3
        )
        self.assertEqual(blocked["reason_code"], "candidate_knowledge_not_ready")
        self.assertFalse((self.project / "docs" / "knowledge-map.json").read_text(encoding="utf-8").find("project-core") >= 0)

    def test_v16_unknown_bootstrap_outcome_fails_closed(self) -> None:
        self.init_project(bootstrap_knowledge=False)
        outcome = HARNESS_MODULE.knowledge_dependency_outcome({"status": "future_terminal"}, self.project)
        self.assertEqual(outcome, "unknown")

    def test_v16_background_v1_status_is_read_only_and_upgrade_migrates(self) -> None:
        installed = self.init_project()
        job_id = installed["knowledge_flow"]["job_id"]
        path = self.project / ".docs-harness" / "background" / "jobs" / job_id / "job.json"
        legacy = json.loads(path.read_text(encoding="utf-8"))
        legacy["schema_version"] = "docs-harness/background-job/v1"
        legacy.pop("may_spawn_child_jobs", None)
        path.write_text(json.dumps(legacy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before = path.read_bytes()
        _, status = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", job_id
        )
        self.assertEqual(status["schema_version"], "docs-harness/background-job/v2")
        self.assertEqual(path.read_bytes(), before)
        _, upgraded = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply"
        )
        self.assertIn(job_id, upgraded["migrated_background_job_ids"])
        migrated = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["schema_version"], "docs-harness/background-job/v2")
        self.assertFalse(migrated["may_spawn_child_jobs"])

    def test_v162_document_route_resolution_explicit_unique_and_ambiguous(self) -> None:
        self.init_project()
        contract = HARNESS_MODULE.resolve_document_routes(
            self.project, required_kinds=("changelog", "todo", "adr_root", "reviews_root")
        )
        self.assertEqual(contract["status"], "resolved")
        self.assertEqual(contract["routes"]["changelog"]["path"], "CHANGELOG.md")
        self.assertEqual(contract["routes"]["changelog"]["source"], "auto")

        (self.project / "docs" / "changelog.md").write_text("# Docs Changelog\n", encoding="utf-8")
        ambiguous = HARNESS_MODULE.resolve_document_routes(self.project, required_kinds=("changelog",))
        self.assertEqual(ambiguous["status"], "unresolved")
        self.assertEqual(ambiguous["reason_code"], "document_route_ambiguous")

        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["background_governance"]["document_routes"] = {"changelog": "docs/changelog.md"}
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        explicit = HARNESS_MODULE.resolve_document_routes(self.project, required_kinds=("changelog",))
        self.assertEqual(explicit["status"], "resolved")
        self.assertEqual(explicit["routes"]["changelog"], {
            "path": "docs/changelog.md", "source": "explicit", "type": "file",
        })

    def test_v162_document_route_invalid_and_symlink_fail_closed(self) -> None:
        self.init_project()
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["background_governance"]["document_routes"] = {"changelog": "../outside.md"}
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        invalid = HARNESS_MODULE.resolve_document_routes(self.project, required_kinds=("changelog",))
        self.assertEqual(invalid["status"], "invalid_config")
        self.assertEqual(invalid["reason_code"], "invalid_document_route_config")

        config["background_governance"].pop("document_routes")
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (self.project / "CHANGELOG.md").unlink()
        outside = self.temp_root / "outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")
        try:
            (self.project / "docs" / "changelog.md").symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"当前环境不允许创建符号链接(Windows 需要开发者模式或管理员权限): {exc}")
        unsafe = HARNESS_MODULE.resolve_document_routes(self.project, required_kinds=("changelog",))
        self.assertEqual(unsafe["status"], "unresolved")
        self.assertIn("document_route_unsafe", [item["reason_code"] for item in unsafe["errors"]])

    def test_v162_unresolved_governance_job_is_zero_write_idempotent_and_retryable(self) -> None:
        self.init_project()
        (self.project / "docs" / "todo.md").unlink()
        package = {
            "task_id": "dh-20260804T000000-aaaaaaaaaa",
            "background_deliverables": [{"deliverable": "adr_changelog_todo_review"}],
            "allowed_scope": ["src/**"],
            "knowledge_context": {"selected_features": []},
        }
        first = HARNESS_MODULE.create_post_completion_governance_job(self.project, package, ["src/a.py"])
        second = HARNESS_MODULE.create_post_completion_governance_job(self.project, package, ["src/a.py"])
        assert first and second
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(first["status"], "needs_user_input")
        self.assertEqual(first["allowed_write_scope"], [])
        self.assertIsNone(first["route_contract_fingerprint"])

        (self.project / "docs" / "todo.md").write_text("# TODO\n", encoding="utf-8")
        _, retried = self.run_harness(
            "background", "retry", "--target", str(self.project), "--job-id", first["job_id"]
        )
        self.assertEqual(retried["status"], "contract_ready")
        _, status = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", first["job_id"]
        )
        self.assertEqual(status["document_route_contract"]["status"], "resolved")
        self.assertEqual(set(status["allowed_write_scope"]), {
            "CHANGELOG.md", "docs/todo.md", "docs/adr/**", "docs/reviews/**",
        })
        self.assertIn("document-kind-changelog", HARNESS_MODULE.background_lock_names(status))

    def test_v162_legacy_governance_job_requires_cancel_then_route_repair(self) -> None:
        self.init_project()
        package = {
            "task_id": "dh-20260804T000000-bbbbbbbbbb",
            "background_deliverables": [{"deliverable": "adr_changelog_todo_review"}],
            "allowed_scope": ["src/**"],
            "knowledge_context": {"selected_features": []},
        }
        job = HARNESS_MODULE.create_post_completion_governance_job(self.project, package, ["src/b.py"])
        assert job
        root = self.project / ".docs-harness" / "background" / "jobs" / job["job_id"]
        legacy = json.loads((root / "job.json").read_text(encoding="utf-8"))
        legacy.pop("document_route_contract")
        legacy.pop("route_contract_fingerprint")
        (root / "job.json").write_text(json.dumps(legacy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _, blocked = self.run_harness(
            "background", "prepare", "--target", str(self.project), "--job-id", job["job_id"], expected=3
        )
        self.assertEqual(blocked["code"], "legacy_governance_route_contract")
        _, not_quiet = self.run_harness(
            "background", "retry", "--target", str(self.project), "--job-id", job["job_id"], expected=3
        )
        self.assertEqual(not_quiet["code"], "legacy_governance_job_not_quiesced")
        self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job["job_id"], "--job-status", "cancelled"
        )
        _, repaired = self.run_harness(
            "background", "retry", "--target", str(self.project), "--job-id", job["job_id"]
        )
        self.assertEqual(repaired["status"], "contract_ready")
        _, current = self.run_harness(
            "background", "status", "--target", str(self.project), "--job-id", job["job_id"]
        )
        self.assertEqual(current["attempt"], 2)
        self.assertEqual(current["max_attempts"], HARNESS_MODULE.BACKGROUND_MAX_ATTEMPTS + 1)

    def test_v162_route_drift_blocks_dispatch(self) -> None:
        self.init_project()
        package = {
            "task_id": "dh-20260804T000000-cccccccccc",
            "background_deliverables": [{"deliverable": "adr_changelog_todo_review"}],
            "allowed_scope": ["src/**"],
            "knowledge_context": {"selected_features": []},
        }
        job = HARNESS_MODULE.create_post_completion_governance_job(self.project, package, ["src/c.py"])
        assert job
        (self.project / "CHANGELOG.md").unlink()
        (self.project / "docs" / "changelog.md").write_text("# Changed route\n", encoding="utf-8")
        _, drift = self.run_harness(
            "background", "dispatch", "--target", str(self.project), "--job-id", job["job_id"],
            "--job-status", "running", expected=3,
        )
        self.assertEqual(drift["reason_code"], "document_route_drift")
        self.assertEqual(drift["status"], "needs_rebase")

    def test_v162_parent_completion_survives_route_block_and_returns_action_required(self) -> None:
        self.init_project()
        (self.project / "docs" / "todo.md").unlink()
        _, verified = self.complete_code_task("src/route-block.py")
        self.assertEqual(verified["control_status"], "complete")
        self.assertEqual(verified["post_completion"]["status"], "action_required")
        self.assertEqual(verified["post_completion"]["reason_code"], "document_route_missing")
        governance = next(
            item for item in verified["background_jobs"]
            if item["task_kind"] == "delivery_governance"
        )
        self.assertEqual(governance["status"], "needs_user_input")
        self.assertEqual(governance["allowed_write_scope"], [])

    def test_v162_project_upgrade_preserves_valid_routes_and_rejects_invalid_routes(self) -> None:
        self.init_project()
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        routes = {
            "changelog": "CHANGELOG.md", "todo": "docs/todo.md",
            "adr_root": "docs/adr", "reviews_root": "docs/reviews",
        }
        config["background_governance"]["document_routes"] = routes
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # 让安装指纹与当前控制器一致，验证 preserve-and-merge 本身。
        config["installed_script_fingerprint"] = HARNESS_MODULE.file_fingerprint(ROOT / "scripts" / "harness.py")
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _, upgraded = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=None
        )
        self.assertNotEqual(upgraded.get("status"), "failed")
        preserved = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(preserved["background_governance"]["document_routes"], routes)

        preserved["background_governance"]["document_routes"] = {"changelog": "../outside.md"}
        config_path.write_text(json.dumps(preserved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _, preview = self.run_harness(
            "project", "upgrade", "--target", str(self.project), expected=0
        )
        self.assertFalse(preview["apply_completion_possible"])
        self.assertIn("invalid_document_route_config", [item.get("reason_code") for item in preview["manual_migrations"]])
        _, rejected = self.run_harness(
            "project", "upgrade", "--target", str(self.project), "--apply", expected=3
        )
        self.assertEqual(rejected["code"], "invalid_document_route_config")

    def test_v162_all_route_kinds_and_missing_candidate_contract(self) -> None:
        self.init_project()
        (self.project / "docs" / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
        complete = HARNESS_MODULE.resolve_document_routes(
            self.project, required_kinds=HARNESS_MODULE.DOCUMENT_ROUTE_KINDS
        )
        self.assertEqual(complete["status"], "resolved")
        self.assertEqual(complete["routes"]["architecture"]["type"], "file")
        (self.project / "docs" / "architecture.md").unlink()
        missing = HARNESS_MODULE.resolve_document_routes(self.project, required_kinds=("architecture",))
        self.assertEqual(missing["status"], "unresolved")
        self.assertEqual(missing["reason_code"], "document_route_missing")

    def downgrade_task_to_v1(self, task_id: str) -> Path:
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        for key in (
            "task_intent", "candidate_intents", "mutation_profile", "read_scope", "write_scope",
            "git_scope", "external_scope", "git_operation", "git_state_snapshot", "git_sync_scope",
            "completion_manifest",
        ):
            package.pop(key, None)
        package["schema_version"] = "docs-harness/task-package/v1"
        package["package_revision"] = 1
        fingerprint = HARNESS_MODULE.package_fingerprint(package)
        compiled = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        compiled.update({"schema_version": "docs-harness/compiled-task/v1", "package_revision": 1, "package_fingerprint": fingerprint})
        freeze = json.loads((state / "freeze.json").read_text(encoding="utf-8"))
        freeze.update({"schema_version": "docs-harness/freeze/v1", "package_revision": 1, "package_fingerprint": fingerprint})
        (state / "task-package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        (state / "compiled-task.json").write_text(json.dumps(compiled, ensure_ascii=False, indent=2), encoding="utf-8")
        (state / "freeze.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def complete_query_task(self, task_text: str = "查询项目文档在哪") -> tuple[dict[str, Any], dict[str, Any]]:
        _, routed = self.run_harness("run", "--target", str(self.project), "--task", task_text)
        task_id = routed["task_id"]
        source = self.project / "docs" / "INDEX.md"
        evidence = self.evidence(
            f"query-{task_id}",
            evidence_type="source_trace",
            covers=task_id,
            changed_paths=[],
            read_set=[{"path": "docs/INDEX.md", "fingerprint": HARNESS_MODULE.file_fingerprint(source)}],
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        return routed, verified

    def test_v17_task_cancel_is_preview_first_idempotent_and_conflicting(self) -> None:
        self.init_project()
        _, routed = self.run_harness("run", "--target", str(self.project), "--task", "查询项目文档在哪")
        task_id = routed["task_id"]
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        tracked = ("task-package.json", "freeze.json", "compiled-task.json")
        before = {name: HARNESS_MODULE.file_fingerprint(state / name) for name in tracked}

        _, invalid = self.run_harness(
            "task", "cancel", "--target", str(self.project), "--task-id", task_id,
            "--reason-code", "not_a_reason", expected=2,
        )
        self.assertEqual(invalid["code"], "invalid_cancel_reason")

        _, preview = self.run_harness(
            "task", "cancel", "--target", str(self.project), "--task-id", task_id, "--reason-code", "operator_abandoned"
        )
        self.assertEqual(preview["mode"], "preview")
        self.assertEqual(preview["previous_status"], "ready_direct")
        self.assertEqual(preview["new_status"], "cancelled")
        self.assertFalse(preview["idempotent"])
        self.assertEqual(before, {name: HARNESS_MODULE.file_fingerprint(state / name) for name in tracked})

        _, applied = self.run_harness(
            "task", "cancel", "--target", str(self.project), "--task-id", task_id,
            "--reason-code", "operator_abandoned", "--apply",
        )
        self.assertEqual(applied["mode"], "apply")
        self.assertEqual(applied["previous_status"], "ready_direct")
        self.assertEqual(applied["new_status"], "cancelled")
        self.assertEqual(applied["reason_code"], "operator_abandoned")
        compiled = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        self.assertEqual(compiled["control_status"], "cancelled")
        self.assertEqual(compiled["next_action"], "none")
        self.assertEqual(compiled["cancellation_reason_code"], "operator_abandoned")
        self.assertTrue(compiled["cancelled_at"])
        self.assertEqual(before["task-package.json"], HARNESS_MODULE.file_fingerprint(state / "task-package.json"))
        self.assertEqual(before["freeze.json"], HARNESS_MODULE.file_fingerprint(state / "freeze.json"))
        events = HARNESS_MODULE.read_jsonl(state / "events.jsonl")
        cancel_events = [item for item in events if item.get("event") == "task_cancelled"]
        self.assertEqual(len(cancel_events), 1)
        self.assertEqual(cancel_events[0]["reason_code"], "operator_abandoned")

        _, again = self.run_harness(
            "task", "cancel", "--target", str(self.project), "--task-id", task_id,
            "--reason-code", "operator_abandoned", "--apply",
        )
        self.assertTrue(again["idempotent"])
        self.assertEqual(again["previous_status"], applied["previous_status"])
        self.assertEqual(again["task_fingerprint"], applied["task_fingerprint"])
        events = HARNESS_MODULE.read_jsonl(state / "events.jsonl")
        self.assertEqual(sum(item.get("event") == "task_cancelled" for item in events), 1)

        _, conflict = self.run_harness(
            "task", "cancel", "--target", str(self.project), "--task-id", task_id,
            "--reason-code", "duplicate", "--apply", expected=2,
        )
        self.assertEqual(conflict["code"], "task_cancel_conflict")
        compiled = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        self.assertEqual(compiled["cancellation_reason_code"], "operator_abandoned")

        _, allowed = self.run_harness("project", "rollback-check", "--target", str(self.project))
        self.assertTrue(allowed["rollback_allowed"])

    def test_v17_task_cancel_protects_terminal_locked_and_legacy_tasks(self) -> None:
        self.init_project()
        routed, _ = self.complete_code_task("src/cancel-terminal.py")
        _, terminal = self.run_harness(
            "task", "cancel", "--target", str(self.project), "--task-id", routed["task_id"],
            "--reason-code", "superseded", "--apply", expected=2,
        )
        self.assertEqual(terminal["code"], "task_already_terminal")

        _, routed = self.run_harness("run", "--target", str(self.project), "--task", "查询项目文档在哪")
        state = HARNESS_MODULE.task_state_dir(self.project, routed["task_id"])
        (state / ".lock").write_text("pid=0\n", encoding="utf-8")
        _, locked = self.run_harness(
            "task", "cancel", "--target", str(self.project), "--task-id", routed["task_id"],
            "--reason-code", "operator_abandoned", expected=2,
        )
        self.assertEqual(locked["code"], "state_locked")
        (state / ".lock").unlink()

        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "列出项目功能文档", "--new-task"
        )
        self.downgrade_task_to_v1(routed["task_id"])
        _, legacy = self.run_harness(
            "task", "cancel", "--target", str(self.project), "--task-id", routed["task_id"],
            "--reason-code", "superseded", expected=2,
        )
        self.assertEqual(legacy["code"], "legacy_task_not_cancellable")

    def test_v17_v1_archive_is_read_only_indexed_and_drift_fails_closed(self) -> None:
        self.init_project()
        _, routed = self.run_harness("run", "--target", str(self.project), "--task", "查询项目文档在哪")
        task_id = routed["task_id"]
        state = self.downgrade_task_to_v1(task_id)
        before = self.snapshot_tree(state)
        index_path = HARNESS_MODULE.runtime_root(self.project) / "task-dispositions.json"

        _, preview = self.run_harness(
            "task", "archive", "--target", str(self.project), "--task-id", task_id, "--reason-code", "superseded"
        )
        self.assertEqual(preview["mode"], "preview")
        self.assertEqual(preview["disposition"], "archived")
        self.assertEqual(self.snapshot_tree(state), before)
        self.assertFalse(index_path.exists())

        _, applied = self.run_harness(
            "task", "archive", "--target", str(self.project), "--task-id", task_id,
            "--reason-code", "superseded", "--apply",
        )
        self.assertEqual(applied["mode"], "apply")
        self.assertEqual(applied["disposition"], "archived")
        self.assertEqual(applied["source_object_fingerprint"], HARNESS_MODULE.file_fingerprint(state / "task-package.json"))
        self.assertEqual(self.snapshot_tree(state), before)

        _, again = self.run_harness(
            "task", "archive", "--target", str(self.project), "--task-id", task_id,
            "--reason-code", "superseded", "--apply",
        )
        self.assertTrue(again["idempotent"])
        _, conflict = self.run_harness(
            "task", "archive", "--target", str(self.project), "--task-id", task_id,
            "--reason-code", "duplicate", "--apply", expected=2,
        )
        self.assertEqual(conflict["code"], "task_archive_conflict")

        _, routed = self.run_harness("run", "--target", str(self.project), "--task", "列出项目功能文档")
        _, rejected = self.run_harness(
            "task", "archive", "--target", str(self.project), "--task-id", routed["task_id"],
            "--reason-code", "superseded", expected=2,
        )
        self.assertEqual(rejected["code"], "invalid_archive_target")

        _, listing = self.run_harness("task", "list", "--target", str(self.project))
        self.assertNotIn(task_id, [item["task_id"] for item in listing["tasks"]])
        self.assertEqual(listing["archived_count"], 1)
        _, full = self.run_harness("task", "list", "--target", str(self.project), "--include-archived")
        entry = next(item for item in full["tasks"] if item["task_id"] == task_id)
        self.assertEqual(entry["disposition"], "archived")

        package_path = state / "task-package.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        package["original_task"] = "被改写的历史任务"
        package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        _, drifted = self.run_harness("task", "list", "--target", str(self.project), expected=1)
        self.assertEqual(drifted["code"], "archive_source_drift")

    def test_v17_task_prune_freezes_candidates_and_rechecks_fingerprints(self) -> None:
        self.init_project()
        completed_routed, _ = self.complete_query_task()
        completed_id = completed_routed["task_id"]
        _, routed = self.run_harness("run", "--target", str(self.project), "--task", "列出项目功能文档")
        cancelled_id = routed["task_id"]
        self.run_harness(
            "task", "cancel", "--target", str(self.project), "--task-id", cancelled_id,
            "--reason-code", "operator_abandoned", "--apply",
        )
        _, active = self.run_harness(
            "run", "--target", str(self.project), "--task", "修复项目核心模块代码", "--scope", "src/active.py"
        )
        active_id = active["task_id"]

        _, combo = self.run_harness(
            "task", "prune", "--target", str(self.project), "--older-than", "0",
            "--dry-run", "--apply", expected=2,
        )
        self.assertEqual(combo["code"], "invalid_prune_request")
        _, retained = self.run_harness(
            "task", "prune", "--target", str(self.project), "--older-than", "30", "--dry-run"
        )
        self.assertEqual(retained["candidates"], [])

        _, preview = self.run_harness(
            "task", "prune", "--target", str(self.project), "--older-than", "0", "--dry-run"
        )
        self.assertEqual(preview["mode"], "dry_run")
        candidate_ids = [item["task_id"] for item in preview["candidates"]]
        self.assertIn(completed_id, candidate_ids)
        self.assertIn(cancelled_id, candidate_ids)
        self.assertNotIn(active_id, candidate_ids)
        self.assertTrue(all(item["state_fingerprint"].startswith("sha256:") for item in preview["candidates"]))
        self.assertTrue(HARNESS_MODULE.task_state_dir(self.project, completed_id).is_dir())

        tampered = HARNESS_MODULE.task_state_dir(self.project, cancelled_id) / "post-preview-note.txt"
        tampered.write_text("候选冻结后写入\n", encoding="utf-8")
        _, applied = self.run_harness(
            "task", "prune", "--target", str(self.project), "--older-than", "0", "--apply"
        )
        self.assertIn(completed_id, applied["removed"])
        self.assertNotIn(cancelled_id, applied["removed"])
        self.assertFalse(HARNESS_MODULE.task_state_dir(self.project, completed_id).exists())
        self.assertTrue(HARNESS_MODULE.task_state_dir(self.project, cancelled_id).is_dir())
        self.assertTrue(HARNESS_MODULE.task_state_dir(self.project, active_id).is_dir())

    def test_v17_task_prune_blocks_on_open_child_jobs_and_findings(self) -> None:
        self.init_project()
        routed, verified = self.complete_code_task("src/prune-guard.py")
        task_id = routed["task_id"]

        _, preview = self.run_harness(
            "task", "prune", "--target", str(self.project), "--older-than", "0", "--dry-run"
        )
        self.assertNotIn(task_id, [item["task_id"] for item in preview["candidates"]])

        job_paths = {
            job["job_id"]: HARNESS_MODULE.read_knowledge_job(self.project, job["job_id"])[0] / "job.json"
            for job in verified["background_jobs"]
        }

        def set_job_status(job_id: str, status: str) -> None:
            path = job_paths[job_id]
            value = json.loads(path.read_text(encoding="utf-8"))
            value["status"] = status
            value["updated_at"] = HARNESS_MODULE.utc_now()
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        for job_id in job_paths:
            set_job_status(job_id, "no_change")
        _, preview = self.run_harness(
            "task", "prune", "--target", str(self.project), "--older-than", "0", "--dry-run"
        )
        self.assertIn(task_id, [item["task_id"] for item in preview["candidates"]])

        first_job = sorted(job_paths)[0]
        set_job_status(first_job, "completed_with_finding")
        _, preview = self.run_harness(
            "task", "prune", "--target", str(self.project), "--older-than", "0", "--dry-run"
        )
        self.assertNotIn(task_id, [item["task_id"] for item in preview["candidates"]])

        set_job_status(first_job, "running")
        _, preview = self.run_harness(
            "task", "prune", "--target", str(self.project), "--older-than", "0", "--dry-run"
        )
        self.assertNotIn(task_id, [item["task_id"] for item in preview["candidates"]])

    def git_sync_task(self, name: str) -> str:
        remote = self.temp_root / "remote.git"
        if not (self.project / ".git").is_dir():
            remote = self.init_git_remote()
        other = self.temp_root / name
        subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        (other / "synced.txt").write_text(f"from remote {name}\n", encoding="utf-8")
        subprocess.run(["git", "add", "synced.txt"], cwd=other, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Remote Test", "-c", "user.email=remote@example.invalid", "commit", "-q", "-m", "sync target"],
            cwd=other,
            check=True,
        )
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=other, check=True)
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        facts = self.write_json(
            f"{name}-facts.json",
            {"git_scope": [".git:refs/remotes/origin/main"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "执行 git pull 同步远端", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for()
        self.run_harness("run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan))
        subprocess.run(["git", "merge", "--ff-only", "origin/main"], cwd=self.project, check=True, capture_output=True)
        return task_id

    def test_v17_delivery_layers_distinguish_applicability_and_verification(self) -> None:
        self.init_project()
        _, query_verified = self.complete_query_task()
        layers = query_verified["delivery_layers"]
        self.assertEqual(layers["remote_delivery"]["expectation"], "not_applicable")
        self.assertEqual(layers["fresh_clone"]["expectation"], "not_applicable")
        self.assertEqual(layers["local_verification"]["expectation"], "not_applicable")
        self.assertEqual(query_verified["acceptance_layers"], ["source"])
        self.assertEqual(query_verified["known_limit_codes"], [])

        _, modified = self.complete_code_task("src/layers.py")
        layers = modified["delivery_layers"]
        self.assertEqual(layers["remote_delivery"]["expectation"], "not_requested")
        self.assertEqual(layers["fresh_clone"]["expectation"], "not_requested")
        self.assertEqual(layers["local_verification"]["status"], "verified")
        self.assertEqual(modified["acceptance_layers"], ["source", "local_verification"])
        self.assertEqual(modified["known_limit_codes"], [])

        task_id = self.git_sync_task("sync-unverified")
        _, verified = self.run_harness("verify", "--target", str(self.project), "--task-id", task_id)
        layers = verified["delivery_layers"]
        self.assertEqual(layers["remote_delivery"], {"expectation": "required", "status": "not_verified", "evidence_refs": []})
        self.assertEqual(layers["git_head"]["status"], "verified")
        self.assertIn("remote_delivery_not_verified", verified["known_limit_codes"])
        self.assertIn("git_head", verified["acceptance_layers"])
        self.assertNotIn("remote_delivery", verified["acceptance_layers"])

        task_id = self.git_sync_task("sync-verified")
        proof = self.evidence(
            "remote-delivery-proof",
            evidence_type="remote_delivery",
            covers=task_id,
            changed_paths=["synced.txt"],
            producer={"adapter": "codex-host", "capability": "command_receipt"},
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(proof)
        )
        layers = verified["delivery_layers"]
        self.assertEqual(layers["remote_delivery"]["expectation"], "required")
        self.assertEqual(layers["remote_delivery"]["status"], "not_verified")
        self.assertEqual(layers["remote_delivery"]["evidence_refs"], [])
        self.assertIn("remote_delivery_not_verified", verified["known_limit_codes"])
        self.assertNotIn("remote_delivery", verified["acceptance_layers"])

    def disable_auto_attribution(self) -> None:
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config.setdefault("verification", {})["auto_attribute_in_scope"] = False
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    def push_remote_commit(self, clone_name: str, relative: str, content: str) -> None:
        remote = self.temp_root / "remote.git"
        other = self.temp_root / clone_name
        if not other.is_dir():
            subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        (other / relative).write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", relative], cwd=other, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Remote Test", "-c", "user.email=remote@example.invalid", "commit", "-q", "-m", f"remote {relative}"],
            cwd=other,
            check=True,
        )
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=other, check=True)

    def test_auto_attribution_only_proves_write_ownership(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整 src/settings.json 的默认阈值", "--scope", "src/settings.json"
        )
        task_id = routed["task_id"]
        (self.project / "src").mkdir(exist_ok=True)
        (self.project / "src" / "settings.json").write_text('{"threshold": 1}\n', encoding="utf-8")
        _, pending_review = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        self.assertEqual(pending_review["missing_evidence_types"], ["change_review"])
        self.assertEqual(pending_review["auto_attributed_paths"], ["src/settings.json"])
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        index = json.loads((state / "evidence-index.json").read_text(encoding="utf-8"))
        attributed = [item for item in index["evidence"] if item.get("type") == "workspace_attribution"]
        self.assertEqual(len(attributed), 1)
        self.assertEqual(attributed[0]["producer"], {"adapter": "docs-harness", "capability": "auto_attribution"})
        self.assertEqual(attributed[0]["write_set"], ["src/settings.json"])
        auto_events = [
            item
            for item in HARNESS_MODULE.read_jsonl(state / "events.jsonl")
            if item.get("event") == "auto_attribution"
        ]
        self.assertEqual(len(auto_events), 1)
        self.assertEqual(auto_events[0]["paths"], ["src/settings.json"])

        review = self.write_json(
            "settings-change-review.json",
            {
                "schema_version": "docs-harness/evidence-declaration/v1",
                "type": "change_review",
                "write_set": ["src/settings.json"],
                "conclusion": "变更内容与任务目标一致",
            },
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(review)
        )
        self.assertEqual(verified["result"], "完成")

        self.disable_auto_attribution()
        _, routed_off = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整 src/limits.json 的默认阈值", "--scope", "src/limits.json"
        )
        task_id_off = routed_off["task_id"]
        (self.project / "src" / "limits.json").write_text('{"limit": 2}\n', encoding="utf-8")
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id_off, expected=3
        )
        self.assertEqual(pending["reason_code"], "unattributed_drift_overlap")
        self.assertEqual(pending["missing_attribution_paths"], ["src/limits.json"])
        self.assertEqual(pending["auto_attributed_paths"], [])
        self.assertEqual([item["action"] for item in pending["recovery_actions"]], ["provide_evidence"])

    def test_evidence_declaration_draft_is_minted_by_controller(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心 `src/core.py` 代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        path = self.project / "src" / "core.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = 1\n", encoding="utf-8")
        draft = self.write_json(
            "declaration-draft.json",
            {
                "schema_version": "docs-harness/evidence-declaration/v1",
                "type": "test_result",
                "write_set": ["src/core.py"],
                "conclusion": "验收通过",
            },
        )
        change_review = self.write_json(
            "declaration-change-review.json",
            {
                "schema_version": "docs-harness/evidence-declaration/v1",
                "type": "change_review",
                "write_set": ["src/core.py"],
                "conclusion": "代码变更与任务意图一致",
            },
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id,
            "--evidence", str(draft), "--evidence", str(change_review),
        )
        self.assertEqual(verified["result"], "完成")
        self.assertIn("test_result", verified["evidence_types"])
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        index = json.loads((state / "evidence-index.json").read_text(encoding="utf-8"))
        minted = [item for item in index["evidence"] if item.get("type") == "test_result"]
        self.assertEqual(len(minted), 1)
        self.assertEqual(minted[0]["producer"], {"adapter": "docs-harness", "capability": "host_declaration"})
        self.assertEqual(minted[0]["trust_level"], "reported")
        self.assertEqual(minted[0]["ingress_trust"], "host_reported")

        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        missing_type = self.write_json(
            "declaration-no-type.json",
            {"schema_version": "docs-harness/evidence-declaration/v1", "write_set": ["src/core.py"]},
        )
        with self.assertRaises(HARNESS_MODULE.HarnessError) as raised:
            HARNESS_MODULE.load_evidence(str(missing_type), expected_cover=task_id, package=package, target=self.project)
        self.assertEqual(raised.exception.code, "invalid_evidence")
        unknown_type = self.write_json(
            "declaration-unknown-type.json",
            {"schema_version": "docs-harness/evidence-declaration/v1", "type": "made_up_type", "write_set": ["src/core.py"]},
        )
        with self.assertRaises(HARNESS_MODULE.HarnessError) as raised:
            HARNESS_MODULE.load_evidence(str(unknown_type), expected_cover=task_id, package=package, target=self.project)
        self.assertEqual(raised.exception.code, "invalid_evidence_type")
        escaped_write_set = self.write_json(
            "declaration-escaped.json",
            {"schema_version": "docs-harness/evidence-declaration/v1", "type": "test_result", "write_set": ["../escape.txt"]},
        )
        with self.assertRaises(HARNESS_MODULE.HarnessError) as raised:
            HARNESS_MODULE.load_evidence(str(escaped_write_set), expected_cover=task_id, package=package, target=self.project)
        self.assertEqual(raised.exception.code, "invalid_scope")
        high_risk = self.write_json(
            "declaration-high-risk.json",
            {"schema_version": "docs-harness/evidence-declaration/v1", "type": "security_acceptance", "write_set": ["src/core.py"]},
        )
        _, minted_high_risk = HARNESS_MODULE.load_evidence(
            str(high_risk), expected_cover=task_id, package=package, target=self.project
        )
        self.assertEqual(minted_high_risk["trust_level"], "reported")
        self.assertEqual(minted_high_risk["ingress_trust"], "host_reported")
        self.assertEqual(minted_high_risk["producer"], {"adapter": "docs-harness", "capability": "host_declaration"})

        _, verified_v2 = self.complete_code_task("src/legacy.py")
        self.assertEqual(verified_v2["result"], "完成")

    def test_git_sync_drift_landed_readmission_completes_without_evidence(self) -> None:
        self.init_project()
        self.init_git_remote()
        self.push_remote_commit("drift-source", "synced.txt", "from remote\n")
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        facts = self.write_json("git-sync-landed.json", {"git_scope": [".git:refs/remotes/origin/main"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "执行 git pull 同步远端", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for()
        self.run_harness("run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan))
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        compiled_before = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        self.assertTrue(compiled_before["plan_fingerprint"])

        self.push_remote_commit("drift-source", "drifted.txt", "remote drift\n")
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        subprocess.run(["git", "merge", "--ff-only", "origin/main"], cwd=self.project, check=True, capture_output=True)
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=4
        )
        self.assertEqual(blocked["reason_code"], "git_remote_drift")

        _, readmitted = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(readmitted["admission_status"], "ready_planned")
        compiled_after = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        self.assertEqual(compiled_after["plan_fingerprint"], compiled_before["plan_fingerprint"])
        package_after = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertEqual(package_after["git_sync_landed_scope"], ["drifted.txt", "synced.txt"])
        self.assertEqual(package_after["write_scope"], ["drifted.txt", "synced.txt"])

        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(verified["result"], "完成")
        self.assertEqual(verified["changed_paths"], ["drifted.txt", "synced.txt"])
        self.assertEqual(verified["auto_attributed_paths"], [])
        self.assertEqual(verified["workspace_attribution"]["blockers"], [])
        self.assertTrue(verified["git_postcheck"]["passed"])

    def test_git_sync_drift_stray_write_still_blocked(self) -> None:
        self.init_project()
        (self.project / "notes.txt").write_text("base\n", encoding="utf-8")
        self.init_git_remote()
        self.push_remote_commit("stray-source", "synced.txt", "from remote\n")
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        facts = self.write_json(
            "git-sync-stray.json",
            {"git_scope": [".git:refs/remotes/origin/main"], "read_scope": ["notes.txt"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "执行 git pull 同步远端", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for()
        self.run_harness("run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan))
        self.push_remote_commit("stray-source", "drifted.txt", "remote drift\n")
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        subprocess.run(["git", "merge", "--ff-only", "origin/main"], cwd=self.project, check=True, capture_output=True)
        (self.project / "notes.txt").write_text("stray local write\n", encoding="utf-8")
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=4
        )
        self.assertEqual(blocked["reason_code"], "git_remote_drift")
        _, readmitted = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(readmitted["admission_status"], "ready_planned")
        _, blocked_again = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=4
        )
        self.assertEqual(blocked_again["reason_code"], "unattributed_drift_overlap")
        self.assertEqual(blocked_again["auto_attributed_paths"], [])
        self.assertNotIn("notes.txt", blocked_again["workspace_attribution"]["task_write_set"])

    def test_git_sync_origin_head_update_not_scope_violation(self) -> None:
        self.init_project()
        self.init_git_remote()
        self.push_remote_commit("origin-head-source", "synced.txt", "from remote\n")
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=self.project, check=True)
        facts = self.write_json("git-sync-origin-head.json", {"git_scope": [".git:refs/remotes/origin/main"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "执行 git pull 同步远端", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        self.assertIn(
            ".git:refs/remotes/origin/HEAD",
            package["git_state_snapshot"]["controlled_refs_namespace"],
        )
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for()
        self.run_harness("run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan))
        subprocess.run(["git", "remote", "set-head", "origin", "main"], cwd=self.project, check=True, capture_output=True)
        subprocess.run(["git", "merge", "--ff-only", "origin/main"], cwd=self.project, check=True, capture_output=True)
        _, verified = self.run_harness("verify", "--target", str(self.project), "--task-id", task_id)
        self.assertEqual(verified["result"], "完成")
        self.assertTrue(verified["git_postcheck"]["checks"]["refs_within_contract"])

    def test_gate_assessment_authoritative_skips_keyword_gates(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_json(
            "gate-assessment-light.json",
            {
                "allowed_scope": ["src/**"],
                "gate_assessment": {
                    "gates": ["code-edit"],
                    "rationale": "单文件空指针修复，不涉及接口契约、安全与发布",
                },
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修复接口的空指针并补测试", "--facts", str(facts)
        )
        self.assertEqual(routed["matched_gates"], ["code-edit"])
        self.assertEqual(routed["gate_decision"]["mode"], "host_declared")
        self.assertEqual(routed["gate_decision"]["declared_gates"], ["code-edit"])

    def test_gate_assessment_trusts_host_without_keyword_override(self) -> None:
        """模型声明 gate 后，文本关键词不再覆盖模型判断。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "testing.md")
        facts = self.write_json(
            "gate-assessment-trust.json",
            {
                "allowed_scope": ["src/**"],
                "gate_assessment": {
                    "gates": ["code-edit"],
                    "rationale": "修复缓存逻辑，但任务包含远端推送",
                },
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修复缓存逻辑并推送到远端", "--facts", str(facts)
        )
        self.assertEqual(routed["matched_gates"], ["code-edit"])
        self.assertEqual(routed["gate_decision"]["mode"], "host_declared")
        self.assertNotIn("floor_added", routed["gate_decision"])

    def test_gate_assessment_invalid_declarations_rejected(self) -> None:
        self.init_project()
        unknown = self.write_json(
            "gate-assessment-unknown.json",
            {"gate_assessment": {"gates": ["not-a-gate"], "rationale": "无效 gate 名称"}},
        )
        _, rejected = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力", "--facts", str(unknown), expected=2
        )
        self.assertEqual(rejected["code"], "invalid_gate")
        missing_rationale = self.write_json(
            "gate-assessment-no-rationale.json",
            {"gate_assessment": {"gates": ["code-edit"]}},
        )
        _, rejected = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力", "--facts", str(missing_rationale), expected=2
        )
        self.assertEqual(rejected["code"], "invalid_gate_assessment")

    def test_gate_assessment_absent_blocks_write_task(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md", "testing.md")
        source = self.project / "src" / "cache.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("# cache\n", encoding="utf-8")
        facts = self.write_json(
            "gate-fallback.json",
            {
                "write_scope": ["src/cache.py"],
                "intent_assessment": {"intents": ["modify"], "rationale": "需要修改缓存实现"},
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现接口的缓存逻辑", "--facts", str(facts),
            expected=3, inject_assessments=False,
        )
        self.assertIn("code-edit", routed["matched_gates"])
        self.assertNotIn("architecture-contract", routed["matched_gates"])
        self.assertEqual(routed["gate_decision"]["mode"], "path_inferred")
        self.assertEqual(routed["admission_status"], "blocked")
        self.assertIn("gate_assessment", routed["assessment_requirements"])

    def test_gate_assessment_does_not_disable_mid_task_path_tripwire(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        source = self.project / "src" / "helper.py"
        source.parent.mkdir(parents=True)
        source.write_text("before\n", encoding="utf-8")
        facts = self.write_json(
            "gate-assessment-tripwire.json",
            {
                "allowed_scope": ["src/**"],
                "gate_assessment": {"gates": [], "rationale": "仅微调现有行为，不触碰契约与安全"},
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整现有能力", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.assertEqual(routed["matched_gates"], [])
        source.write_text("after\n", encoding="utf-8")
        receipt = self.evidence(
            "gate-assessment-tripwire",
            evidence_type="test_result",
            covers=task_id,
            changed_paths=["src/helper.py"],
        )
        _, pending = self.run_harness(
            "verify",
            "--target",
            str(self.project),
            "--task-id",
            task_id,
            "--evidence",
            str(receipt),
            expected=3,
        )
        self.assertEqual(pending["reason_code"], "incremental_gate_context_required")
        self.assertEqual(pending["added_gates"], ["code-edit"])

    # --- v1.6.8 可用性缺口修复回归测试 ---

    def test_authorization_mismatch_error_is_actionable(self) -> None:
        """缺口三：授权范围未覆盖错误必须携带 missing_items 和 suggested_fix。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_gate_facts("authorization-mismatch.json", ["release-external"])
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "发布 release",
            "--scope", "dist/app.zip", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        # 先完成 plan 阶段
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for({
            "外部目标": "测试发布目标。",
            "发布与回滚": "失败时撤回。",
        })
        self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        # 提交一个不完整的授权文件（缺少 external_write 动作）
        auth = self.write_json(
            "auth-incomplete.json",
            {
                "schema_version": "docs-harness/authorization-receipt/v2",
                "task_id": task_id,
                "approved": True,
                "authorized_actions": ["write"],
                "authorized_scope": ["dist/app.zip"],
            },
        )
        result, payload = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--authorization", str(auth), expected=2
        )
        self.assertEqual(payload["code"], "authorization_mismatch")
        self.assertIn("missing_items", payload)
        self.assertIn("suggested_fix", payload)
        missing_types = {item["scope_type"] for item in payload["missing_items"]}
        self.assertIn("authorized_actions", missing_types)
        # 验证 hint 内容
        action_hint = next(item["hint"] for item in payload["missing_items"] if item["scope_type"] == "authorized_actions")
        self.assertIn("authorized_actions", action_hint)

    def test_stale_evidence_error_is_actionable(self) -> None:
        """缺口三：stale_evidence 错误必须携带具体路径和修复建议。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 README.md 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        # 先加载 action context
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        # 读取任务包获取正确的 package_fingerprint 和 target_identity
        package = json.loads((self.project / ".docs-harness" / "runs" / task_id / "task-package.json").read_text())
        target_identity = HARNESS_MODULE.target_identity(self.project)
        # 创建一个包含未变化路径的 write_set 证据
        evidence = self.write_json(
            "evidence-stale.json",
            {
                "schema_version": "docs-harness/evidence-receipt/v2",
                "task_id": task_id,
                "target_identity": target_identity,
                "package_fingerprint": HARNESS_MODULE.package_fingerprint(package),
                "producer": {"adapter": "docs-harness", "capability": "host_declaration"},
                "command_argv_digest": "sha256:" + "0" * 64,
                "cwd": str(self.project.resolve()),
                "started_at": HARNESS_MODULE.utc_now(),
                "ended_at": HARNESS_MODULE.utc_now(),
                "ttl": 3600,
                "exit_code": 0,
                "output_or_artifact_digest": "sha256:" + "0" * 64,
                "read_set": [],
                "write_set": ["README.md", "nonexistent/path.py"],
                "type": "document_review",
                "result": "passed",
                "covers": [task_id],
            },
        )
        _, payload = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=2
        )
        self.assertEqual(payload["code"], "stale_evidence")
        self.assertIn("missing_items", payload)
        self.assertIn("suggested_fix", payload)
        stale_paths = [item["path"] for item in payload["missing_items"]]
        self.assertIn("nonexistent/path.py", stale_paths)

    def test_evidence_format_error_is_actionable(self) -> None:
        """缺口三：证据格式错误必须携带 actual_vs_expected 和 suggested_fix。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "审查 README.md 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        # 先加载 action context
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        # 提交一个 JSON 数组而不是对象
        evidence = self.write_json("evidence-array.json", [{"type": "test_result"}])
        _, payload = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=2
        )
        self.assertEqual(payload["code"], "invalid_evidence")
        self.assertIn("actual_vs_expected", payload)
        self.assertIn("suggested_fix", payload)
        self.assertIn("JSON list", payload["actual_vs_expected"]["actual"])
        self.assertIn("single JSON object", payload["actual_vs_expected"]["expected"])

    def test_authorization_template_command(self) -> None:
        """缺口二：授权模板命令生成符合 schema 的模板。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_gate_facts(
            "authorization-template.json",
            ["release-external", "document-edit"],
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 并推送到 origin",
            "--scope", "README.md", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        _, payload = self.run_harness(
            "authorization", "template", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(payload["action"], "template")
        self.assertEqual(payload["task_id"], task_id)
        template = payload["template"]
        self.assertEqual(template["schema_version"], "docs-harness/authorization-receipt/v2")
        self.assertEqual(template["task_id"], task_id)
        self.assertIn("_template_hints", template)
        self.assertIn(".git:refs/remotes/", template["_template_hints"]["git_scope_format"])
        self.assertIn("not git-remote:", template["_template_hints"]["external_scope_format"])
        # 验证模板可被直接消费（填充必需字段后）；时间字段相对当前时间生成，避免绝对日期过期
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        template["authorized_at"] = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        template["authorized_by"] = "test-user"
        template["expires_at"] = (now_utc + datetime.timedelta(days=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        auth_file = self.write_json("auth-from-template.json", template)
        # 先完成 plan 阶段
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for({
            "外部目标": "推送到 origin。",
            "发布与回滚": "失败时撤回。",
            "文档真源": "README.md",
            "索引与残留": "无残留。",
        })
        self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        _, auth_payload = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--authorization", str(auth_file)
        )
        self.assertNotEqual(auth_payload.get("code"), "authorization_mismatch")

    def test_cross_platform_task_detection(self) -> None:
        """缺口一：跨平台任务被正确识别并提示。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        # 按当前平台选择异平台脚本作为 scope，保证 Windows 与 unix 下都真实命中跨平台场景
        current = HARNESS_MODULE.current_platform()
        scope_path, other_platform = (
            ("scripts/unix/launch.sh", "unix") if current == "windows" else ("scripts/windows/launch.ps1", "windows")
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", f"修改 {other_platform} 启动脚本", "--scope", scope_path
        )
        self.assertIn("cross_platform_notice", routed)
        notice = routed["cross_platform_notice"]
        self.assertTrue(notice["detected"])
        self.assertIn(other_platform, notice["target_platforms"])
        self.assertEqual(notice["current_platform"], current)
        # 验证任务包中包含 platform_scope
        package = json.loads((self.project / ".docs-harness" / "runs" / routed["task_id"] / "task-package.json").read_text())
        self.assertIn("platform_scope", package)
        self.assertTrue(package["platform_scope"]["cross_platform"])
        self.assertIn(other_platform, package["platform_scope"]["detected_platforms"])

    def test_non_cross_platform_task_no_notice(self) -> None:
        """缺口一：非跨平台任务不显示跨平台提示。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md"
        )
        self.assertNotIn("cross_platform_notice", routed)
        package = json.loads((self.project / ".docs-harness" / "runs" / routed["task_id"] / "task-package.json").read_text())
        self.assertFalse(package["platform_scope"]["cross_platform"])

    def test_task_adopt_external_completion(self) -> None:
        """缺口四：外部完成的任务可被补录。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        _, payload = self.run_harness(
            "task", "adopt", "--target", str(self.project), "--task-id", task_id,
            "--outcome", "代码修改完成并通过测试",
            "--bypass-reason", "authorization_flow_too_complex",
        )
        self.assertEqual(payload["action"], "adopt")
        self.assertEqual(payload["status"], "adopted")
        self.assertEqual(payload["next_action"], "ledger_add")
        self.assertIn("adoption_record", payload)
        record = payload["adoption_record"]
        self.assertEqual(record["schema_version"], "docs-harness/task-adoption/v1")
        self.assertEqual(record["verification_status"], "adopted_external")
        self.assertEqual(record["bypass_reason"], "authorization_flow_too_complex")
        # 验证任务状态已转为 complete
        _, status = self.run_harness("task", "status", "--target", str(self.project), "--task-id", task_id)
        self.assertEqual(status["control_status"], "complete")

    def test_task_adopt_terminal_task_rejected(self) -> None:
        """缺口四：终态任务不可被补录。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        # 先补录一次
        self.run_harness(
            "task", "adopt", "--target", str(self.project), "--task-id", task_id,
            "--outcome", "第一次补录",
        )
        # 再次补录应被拒绝
        _, payload = self.run_harness(
            "task", "adopt", "--target", str(self.project), "--task-id", task_id,
            "--outcome", "第二次补录",
            expected=2,
        )
        self.assertEqual(payload["code"], "task_already_terminal")
        self.assertIn("suggested_fix", payload)

    def test_task_adopt_missing_outcome_rejected(self) -> None:
        """缺口四：缺少 outcome 的补录被拒绝。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        _, payload = self.run_harness(
            "task", "adopt", "--target", str(self.project), "--task-id", task_id,
            expected=2,
        )
        self.assertEqual(payload["code"], "missing_outcome")
        self.assertIn("suggested_fix", payload)


class DocsHarnessV173VerifyLoopTest(DocsHarnessContractTest):
    """v1.7.3 验收循环修复：T1–T17 合同测试 + V1 回放复现 + V2 交互/失败关闭矩阵。"""

    def state_dir(self, task_id: str) -> Path:
        return self.project / ".docs-harness" / "runs" / task_id

    def read_package(self, task_id: str) -> dict[str, Any]:
        return json.loads((self.state_dir(task_id) / "task-package.json").read_text(encoding="utf-8"))

    def read_events(self, task_id: str) -> list[dict[str, Any]]:
        return HARNESS_MODULE.read_jsonl(self.state_dir(task_id) / "events.jsonl")

    def admit_review_task(self) -> str:
        """准入一个 direct 路线、需要 test_result + review_result 两类证据的任务。"""
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_gate_facts("review-task.json", ["code-edit", "review-audit"])
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码并完成审查",
            "--scope", "src/core.py", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.assertEqual(routed["execution_route"], "direct")
        required = routed["completion_manifest"]["required_evidence_types"]
        self.assertIn("test_result", required)
        self.assertIn("review_result", required)
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        return task_id

    def write_file(self, relative: str, content: str = "VALUE = 1\n") -> None:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # ---------- T1：新路径必须带语义声明重新准入 ----------
    def test_v173_t1_write_scope_violation_requires_semantic_readmission(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        self.assertEqual(routed["execution_route"], "direct")
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("src/core.py")
        self.write_file("src/extra.py")
        evidence = self.evidence(
            "t1-extension", evidence_type="test_result", covers=task_id,
            changed_paths=["src/core.py", "src/extra.py"],
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertEqual(blocked["reason_code"], "write_scope_violation")
        self.assertNotIn("scope_extended", blocked)
        self.assertEqual([item["action"] for item in blocked["recovery_actions"]], ["full_readmission"])
        template = blocked["readmission_hint"]["facts_template"]
        self.assertEqual(set(template["write_scope"]), {"src/core.py", "src/extra.py"})
        self.assertIn("intent_assessment", template)
        self.assertIn("gate_assessment", template)
        package = self.read_package(task_id)
        self.assertEqual(package["package_revision"], 1)
        self.assertEqual(package["write_scope"], ["src/core.py"])
        self.assertNotIn("scope_extension_readmission", [item["event"] for item in self.read_events(task_id)])

    # ---------- T2：越界阻断不会暗中改指纹或继承证据 ----------
    def test_v173_t2_scope_violation_preserves_existing_contract_and_receipts(self) -> None:
        task_id = self.admit_review_task()
        self.write_file("src/core.py")
        first = self.evidence(
            "t2-round1", evidence_type="test_result", covers=task_id, changed_paths=["src/core.py"]
        )
        old_fingerprint = HARNESS_MODULE.package_fingerprint(self.read_package(task_id))
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(first), expected=3
        )
        self.assertEqual(pending["missing_evidence_types"], ["review_result"])
        self.write_file("src/extra.py")
        second = self.evidence(
            "t2-round2", evidence_type="review_result", covers=task_id, changed_paths=["src/extra.py"]
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(second), expected=4
        )
        self.assertEqual(blocked["reason_code"], "write_scope_violation")
        self.assertEqual(HARNESS_MODULE.package_fingerprint(self.read_package(task_id)), old_fingerprint)
        index = json.loads((self.state_dir(task_id) / "evidence-index.json").read_text(encoding="utf-8"))
        items = index["evidence"]
        self.assertTrue(any(item.get("id") == "t2-round1" for item in items))
        self.assertFalse(any(item.get("id") == "t2-round2" for item in items))
        self.assertTrue(all(item["package_fingerprint"] == old_fingerprint for item in items))

    # ---------- T3：授权任务越界不扩展，携带 readmission_hint ----------
    def test_v173_t3_authorized_task_gets_readmission_hint_instead_of_extension(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_gate_facts(
            "authorized-scope-extension.json",
            ["release-external", "document-edit"],
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 并推送到 origin",
            "--scope", "README.md", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.assertTrue(routed["authorization_requirements"])
        _, template_payload = self.run_harness(
            "authorization", "template", "--target", str(self.project), "--task-id", task_id
        )
        template = template_payload["template"]
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        template["authorized_at"] = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        template["authorized_by"] = "test-user"
        template["expires_at"] = (now_utc + datetime.timedelta(days=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        auth_file = self.write_json("t3-auth.json", template)
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan_extra = {field: "已覆盖" for field in routed["plan_fields"] if field != "执行范围"}
        if "执行范围" in routed["plan_fields"]:
            plan_extra["执行范围"] = ["README.md"]
        plan = self.plan_for(plan_extra)
        self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan), expected=3
        )
        _, ready = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--authorization", str(auth_file)
        )
        self.assertEqual(ready["admission_status"], "ready_planned")
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("README.md", "# README\n")
        self.write_file("notes/extra.md", "# extra\n")
        evidence = self.evidence(
            "t3-authorized", evidence_type="external_state", covers=task_id,
            changed_paths=["README.md", "notes/extra.md"],
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertEqual(blocked["reason_code"], "write_scope_violation")
        hint = blocked["readmission_hint"]
        self.assertEqual(hint["facts_template"]["write_scope"], ["README.md", "notes/extra.md"])
        self.assertIn("intent_assessment", hint["facts_template"])
        self.assertIn("gate_assessment", hint["facts_template"])
        self.assertIn("--facts", hint["example_argv"])
        package = self.read_package(task_id)
        self.assertEqual(package["write_scope"], ["README.md"])
        self.assertNotIn("scope_extension_readmission", [item["event"] for item in self.read_events(task_id)])

    # ---------- T4：越界与 new_risk_gate 共存走既有路径 ----------
    def test_v173_t4_mixed_blockers_do_not_trigger_extension(self) -> None:
        self.init_project()
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["gate_path_rules"] = [{"pattern": "src/security/**", "gates": ["security-sensitive"]}]
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        self.make_project_facts_meaningful("architecture.md", "security.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("src/core.py")
        self.write_file("src/security/extra.py")
        evidence = self.evidence(
            "t4-mixed", evidence_type="test_result", covers=task_id,
            changed_paths=["src/core.py", "src/security/extra.py"],
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertIn("security-sensitive", blocked["new_gates"])
        self.assertIn("readmission_hint", blocked)
        self.assertNotIn("scope_extended", blocked)
        self.assertEqual(self.read_package(task_id)["package_revision"], 1)
        self.assertNotIn("scope_extension_readmission", [item["event"] for item in self.read_events(task_id)])

    # ---------- T5：越界写入每次都直接要求重新准入 ----------
    def test_v173_t5_every_scope_violation_requires_readmission(self) -> None:
        task_id = self.admit_review_task()
        self.write_file("src/core.py")
        self.write_file("src/extra.py")
        evidence = self.evidence(
            "t5-scope", evidence_type="test_result", covers=task_id,
            changed_paths=["src/core.py", "src/extra.py"],
        )
        for _ in range(2):
            _, blocked = self.run_harness(
                "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
            )
            self.assertEqual(blocked["reason_code"], "write_scope_violation")
            self.assertNotIn("scope_extended", blocked)
        self.assertEqual(self.read_package(task_id)["package_revision"], 1)
        self.assertFalse(any(item["event"] == "scope_extension_readmission" for item in self.read_events(task_id)))

    # ---------- T6：planned 路线也不能自动扩围 ----------
    def test_v173_t6_planned_route_scope_violation_requires_readmission(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("product.md", "design.md", "architecture.md")
        facts = self.write_gate_facts(
            "t6-facts.json", ["frontend-design"], allowed_scope=["src/view.tsx"]
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现 UI 页面", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.assertEqual(routed["execution_route"], "planned")
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan_extra = {field: "已覆盖" for field in routed["plan_fields"]}
        plan_extra["执行范围"] = ["src/view.tsx"]
        plan = self.plan_for(plan_extra)
        _, ready = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan)
        )
        self.assertEqual(ready["admission_status"], "ready_planned")
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("src/view.tsx", "export {}\n")
        self.write_file("src/extra.tsx", "export {}\n")
        evidence = self.evidence(
            "t6-planned", evidence_type="ui_acceptance", covers=task_id,
            changed_paths=["src/view.tsx", "src/extra.tsx"],
        )
        extra_evidence = self.evidence(
            "t6-planned-test", evidence_type="test_result", covers=task_id,
            changed_paths=["src/view.tsx", "src/extra.tsx"],
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id,
            "--evidence", str(evidence), "--evidence", str(extra_evidence), expected=4,
        )
        self.assertEqual(blocked["reason_code"], "write_scope_violation")
        self.assertIn("intent_assessment", blocked["readmission_hint"]["facts_template"])
        self.assertNotIn("scope_extended", blocked)

    def test_v173_t6_legacy_scope_extension_helper_is_removed(self) -> None:
        self.assertFalse(hasattr(HARNESS_MODULE, "incrementally_extend_write_scope"))

    # ---------- T7：三处响应 evidence_checklist 齐全且骨架同一助手 ----------
    def test_v173_t7_evidence_checklist_in_three_responses(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        for payload in (routed,):
            checklist = payload["evidence_checklist"]
            self.assertEqual(
                set(checklist),
                {"required", "conditional", "required_receipts", "skeletons", "trust_requirements"},
            )
            self.assertIn("test_result", checklist["required"])
            receipt_names = [item["receipt"] for item in checklist["required_receipts"]]
            self.assertIn("write_set", receipt_names)
            write_set_entry = next(item for item in checklist["required_receipts"] if item["receipt"] == "write_set")
            self.assertIn("无写入时不要求", write_set_entry["condition"])
            for skeleton_ref in checklist["skeletons"]:
                skeleton = json.loads(Path(skeleton_ref).read_text(encoding="utf-8"))
                self.assertIn("_instructions", skeleton)
        _, second = self.run_harness("run", "--target", str(self.project), "--task-id", task_id)
        self.assertIn("evidence_checklist", second)
        _, status = self.run_harness("task", "status", "--target", str(self.project), "--task-id", task_id)
        self.assertIn("evidence_checklist", status)
        # verify 失败路径与准入预生成骨架一致（同一助手、同一批文件）
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("src/core.py")
        _, missing = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        self.assertEqual(set(missing["evidence_skeletons"]), set(routed["evidence_checklist"]["skeletons"]))

    # ---------- T8：所有路线共用同一个扩围失败关闭原则 ----------
    def test_v173_t8_no_route_has_an_automatic_scope_extension_helper(self) -> None:
        self.assertFalse(hasattr(HARNESS_MODULE, "incrementally_extend_write_scope"))

    # ---------- T9：auto-attribution / new_risk_gate 增量 / read_set_drift 不回归 ----------
    def test_v173_t9_auto_attribution_not_hijacked_by_extension(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("README.md", "# README\n")
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        self.assertEqual(pending["auto_attributed_paths"], ["README.md"])
        self.assertNotIn("scope_extended", pending)
        self.assertNotIn("scope_extension_readmission", [item["event"] for item in self.read_events(task_id)])

    # ---------- T10：write_scope 原为空的任务扩展失败关闭 ----------
    def test_v173_t10_read_only_task_extension_fails_closed(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "查询 README 文档状态", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        package = self.read_package(task_id)
        self.assertEqual(package["mutation_profile"], "read_only")
        self.assertEqual(package["write_scope"], [])
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("extra.txt")
        evidence = self.evidence(
            "t10-readonly", evidence_type="source_trace", covers=task_id, changed_paths=["extra.txt"]
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertEqual(blocked["reason_code"], "write_scope_violation")
        self.assertIn("readmission_hint", blocked)
        after = self.read_package(task_id)
        self.assertEqual(after["mutation_profile"], "read_only")
        self.assertEqual(after["write_scope"], [])
        self.assertEqual(after["read_scope"], ["README.md"])

    # ---------- T13：fast_track checklist 含 test_run；read_only 无 conditional ----------
    def test_v173_t13_fast_track_and_read_only_checklists(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_json("t13-fast-track.json", {
            "fast_track": True,
            "verification_commands": [{"argv": ["python3", "-m", "unittest"], "produces": ["test_run"]}],
        })
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md",
            "--facts", str(facts)
        )
        self.assertTrue(routed["fast_track"])
        checklist = routed["evidence_checklist"]
        self.assertIn("code_diff", checklist["required"])
        self.assertIn("test_run", checklist["required"])
        self.assertEqual(checklist["conditional"], [])
        _, read_only = self.run_harness(
            "run", "--target", str(self.project), "--task", "查询 README 文档状态", "--scope", "README.md"
        )
        self.assertEqual(read_only["evidence_checklist"]["conditional"], [])

    # ---------- T14：二次 run ready 响应含 evidence_checklist ----------
    def test_v173_t14_second_run_ready_response_carries_checklist(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        _, second = self.run_harness("run", "--target", str(self.project), "--task-id", routed["task_id"])
        self.assertEqual(second["admission_status"], "ready_direct")
        self.assertEqual(second["evidence_checklist"], routed["evidence_checklist"])
        self.assertIn("pending_context_receipts", second)

    # ---------- T15：changes-preview 零状态变更 + stale_evidence 双清单 ----------
    def test_v173_t15_changes_preview_is_read_only_and_stale_payload_lists(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("README.md", "# README\n")
        self.write_file("notes/extra.md", "# extra\n")
        before = self.snapshot_tree(self.state_dir(task_id))
        _, preview = self.run_harness(
            "task", "changes-preview", "--target", str(self.project), "--task-id", task_id
        )
        self.assertEqual(preview["action"], "changes-preview")
        self.assertEqual(preview["changed_paths"], ["README.md", "notes/extra.md"])
        self.assertEqual(preview["changed_in_write_scope"], ["README.md"])
        self.assertEqual(preview["changed_outside_write_scope"], ["notes/extra.md"])
        self.assertEqual(preview["changed_in_read_scope"], [])
        self.assertEqual(preview["attribution_status"], "unknown_until_evidence")
        self.assertEqual(self.snapshot_tree(self.state_dir(task_id)), before)
        stale = self.evidence(
            "t15-stale", evidence_type="document_review", covers=task_id,
            changed_paths=["README.md", "ghost.md"],
        )
        _, error = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(stale), expected=2
        )
        self.assertEqual(error["code"], "stale_evidence")
        self.assertEqual(error["stale_write_paths"], ["ghost.md"])
        self.assertEqual(error["actual_changed_paths"], ["README.md", "notes/extra.md"])
        self.assertIn("missing_items", error)

    # ---------- T16：git_sync 与规则漂移同样失败关闭 ----------
    def test_v173_t16_git_sync_and_rule_drift_fail_closed(self) -> None:
        self.assertFalse(hasattr(HARNESS_MODULE, "incrementally_extend_write_scope"))
        task_id = self.admit_review_task()
        routed = self.read_package(task_id)
        self.assertTrue(routed["matched_rules"], "需要命中规则的任务才能构造规则漂移场景")
        rule_file = self.project / ".docs-harness" / "harness-home" / "rules" / "scope-change-readmission.md"
        tampered = re.sub(r"content_fingerprint: sha256:[0-9a-f]{64}", "content_fingerprint: sha256:" + "0" * 64, rule_file.read_text(encoding="utf-8"))
        rule_file.write_text(tampered, encoding="utf-8")
        self.write_file("src/core.py")
        self.write_file("src/extra.py")
        evidence = self.evidence(
            "t16-rule-drift", evidence_type="test_result", covers=task_id,
            changed_paths=["src/core.py", "src/extra.py"],
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertEqual(blocked["reason_code"], "write_scope_violation")
        self.assertNotIn("scope_extended", blocked)
        self.assertNotIn("scope_extension_readmission", [item["event"] for item in self.read_events(task_id)])

    # ---------- T17：pending_context_receipts 三处置位 ----------
    def test_v173_t17_pending_context_receipts_in_three_responses(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        self.assertIn("action", routed["pending_context_receipts"])
        _, second = self.run_harness("run", "--target", str(self.project), "--task-id", task_id)
        self.assertIn("action", second["pending_context_receipts"])
        _, status = self.run_harness("task", "status", "--target", str(self.project), "--task-id", task_id)
        self.assertIn("action", status["pending_context_receipts"])
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("src/core.py")
        evidence = self.evidence(
            "t17-telemetry", evidence_type="test_result", covers=task_id, changed_paths=["src/core.py"]
        )
        self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        attempts = [item for item in self.read_events(task_id) if item["event"] == "verification_attempt"]
        self.assertTrue(attempts)
        self.assertIn("evidence_round_count", attempts[-1])

    # ---------- T18：宿主不看清单也不加载上下文 → 缺证失败载荷自身携带清单（失败即前置） ----------
    def test_v173_t18_missing_evidence_failure_carries_checklist(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        # 宿主完全不遵守指引：不加载上下文、不带任何证据直接 verify
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        # 第一级兜底：action_context_missing 失败载荷自身携带 pending 与清单
        self.assertEqual(blocked["reason_code"], "action_context_missing")
        self.assertIn("action", blocked["pending_context_receipts"])
        self.assertEqual(blocked["evidence_checklist"], routed["evidence_checklist"])
        for stage in blocked["pending_context_receipts"]:
            self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", stage)
        # 第二级兜底：缺证失败载荷仍携带完整清单，且骨架与清单一致
        _, missing = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        self.assertEqual(missing["result"], "补充证据")
        self.assertEqual(missing["evidence_checklist"], routed["evidence_checklist"])
        self.assertEqual(missing["pending_context_receipts"], [])
        self.assertEqual(set(missing["evidence_checklist"]["skeletons"]), set(missing["evidence_skeletons"]))
        # 宿主照失败载荷补证后一次过
        self.write_file("src/core.py")
        evidence = self.evidence(
            "t18-recovery", evidence_type="test_result", covers=task_id, changed_paths=["src/core.py"]
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(verified["result"], "完成")

    # ---------- T19：范围越界先重准入，未准入证据不进索引 ----------
    def test_v173_t19_scope_violation_precedes_evidence_adoption(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("src/core.py")
        self.write_file("src/extra.py")
        revision_before = self.read_package(task_id)["package_revision"]
        overstated = self.evidence(
            "t19-overstated", evidence_type="test_result", covers=task_id,
            changed_paths=["src/core.py", "src/extra.py"],
            write_set=["src/core.py", "src/extra.py", "src/ghost-never-touched.py"],
        )
        _, failed = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(overstated),
            expected=4,
        )
        self.assertEqual(failed["reason_code"], "write_scope_violation")
        package = self.read_package(task_id)
        self.assertEqual(package["package_revision"], revision_before)
        self.assertEqual(package["write_scope"], ["src/core.py"])
        index = json.loads((self.state_dir(task_id) / "evidence-index.json").read_text(encoding="utf-8"))
        self.assertFalse(
            any(item.get("id") == "t19-overstated" for item in index["evidence"]),
            "虚报证据不得入索引",
        )
        self.assertIn("intent_assessment", failed["readmission_hint"]["facts_template"])

    # ---------- T20：pending_context_receipts 覆盖 work_packages ----------
    def test_v173_t20_pending_context_receipts_cover_work_packages(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_json(
            "t20-facts.json",
            {
                "execution_route": "extended",
                "allowed_scope": ["docs/a.md", "docs/b.md"],
                "work_packages": [
                    {
                        "id": "wp-a", "goal": "交付 A", "scope": ["docs/a.md"], "dependencies": [],
                        "owner": "owner-a", "success_criteria": ["A 完成"], "acceptance": ["A 有证据"],
                    },
                    {
                        "id": "wp-b", "goal": "交付 B", "scope": ["docs/b.md"], "dependencies": ["wp-a"],
                        "owner": "owner-b", "success_criteria": ["B 完成"], "acceptance": ["B 有证据"],
                    },
                ],
            },
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现多工作包文档", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "plan")
        plan = self.plan_for({"文档真源": "根项目文档地图。", "索引与残留": "同步索引并清除旧引用。"})
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        _, admitted = self.run_harness(
            "run", "--target", str(self.project), "--task-id", task_id, "--plan", str(plan)
        )
        self.assertEqual(admitted["admission_status"], "ready_extended")
        self.assertEqual(
            sorted(admitted["pending_context_receipts"]), ["work_package:wp-a", "work_package:wp-b"]
        )
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--work-package", "wp-a")
        _, status = self.run_harness("task", "status", "--target", str(self.project), "--task-id", task_id)
        self.assertEqual(status["pending_context_receipts"], ["work_package:wp-b"])

    # ---------- T21：宿主自报 concurrent 不得被自动归因或升级为 verified ----------
    def test_v173_t21_reported_concurrent_overlap_requires_controlled_evidence(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_json(
            "t21-facts.json",
            {"allowed_scope": ["docs/a.md", "docs/b.md"], "write_scope": ["docs/a.md"], "read_scope": ["docs/b.md"]},
        )
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改文档 a 并审阅 b", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("docs/a.md", "# A\n")
        self.write_file("docs/b.md", "# B\n")
        evidence = self.evidence(
            "t21-drift", evidence_type="document_review", covers=task_id,
            changed_paths=["docs/a.md"], concurrent_drift=["docs/b.md"],
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=3
        )
        self.assertEqual(blocked["reason_code"], "concurrent_drift_unverified")
        self.assertEqual(blocked["auto_attributed_paths"], [])
        self.assertEqual(blocked["reported_concurrent_paths"], ["docs/b.md"])
        self.assertEqual(blocked["next_action"], "provide_evidence")

    # ---------- T22：行尾宽容指纹在 1MiB chunk 边界的 CRLF 归一化 ----------
    def test_v173_t22_tolerant_fingerprint_crlf_chunk_boundary(self) -> None:
        boundary = 1024 * 1024
        body = b"x" * (boundary - 1)
        lf = self.project / "lf.txt"
        crlf = self.project / "crlf.txt"
        lf.write_bytes(body + b"\n" + b"y" * 16)
        crlf.write_bytes(body + b"\r\n" + b"y" * 16)
        self.assertEqual(
            HARNESS_MODULE.script_fingerprint_tolerant(lf),
            HARNESS_MODULE.script_fingerprint_tolerant(crlf),
            "跨 chunk 边界的 CRLF 必须与 LF 指纹一致",
        )
        standalone = self.project / "cr.txt"
        standalone.write_bytes(body + b"\r" + b"y" * 16)
        self.assertNotEqual(
            HARNESS_MODULE.script_fingerprint_tolerant(standalone),
            HARNESS_MODULE.script_fingerprint_tolerant(lf),
        )

    # ---------- T23：legacy v1 任务 changes-preview 结构化失败关闭 + manifest 守卫一致 ----------
    def test_v173_t23_changes_preview_legacy_guard_and_manifest_guard_consistency(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "查询项目文档在哪"
        )
        task_id = routed["task_id"]
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        package["schema_version"] = "docs-harness/task-package/v1"
        (state / "task-package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        with self.assertRaises(HARNESS_MODULE.HarnessError) as raised:
            HARNESS_MODULE.task_changes_preview(self.project, state, task_id)
        self.assertEqual(raised.exception.code, "legacy_task_requires_migration")
        # completion_manifest 缺失/无效时不抛 KeyError，与二次 run / task status 的守卫一致
        package.pop("completion_manifest", None)
        (state / "task-package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        compiled = json.loads((state / "compiled-task.json").read_text(encoding="utf-8"))
        code, payload = HARNESS_MODULE.first_run_payload(self.project, state, package, compiled)
        self.assertEqual(code, 0)
        self.assertNotIn("evidence_checklist", payload)
        self.assertNotIn("pending_context_receipts", payload)

    # ---------- V1 回放：write_scope 循环在第一个新路径即停止 ----------
    def test_v173_replay_write_scope_loop_stops_at_first_new_path(self) -> None:
        task_id = self.admit_review_task()
        self.write_file("src/core.py")
        self.write_file("src/loop1.py")
        evidence = self.evidence(
            "replay-loop1", evidence_type="test_result", covers=task_id,
            changed_paths=["src/core.py", "src/loop1.py"],
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertEqual(blocked["reason_code"], "write_scope_violation")
        self.assertEqual(self.read_package(task_id)["package_revision"], 1)

    # ---------- V1 回放：checklist 一次备齐消灭首轮补证 ----------
    def test_v173_replay_checklist_eliminates_first_round_evidence_chase(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        checklist = routed["evidence_checklist"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("src/core.py")
        evidence_args: list[str] = []
        for evidence_type in checklist["required"]:
            evidence_args.extend([
                "--evidence",
                str(self.evidence(f"replay-{evidence_type}", evidence_type=evidence_type, covers=task_id, changed_paths=["src/core.py"])),
            ])
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, *evidence_args
        )
        self.assertEqual(verified["control_status"], "complete")
        self.assertEqual(
            sum(1 for item in self.read_events(task_id) if item["event"] == "verification_attempt"), 1
        )

    # ---------- V1 回放：stale_evidence 预览后一次修正 ----------
    def test_v173_replay_stale_evidence_fixed_after_preview(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改 README 文档", "--scope", "README.md"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("README.md", "# README\n")
        _, preview = self.run_harness(
            "task", "changes-preview", "--target", str(self.project), "--task-id", task_id
        )
        evidence = self.evidence(
            "replay-stale-fixed", evidence_type="document_review", covers=task_id,
            changed_paths=list(preview["changed_in_write_scope"]),
        )
        _, verified = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence)
        )
        self.assertEqual(verified["control_status"], "complete")

    # ---------- V1 回放：自报 concurrent 返回最小补证动作 ----------
    def test_v173_replay_reported_concurrent_returns_provide_evidence(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        facts = self.write_json("replay-drift-facts.json", {"allowed_scope": ["docs/a.md", "docs/b.md"]})
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "修改文档 a 与 b", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("docs/a.md", "# A\n")
        self.write_file("docs/b.md", "# B\n")
        evidence = self.evidence(
            "replay-drift", evidence_type="document_review", covers=task_id,
            changed_paths=["docs/a.md"], concurrent_drift=["docs/b.md"],
        )
        _, blocked = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=3
        )
        self.assertEqual(blocked["reason_code"], "concurrent_drift_unverified")
        self.assertEqual([item["action"] for item in blocked["recovery_actions"]], ["provide_evidence"])
        self.assertEqual(blocked["auto_attributed_paths"], [])

    # ---------- V2 矩阵：越界重 verify 幂等地继续阻断 ----------
    def test_v173_matrix_reverify_after_scope_violation_is_idempotent(self) -> None:
        task_id = self.admit_review_task()
        self.write_file("src/core.py")
        self.write_file("src/extra1.py")
        evidence = self.evidence(
            "matrix-idem", evidence_type="test_result", covers=task_id,
            changed_paths=["src/core.py", "src/extra1.py"],
        )
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertEqual(pending["reason_code"], "write_scope_violation")
        _, again = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=4
        )
        self.assertEqual(again["reason_code"], "write_scope_violation")
        self.assertNotIn("scope_extended", again)
        self.assertFalse(any(item["event"] == "scope_extension_readmission" for item in self.read_events(task_id)))

    # ---------- V2 矩阵：同源证据不双写 ----------
    def test_v173_matrix_duplicate_source_fingerprint_not_double_indexed(self) -> None:
        self.init_project()
        self.make_project_facts_meaningful("architecture.md")
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        self.run_harness("context", "--target", str(self.project), "--task-id", task_id, "--stage", "action")
        self.write_file("src/core.py")
        evidence = self.evidence(
            "matrix-dup", evidence_type="test_result", covers=task_id, changed_paths=["src/core.py"]
        )
        self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id,
            "--evidence", str(evidence), "--evidence", str(evidence)
        )
        index = json.loads((self.state_dir(task_id) / "evidence-index.json").read_text(encoding="utf-8"))
        fingerprints = [item["source_fingerprint"] for item in index["evidence"]]
        self.assertEqual(len(fingerprints), len(set(fingerprints)))

    # ---------- V2 矩阵：阻断时不产生伪重编译归档 ----------
    def test_v173_matrix_scope_violation_does_not_archive_a_fake_revision(self) -> None:
        task_id = self.admit_review_task()
        created_at = self.read_package(task_id)["created_at"]
        self.write_file("src/core.py")
        self.write_file("src/extra1.py")
        evidence = self.evidence(
            "matrix-archive", evidence_type="test_result", covers=task_id,
            changed_paths=["src/core.py", "src/extra1.py"],
        )
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, "--evidence", str(evidence), expected=4
        )
        self.assertEqual(pending["reason_code"], "write_scope_violation")
        history = self.state_dir(task_id) / "package-history"
        self.assertFalse(history.exists())
        after = self.read_package(task_id)
        self.assertEqual(after["created_at"], created_at)
        self.assertEqual(after["package_revision"], 1)

    # ---------- V2 矩阵：旧扩围入口不可被调用 ----------
    def test_v173_matrix_legacy_scope_extension_entrypoint_is_absent(self) -> None:
        self.assertFalse(hasattr(HARNESS_MODULE, "incrementally_extend_write_scope"))

    # ---------- v1.7.5：本地提交意图 + 安全底线否定守卫 ----------
    def test_v175_git_commit_intent_admits_local_commit_layer(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "先提交当前的用户改动，然后继续（只本地提交，不推送）",
        )
        self.assertEqual(routed["task_intent"], "git_commit")
        self.assertEqual(routed["mutation_profile"], "git_metadata_write")
        self.assertIn("git_commit", routed["allowed_actions"])
        self.assertNotIn("git_fetch", routed["allowed_actions"])
        self.assertNotIn("external_write", routed["allowed_actions"])
        self.assertNotIn("release-external", routed["matched_gates"])

    def test_v175_negated_push_does_not_trip_release_gate_or_rule(self) -> None:
        self.init_project()
        _, routed = self.run_harness(
            "run",
            "--target",
            str(self.project),
            "--task",
            "查询远端状态，不推送，也不要修改文件",
        )
        self.assertNotIn("release-external", routed["matched_gates"])
        package = self.read_package(routed["task_id"])
        self.assertNotIn(
            "DH-RELEASE-AUTHORIZATION-ROLLBACK",
            {rule["rule_id"] for rule in package["matched_rules"]},
        )

    def test_v175_text_keywords_no_longer_infer_gates(self) -> None:
        gates = HARNESS_MODULE.infer_gates("把代码推送到远端", [], mutation_profile="workspace_write")
        self.assertEqual(gates, [])
        gates = HARNESS_MODULE.infer_gates("发布上线新版本", [], mutation_profile="workspace_write")
        self.assertEqual(gates, [])

    def test_v175_delivery_layer_negation_guard(self) -> None:
        base = {"task_intent": "modify", "matched_gates": []}
        negated = HARNESS_MODULE.build_delivery_layers(
            {**base, "success_criteria": ["只本地提交，不推送"]},
            ["code_diff"],
        )
        self.assertNotEqual(negated["remote_delivery"]["expectation"], "required")
        required = HARNESS_MODULE.build_delivery_layers(
            {**base, "success_criteria": ["需要推送到远端"]},
            ["code_diff"],
        )
        self.assertEqual(required["remote_delivery"]["expectation"], "required")

    def test_v175_git_commit_intent_boundaries(self) -> None:
        current, _, _ = HARNESS_MODULE.classify_task_intents(
            "提交证据清单", {}, has_declared_scope=False
        )
        self.assertNotIn("git_commit", {item["intent"] for item in current})
        current, deferred, reason_codes = HARNESS_MODULE.classify_task_intents(
            "后续再提交改动", {}, has_declared_scope=False
        )
        self.assertNotIn("git_commit", {item["intent"] for item in current})
        self.assertIn("git_commit", {item["intent"] for item in deferred})
        self.assertIn("future_clause_deferred", reason_codes)
        current, _, _ = HARNESS_MODULE.classify_task_intents(
            "已经提交了改动", {}, has_declared_scope=False
        )
        self.assertNotIn("git_commit", {item["intent"] for item in current})

    # ---------- 声明制准入与证据信任收敛 ----------
    def test_declared_intent_is_authoritative_over_text_keywords(self) -> None:
        current, deferred, reasons = HARNESS_MODULE.classify_task_intents(
            "审查消息发送逻辑，不修改任何文件",
            {
                "intent_assessment": {
                    "intents": ["query", "audit"],
                    "rationale": "只读审查发送模块的实现，不执行外部发送",
                }
            },
            has_declared_scope=False,
        )
        self.assertEqual([item["intent"] for item in current], ["query", "audit"])
        self.assertEqual(deferred, [])
        self.assertEqual(reasons, ["host_declared_intent"])

    def test_write_task_without_assessments_is_blocked_with_templates(self) -> None:
        self.init_project()
        _, blocked = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整默认阈值",
            "--scope", "src/settings.json", expected=3, inject_assessments=False,
        )
        self.assertEqual(blocked["admission_status"], "blocked")
        self.assertTrue(any("intent_assessment" in item for item in blocked["blockers"]))
        self.assertTrue(any("gate_assessment" in item for item in blocked["blockers"]))
        self.assertEqual(blocked["assessment_requirements"]["intent_assessment"]["intents"], ["modify"])

    def test_auto_attribution_cannot_replace_change_review(self) -> None:
        self.init_project()
        facts = self.write_json("strict-write.json", {
            "intent_assessment": {"intents": ["modify"], "rationale": "修改项目配置"},
            "gate_assessment": {"gates": [], "rationale": "普通配置调整，无高风险 Gate"},
            "write_scope": ["src/settings.json"],
        })
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整默认阈值", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        path = self.project / "src" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"threshold": 1}\n', encoding="utf-8")
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id, expected=3
        )
        self.assertEqual(pending["auto_attributed_paths"], ["src/settings.json"])
        self.assertIn("change_review", pending["missing_evidence_types"])
        review = self.write_json("change-review.json", {
            "schema_version": "docs-harness/evidence-declaration/v1",
            "type": "change_review",
            "write_set": ["src/settings.json"],
            "conclusion": "阈值变更符合任务目标",
        })
        _, complete = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id,
            "--evidence", str(review),
        )
        self.assertEqual(complete["result"], "完成")

    def test_host_declaration_is_reported_and_cannot_prove_concurrent_drift(self) -> None:
        self.init_project()
        facts = self.write_json("reported-evidence.json", {
            "intent_assessment": {"intents": ["modify"], "rationale": "修改项目配置"},
            "gate_assessment": {"gates": [], "rationale": "普通配置调整"},
            "write_scope": ["src/settings.json"],
        })
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整默认阈值", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        state = HARNESS_MODULE.task_state_dir(self.project, task_id)
        package = json.loads((state / "task-package.json").read_text(encoding="utf-8"))
        freeze = json.loads((state / "freeze.json").read_text(encoding="utf-8"))
        self.write_file("src/settings.json", '{"threshold": 1}\n')
        self.write_file("external.txt", "concurrent\n")
        declaration = self.write_json("reported-declaration.json", {
            "schema_version": "docs-harness/evidence-declaration/v1",
            "type": "change_review",
            "write_set": ["src/settings.json"],
            "concurrent_drift": ["external.txt"],
            "conclusion": "配置审查通过",
        })
        _, normalized = HARNESS_MODULE.load_evidence(
            str(declaration), expected_cover=task_id, package=package, target=self.project
        )
        self.assertEqual(normalized["trust_level"], "reported")
        self.assertEqual(normalized["attribution_quality"], "reported")
        attribution = HARNESS_MODULE.workspace_change_attribution(
            self.project, package, freeze, [normalized]
        )
        self.assertEqual(attribution["concurrent_drift"], [])
        self.assertEqual(attribution["reported_concurrent_drift"], ["external.txt"])
        self.assertIn("external.txt", attribution["unattributed_drift"])
        high_risk = self.write_json("reported-security.json", {
            "schema_version": "docs-harness/evidence-declaration/v1",
            "type": "security_acceptance",
            "write_set": ["src/settings.json"],
            "conclusion": "安全验收通过",
        })
        _, normalized_high_risk = HARNESS_MODULE.load_evidence(
            str(high_risk), expected_cover=task_id, package=package, target=self.project
        )
        self.assertEqual(normalized_high_risk["trust_level"], "reported")

    def test_external_receipt_cannot_impersonate_controller_producer(self) -> None:
        self.init_project()
        facts = self.write_json("producer-task.json", {
            "intent_assessment": {"intents": ["modify"], "rationale": "修改项目配置"},
            "gate_assessment": {"gates": [], "rationale": "普通配置调整"},
            "write_scope": ["src/settings.json"],
        })
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整默认阈值", "--facts", str(facts)
        )
        forged = self.evidence(
            "forged-controller", evidence_type="change_review", covers=routed["task_id"],
            changed_paths=[], producer={"adapter": "docs-harness", "capability": "verification_command"},
        )
        package = self.read_package(routed["task_id"])
        with self.assertRaises(HARNESS_MODULE.HarnessError) as raised:
            HARNESS_MODULE.load_evidence(
                str(forged), expected_cover=routed["task_id"], package=package, target=self.project
            )
        self.assertEqual(raised.exception.code, "forged_evidence_producer")

    def test_failed_verification_returns_retry_action(self) -> None:
        self.init_project()
        facts = self.write_json("retry-action.json", {
            "intent_assessment": {"intents": ["modify"], "rationale": "修改项目配置"},
            "gate_assessment": {"gates": [], "rationale": "普通配置调整"},
            "write_scope": ["src/settings.json"],
            "verification_commands": [{
                "argv": ["python3", "-m", "unittest", "test_module_that_does_not_exist"],
                "produces": ["test_result"],
            }],
        })
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整默认阈值", "--facts", str(facts)
        )
        task_id = routed["task_id"]
        self.write_file("src/settings.json", '{"threshold": 1}\n')
        review = self.write_json("retry-review.json", {
            "schema_version": "docs-harness/evidence-declaration/v1", "type": "change_review",
            "write_set": ["src/settings.json"], "conclusion": "变更符合目标",
        })
        test_result = self.write_json("retry-test-result.json", {
            "schema_version": "docs-harness/evidence-declaration/v1", "type": "test_result",
            "write_set": ["src/settings.json"], "conclusion": "宿主报告测试结果",
        })
        _, pending = self.run_harness(
            "verify", "--target", str(self.project), "--task-id", task_id,
            "--evidence", str(review), "--evidence", str(test_result), expected=3,
        )
        self.assertEqual(pending["next_action"], "retry_verification")
        self.assertEqual([item["action"] for item in pending["recovery_actions"]], ["retry_verification"])

    def test_changes_preview_reports_workspace_partition_not_verify_attribution(self) -> None:
        self.init_project()
        facts = self.write_json("preview-contract.json", {
            "intent_assessment": {"intents": ["modify"], "rationale": "修改项目配置"},
            "gate_assessment": {"gates": [], "rationale": "普通配置调整"},
            "write_scope": ["src/settings.json"],
        })
        _, routed = self.run_harness(
            "run", "--target", str(self.project), "--task", "调整默认阈值", "--facts", str(facts)
        )
        self.write_file("src/settings.json", '{"threshold": 1}\n')
        self.write_file("external.txt", "other\n")
        _, preview = self.run_harness(
            "task", "changes-preview", "--target", str(self.project), "--task-id", routed["task_id"]
        )
        self.assertEqual(preview["changed_in_write_scope"], ["src/settings.json"])
        self.assertEqual(preview["changed_outside_write_scope"], ["external.txt"])
        self.assertEqual(preview["attribution_status"], "unknown_until_evidence")
        self.assertNotIn("outside_scope", preview)

    def test_semantic_path_gates_require_project_mapping(self) -> None:
        self.init_project()
        self.assertNotIn(
            "security-sensitive",
            HARNESS_MODULE.infer_gates_from_paths(["docs/auth.md"]),
        )
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["gate_path_rules"] = [{"pattern": "docs/auth.md", "gates": ["security-sensitive"]}]
        config_path.write_text(json.dumps(config), encoding="utf-8")
        self.assertIn(
            "security-sensitive",
            HARNESS_MODULE.gates_for_paths(self.project, ["docs/auth.md"]),
        )


if __name__ == "__main__":
    unittest.main()
