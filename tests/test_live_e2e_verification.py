"""大任务全量实机闭环（live_e2e）：Acceptance 冻结判据 ↔ Runtime 对齐 ↔ assets-check 合同测试。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class LiveE2EVerificationTest(HarnessTestBase):
    def live_e2e_config(self, **overrides: Any) -> dict[str, Any]:
        config: dict[str, Any] = {
            "real_dependencies": ["测试环境云端大模型 API", "测试环境 PostgreSQL 数据库"],
            "environment": "staging-01 测试环境（独立测试租户与真实数据库实例）",
            "isolation_and_cleanup": "使用独立测试账号 test_e2e，单次费用上限 5 元，完成后按租户 ID 清理",
            "deploy_command": "docker compose -f staging.yml up -d --build",
        }
        config.update(overrides)
        return config

    def live_acceptance_target(self, **overrides: Any) -> dict[str, Any]:
        target: dict[str, Any] = {
            "schema_version": "docs-harness/acceptance-target-input/v1",
            "title": "大版本全量实机闭环验收",
            "key_symbols": ["LIVE_E2E_FIELDS", "validate_acceptance_alignment"],
            "objective": "在测试环境真实调用云端模型与数据库跑完全部主流程并修复闭环。",
            "live_e2e": self.live_e2e_config(),
            "criteria": [
                {
                    "id": "flow.chat",
                    "title": "对话模块真实调用云端模型并流式返回",
                    "acceptance_type": "behavior_acceptance",
                    "layer": "L3",
                    "evidence_layer": "local_runtime",
                    "pass_criteria": "输入真实问题后返回非空云端模型回复且延迟低于 10 秒并写入消息表",
                    "fail_criteria": "返回空文本、命中 mock 占位响应、报错或未落库均判失败",
                },
                {
                    "id": "flow.db_save",
                    "title": "业务表单提交真实写入并刷新回读",
                    "acceptance_type": "behavior_acceptance",
                    "layer": "L3",
                    "evidence_layer": "local_runtime",
                    "pass_criteria": "提交后 HTTP 200 且刷新页面后可从真实数据库回读同一记录",
                    "fail_criteria": "提交报 4xx/5xx、刷新后数据丢失或字段错位均判失败",
                },
            ],
        }
        target.update(overrides)
        return target

    def create_live_acceptance(self, name: str = "big-release", **overrides: Any) -> str:
        self.run_cli("project", "init", "--target", str(self.project), "--apply")
        target = self.live_acceptance_target(**overrides)
        input_path = self.write_json(f".docs-harness/inputs/{name}-acc.json", target)
        output = f"docs/acceptance/{name}.json"
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(input_path.relative_to(self.project)),
            "--output", output,
        )
        return output

    def write_live_packet(
        self,
        relative: str,
        packet: dict[str, Any],
        logs: dict[str, str] | None = None,
    ) -> str:
        packet_path = self.project / relative
        evidence_dir = packet_path.parent / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        for fname, text in (logs or {"run.log": "staging-build-102 exit 0 real cloud model + db verified\n"}).items():
            (evidence_dir / fname).write_text(text, encoding="utf-8")
        self.write_json(relative, packet)
        return relative

    def live_packet(self, acceptance_ref: str, *, task: str = "big-release") -> dict[str, Any]:
        return {
            "schema_version": "docs-harness/runtime-verification/v1",
            "task": task,
            "surface": "api",
            "risk": "complex",
            "acceptance_ref": acceptance_ref,
            "environment": {
                "description": "Staging server with live cloud LLM API and staging PostgreSQL",
                "start_command": "docker compose -f staging.yml up -d --build",
                "data_setup": "Seeded isolated tenant test_e2e and cleaned up after run",
                "mock": False,
            },
            "flows": [
                {
                    "name": "real cloud chat flow",
                    "criterion_id": "flow.chat",
                    "steps": ["send live prompt to staging chat endpoint", "verify DB message row"],
                    "expected": "chat endpoint returns live cloud reply and persists row in DB",
                    "observed": "trace req-8812 returned 142-char reply in 2.3s and inserted msg_id=901",
                    "evidence_refs": ["evidence/run.log"],
                },
                {
                    "name": "real db save and reload flow",
                    "criterion_id": "flow.db_save",
                    "steps": ["submit order form to staging API", "re-query record after reload"],
                    "expected": "HTTP 200 and re-queried payload matches submitted fields",
                    "observed": "POST /orders returned 200 with id=44 and GET /orders/44 matched fields",
                    "evidence_refs": ["evidence/run.log"],
                },
            ],
            "states": [
                {"name": "success", "applicable": True, "expected": "valid call returns 200", "observed": "chat and order endpoints returned HTTP 200 with persisted IDs", "evidence_refs": ["evidence/run.log"], "reason": None},
                {"name": "validation_error", "applicable": True, "expected": "empty payload returns 400", "observed": "POST /orders with empty body returned 400 with field message", "evidence_refs": ["evidence/run.log"], "reason": None},
                {"name": "auth_error", "applicable": True, "expected": "missing token returns 401", "observed": "unauthenticated call returned 401 and did not hit cloud model", "evidence_refs": ["evidence/run.log"], "reason": None},
                {"name": "not_found", "applicable": True, "expected": "missing id returns 404", "observed": "GET /orders/999999 returned 404 with order_not_found payload", "evidence_refs": ["evidence/run.log"], "reason": None},
            ],
            "data": [
                {"scenario": "realistic", "input": "normal Chinese user query and order payload", "expected": "persists and responds", "observed": "stored msg_id=901 and order id=44 cleanly in staging DB", "evidence_refs": ["evidence/run.log"]},
                {"scenario": "empty", "input": "empty string body", "expected": "rejected with 400", "observed": "API returned 400 validation_error without touching DB", "evidence_refs": ["evidence/run.log"]},
                {"scenario": "invalid", "input": "negative amount -5", "expected": "rejected with 400", "observed": "API returned 400 amount_must_be_positive", "evidence_refs": ["evidence/run.log"]},
                {"scenario": "boundary", "input": "max-length 2000-char prompt", "expected": "handled without truncation crash", "observed": "cloud model processed 2000-char prompt and persisted full row", "evidence_refs": ["evidence/run.log"]},
            ],
            "ui": {"applicable": False, "reason": "Staging API and cloud/DB integration sweep with no UI edits"},
            "probes": [
                {"name": "expired auth token probe", "intent": "permission", "result": "expired JWT returned 401 before invoking upstream cloud LLM", "evidence_refs": ["evidence/run.log"]},
                {"name": "duplicate submit probe", "intent": "recovery", "result": "same idempotency key returned original order id=44 without duplicate row", "evidence_refs": ["evidence/run.log"]},
            ],
            "defects": [
                {
                    "summary": "order reload returned stale timezone string on staging-build-101",
                    "severity": "major",
                    "fix": "normalized PostgreSQL timestamptz serializer to ISO-8601 UTC",
                    "recheck": "redeployed staging-build-102 and verified GET /orders/44 + flow.chat regression",
                    "evidence_refs": ["evidence/run.log"],
                }
            ],
            "no_defect_rationale": None,
            "iterations": [
                {
                    "pass": 1,
                    "status": "failed",
                    "deploy_ref": "staging-build-101",
                    "summary": "flow.chat passed on staging-build-101; flow.db_save failed timezone mismatch",
                    "evidence_refs": ["evidence/run.log"],
                },
                {
                    "pass": 2,
                    "status": "passed",
                    "deploy_ref": "staging-build-102",
                    "rechecked_criteria": ["flow.db_save", "flow.chat"],
                    "summary": "redeployed staging-build-102; both flow.db_save and flow.chat passed on real env",
                    "evidence_refs": ["evidence/run.log"],
                },
            ],
            "uncovered": [],
            "conclusion": "All frozen live_e2e criteria passed on staging-build-102 with real cloud LLM and PostgreSQL.",
        }

    def test_live_e2e_acceptance_create_render_and_amend(self) -> None:
        acc_ref = self.create_live_acceptance()
        asset = json.loads((self.project / acc_ref).read_text(encoding="utf-8"))
        self.assertEqual(asset["live_e2e"]["max_fix_rounds"], 3)
        self.assertTrue(asset["live_e2e"]["confirm_before_run"])
        md = (self.project / "docs/acceptance/big-release.md").read_text(encoding="utf-8")
        self.assertIn("## 实机全量验收契约（live_e2e）", md)
        self.assertIn("执行前确认门：是", md)
        self.assertIn("- 通过标准：", md)
        self.assertIn("- 失败判定：", md)

        revised = self.live_acceptance_target(
            live_e2e=self.live_e2e_config(max_fix_rounds=2, confirm_before_run=False)
        )
        rev_input = self.write_json(".docs-harness/inputs/amend-live.json", revised)
        amended = self.run_cli(
            "acceptance", "amend", "--target", str(self.project),
            "--acceptance", acc_ref, "--input", str(rev_input.relative_to(self.project)),
            "--reason", "用户已授权直接连跑并收紧熔断轮次",
        )
        self.assertEqual(amended["revision"], 2)
        updated = json.loads((self.project / acc_ref).read_text(encoding="utf-8"))
        self.assertEqual(updated["live_e2e"]["max_fix_rounds"], 2)
        self.assertFalse(updated["live_e2e"]["confirm_before_run"])

    def test_live_e2e_acceptance_rejects_invalid_expectations_and_config(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project), "--apply")
        bad = self.live_acceptance_target(
            live_e2e=self.live_e2e_config(max_fix_rounds=0, rogue="x"),
            criteria=[
                {
                    "id": "flow.only_pass",
                    "title": "只写通过标准",
                    "acceptance_type": "behavior_acceptance",
                    "layer": "L3",
                    "evidence_layer": "local_runtime",
                    "pass_criteria": "请求返回 200 且数据落库",
                },
                {
                    "id": "flow.same",
                    "title": "通过与失败相同",
                    "acceptance_type": "behavior_acceptance",
                    "layer": "L3",
                    "evidence_layer": "local_runtime",
                    "pass_criteria": "接口返回状态码 200 且写入表",
                    "fail_criteria": "接口返回状态码 200 且写入表",
                },
            ],
        )
        inp = self.write_json(".docs-harness/inputs/bad-live.json", bad)
        payload = self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(inp.relative_to(self.project)),
            "--output", "docs/acceptance/bad-live.json", "--dry-run", expected=1,
        )
        messages = "\n".join(item["message"] for item in payload["errors"])
        self.assertIn("成对填写", messages)
        self.assertIn("不能相同", messages)
        self.assertIn("未注册字段：rogue", messages)

        no_live_criteria = self.live_acceptance_target(
            criteria=[{
                "id": "c.static",
                "title": "仅静态检查",
                "acceptance_type": "contract_check",
                "layer": "L1",
            }]
        )
        inp2 = self.write_json(".docs-harness/inputs/no-live.json", no_live_criteria)
        payload2 = self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(inp2.relative_to(self.project)),
            "--output", "docs/acceptance/no-live.json", "--dry-run", expected=1,
        )
        self.assertTrue(any("local_runtime 或 real_device" in item["message"] for item in payload2["errors"]))

    def test_live_e2e_full_loop_record_settle_and_assets_check_pass(self) -> None:
        acc_ref = self.create_live_acceptance()
        pkt_ref = self.write_live_packet(
            "docs/runtime-verification/big-release/packet.json",
            self.live_packet(acc_ref),
        )
        checked = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", pkt_ref)
        self.assertEqual(checked["status"], "passed", checked)
        self.assertEqual(checked["warnings"], [])

        settle_in = self.write_json(
            ".docs-harness/inputs/settle-live.json",
            {
                "schema_version": "docs-harness/acceptance-settle-input/v1",
                "objective": "在测试环境真实调用云端模型与数据库跑完全部主流程并修复闭环。",
                "records": [
                    {
                        "criterion_id": cid,
                        "acceptance_type": "behavior_acceptance",
                        "status": "passed",
                        "layer": "L3",
                        "evidence_layer": "local_runtime",
                        "method": f"staging-build-102 实机跑通 {cid} 并通过 runtime check",
                        "evidence_refs": [pkt_ref],
                    }
                    for cid in ("flow.chat", "flow.db_save")
                ],
            },
        )
        settled = self.run_cli(
            "acceptance", "settle", "--target", str(self.project),
            "--acceptance", acc_ref, "--status", "passed",
            "--input", str(settle_in.relative_to(self.project)),
        )
        self.assertEqual(settled["status"], "passed")
        assets = self.run_cli("assets-check", "--target", str(self.project), "--fast", "--strict")
        self.assertEqual(assets["status"], "passed", assets)

    def test_live_e2e_runtime_rejects_mock_uncovered_deploy_and_tampering(self) -> None:
        acc_ref = self.create_live_acceptance()

        # 1. mock=True forbidden
        pkt_mock = self.live_packet(acc_ref, task="mock-bad")
        pkt_mock["environment"]["mock"] = True
        pkt_mock["environment"]["mock_rationale"] = "tried to stub cloud model instead of calling real API"
        pkt_mock["environment"]["mock_limitations"] = "cannot prove real cloud model schema or DB commit"
        ref = self.write_live_packet("docs/runtime-verification/mock-bad/packet.json", pkt_mock)
        res = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", ref, expected=2)
        self.assertIn("runtime_live_e2e_mock_forbidden", {e["code"] for e in res["errors"]})

        # 2. uncovered criterion_id
        pkt_gap = self.live_packet(acc_ref, task="gap-bad")
        pkt_gap["flows"][1].pop("criterion_id")
        ref = self.write_live_packet("docs/runtime-verification/gap-bad/packet.json", pkt_gap)
        res = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", ref, expected=2)
        self.assertIn("runtime_live_e2e_criteria_uncovered", {e["code"] for e in res["errors"]})
        self.assertTrue(any("flow.db_save" in e["message"] for e in res["errors"]))

        # 3. unchanged deploy_ref and missing rechecked_criteria after defect
        pkt_dep = self.live_packet(acc_ref, task="dep-bad")
        pkt_dep["iterations"][1]["deploy_ref"] = "staging-build-101"
        pkt_dep["iterations"][1].pop("rechecked_criteria")
        ref = self.write_live_packet("docs/runtime-verification/dep-bad/packet.json", pkt_dep)
        res = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", ref, expected=2)
        codes = {e["code"] for e in res["errors"]}
        self.assertIn("runtime_live_e2e_deploy_unchanged", codes)
        self.assertIn("runtime_live_e2e_final_regression_missing", codes)

        # 4. local-only path forbidden for live_e2e
        pkt_local = self.live_packet(acc_ref, task="local-bad")
        pkt_local["risk"] = "simple"
        ref = self.write_live_packet(".docs-harness/runtime/local-bad/packet.json", pkt_local)
        res = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", ref, expected=2)
        self.assertIn("runtime_live_e2e_location_invalid", {e["code"] for e in res["errors"]})

        # 5. tampered Acceptance fingerprint rejected
        acc_path = self.project / acc_ref
        tampered = json.loads(acc_path.read_text(encoding="utf-8"))
        tampered["criteria"][0]["pass_criteria"] = "偷偷把通过标准改松"
        acc_path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2), encoding="utf-8")
        pkt_ok = self.live_packet(acc_ref, task="tamper-check")
        ref = self.write_live_packet("docs/runtime-verification/tamper-check/packet.json", pkt_ok)
        res = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", ref, expected=2)
        self.assertIn("runtime_acceptance_fingerprint_invalid", {e["code"] for e in res["errors"]})

    def test_live_e2e_warns_when_failed_rounds_exceed_max_fix_rounds(self) -> None:
        acc_ref = self.create_live_acceptance(
            name="rounds-warn", live_e2e=self.live_e2e_config(max_fix_rounds=1)
        )
        pkt = self.live_packet(acc_ref, task="rounds-warn")
        pkt["iterations"] = [
            {"pass": 1, "status": "failed", "deploy_ref": "staging-build-101", "summary": "first run failed on timezone format", "evidence_refs": ["evidence/run.log"]},
            {"pass": 2, "status": "failed", "deploy_ref": "staging-build-102", "summary": "second run failed on retry timeout", "evidence_refs": ["evidence/run.log"]},
            {"pass": 3, "status": "passed", "deploy_ref": "staging-build-103", "rechecked_criteria": ["flow.db_save", "flow.chat"], "summary": "third run passed all flows on staging-build-103", "evidence_refs": ["evidence/run.log"]},
        ]
        ref = self.write_live_packet("docs/runtime-verification/rounds-warn/packet.json", pkt)
        res = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", ref)
        self.assertEqual(res["status"], "passed")
        self.assertIn("runtime_live_e2e_rounds_exceeded", {w["code"] for w in res["warnings"]})

    def test_acceptance_record_and_assets_check_enforce_runtime_packet_gate(self) -> None:
        acc_ref = self.create_live_acceptance(name="gate-check")
        plain_log = self.project / "docs/acceptance/evidence/plain.log"
        plain_log.parent.mkdir(parents=True, exist_ok=True)
        plain_log.write_text("manual run passed without packet\n", encoding="utf-8")

        # 1. live_e2e criterion cannot pass with only a plain log
        rec_plain = self.write_json(
            ".docs-harness/inputs/rec-plain.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.chat",
                "objective": "在测试环境真实调用云端模型与数据库跑完全部主流程并修复闭环。",
                "acceptance_type": "behavior_acceptance",
                "status": "passed",
                "layer": "L3",
                "evidence_layer": "local_runtime",
                "method": "only wrote a plain log",
                "evidence_refs": ["docs/acceptance/evidence/plain.log"],
            },
        )
        rejected = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(rec_plain.relative_to(self.project)),
            "--acceptance", acc_ref, expected=1,
        )
        self.assertEqual(rejected["code"], "acceptance_live_e2e_packet_required")

        # 2. broken committed packet fails BOTH acceptance record AND assets-check
        bad_pkt = self.live_packet(acc_ref, task="broken-gate")
        bad_pkt["flows"][0]["observed"] = "通过"
        bad_ref = self.write_live_packet("docs/runtime-verification/broken-gate/packet.json", bad_pkt)
        rec_bad = self.write_json(
            ".docs-harness/inputs/rec-bad.json",
            {
                "schema_version": "docs-harness/acceptance-input/v3",
                "criterion_id": "flow.chat",
                "objective": "在测试环境真实调用云端模型与数据库跑完全部主流程并修复闭环。",
                "acceptance_type": "behavior_acceptance",
                "status": "passed",
                "layer": "L3",
                "evidence_layer": "local_runtime",
                "method": "referenced broken packet",
                "evidence_refs": [bad_ref],
            },
        )
        rejected_pkt = self.run_cli(
            "acceptance", "record", "--target", str(self.project),
            "--input", str(rec_bad.relative_to(self.project)),
            "--acceptance", acc_ref, expected=2,
        )
        self.assertEqual(rejected_pkt["code"], "acceptance_runtime_packet_invalid")

        assets_failed = self.run_cli(
            "assets-check", "--target", str(self.project), "--fast", expected=1
        )
        self.assertTrue(
            any("docs/runtime-verification/broken-gate/packet.json" in item for item in assets_failed["failures"]),
            assets_failed["failures"],
        )

    def test_criterion_id_requires_acceptance_ref_and_must_exist(self) -> None:
        acc_ref = self.create_live_acceptance(name="cid-check")
        pkt_no_ref = self.live_packet(acc_ref, task="no-ref")
        pkt_no_ref.pop("acceptance_ref")
        ref1 = self.write_live_packet("docs/runtime-verification/no-ref/packet.json", pkt_no_ref)
        res1 = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", ref1, expected=2)
        self.assertIn("runtime_acceptance_ref_required", {e["code"] for e in res1["errors"]})

        pkt_unknown = self.live_packet(acc_ref, task="unknown-cid")
        pkt_unknown["flows"][0]["criterion_id"] = "flow.nonexistent"
        ref2 = self.write_live_packet("docs/runtime-verification/unknown-cid/packet.json", pkt_unknown)
        res2 = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", ref2, expected=2)
        self.assertIn("runtime_acceptance_criterion_unknown", {e["code"] for e in res2["errors"]})


if __name__ == "__main__":
    unittest.main()
