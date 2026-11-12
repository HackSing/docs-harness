"""Jev 适配器的离线契约测试：请求形状、阈值策略与错误处理，不发网络请求。"""

from __future__ import annotations

import http.server
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import ROOT  # noqa: E402

JEV_PATH = ROOT / "evals" / "intent_routing" / "jev_predict.py"
CASES_PATH = ROOT / "evals" / "intent_routing" / "cases.json"

SPEC = importlib.util.spec_from_file_location("intent_routing_jev", JEV_PATH)
assert SPEC and SPEC.loader
jev_predict = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jev_predict)

INTENTS = (
    "answer_only", "code_task", "bug_fix", "plan_decision",
    "asset_lifecycle", "release", "docs_change",
)


def jev_response(
    primary: str,
    confidence: float,
    scores: dict[str, float],
    *,
    clarify: float = 0.1,
    direct_override: float = 0.02,
    code_verify: float = 0.02,
) -> dict:
    values = {intent: 0.01 for intent in INTENTS}
    values.update(scores)
    answers = {
        "primary_intent": {
            "type": "choice",
            "choice": primary,
            "confidence": confidence,
            "probabilities": {primary: confidence},
        },
        "clarify_required": {"type": "noul", "noul": clarify},
        "direct_override": {"type": "noul", "noul": direct_override},
        "code_verify": {"type": "noul", "noul": code_verify},
    }
    for intent, value in values.items():
        answers[f"intent_{intent}"] = {"type": "noul", "noul": value}
    return {"model": "jev-test", "answers": answers, "usage": {"input_tokens": 10, "output_tokens": 2}}


class JevPredictTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = jev_predict._load_cases(CASES_PATH)

    def case(self, case_id: str) -> dict:
        return next(item for item in self.dataset["cases"] if item["id"] == case_id)

    def test_payload_has_primary_intent_nouls_and_aux_questions(self) -> None:
        case = self.case("code-rename-slugify")
        payload = jev_predict.build_payload(case, "jev-test")
        self.assertEqual(payload["model"], "jev-test")
        self.assertEqual(payload["state"]["user_request"], case["prompt"])
        self.assertEqual(payload["questions"]["primary_intent"]["type"], "choice")
        for intent in INTENTS:
            self.assertEqual(payload["questions"][f"intent_{intent}"]["type"], "noul")
        for name in ("clarify_required", "direct_override", "code_verify"):
            self.assertEqual(payload["questions"][name]["type"], "noul")

    def test_vague_change_clarifies_and_keeps_tentative_intent(self) -> None:
        response = jev_response("unclear", 0.52, {"code_task": 0.95}, clarify=0.96)
        prediction = jev_predict.interpret_response(
            self.case("ambiguous-change-scope"), response, self.dataset
        )
        self.assertTrue(prediction["must_clarify"])
        self.assertEqual(prediction["modules"], [])
        self.assertEqual(prediction["intents"], ["code_task"])
        self.assertEqual(prediction["triggers"], ["clarify_required"])

    def test_secondary_intent_above_threshold_adds_modules(self) -> None:
        response = jev_response(
            "release", 0.92, {"release": 0.98, "bug_fix": 0.85}, clarify=0.2
        )
        prediction = jev_predict.interpret_response(
            self.case("release-after-bugfix"), response, self.dataset
        )
        self.assertEqual(prediction["intents"], ["bug_fix", "release"])
        self.assertEqual(prediction["modules"], ["bugfix", "code", "release"])
        self.assertFalse(prediction["must_clarify"])

    def test_borderline_secondary_is_excluded(self) -> None:
        response = jev_response(
            "release", 0.92, {"release": 0.98, "bug_fix": 0.76}, clarify=0.2
        )
        prediction = jev_predict.interpret_response(
            self.case("release-after-bugfix"), response, self.dataset
        )
        self.assertEqual(prediction["intents"], ["release"])
        self.assertEqual(prediction["modules"], ["release"])

    def test_answer_only_is_dropped_when_action_intent_is_selected(self) -> None:
        response = jev_response(
            "answer_only", 0.9, {"answer_only": 0.9, "code_task": 0.9}, clarify=0.1
        )
        prediction = jev_predict.interpret_response(
            self.case("ambiguous-review-login"), response, self.dataset
        )
        self.assertEqual(prediction["intents"], ["code_task"])
        self.assertEqual(prediction["modules"], ["code"])

    def test_low_primary_confidence_clarifies(self) -> None:
        response = jev_response("code_task", 0.4, {"code_task": 0.6}, clarify=0.2)
        prediction = jev_predict.interpret_response(
            self.case("code-rename-slugify"), response, self.dataset
        )
        self.assertTrue(prediction["must_clarify"])
        self.assertEqual(prediction["modules"], [])
        self.assertEqual(prediction["intents"], ["code_task"])

    def test_cli_without_api_key_fails_before_network(self) -> None:
        env = {key: value for key, value in os.environ.items() if key != "TYPESAFE_API_KEY"}
        result = subprocess.run(
            [sys.executable, str(JEV_PATH), "--limit", "1"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("TYPESAFE_API_KEY 未设置", result.stderr)

    def test_gemini_decision_payload_uses_input_and_description_criteria(self) -> None:
        case = self.case("code-rename-slugify")
        payload = jev_predict.build_payload(case, "gemini-decision-1")
        self.assertEqual(payload["model"], "gemini-decision-1")
        self.assertNotIn("state", payload)
        parsed_input = json.loads(payload["input"])
        self.assertEqual(parsed_input["user_request"], case["prompt"])
        self.assertEqual(payload["questions"]["primary_intent"]["type"], "choice")
        for intent in INTENTS:
            q = payload["questions"][f"intent_{intent}"]
            self.assertEqual(q["type"], "noul")
            self.assertIn("true_description", q["criteria"])
            self.assertIn("false_description", q["criteria"])
            self.assertNotIn("true", q["criteria"])
            self.assertNotIn("false", q["criteria"])

    def test_extract_usage_supports_gemini_and_jev_shapes(self) -> None:
        gemini_resp = {
            "usage": {
                "total_input_tokens": 240,
                "total_output_tokens": 0,
                "total_tokens": 240,
            }
        }
        self.assertEqual(jev_predict.extract_usage(gemini_resp), (240, 0))
        self.assertEqual(
            jev_predict.extract_usage({"usage": {"input_tokens": 10, "output_tokens": 2}}),
            (10, 2),
        )

    def test_cli_gemini_model_without_api_key_fails_before_network(self) -> None:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")
        }
        result = subprocess.run(
            [sys.executable, str(JEV_PATH), "--model", "gemini-decision-1", "--limit", "1"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("GEMINI_API_KEY 未设置", result.stderr)

    def test_route_prompt_with_decisions_against_local_server(self) -> None:
        captured: dict = {}
        canned = jev_response("code_task", 0.94, {"code_task": 0.96}, clarify=0.05)
        canned["model"] = "gemini-decision-1"
        canned["usage"] = {
            "total_input_tokens": 500,
            "total_output_tokens": 0,
            "total_tokens": 500,
        }

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                captured["path"] = self.path
                captured["api_key"] = self.headers.get("x-goog-api-key")
                captured["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
                body = json.dumps(canned).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            profile, metadata = jev_predict.route_prompt_with_decisions(
                "修改 scripts/demo.py 并跑聚焦测试",
                api_key="test-gemini-key",
                base_url=base_url,
            )
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(captured["path"], "/v1beta/decisions")
        self.assertEqual(captured["api_key"], "test-gemini-key")
        self.assertEqual(captured["body"]["model"], "gemini-decision-1")
        self.assertEqual(profile["intents"], ["code_task"])
        self.assertEqual(profile["triggers"], ["code_edit"])
        self.assertFalse(profile["must_clarify"])
        self.assertEqual(metadata["name"], "gemini-decision-1")
        self.assertEqual(metadata["version"], "v1beta")
        self.assertEqual(metadata["tokens_in"], 500)
        self.assertEqual(metadata["tokens_out"], 0)
        self.assertEqual(metadata["cost_usd"], 0.00005)

    def test_qoder_hook_decisions_backend_end_to_end(self) -> None:
        canned = jev_response("code_task", 0.96, {"code_task": 0.96}, clarify=0.03)
        canned["model"] = "gemini-decision-1"
        canned["usage"] = {
            "total_input_tokens": 320,
            "total_output_tokens": 0,
            "total_tokens": 320,
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
            with tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp) / "project"
                (project / "routing").mkdir(parents=True)
                shutil.copy2(
                    ROOT / "routing" / "registry.json",
                    project / "routing" / "registry.json",
                )
                env = {
                    k: v
                    for k, v in os.environ.items()
                    if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")
                }
                env_file = Path(tmp) / "gemini.env"
                env_file.write_text("GEMINI_API_KEY=test-key-from-env-file\n", encoding="utf-8")
                env.update(
                    {
                        "QODER_PROJECT_DIR": str(project),
                        "DOCS_HARNESS_ROOT": str(ROOT),
                        "DOCS_HARNESS_ROUTER_ENABLED": "1",
                        "DOCS_HARNESS_ROUTER_PHASE": "canary",
                        "DOCS_HARNESS_ROUTER_BACKEND": "decisions",
                        "DOCS_HARNESS_GEMINI_ENV_FILE": str(env_file),
                        "DOCS_HARNESS_DECISIONS_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                        "NO_PROXY": "127.0.0.1,localhost",
                    }
                )
                payload = {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "sess-decisions-1",
                    "cwd": str(project),
                    "prompt": "修改 routing/registry.json 里的契约文案，然后跑聚焦测试",
                }
                result = subprocess.run(
                    [sys.executable, str(ROOT / "routing" / "hosts" / "qoder" / "route_hook.py")],
                    cwd=project,
                    input=json.dumps(payload, ensure_ascii=False),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                    env=env,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr.strip(), "")
                output = json.loads(result.stdout)
                self.assertIn(
                    "代码改动契约",
                    output["hookSpecificOutput"]["additionalContext"],
                )
                shadow_files = list((project / ".docs-harness" / "routing").glob("shadow-*.jsonl"))
                self.assertEqual(len(shadow_files), 1)
                event = json.loads(shadow_files[0].read_text(encoding="utf-8").splitlines()[0])
                self.assertEqual(event["model"]["name"], "gemini-decision-1")
                self.assertEqual(event["model"]["version"], "v1beta")
                self.assertEqual(event["model"]["tokens_in"], 320)
                self.assertEqual(event["model"]["tokens_out"], 0)
                self.assertEqual(event["model"]["cost_usd"], 0.000032)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
