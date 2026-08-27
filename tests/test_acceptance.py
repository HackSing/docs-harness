"""Acceptance 域：类型/层级耦合、失败归因、用户确认门与生命周期。"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class AcceptanceTest(HarnessTestBase):
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

if __name__ == "__main__":
    unittest.main()
