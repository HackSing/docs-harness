"""Qoder UserPromptSubmit hook 原型的独立 stdin 合同测试。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import ROOT  # noqa: E402

HOOK = ROOT / "routing" / "hosts" / "qoder" / "route_hook.py"
REGISTRY = ROOT / "routing" / "registry.json"
PROMPT = "修改 routing/registry.json 里的契约文案，然后跑聚焦测试"


def code_profile() -> dict:
    return {
        "intents": ["code_task"],
        "triggers": ["code_edit"],
        "must_clarify": False,
        "confidence": 0.95,
        "evidence": ["测试 fixture"],
    }


class QoderHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()
        (self.project / "routing").mkdir()
        shutil.copy2(REGISTRY, self.project / "routing" / "registry.json")
        self.fake = self.project / "fake_profile.json"
        self.write_fake(code_profile())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_fake(self, profile: dict) -> None:
        self.fake.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")

    def run_hook(
        self,
        prompt: str = PROMPT,
        *,
        enabled: bool = True,
        fake: Path | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-test-1",
            "cwd": str(self.project),
            "prompt": prompt,
        }
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("DOCS_HARNESS_ROUTER_")
            and key not in {"QODER_PROJECT_DIR", "DOCS_HARNESS_REGISTRY", "DOCS_HARNESS_ROOT"}
        }
        env["QODER_PROJECT_DIR"] = str(self.project)
        env["DOCS_HARNESS_ROUTER_FAKE_PROFILE"] = str(fake or self.fake)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if enabled:
            env["DOCS_HARNESS_ROUTER_ENABLED"] = "1"
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(HOOK)],
            cwd=self.project,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def shadow_events(self) -> list[dict]:
        files = sorted((self.project / ".docs-harness" / "routing").glob("shadow-*.jsonl"))
        if not files:
            return []
        return [
            json.loads(line)
            for path in files
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_enabled_hook_injects_selected_contract_and_logs_shadow(self) -> None:
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("代码改动契约", context)
        self.assertIn("保持最小修改面", context)
        self.assertNotIn("文档交付契约", context)
        self.assertNotIn("版本发布契约", context)
        self.assertNotIn(PROMPT, context)
        events = self.shadow_events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["modules"], ["code"])
        self.assertEqual(event["profile"]["intents"], ["code_task"])
        self.assertEqual(event["model"]["name"], "fake-router")
        self.assertEqual(event["phase"], "shadow")
        self.assertEqual(event["task_hash"], "sha256:" + hashlib.sha256(PROMPT.encode("utf-8")).hexdigest())
        self.assertEqual(event["task_chars"], len(PROMPT))
        self.assertNotIn(PROMPT, json.dumps(event, ensure_ascii=False))

    def test_hook_is_off_by_default(self) -> None:
        result = self.run_hook(enabled=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(self.shadow_events(), [])

    def test_missing_registry_is_non_blocking(self) -> None:
        (self.project / "routing" / "registry.json").unlink()
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("registry_missing", result.stderr)
        self.assertEqual(self.shadow_events(), [])

    def test_invalid_profile_is_non_blocking_and_redacted(self) -> None:
        self.write_fake({"intents": ["nope"], "triggers": [], "must_clarify": False, "confidence": 0.9})
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("profile_invalid", result.stderr)
        self.assertIn("unknown_intent", result.stderr)
        errors = (self.project / ".docs-harness" / "routing" / "hook-errors.jsonl").read_text(
            encoding="utf-8"
        )
        self.assertIn("profile_invalid", errors)
        self.assertNotIn(PROMPT, errors)

    def test_direct_override_skips_injection_and_logging(self) -> None:
        result = self.run_hook(prompt="这次不使用 Harness，直接改 routing/registry.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(self.shadow_events(), [])

    def test_clarify_profile_logs_without_injection(self) -> None:
        self.write_fake(
            {
                "intents": [],
                "triggers": ["clarify_required"],
                "must_clarify": True,
                "confidence": 0.4,
            }
        )
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        events = self.shadow_events()
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["profile"]["must_clarify"])
        self.assertEqual(events[0]["modules"], [])

    def test_unreadable_fake_profile_is_non_blocking(self) -> None:
        result = self.run_hook(fake=self.project / "missing.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("fake_profile_unreadable", result.stderr)
        self.assertEqual(self.shadow_events(), [])

    def test_invalid_phase_is_non_blocking(self) -> None:
        result = self.run_hook(extra_env={"DOCS_HARNESS_ROUTER_PHASE": "unknown"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("phase_invalid", result.stderr)
        self.assertEqual(self.shadow_events(), [])


if __name__ == "__main__":
    unittest.main()
