import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / "routing" / "hosts" / "antigravity" / "route_hook.py"


class AntigravityHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name) / "project"
        (self.project / "routing").mkdir(parents=True)
        shutil.copy2(
            ROOT / "routing" / "registry.json",
            self.project / "routing" / "registry.json",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_hook(
        self,
        payload: dict,
        args: list[str] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("DOCS_HARNESS_")
            and k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")
        }
        if extra_env:
            env.update(extra_env)
        cmd = [sys.executable, str(HOOK_PATH)] + (args or [])
        return subprocess.run(
            cmd,
            cwd=self.project,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=env,
        )

    def test_shadow_phase_extracts_user_request_and_deduplicates_same_turn(self) -> None:
        payload = {
            "conversationId": "agy-conv-1",
            "workspacePaths": [str(self.project)],
            "lastUserInput": (
                "<USER_REQUEST>\n修改 scripts/demo.py 并跑聚焦测试\n</USER_REQUEST>\n"
                "<ADDITIONAL_METADATA>\nThe current local time is: 2026-11-12T19:45:00+08:00.\n"
                "</ADDITIONAL_METADATA>"
            ),
            "invocationNum": 1,
        }
        r1 = self._run_hook(
            payload,
            args=["--enabled", "--phase", "shadow", "--backend", "fake"],
        )
        self.assertEqual(r1.returncode, 0, r1.stderr)
        self.assertEqual(json.loads(r1.stdout), {})
        shadow_files = list((self.project / ".docs-harness" / "routing").glob("shadow-*.jsonl"))
        self.assertEqual(len(shadow_files), 1)
        lines = shadow_files[0].read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        event = json.loads(lines[0])
        self.assertEqual(event["phase"], "shadow")
        self.assertEqual(event["task_chars"], len("修改 scripts/demo.py 并跑聚焦测试"))

        # Second PreInvocation in the same turn (tool loop continuation with identical lastUserInput)
        payload["invocationNum"] = 2
        r2 = self._run_hook(
            payload,
            args=["--enabled", "--phase", "shadow", "--backend", "fake"],
        )
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertEqual(json.loads(r2.stdout), {})
        lines_after = shadow_files[0].read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines_after), 1)

        # Follow-up user prompt in the same conversation hits session route cache
        payload["lastUserInput"] = "<USER_REQUEST>\n顺便补一条单测\n</USER_REQUEST>"
        payload["invocationNum"] = 3
        r3 = self._run_hook(
            payload,
            args=["--enabled", "--phase", "shadow", "--backend", "fake"],
        )
        self.assertEqual(r3.returncode, 0, r3.stderr)
        lines_followup = shadow_files[0].read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines_followup), 2)
        followup_event = json.loads(lines_followup[1])
        self.assertTrue(followup_event["model"]["cache_hit"])

    def test_canary_phase_emits_inject_steps_system_message(self) -> None:
        payload = {
            "conversationId": "agy-conv-canary",
            "workspacePaths": [str(self.project)],
            "lastUserInput": "修改 routing/registry.json 并跑单测",
            "invocationNum": 1,
        }
        r = self._run_hook(
            payload,
            args=["--enabled", "--phase", "canary", "--backend", "fake"],
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        msg = out["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("代码改动契约", msg)

    def test_non_docs_harness_workspace_exits_quietly_with_empty_json(self) -> None:
        other = Path(self._tmp.name) / "plain_workspace"
        other.mkdir(parents=True)
        payload = {
            "conversationId": "agy-conv-plain",
            "workspacePaths": [str(other)],
            "lastUserInput": "普通项目提问",
            "invocationNum": 1,
        }
        r = self._run_hook(
            payload,
            args=["--enabled", "--phase", "shadow", "--backend", "fake"],
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {})
        self.assertFalse((other / ".docs-harness").exists())

    def test_decisions_backend_reads_env_file_flag_and_logs_shadow(self) -> None:
        from tests.test_jev_predict import jev_response

        canned = jev_response("code_task", 0.96, {"code_task": 0.96}, clarify=0.02)
        canned["model"] = "gemini-decision-1"
        canned["usage"] = {
            "total_input_tokens": 410,
            "total_output_tokens": 0,
            "total_tokens": 410,
        }
        body = json.dumps(canned).encode("utf-8")

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            env_file = Path(self._tmp.name) / "gemini.env"
            env_file.write_text("GEMINI_API_KEY=agy-file-key\n", encoding="utf-8")
            payload = {
                "conversationId": "agy-conv-decisions",
                "workspacePaths": [str(self.project)],
                "lastUserInput": "<USER_REQUEST>\n修改 scripts/demo.py 并跑测试\n</USER_REQUEST>",
                "invocationNum": 1,
            }
            r = self._run_hook(
                payload,
                args=[
                    "--enabled",
                    "--phase",
                    "shadow",
                    "--backend",
                    "decisions",
                    "--model",
                    "gemini-decision-1",
                    "--env-file",
                    str(env_file),
                ],
                extra_env={
                    "DOCS_HARNESS_DECISIONS_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                    "NO_PROXY": "127.0.0.1,localhost",
                },
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), {})
            shadow_files = list((self.project / ".docs-harness" / "routing").glob("shadow-*.jsonl"))
            event = json.loads(shadow_files[0].read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(event["model"]["name"], "gemini-decision-1")
            self.assertEqual(event["model"]["tokens_in"], 410)
            self.assertEqual(event["modules"], ["code"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
