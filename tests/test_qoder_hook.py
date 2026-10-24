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
USER_HOOK = ROOT / "routing" / "hosts" / "qoder" / "user-hook.sh"
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

    def install_fake_cli(self) -> Path:
        path = self.project / "fake_qoder_cli"
        path.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys

log = os.environ.get("FAKE_CLI_LOG")
if log:
    with open(log, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "argv": sys.argv[1:],
                "cwd": os.getcwd(),
                "sdk_entrypoint": os.environ.get("QODER_AGENT_SDK_ENTRYPOINT"),
                "international_token": os.environ.get("QODER_PERSONAL_ACCESS_TOKEN"),
                "cn_config_dir": os.environ.get("QODERCN_CONFIG_DIR"),
            },
            handle,
            ensure_ascii=False,
        )
mode = os.environ.get("FAKE_CLI_MODE", "success")
if "--version" in sys.argv:
    print("9.9.9")
    raise SystemExit(0)
if mode == "not_logged_in":
    print(json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "result": "Not logged in · Please run /login",
        "usage": {},
        "modelUsage": {},
    }))
    raise SystemExit(0)
if mode == "invalid_profile":
    text = "this is not a routing profile"
elif mode == "docs":
    text = json.dumps({
        "intents": ["docs_change"],
        "triggers": ["docs_edit"],
        "must_clarify": False,
        "confidence": 0.9,
    })
else:
    text = json.dumps({
        "intents": ["code_task"],
        "triggers": ["code_edit"],
        "must_clarify": False,
        "confidence": 0.9,
    })
print(json.dumps({
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "duration_ms": 12,
    "num_turns": 1,
    "result": text,
    "total_cost_usd": 0.001,
    "total_credits": 3.5,
    "usage": {
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    },
    "modelUsage": {"performance": {"inputTokens": 100, "outputTokens": 20, "credits": 3.5}},
}))
""",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

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

    def test_project_without_docs_harness_is_skipped(self) -> None:
        (self.project / "routing" / "registry.json").unlink()
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(result.stderr.strip(), "")
        self.assertEqual(self.shadow_events(), [])
        self.assertFalse((self.project / ".docs-harness" / "routing").exists())

    def test_installed_project_without_registry_uses_source_registry(self) -> None:
        (self.project / "routing" / "registry.json").unlink()
        (self.project / ".docs-harness").mkdir()
        (self.project / ".docs-harness" / "config.json").write_text("{}", encoding="utf-8")
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("代码改动契约", context)
        self.assertEqual(len(self.shadow_events()), 1)

    def run_user_hook(
        self, project: Path, prompt: str = PROMPT
    ) -> subprocess.CompletedProcess[str]:
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-user-hook",
            "cwd": str(project),
            "prompt": prompt,
        }
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("DOCS_HARNESS_ROUTER_")
            and key not in {"QODER_PROJECT_DIR", "DOCS_HARNESS_REGISTRY", "DOCS_HARNESS_ROOT"}
        }
        env.update(
            {
                "QODER_PROJECT_DIR": str(project),
                "DOCS_HARNESS_ROOT": str(ROOT),
                "DOCS_HARNESS_ROUTER_ENABLED": "1",
                "DOCS_HARNESS_ROUTER_BACKEND": "fake",
                "DOCS_HARNESS_ROUTER_FAKE_PROFILE": str(self.fake),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", ""),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        return subprocess.run(
            [str(USER_HOOK)],
            cwd=project,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def test_user_hook_wrapper_skips_project_without_docs_harness(self) -> None:
        project = Path(self.temp.name) / "other"
        project.mkdir()
        result = self.run_user_hook(project)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(result.stderr.strip(), "")
        self.assertFalse((project / ".docs-harness").exists())

    def test_user_hook_wrapper_delegates_for_docs_harness_project(self) -> None:
        result = self.run_user_hook(self.project)
        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("代码改动契约", context)
        self.assertEqual(len(self.shadow_events()), 1)

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
                "intents": ["code_task"],
                "triggers": ["code_edit", "clarify_required"],
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

    def run_cli_hook(
        self,
        *,
        mode: str = "success",
        prompt: str = PROMPT,
        model: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cli = self.install_fake_cli()
        config = self.project / "cli-config"
        empty = self.project / "cli-empty"
        log = self.project / "cli-log.json"
        extra_env = {
            "DOCS_HARNESS_ROUTER_BACKEND": "cli",
            "DOCS_HARNESS_QODER_CLI": str(cli),
            "DOCS_HARNESS_QODER_CLI_VERSION": "9.9.9",
            "DOCS_HARNESS_QODER_CONFIG_DIR": str(config),
            "DOCS_HARNESS_QODER_EMPTY_DIR": str(empty),
            "FAKE_CLI_LOG": str(log),
            "FAKE_CLI_MODE": mode,
            "QODER_AGENT_SDK_ENTRYPOINT": "must-be-dropped",
            "QODER_PERSONAL_ACCESS_TOKEN": "international-token",
        }
        if model:
            extra_env["DOCS_HARNESS_ROUTER_MODEL"] = model
        return self.run_hook(prompt=prompt, extra_env=extra_env)

    def test_cli_backend_injects_contract_and_records_usage(self) -> None:
        result = self.run_cli_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertIn("代码改动契约", output["hookSpecificOutput"]["additionalContext"])
        events = self.shadow_events()
        self.assertEqual(len(events), 1)
        model = events[0]["model"]
        self.assertEqual(model["name"], "performance")
        self.assertEqual(model["version"], "9.9.9")
        self.assertEqual(model["tokens_in"], 100)
        self.assertEqual(model["tokens_out"], 20)
        self.assertEqual(model["cost_usd"], 0.001)
        self.assertEqual(model["credits"], 3.5)
        self.assertGreater(model["latency_ms"], 0)
        log = json.loads((self.project / "cli-log.json").read_text(encoding="utf-8"))
        argv = log["argv"]
        self.assertIsNone(log["sdk_entrypoint"])
        self.assertIsNone(log["international_token"])
        self.assertEqual(log["cn_config_dir"], str(self.project / "cli-config"))
        self.assertEqual(
            Path(log["cwd"]).resolve(), (self.project / "cli-empty").resolve()
        )
        self.assertEqual(argv[0], "-p")
        self.assertEqual(argv[1], PROMPT)
        self.assertIn("--output-format", argv)
        self.assertEqual(argv[argv.index("--output-format") + 1], "json")
        self.assertNotIn("--model", argv)
        self.assertEqual(argv[argv.index("--max-turns") + 1], "1")
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertIn("--no-session-persistence", argv)
        self.assertEqual(
            Path(argv[argv.index("--cwd") + 1]).resolve(),
            (self.project / "cli-empty").resolve(),
        )
        self.assertEqual(
            Path(argv[argv.index("--config-dir") + 1]).resolve(),
            (self.project / "cli-config").resolve(),
        )
        self.assertIn("--system-prompt", argv)
        self.assertIn("--settings", argv)

    def test_cli_backend_model_override_is_passed_only_when_configured(self) -> None:
        result = self.run_cli_hook(model="DeepSeek-V4-Pro")
        self.assertEqual(result.returncode, 0, result.stderr)
        log = json.loads((self.project / "cli-log.json").read_text(encoding="utf-8"))
        argv = log["argv"]
        self.assertEqual(argv[argv.index("--model") + 1], "DeepSeek-V4-Pro")

    def test_cli_backend_not_logged_in_is_non_blocking(self) -> None:
        result = self.run_cli_hook(mode="not_logged_in")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("qoder_cli_not_logged_in", result.stderr)
        self.assertEqual(self.shadow_events(), [])

    def test_cli_backend_invalid_profile_is_non_blocking(self) -> None:
        result = self.run_cli_hook(mode="invalid_profile")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("router_profile_not_json", result.stderr)
        self.assertEqual(self.shadow_events(), [])

    def test_cli_backend_missing_executable_is_non_blocking(self) -> None:
        result = self.run_hook(
            extra_env={
                "DOCS_HARNESS_ROUTER_BACKEND": "cli",
                "DOCS_HARNESS_QODER_CLI": str(self.project / "missing-qoder"),
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("qoder_cli_missing", result.stderr)
        self.assertEqual(self.shadow_events(), [])

    def session_caches(self) -> list[Path]:
        directory = self.project / ".docs-harness" / "routing" / "sessions"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    def test_followup_reuses_session_cache_without_cli(self) -> None:
        first = self.run_hook()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(len(self.session_caches()), 1)
        second = self.run_hook(
            prompt="继续把这个契约文案改短",
            extra_env={
                "DOCS_HARNESS_ROUTER_BACKEND": "cli",
                "DOCS_HARNESS_QODER_CLI": str(self.project / "missing-qoder"),
            },
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotIn("qoder_cli_missing", second.stderr)
        self.assertIn("沿用上次路由", json.loads(second.stdout)["hookSpecificOutput"]["additionalContext"])
        events = self.shadow_events()
        self.assertEqual(len(events), 2)
        self.assertTrue(events[-1]["model"]["cache_hit"])
        self.assertEqual(events[-1]["model"]["name"], "route-cache")
        self.assertEqual(events[-1]["modules"], ["code"])

    def test_new_task_marker_bypasses_cache(self) -> None:
        first = self.run_hook()
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_cli_hook(prompt="新任务：写一个发布说明", mode="docs")
        self.assertEqual(second.returncode, 0, second.stderr)
        context = json.loads(second.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("文档交付契约", context)
        self.assertNotIn("沿用上次路由", context)
        events = self.shadow_events()
        self.assertEqual(events[-1]["modules"], ["docs"])
        self.assertEqual(events[-1]["model"]["name"], "performance")

    def test_route_reset_clears_cache(self) -> None:
        first = self.run_hook()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(len(self.session_caches()), 1)
        reset = self.run_hook(
            prompt="/route-reset",
            extra_env={
                "DOCS_HARNESS_ROUTER_BACKEND": "cli",
                "DOCS_HARNESS_QODER_CLI": str(self.project / "missing-qoder"),
            },
        )
        self.assertEqual(reset.returncode, 0, reset.stderr)
        self.assertEqual(reset.stdout.strip(), "")
        self.assertEqual(self.session_caches(), [])

    def test_cache_ttl_zero_forces_reroute(self) -> None:
        first = self.run_hook()
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_hook(
            prompt="继续把这个契约文案改短",
            extra_env={
                "DOCS_HARNESS_ROUTER_BACKEND": "cli",
                "DOCS_HARNESS_QODER_CLI": str(self.project / "missing-qoder"),
                "DOCS_HARNESS_ROUTER_CACHE_TTL_SECONDS": "0",
            },
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("qoder_cli_missing", second.stderr)
        self.assertNotIn("沿用上次路由", second.stdout)


if __name__ == "__main__":
    unittest.main()
