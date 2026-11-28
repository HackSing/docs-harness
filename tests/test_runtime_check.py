"""运行态验证证据包的合同测试：真实证据通过，空泛/缺项/未闭环被拒绝。"""

from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


class RuntimeCheckTest(HarnessTestBase):
    def write_evidence(self, packet_dir: Path, name: str, content: bytes) -> None:
        path = self.project / packet_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def write_packet(self, relative: str, packet: dict, images: dict[str, bytes] | None = None) -> str:
        self.write_json(relative, packet)
        packet_dir = Path(relative).parent
        self.write_evidence(packet_dir, "evidence/run.log", b"runtime log: success path executed\n" * 3)
        for name, content in (images or {}).items():
            self.write_evidence(packet_dir, f"evidence/{name}", content)
        return relative

    def base_packet(self, task: str = "smoke") -> dict:
        ref = ["evidence/run.log"]
        return {
            "schema_version": "docs-harness/runtime-verification/v1",
            "task": task,
            "surface": "cli",
            "risk": "simple",
            "environment": {
                "description": "Windows 11, Python 3.14.4, temporary project",
                "start_command": "python scripts/harness.py runtime check --packet <path>",
                "data_setup": "three fixture records created by the test helper",
                "mock": False,
            },
            "flows": [
                {
                    "name": "main flow",
                    "steps": ["create fixture", "run command", "read output"],
                    "expected": "command reports passed for valid input",
                    "observed": "stdout contained status=passed and checked evidence count 1",
                    "evidence_refs": ref,
                }
            ],
            "states": [
                self.state("success", "valid input exits 0", "exit code was 0 and status field was passed"),
                self.state("invalid_input", "bad input exits 2", "exit code was 2 with code runtime_packet_invalid"),
                self.state("runtime_error", "missing file exits 2", "missing packet returned runtime_packet_missing"),
            ],
            "data": [
                self.data("realistic", "one valid record", "record accepted", "output listed record id A-1"),
                self.data("empty", "zero records", "empty summary shown", "output said total=0 and exit 0"),
                self.data("invalid", "record without id", "validation error shown", "error text named missing field id"),
                self.data("boundary", "100 records", "summary stays readable", "output reported total=100 without truncation"),
            ],
            "ui": {"applicable": False, "reason": "CLI-only smoke test has no visual surface"},
            "probes": [
                {
                    "name": "truncated packet",
                    "intent": "edge",
                    "result": "truncated JSON returned line and column details",
                    "evidence_refs": ref,
                }
            ],
            "defects": [],
            "no_defect_rationale": "Two invalid and edge probes were exercised; both produced explicit errors and no silent success was observed.",
            "iterations": [
                {
                    "pass": 1,
                    "status": "passed",
                    "summary": "first pass exercised success, invalid and missing-file paths",
                    "evidence_refs": ref,
                }
            ],
            "uncovered": [],
            "conclusion": "CLI runtime path passed functional and error checks; no known uncovered behavior remains.",
        }

    def state(self, name: str, expected: str, observed: str, ref: list[str] | None = None) -> dict:
        return {
            "name": name,
            "applicable": True,
            "expected": expected,
            "observed": observed,
            "evidence_refs": ref or ["evidence/run.log"],
            "reason": None,
        }

    def data(self, scenario: str, input_value: str, expected: str, observed: str) -> dict:
        return {
            "scenario": scenario,
            "input": input_value,
            "expected": expected,
            "observed": observed,
            "evidence_refs": ["evidence/run.log"],
        }

    def ui_packet(self, task: str = "ui-smoke") -> dict:
        packet = self.base_packet(task)
        packet.update({"surface": "web_ui", "risk": "complex"})
        packet["environment"].update({
            "mock": True,
            "mock_rationale": "The page uses fixture records because the real backend is outside this task.",
            "mock_limitations": "Mock data cannot prove production latency or third-party API failures.",
        })
        packet["flows"].append({
            "name": "empty state recovery",
            "steps": ["open page with no records", "click retry", "see refreshed content"],
            "expected": "empty state offers a retry action",
            "observed": "retry button was visible and refreshed the list after one click",
            "evidence_refs": ["evidence/run.log"],
        })
        packet["states"].append(self.state(
            "empty", "empty state explains why there is no data", "empty illustration and create action were visible"
        ))
        packet["states"].append(self.state(
            "loading", "skeleton appears before data arrives", "skeleton rendered for 300ms before rows appeared"
        ))
        packet["states"].append(self.state(
            "error", "error state offers retry", "error banner showed retry and retry succeeded"
        ))
        packet["data"].append(self.data(
            "long", "a 120-character record title", "title truncates without breaking layout",
            "row kept one line and ellipsis appeared at the end"
        ))
        packet["ui"] = {
            "applicable": True,
            "reason": None,
            "viewports": [
                {"name": "desktop", "size": "1440x900", "evidence_refs": ["evidence/desktop.png"]},
                {"name": "mobile", "size": "390x844", "evidence_refs": ["evidence/mobile.png"]},
            ],
            "visual_checks": {
                "hierarchy": "page title is the strongest element, followed by primary action and rows",
                "spacing": "16px gaps between cards, 24px page padding at both viewports",
                "contrast": "primary button text passed the 4.5:1 contrast check",
                "responsive": "row actions wrapped below the title on mobile without overlap",
            },
            "interaction_checks": {
                "feedback": "button showed a spinner and disabled state during retry",
                "loading": "skeleton appeared for 300ms and was replaced by rows",
                "keyboard": "tab moved from search to retry, enter triggered retry",
                "error_recovery": "error banner retry recovered after the fixture was fixed",
            },
            "copy_checks": {
                "terminology": "empty state used records instead of backend entity names",
                "error_messages": "error banner said the list could not load and offered retry",
                "next_action": "empty state offered a create action and retry action",
                "no_internal_terms": "no error codes, variable names or internal service names were visible",
            },
            "accessibility_checks": {
                "focus_visible": "keyboard focus ring was visible on search and retry",
                "labels": "search input had a visible label and placeholder",
                "contrast": "body text and muted helper text both passed contrast checks",
                "keyboard_navigation": "all actions were reachable in tab order without a mouse",
            },
            "evidence_refs": ["evidence/desktop.png", "evidence/mobile.png"],
        }
        packet["probes"] = [
            {
                "name": "rapid retry",
                "intent": "recovery",
                "result": "two rapid clicks produced one request and a single recovery",
                "evidence_refs": ["evidence/run.log"],
            },
            {
                "name": "invalid record",
                "intent": "invalid",
                "result": "invalid record was isolated and the rest of the list remained usable",
                "evidence_refs": ["evidence/run.log"],
            },
        ]
        return packet

    def assert_rejected(self, relative: str, code: str) -> dict:
        payload = self.run_cli(
            "runtime", "check", "--target", str(self.project), "--packet", relative, expected=2
        )
        self.assertEqual(payload["status"], "failed")
        self.assertIn(code, [item["code"] for item in payload["errors"]], payload)
        return payload

    def test_valid_cli_packet_passes(self) -> None:
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", self.base_packet())
        payload = self.run_cli(
            "runtime", "check", "--target", str(self.project), "--packet", relative
        )
        self.assertEqual(payload["status"], "passed", payload)
        self.assertEqual(payload["root_kind"], "local")
        self.assertEqual(payload["checked"]["states"], 3)

    def test_valid_ui_packet_passes(self) -> None:
        packet = self.ui_packet()
        relative = self.write_packet(
            "docs/runtime-verification/ui-smoke/packet.json", packet,
            {"desktop.png": b"desktop-image" + b"d" * 2048, "mobile.png": b"mobile-image" + b"m" * 2048},
        )
        payload = self.run_cli(
            "runtime", "check", "--target", str(self.project), "--packet", relative
        )
        self.assertEqual(payload["status"], "passed", payload)
        self.assertEqual(payload["checked"]["viewports"], 2)

    def test_generic_observation_is_rejected(self) -> None:
        packet = self.base_packet()
        packet["flows"][0]["observed"] = "正常"
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_packet_text_invalid")

    def test_repeated_generic_observation_is_rejected(self) -> None:
        packet = self.base_packet()
        packet["flows"][0]["observed"] = "正常" * 6
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_packet_text_invalid")

    def test_copied_observation_is_rejected(self) -> None:
        packet = self.base_packet()
        packet["flows"][0]["observed"] = packet["flows"][0]["expected"]
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_packet_observation_copied")

    def test_missing_state_is_rejected(self) -> None:
        packet = self.base_packet()
        packet["states"] = [item for item in packet["states"] if item["name"] != "invalid_input"]
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_state_missing")

    def test_duplicate_flows_are_rejected(self) -> None:
        packet = self.base_packet()
        packet["flows"].append(copy.deepcopy(packet["flows"][0]))
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_flow_duplicate")

    def test_missing_evidence_is_rejected(self) -> None:
        packet = self.base_packet()
        packet["states"][0]["evidence_refs"] = []
        packet["flows"][0]["evidence_refs"] = ["evidence/missing.log"]
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_packet_evidence_missing")

    def test_mock_without_limitations_is_rejected(self) -> None:
        packet = self.base_packet()
        packet["environment"]["mock"] = True
        packet["environment"]["mock_rationale"] = "fixture records are used for the list"
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_packet_text_invalid")

    def test_ui_single_viewport_is_rejected(self) -> None:
        packet = self.ui_packet()
        packet["ui"]["viewports"] = packet["ui"]["viewports"][:1]
        packet["ui"]["evidence_refs"] = ["evidence/desktop.png"]
        relative = self.write_packet(
            "docs/runtime-verification/ui-smoke/packet.json", packet,
            {"desktop.png": b"desktop-image" + b"d" * 2048, "mobile.png": b"mobile-image" + b"m" * 2048},
        )
        self.assert_rejected(relative, "runtime_ui_viewports")

    def test_ui_duplicate_screenshot_is_rejected(self) -> None:
        packet = self.ui_packet()
        packet["ui"]["viewports"][1]["evidence_refs"] = ["evidence/desktop.png"]
        relative = self.write_packet(
            "docs/runtime-verification/ui-smoke/packet.json", packet,
            {"desktop.png": b"same-image" + b"x" * 2048},
        )
        self.assert_rejected(relative, "runtime_ui_viewports_duplicate")

    def test_ui_copy_dimension_is_required(self) -> None:
        packet = self.ui_packet()
        packet["ui"]["copy_checks"]["error_messages"] = "正常"
        relative = self.write_packet(
            "docs/runtime-verification/ui-smoke/packet.json", packet,
            {"desktop.png": b"desktop-image" + b"d" * 2048, "mobile.png": b"mobile-image" + b"m" * 2048},
        )
        self.assert_rejected(relative, "runtime_packet_text_invalid")

    def test_ui_accessibility_dimension_is_required(self) -> None:
        packet = self.ui_packet()
        del packet["ui"]["accessibility_checks"]
        relative = self.write_packet(
            "docs/runtime-verification/ui-smoke/packet.json", packet,
            {"desktop.png": b"desktop-image" + b"d" * 2048, "mobile.png": b"mobile-image" + b"m" * 2048},
        )
        self.assert_rejected(relative, "runtime_packet_required_field")

    def test_non_ui_cannot_claim_ui_evidence(self) -> None:
        packet = self.base_packet()
        packet["ui"] = {"applicable": True, "reason": None}
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_ui_unexpected")

    def test_defect_without_recheck_cannot_pass(self) -> None:
        packet = self.base_packet()
        packet["defects"] = [{
            "summary": "invalid input rendered a blank error banner",
            "severity": "major",
            "fix": "mapped validation failures to a readable message",
            "recheck": "re-ran invalid input and saw the message",
            "evidence_refs": ["evidence/run.log"],
        }]
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_defect_unclosed")

    def test_committed_packet_requires_complex_risk(self) -> None:
        packet = self.base_packet()
        relative = self.write_packet("docs/runtime-verification/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_packet_location_invalid")

    def test_local_packet_rejects_complex_risk(self) -> None:
        packet = self.base_packet()
        packet["risk"] = "complex"
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_packet_location_invalid")

    def test_closed_defect_loop_passes(self) -> None:
        packet = self.base_packet()
        packet["defects"] = [{
            "summary": "invalid input rendered a blank error banner",
            "severity": "major",
            "fix": "mapped validation failures to a readable message",
            "recheck": "re-ran invalid input and saw the message",
            "evidence_refs": ["evidence/run.log"],
        }]
        packet["iterations"] = [
            {
                "pass": 1,
                "status": "failed",
                "summary": "invalid input produced a blank banner",
                "evidence_refs": ["evidence/run.log"],
            },
            {
                "pass": 2,
                "status": "passed",
                "summary": "after the fix the banner explained the problem and next step",
                "evidence_refs": ["evidence/run.log"],
            },
        ]
        packet["no_defect_rationale"] = None
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        payload = self.run_cli(
            "runtime", "check", "--target", str(self.project), "--packet", relative
        )
        self.assertEqual(payload["status"], "passed", payload)
        self.assertEqual(payload["checked"]["iterations"], 2)

    def test_committed_evidence_cannot_be_gitignored(self) -> None:
        subprocess.run(
            ["git", "-C", str(self.project), "init"],
            capture_output=True, text=True, check=True,
        )
        packet = self.ui_packet()
        relative = self.write_packet(
            "docs/runtime-verification/ui-smoke/packet.json", packet,
            {"desktop.png": b"desktop-image" + b"d" * 2048, "mobile.png": b"mobile-image" + b"m" * 2048},
        )
        (self.project / "docs/runtime-verification/ui-smoke/evidence/.gitignore").write_text(
            "*\n", encoding="utf-8"
        )
        self.assert_rejected(relative, "runtime_packet_evidence_ignored")

    def test_packet_outside_allowed_roots_is_rejected(self) -> None:
        relative = self.write_packet("runtime/smoke/packet.json", self.base_packet())
        self.assert_rejected(relative, "runtime_packet_location_invalid")

    def test_unknown_field_is_rejected(self) -> None:
        packet = self.base_packet()
        packet["extra"] = "not allowed"
        relative = self.write_packet(".docs-harness/runtime/smoke/packet.json", packet)
        self.assert_rejected(relative, "runtime_packet_unknown_field")

    def test_missing_packet_is_structured_error(self) -> None:
        payload = self.run_cli(
            "runtime", "check", "--target", str(self.project),
            "--packet", ".docs-harness/runtime/missing/packet.json", expected=2,
        )
        self.assertEqual(payload["errors"][0]["code"], "runtime_packet_missing")

    def ui_images(self) -> dict[str, bytes]:
        return {
            "desktop.png": b"desktop-image" + b"d" * 2048,
            "mobile.png": b"mobile-image" + b"m" * 2048,
            "extra.png": b"extra-image" + b"e" * 2048,
        }

    def valid_visual_review(self) -> dict[str, object]:
        return {
            "reviewer": "product_visual_director_subagent",
            "verdict": "approved",
            "reviewed_screenshots": ["evidence/desktop.png", "evidence/mobile.png"],
            "findings": [
                "P2: desktop 1440x900 primary CTA hierarchy and 16px card spacing are clear with no clipping",
                "P2: mobile 390x844 error alert wraps cleanly and consumer copy gives a concrete retry action",
            ],
        }

    def test_ui_visual_review_subagent_and_fallback_pass(self) -> None:
        packet = self.ui_packet()
        packet["ui"]["visual_review"] = self.valid_visual_review()
        relative = self.write_packet("docs/runtime-verification/ui-smoke/packet.json", packet, self.ui_images())
        payload = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", relative)
        self.assertEqual(payload["status"], "passed", payload)

        fallback = self.ui_packet()
        fallback["task"] = "ui-fallback"
        fallback["ui"]["visual_review"] = {
            **self.valid_visual_review(),
            "reviewer": "fallback_self",
            "fallback_reason": "Current headless CI runner does not provide a multimodal subagent",
        }
        rel2 = self.write_packet("docs/runtime-verification/ui-fallback/packet.json", fallback, self.ui_images())
        payload2 = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", rel2)
        self.assertEqual(payload2["status"], "passed", payload2)

    def test_ui_visual_review_rejects_unapproved_fake_screenshots_and_generic_findings(self) -> None:
        # 1. changes_requested cannot pass closeout
        p1 = self.ui_packet()
        p1["ui"]["visual_review"] = {**self.valid_visual_review(), "verdict": "changes_requested"}
        r1 = self.write_packet("docs/runtime-verification/ui-smoke/packet.json", p1, self.ui_images())
        self.assert_rejected(r1, "runtime_ui_visual_review_unapproved")

        # 2. reviewed_screenshots not belonging to ui.viewports
        p2 = self.ui_packet()
        p2["ui"]["visual_review"] = {**self.valid_visual_review(), "reviewed_screenshots": ["evidence/desktop.png", "evidence/extra.png"]}
        r2 = self.write_packet("docs/runtime-verification/ui-smoke/packet.json", p2, self.ui_images())
        self.assert_rejected(r2, "runtime_ui_visual_review_screenshots_invalid")

        # 3. duplicate screenshot / single viewport
        p3 = self.ui_packet()
        p3["ui"]["visual_review"] = {**self.valid_visual_review(), "reviewed_screenshots": ["evidence/desktop.png", "evidence/desktop.png"]}
        r3 = self.write_packet("docs/runtime-verification/ui-smoke/packet.json", p3, self.ui_images())
        self.assert_rejected(r3, "runtime_ui_visual_review_screenshots_invalid")

        # 4. hollow generic finding & missing fallback_reason
        p4 = self.ui_packet()
        p4["ui"]["visual_review"] = {**self.valid_visual_review(), "reviewer": "fallback_self", "findings": ["通过"]}
        r4 = self.write_packet("docs/runtime-verification/ui-smoke/packet.json", p4, self.ui_images())
        res4 = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", r4, expected=2)
        self.assertIn("runtime_packet_text_invalid", {item["code"] for item in res4["errors"]})

        # 5. non-UI packet cannot declare ui.visual_review
        non_ui = self.base_packet()
        non_ui["ui"]["visual_review"] = self.valid_visual_review()
        r5 = self.write_packet(".docs-harness/runtime/smoke/packet.json", non_ui)
        self.assert_rejected(r5, "runtime_ui_unexpected")

    def test_ui_packet_with_acceptance_ref_requires_visual_review(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project), "--apply")
        acc_in = self.write_json(
            ".docs-harness/inputs/ui-acc.json",
            {
                "schema_version": "docs-harness/acceptance-target-input/v1",
                "title": "UI 页面验收",
                "key_symbols": ["UiPage", "validate_ui_visual_review"],
                "objective": "验证 UI 页面在双视口下通过产品视觉总监子智能体审查。",
                "criteria": [{
                    "id": "ui.flow",
                    "title": "页面交互与视觉审查",
                    "acceptance_type": "behavior_acceptance",
                    "layer": "L3",
                    "evidence_layer": "local_runtime",
                }],
            },
        )
        self.run_cli(
            "acceptance", "create", "--target", str(self.project),
            "--input", str(acc_in.relative_to(self.project)),
            "--output", "docs/acceptance/ui-acc.json",
        )
        pkt = self.ui_packet()
        pkt["acceptance_ref"] = "docs/acceptance/ui-acc.json"
        rel = self.write_packet("docs/runtime-verification/ui-smoke/packet.json", pkt, self.ui_images())
        self.assert_rejected(rel, "runtime_ui_visual_review_missing")

        pkt["ui"]["visual_review"] = self.valid_visual_review()
        rel = self.write_packet("docs/runtime-verification/ui-smoke/packet.json", pkt, self.ui_images())
        ok = self.run_cli("runtime", "check", "--target", str(self.project), "--packet", rel)
        self.assertEqual(ok["status"], "passed", ok)


if __name__ == "__main__":
    unittest.main()
