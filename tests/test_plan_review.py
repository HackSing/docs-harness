"""Plan blind review prompt builder tests."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT  # noqa: E402


class PlanReviewPromptTest(HarnessTestBase):
    def test_frozen_full_plan_generates_both_zero_context_prompts_without_side_effects(self) -> None:
        self.create_full_plan(acceptance_required=True, knowledge_impact="unchanged", basename="blind-target")
        self.write_lines("docs/contracts.md", ["# Contracts", "Contract body"])
        self.write_lines("src/sample.py", ["def run():", "    return 1"])
        before = self.snapshot_project()

        payload = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--plan", "docs/plans/blind-target.json",
            "--lens", "all",
            "--context-ref", "docs/contracts.md",
            "--context-ref", "src",
            "--context-ref", "docs/contracts.md",
        )

        self.assertEqual(self.snapshot_project(), before)
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["lens"], "all")
        self.assertEqual(payload["warnings"], [])
        self.assertEqual(payload["source"]["kind"], "frozen_plan")
        self.assertEqual(payload["source"]["plan_level"], "full")
        self.assertEqual(payload["context_refs"], ["docs/contracts.md", "src"])
        self.assertTrue(payload["recommended_execution"]["forbid_fork_from_coordinator"])
        self.assertEqual(
            [item["lens"] for item in payload["prompts"]],
            ["comprehension", "implementation_readiness"],
        )
        for item in payload["prompts"]:
            self.assertIn("NEVER fork from coordinator", item["prompt"])
            self.assertIn("- docs/contracts.md", item["prompt"])
            self.assertIn("- src", item["prompt"])
        self.assertIn("VERDICT: PASS | REVISE", payload["prompts"][0]["prompt"])
        self.assertIn("ZERO-DECISION RULE", payload["prompts"][1]["prompt"])
        self.assertIn("VERDICT: READY | NOT_READY", payload["prompts"][1]["prompt"])

    def test_single_lens_comprehension_and_empty_context_allowlist(self) -> None:
        self.create_full_plan(acceptance_required=False, knowledge_impact="unchanged", basename="single-lens")
        payload = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--plan", "docs/plans/single-lens.json",
            "--lens", "implementation_readiness",
        )
        self.assertEqual(len(payload["prompts"]), 1)
        self.assertEqual(payload["prompts"][0]["lens"], "implementation_readiness")
        self.assertEqual(payload["context_refs"], [])
        self.assertIn("NONE (Plan Packet only", payload["prompts"][0]["prompt"])

    def test_pre_freeze_json_and_markdown_drafts_supported(self) -> None:
        draft_json = self.write_json(
            "inputs/draft-brief.json",
            {
                "title": "轻量草案",
                "key_symbols": ["plan_review_prompt", "build_review_prompts"],
                "objective": "验证 brief 草案警告",
                "scope": "scripts/plan_review.py",
                "steps": "1. 写草案 2. 生成提示词",
                "acceptance": "运行 focused test",
            },
        )
        brief_payload = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--content", str(draft_json),
        )
        self.assertEqual(brief_payload["source"]["kind"], "draft_json")
        self.assertEqual(brief_payload["source"]["plan_level"], "brief")
        self.assertEqual(len(brief_payload["warnings"]), 1)
        self.assertIn("brief", brief_payload["warnings"][0])

        self.write_lines("drafts/pre-freeze.md", ["# Draft RFC", "", "## Goal", "Verify markdown draft."])
        md_payload = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--content", "drafts/pre-freeze.md",
            "--lens", "comprehension",
        )
        self.assertEqual(md_payload["source"]["kind"], "draft_markdown")
        self.assertEqual(md_payload["source"]["title"], "Draft RFC")
        self.assertEqual(len(md_payload["prompts"]), 1)
        self.assertIn("Verify markdown draft.", md_payload["prompts"][0]["prompt"])

    def test_handwritten_markdown_plan_supported(self) -> None:
        self.write_lines(
            "docs/plans/handwritten.md",
            [
                "# Handwritten Migration Plan",
                "",
                "> 状态：有效",
                "",
                "Manual plan body.",
            ],
        )
        payload = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--plan", "docs/plans/handwritten.md",
        )
        self.assertEqual(payload["source"]["kind"], "handwritten_markdown")
        self.assertEqual(payload["source"]["title"], "Handwritten Migration Plan")

    def test_installed_copy_runs_plan_review_prompt(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project), "--apply")
        self.assertTrue((self.project / "scripts" / "plan_review.py").is_file())
        self.write_lines("drafts/installed-draft.md", ["# Installed Check", "", "Body"])
        payload = self.run_installed(
            "plan", "review-prompt", "--target", ".",
            "--content", "drafts/installed-draft.md",
        )
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(len(payload["prompts"]), 2)

    def test_rejects_none_level_conflicting_missing_and_invalid_context_refs(self) -> None:
        none_draft = self.write_json("inputs/none.json", {"plan_level": "none", "title": "Skip"})
        none_err = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--content", str(none_draft),
            expected=2,
        )
        self.assertEqual(none_err["code"], "plan_review_not_applicable")

        conflict_err = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--plan", "docs/plans/missing.json",
            "--content", str(none_draft),
            expected=2,
        )
        self.assertEqual(conflict_err["code"], "conflicting_plan_input")

        missing_err = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            expected=2,
        )
        self.assertEqual(missing_err["code"], "missing_plan_input")

        self.write_lines("drafts/ok.md", ["# Ok", "Body"])
        missing_ref = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--content", "drafts/ok.md",
            "--context-ref", "does-not-exist.md",
            expected=2,
        )
        self.assertEqual(missing_ref["code"], "invalid_context_ref")

        root_ref = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--content", "drafts/ok.md",
            "--context-ref", ".",
            expected=2,
        )
        self.assertEqual(root_ref["code"], "invalid_context_ref")

        with tempfile.TemporaryDirectory() as outside:
            outside_file = Path(outside) / "secret.txt"
            outside_file.write_text("secret", encoding="utf-8")
            escape_err = self.run_cli(
                "plan", "review-prompt", "--target", str(self.project),
                "--content", "drafts/ok.md",
                "--context-ref", str(outside_file),
                expected=2,
            )
            self.assertEqual(escape_err["code"], "invalid_context_ref")

    def test_rejects_symlink_context_ref_and_unsupported_flags(self) -> None:
        self.write_lines("drafts/ok.md", ["# Ok", "Body"])
        self.write_lines("src/real.py", ["x = 1"])
        link = self.project / "src" / "alias.py"
        try:
            os.symlink(self.project / "src" / "real.py", link)
        except OSError:
            link = None
        if link is not None:
            sym_err = self.run_cli(
                "plan", "review-prompt", "--target", str(self.project),
                "--content", "drafts/ok.md",
                "--context-ref", "src/alias.py",
                expected=2,
            )
            self.assertEqual(sym_err["code"], "invalid_context_ref")

        dry_flag = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--content", "drafts/ok.md",
            "--dry-run",
            expected=2,
        )
        self.assertEqual(dry_flag["code"], "dry_run_unsupported")

        bad_flag = self.run_cli(
            "plan", "review-prompt", "--target", str(self.project),
            "--content", "drafts/ok.md",
            "--strict",
            expected=2,
        )
        self.assertEqual(bad_flag["code"], "unsupported_flag")

        bad_lens = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "harness.py"),
                "plan", "review-prompt", "--target", str(self.project),
                "--content", "drafts/ok.md", "--lens", "unknown", "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(bad_lens.returncode, 0)


if __name__ == "__main__":
    unittest.main()
