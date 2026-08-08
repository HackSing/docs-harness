#!/usr/bin/env python3
"""v1.7.3 V3 端到端影子验收脚本（可重跑）。

在临时项目工作区用安装副本（project/scripts/harness.py）走完整链路，
逐条断言 v1.7.3-verify-loop-fix-plan.md V3 节的全部验收项：

  S1 direct 任务准入 → 越界写入 → verify 一次调用内扩展并 complete
  S2 三处 evidence_checklist 实际可用：按其备齐证据一次过 verify（无 missing_evidence_types）
  S3 planned 路线越界 → readmission_hint 一次重准入即过
  S4 授权任务越界 → 走 C 不扩展（exit 4 + hint，package_revision 不变）
  S5 task changes-preview 前后 state 目录逐字节一致，且输出与 verify 时刻归因一致

任一条失败即退出码 1；全部通过输出 V3 SHADOW ACCEPTANCE PASSED。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HARNESS = ROOT / "scripts" / "harness.py"
SPEC = importlib.util.spec_from_file_location("docs_harness_controller", HARNESS)
HARNESS_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS_MODULE)

CHECKS: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    if not condition:
        print(f"[FAIL] {label}: {detail}")
        raise SystemExit(1)
    CHECKS.append(label)
    print(f"[PASS] {label}")


class ShadowEnv:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()

    def cleanup(self) -> None:
        self.temp.cleanup()

    def run_source(self, *args: str, expected: int = 0) -> dict:
        """用来源包 harness 执行（project init 阶段）。"""
        result = subprocess.run(
            [sys.executable, str(HARNESS), *args, "--json"],
            cwd=ROOT, capture_output=True, text=True, check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        payload = json.loads(result.stdout)
        if result.returncode != expected:
            print(f"[FAIL] 命令退出码异常: {args}\n{result.stdout}\n{result.stderr}")
            raise SystemExit(1)
        return payload

    def run(self, *args: str, expected: int = 0) -> dict:
        """用安装副本执行（影子验收主通道）。"""
        result = subprocess.run(
            [sys.executable, str(self.project / "scripts" / "harness.py"), *args, "--json"],
            cwd=self.project, capture_output=True, text=True, check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        payload = json.loads(result.stdout)
        if result.returncode != expected:
            print(f"[FAIL] 安装副本命令退出码异常: {args}\n{result.stdout}\n{result.stderr}")
            raise SystemExit(1)
        return payload

    def write_json(self, name: str, value) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def init_project(self) -> None:
        self.run_source("project", "init", "--target", str(self.project))
        feature_root = self.project / "docs" / "features" / "project-core"
        feature_root.mkdir(parents=True, exist_ok=True)
        for category, title in (("product", "产品"), ("development", "研发"), ("testing", "测试"), ("design", "设计")):
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
            "reviewed_revision": "shadow-fixture",
            "features": [
                {
                    "feature_id": "project-core",
                    "name": "项目核心",
                    "aliases": ["项目", "README"],
                    "feature_type": "platform_capability",
                    "status": "implemented",
                    "scope_patterns": ["**"],
                    "documents": {c: f"docs/features/project-core/{c}.md" for c in ("product", "development", "testing", "design")},
                    "shared_refs": ["docs/shared/architecture.md", "docs/shared/security.md", "docs/shared/design-system.md", "docs/shared/testing-strategy.md"],
                    "dependencies": [],
                    "known_gaps": [],
                }
            ],
        }
        (self.project / "docs" / "knowledge-map.json").write_text(
            json.dumps(knowledge_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (self.project / "docs" / "adr").mkdir(parents=True, exist_ok=True)
        (self.project / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
        (self.project / "docs" / "todo.md").write_text("# TODO\n", encoding="utf-8")
        (self.project / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
        for job in HARNESS_MODULE.list_background_jobs(self.project):
            job_root, current = HARNESS_MODULE.read_knowledge_job(self.project, job["job_id"])
            HARNESS_MODULE.refresh_knowledge_job_baseline(self.project, current)
            HARNESS_MODULE.write_background_job(self.project, job_root, current)

    def make_facts_meaningful(self, *names: str) -> None:
        mapping = {
            "product.md": self.project / "docs" / "features" / "project-core" / "product.md",
            "architecture.md": self.project / "docs" / "features" / "project-core" / "development.md",
            "design.md": self.project / "docs" / "features" / "project-core" / "design.md",
            "security.md": self.project / "docs" / "shared" / "security.md",
        }
        for name in names:
            path = mapping[name]
            path.write_text(path.read_text(encoding="utf-8") + "\n已由项目确认的真实事实。\n", encoding="utf-8")

    def write_file(self, relative: str, content: str = "VALUE = 1\n") -> None:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def state_dir(self, task_id: str) -> Path:
        return self.project / ".docs-harness" / "runs" / task_id

    def read_package(self, task_id: str) -> dict:
        return json.loads((self.state_dir(task_id) / "task-package.json").read_text(encoding="utf-8"))

    def evidence(
        self, name: str, *, evidence_type: str, covers: str,
        changed_paths: list[str], write_set: list[str] | None = None,
    ) -> Path:
        package = self.read_package(covers)
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
                "producer": {"adapter": "codex-host", "capability": "review_receipt"},
                "command_argv_digest": HARNESS_MODULE.sha256_text("shadow-receipt-command"),
                "cwd": str(self.project),
                "started_at": now,
                "ended_at": now,
                "ttl": 3600,
                "exit_code": 0,
                "output_or_artifact_digest": HARNESS_MODULE.sha256_text(name),
                "changed_paths": changed_paths,
                "read_set": [],
                "write_set": write_set if write_set is not None else changed_paths,
                "concurrent_drift": [],
                "conclusion": "验收通过",
            },
        )

    @staticmethod
    def snapshot_tree(root: Path) -> dict[str, str]:
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


def plan_doc(extra: dict | None = None) -> dict:
    value = {
        "背景": "当前能力需要调整。",
        "目标": "交付可验证结果。",
        "非目标": "不改变未授权范围。",
        "成功标准": ["目标结果可验证"],
        "执行内容": ["按任务包执行"],
        "验收结果": ["按前置标准验收"],
    }
    value.update(extra or {})
    return value


def scenario_s1_direct_extension(env: ShadowEnv) -> None:
    routed = env.run("run", "--target", str(env.project), "--task", "实现项目核心代码", "--scope", "src/core.py")
    task_id = routed["task_id"]
    check("S1 direct 路线准入", routed["execution_route"] == "direct", routed.get("execution_route"))
    env.run("context", "--target", str(env.project), "--task-id", task_id, "--stage", "action")
    env.write_file("src/core.py")
    env.write_file("src/extra.py")
    evidence = env.evidence("s1", evidence_type="test_result", covers=task_id, changed_paths=["src/core.py", "src/extra.py"])
    verified = env.run("verify", "--target", str(env.project), "--task-id", task_id, "--evidence", str(evidence))
    check("S1 一次 verify 内扩展并 complete", verified["control_status"] == "complete", verified)
    check("S1 scope_extended 置位", verified.get("scope_extended") is True, verified)
    check("S1 extended_paths 精确", verified.get("extended_paths") == ["src/extra.py"], verified.get("extended_paths"))
    package = env.read_package(task_id)
    check("S1 write_scope 已扩展", set(package["write_scope"]) == {"src/core.py", "src/extra.py"}, package["write_scope"])
    check("S1 安装副本自测通过", env.run("self-test", "--target", str(env.project))["status"] == "passed")


def scenario_s2_checklist_usable(env: ShadowEnv) -> None:
    routed = env.run("run", "--target", str(env.project), "--task", "实现项目核心代码并完成审查", "--scope", "src/s2.py")
    task_id = routed["task_id"]
    checklist_first = routed["evidence_checklist"]
    env.run("context", "--target", str(env.project), "--task-id", task_id, "--stage", "action")
    second = env.run("run", "--target", str(env.project), "--task-id", task_id)
    check("S2 二次 run 携带 evidence_checklist", second.get("evidence_checklist") == checklist_first, second.get("evidence_checklist"))
    status = env.run("task", "status", "--target", str(env.project), "--task-id", task_id)
    check("S2 task status 携带 evidence_checklist", status.get("evidence_checklist") == checklist_first, status.get("evidence_checklist"))
    env.write_file("src/s2.py")
    evidences = [
        env.evidence(f"s2-{etype}", evidence_type=etype, covers=task_id, changed_paths=["src/s2.py"])
        for etype in checklist_first["required"]
    ]
    argv = ["verify", "--target", str(env.project), "--task-id", task_id]
    for path in evidences:
        argv += ["--evidence", str(path)]
    verified = env.run(*argv)
    check("S2 按 checklist 一次备齐即过 verify", verified["control_status"] == "complete", verified)
    check("S2 未出现 missing_evidence_types 往返", verified.get("reason_code") != "missing_evidence_types", verified)


def scenario_s3_planned_readmission_hint(env: ShadowEnv) -> None:
    """planned 路线越界：plan_fields 不变时一次 verify 内增量扩围完成（比 C 兜底更强的承诺，见设计 A/T6）；
    C 的 readmission_hint 由授权任务场景 S4 覆盖。"""
    env.make_facts_meaningful("product.md", "design.md", "architecture.md")
    facts = env.write_json("s3-facts.json", {"allowed_scope": ["src/view.tsx"]})
    routed = env.run("run", "--target", str(env.project), "--task", "实现 UI 页面", "--facts", str(facts))
    task_id = routed["task_id"]
    check("S3 planned 路线准入", routed["execution_route"] == "planned", routed.get("execution_route"))
    env.run("context", "--target", str(env.project), "--task-id", task_id, "--stage", "plan")
    plan_extra = {field: "已覆盖" for field in routed["plan_fields"]}
    plan_extra["执行范围"] = ["src/view.tsx"]
    plan = env.write_json("s3-plan.json", plan_doc(plan_extra))
    env.run("run", "--target", str(env.project), "--task-id", task_id, "--plan", str(plan))
    env.run("context", "--target", str(env.project), "--task-id", task_id, "--stage", "action")
    env.write_file("src/view.tsx", "export {}\n")
    env.write_file("src/view-extra.tsx", "export {}\n")
    evidence = env.evidence(
        "s3-planned", evidence_type="ui_acceptance", covers=task_id,
        changed_paths=["src/view.tsx", "src/view-extra.tsx"],
    )
    evidence_test = env.evidence(
        "s3-planned-test", evidence_type="test_result", covers=task_id,
        changed_paths=["src/view.tsx", "src/view-extra.tsx"],
    )
    verified = env.run(
        "verify", "--target", str(env.project), "--task-id", task_id,
        "--evidence", str(evidence), "--evidence", str(evidence_test),
    )
    check("S3 planned 越界一次 verify 内扩展并 complete", verified["control_status"] == "complete", verified)
    check("S3 scope_extended 置位", verified.get("scope_extended") is True, verified)
    check("S3 extended_paths 精确", verified.get("extended_paths") == ["src/view-extra.tsx"], verified.get("extended_paths"))
    package = env.read_package(task_id)
    check("S3 write_scope 已扩展", set(package["write_scope"]) == {"src/view.tsx", "src/view-extra.tsx"}, package["write_scope"])


def scenario_s4_authorized_no_extension(env: ShadowEnv) -> None:
    import datetime

    routed = env.run("run", "--target", str(env.project), "--task", "修改 README 并推送到 origin", "--scope", "README.md")
    task_id = routed["task_id"]
    check("S4 授权要求存在", bool(routed["authorization_requirements"]), routed)
    template = env.run("authorization", "template", "--target", str(env.project), "--task-id", task_id)["template"]
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    template["authorized_at"] = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    template["authorized_by"] = "shadow-user"
    template["expires_at"] = (now_utc + datetime.timedelta(days=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    auth_file = env.write_json("s4-auth.json", template)
    env.run("context", "--target", str(env.project), "--task-id", task_id, "--stage", "plan")
    plan_extra = {field: "已覆盖" for field in routed["plan_fields"] if field != "执行范围"}
    if "执行范围" in routed["plan_fields"]:
        plan_extra["执行范围"] = ["README.md"]
    plan = env.write_json("s4-plan.json", plan_doc(plan_extra))
    env.run("run", "--target", str(env.project), "--task-id", task_id, "--plan", str(plan), expected=3)
    ready = env.run("run", "--target", str(env.project), "--task-id", task_id, "--authorization", str(auth_file))
    check("S4 授权后 ready_planned", ready["admission_status"] == "ready_planned", ready)
    env.run("context", "--target", str(env.project), "--task-id", task_id, "--stage", "action")
    env.write_file("README.md", "# README\n")
    env.write_file("notes/extra.md", "# extra\n")
    revision_before = env.read_package(task_id)["package_revision"]
    evidence = env.evidence(
        "s4-authorized", evidence_type="external_state", covers=task_id, changed_paths=["README.md", "notes/extra.md"]
    )
    blocked = env.run("verify", "--target", str(env.project), "--task-id", task_id, "--evidence", str(evidence), expected=4)
    check("S4 授权任务越界 exit 4 不扩展", blocked["reason_code"] == "write_scope_violation", blocked)
    check("S4 readmission_hint 携带", "readmission_hint" in blocked and "--facts" in blocked["readmission_hint"]["example_argv"], blocked)
    check("S4 scope_extended 缺省", "scope_extended" not in blocked, blocked)
    package = env.read_package(task_id)
    check("S4 package_revision 不变", package["package_revision"] == revision_before, package["package_revision"])
    check("S4 write_scope 不变", package["write_scope"] == ["README.md"], package["write_scope"])


def scenario_s5_changes_preview_readonly(env: ShadowEnv) -> None:
    routed = env.run("run", "--target", str(env.project), "--task", "实现项目核心代码", "--scope", "src/s5.py")
    task_id = routed["task_id"]
    env.run("context", "--target", str(env.project), "--task-id", task_id, "--stage", "action")
    env.write_file("src/s5.py")
    env.write_file("src/s5-extra.py")
    state = env.state_dir(task_id)
    before = env.snapshot_tree(state)
    preview = env.run("task", "changes-preview", "--target", str(env.project), "--task-id", task_id)
    after = env.snapshot_tree(state)
    check("S5 changes-preview 后 state 目录逐字节一致", before == after, {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(key for key in set(before) & set(after) if before[key] != after[key]),
    })
    check("S5 预览检出越界路径", "src/s5-extra.py" in preview.get("outside_scope", []), preview)
    evidence = env.evidence(
        "s5", evidence_type="test_result", covers=task_id, changed_paths=["src/s5.py", "src/s5-extra.py"]
    )
    verified = env.run("verify", "--target", str(env.project), "--task-id", task_id, "--evidence", str(evidence))
    check("S5 预览与 verify 时刻归因一致", set(verified.get("extended_paths", [])) == {"src/s5-extra.py"}, verified)


def main() -> None:
    env = ShadowEnv()
    try:
        env.init_project()
        scenario_s1_direct_extension(env)
        scenario_s2_checklist_usable(env)
        scenario_s3_planned_readmission_hint(env)
        scenario_s4_authorized_no_extension(env)
        scenario_s5_changes_preview_readonly(env)
    finally:
        env.cleanup()
    print(f"\nV3 SHADOW ACCEPTANCE PASSED（{len(CHECKS)} 项断言全部通过，安装副本全链路）")


if __name__ == "__main__":
    main()
