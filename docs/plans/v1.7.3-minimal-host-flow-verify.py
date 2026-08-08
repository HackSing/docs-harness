#!/usr/bin/env python3
"""v1.7.3 最小宿主流程验证（可重跑）：前置清单 + 实时铸证 → 一次 verify 通过。

在临时项目工作区用安装副本（project/scripts/harness.py）走最小闭环：

  M1 准入即得前置清单：evidence_checklist 四段齐全、骨架已预生成含 _instructions、
     pending_context_receipts 置位 action
  M2 按 pending 加载上下文后，三处响应 pending_context_receipts 清零
  M3 宿主按清单执行中实时铸 evidence-declaration/v1（只给语义体），
     verify 一次通过，控制器代铸绑定（producer=host_declaration，trust_level=verified）
  M4 反例：声明虚报未实际变化的路径 → stale_evidence 精确拦下，按真实写入重铸即过
  M5 铸证后同路径多次再修改仍一次过（绑定在 verify 时刻代铸，天然免疫 stale）

任一条失败即退出码 1；全部通过输出 MINIMAL HOST FLOW PASSED。
"""
from __future__ import annotations

import importlib.util
import json
import os
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
        for category in ("product", "development", "testing", "design"):
            (feature_root / f"{category}.md").write_text(
                f"# 项目核心：{category}事实\n\n## 当前状态\n\n已由测试项目确认的真实事实和当前边界。\n",
                encoding="utf-8",
            )
        knowledge_map = {
            "schema_version": "docs-harness/knowledge-map/v1",
            "knowledge_level": "L2",
            "reviewed_revision": "minimal-fixture",
            "features": [
                {
                    "feature_id": "project-core",
                    "name": "项目核心",
                    "aliases": ["项目"],
                    "feature_type": "platform_capability",
                    "status": "implemented",
                    "scope_patterns": ["**"],
                    "documents": {c: f"docs/features/project-core/{c}.md" for c in ("product", "development", "testing", "design")},
                    "shared_refs": [],
                    "dependencies": [],
                    "known_gaps": [],
                }
            ],
        }
        (self.project / "docs" / "knowledge-map.json").write_text(
            json.dumps(knowledge_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        for job in HARNESS_MODULE.list_background_jobs(self.project):
            job_root, current = HARNESS_MODULE.read_knowledge_job(self.project, job["job_id"])
            HARNESS_MODULE.refresh_knowledge_job_baseline(self.project, current)
            HARNESS_MODULE.write_background_job(self.project, job_root, current)

    def make_facts_meaningful(self) -> None:
        path = self.project / "docs" / "features" / "project-core" / "development.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n已由项目确认的真实事实。\n", encoding="utf-8")

    def write_file(self, relative: str, content: str = "VALUE = 1\n") -> None:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def state_dir(self, task_id: str) -> Path:
        return self.project / ".docs-harness" / "runs" / task_id

    def declaration(self, name: str, evidence_type: str, write_set: list[str]) -> Path:
        """宿主实时铸证通道：只给语义体，绑定字段由控制器在 verify 代铸。"""
        return self.write_json(
            f"declaration-{name}.json",
            {
                "schema_version": "docs-harness/evidence-declaration/v1",
                "type": evidence_type,
                "write_set": write_set,
                "conclusion": "按前置清单完成验证",
            },
        )


def main() -> None:
    env = ShadowEnv()
    try:
        env.init_project()
        env.make_facts_meaningful()

        # ---- M1：准入即得前置清单（checklist 四段 + 骨架预生成 + pending 置位）----
        routed = env.run(
            "run", "--target", str(env.project), "--task", "实现项目核心代码", "--scope", "src/core.py"
        )
        task_id = routed["task_id"]
        checklist = routed["evidence_checklist"]
        check("M1 evidence_checklist 四段齐全", set(checklist) == {"required", "conditional", "required_receipts", "skeletons"}, checklist)
        check("M1 required 非空且 skeletons 一一对应", bool(checklist["required"]) and len(checklist["skeletons"]) == len(checklist["required"]), checklist)
        for etype in checklist["required"]:
            skeleton_path = Path(str(env.state_dir(task_id) / "templates" / f"evidence-{etype.replace('_', '-')}-skeleton.json"))
            check(f"M1 骨架已预生成：{etype}", skeleton_path.exists(), skeleton_path)
            skeleton = json.loads(skeleton_path.read_text(encoding="utf-8"))
            check(f"M1 骨架含 _instructions 指引：{etype}", bool(skeleton.get("_instructions")), skeleton)
        check("M1 pending_context_receipts 置位 action", "action" in routed["pending_context_receipts"], routed["pending_context_receipts"])

        # ---- M2：按 pending 逐阶段加载上下文后清零 ----
        for stage in routed["pending_context_receipts"]:
            env.run("context", "--target", str(env.project), "--task-id", task_id, "--stage", stage)
        status = env.run("task", "status", "--target", str(env.project), "--task-id", task_id)
        check("M2 加载 action 上下文后 pending 清零", status["pending_context_receipts"] == [], status["pending_context_receipts"])
        check("M2 三处 checklist 一致（task status）", status["evidence_checklist"] == checklist, status["evidence_checklist"])

        # ---- M3：执行中实时铸 declaration → 一次 verify 通过 ----
        env.write_file("src/core.py")
        declarations = [env.declaration(f"m3-{etype}", etype, ["src/core.py"]) for etype in checklist["required"]]
        argv = ["verify", "--target", str(env.project), "--task-id", task_id]
        for path in declarations:
            argv += ["--evidence", str(path)]
        verified = env.run(*argv)
        check("M3 按前置清单实时铸证一次 verify 通过", verified["control_status"] == "complete", verified)
        check("M3 无 reason_code 往返", verified.get("reason_code") is None, verified.get("reason_code"))
        index = json.loads((env.state_dir(task_id) / "evidence-index.json").read_text(encoding="utf-8"))
        minted = {item["type"]: item for item in index["evidence"]}
        for etype in checklist["required"]:
            check(f"M3 控制器代铸绑定：{etype}", minted[etype]["producer"] == {"adapter": "docs-harness", "capability": "host_declaration"}, minted.get(etype))
            check(f"M3 代铸信任级 verified：{etype}", minted[etype]["trust_level"] == "verified", minted.get(etype))

        # ---- M4：反例——声明虚报未实际变化的路径 → stale_evidence 精确拦下 ----
        routed2 = env.run("run", "--target", str(env.project), "--task", "实现项目核心代码", "--scope", "src/m4.py")
        task_id2 = routed2["task_id"]
        checklist2 = routed2["evidence_checklist"]
        for stage in routed2["pending_context_receipts"]:
            env.run("context", "--target", str(env.project), "--task-id", task_id2, "--stage", stage)
        env.write_file("src/m4.py")
        overstated = env.declaration("m4-overstated", checklist2["required"][0], ["src/m4.py", "src/never-touched.py"])
        blocked = env.run(
            "verify", "--target", str(env.project), "--task-id", task_id2,
            "--evidence", str(overstated), expected=2,
        )
        check("M4 虚报未变化路径被 stale_evidence 拦下", blocked.get("code") == "stale_evidence", blocked.get("code"))
        flagged = {item["path"] for item in blocked.get("missing_items", [])}
        check("M4 精确指出虚报路径", flagged == {"src/never-touched.py"}, blocked.get("missing_items"))
        fresh = [env.declaration(f"m4-fresh-{etype}", etype, ["src/m4.py"]) for etype in checklist2["required"]]
        argv2 = ["verify", "--target", str(env.project), "--task-id", task_id2]
        for path in fresh:
            argv2 += ["--evidence", str(path)]
        verified2 = env.run(*argv2)
        check("M4 按真实写入重铸声明即过", verified2["control_status"] == "complete", verified2)

        # ---- M5：铸证后同路径多次再修改 → 声明绑定在 verify 时刻代铸，天然免疫 stale ----
        routed3 = env.run("run", "--target", str(env.project), "--task", "实现项目核心代码", "--scope", "src/m5.py")
        task_id3 = routed3["task_id"]
        checklist3 = routed3["evidence_checklist"]
        for stage in routed3["pending_context_receipts"]:
            env.run("context", "--target", str(env.project), "--task-id", task_id3, "--stage", stage)
        env.write_file("src/m5.py")
        early = env.declaration("m5-early", checklist3["required"][0], ["src/m5.py"])
        env.write_file("src/m5.py", "VALUE = 2  # 铸证后第一次改\n")
        env.write_file("src/m5.py", "VALUE = 3  # 铸证后第二次改\n")
        verified3 = env.run("verify", "--target", str(env.project), "--task-id", task_id3, "--evidence", str(early))
        check("M5 铸证后多次改同路径仍一次过（绑定 verify 时代铸）", verified3["control_status"] == "complete", verified3.get("control_status"))
    finally:
        env.cleanup()
    print(f"\nMINIMAL HOST FLOW PASSED（{len(CHECKS)} 项断言全部通过，安装副本全链路）")


if __name__ == "__main__":
    main()
