"""Shadow 路由事件的脱敏、写入、读取与失败路径测试。"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harness_test_base import REQUIRES_SYMLINK, ROOT  # noqa: E402

import routing_contract as rc  # noqa: E402
import routing_shadow as rs  # noqa: E402

REGISTRY_PATH = ROOT / "routing" / "registry.json"
MOMENT = dt.datetime(2026, 10, 23, 12, 0, tzinfo=dt.timezone.utc)


def profile(**overrides: object) -> dict:
    value = {
        "intents": ["code_task"],
        "triggers": ["code_edit"],
        "must_clarify": False,
        "confidence": 0.95,
    }
    value.update(overrides)
    return value


def outcome(**overrides: object) -> dict:
    value = {"clarify_asked": False, "rework": [], "completed": True}
    value.update(overrides)
    return value


class ShadowEventTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = rc.load_registry(REGISTRY_PATH)

    def build(self, **overrides: object) -> dict:
        args = {
            "task_id": "task-1",
            "profile": profile(),
            "actual_modules": ["code"],
            "outcome": outcome(),
            "registry": self.registry,
            "now": MOMENT,
        }
        args.update(overrides)
        return rs.build_shadow_event(**args)

    def test_event_contains_only_whitelisted_structured_fields(self) -> None:
        event = self.build(
            profile=profile(evidence=["用户提到 secret-token-123"]),
            task_text="用户任务原文 secret-token-123",
            model={
                "name": "strong-router",
                "version": "1.0",
                "tokens_in": 100,
                "tokens_out": 20,
                "latency_ms": 350,
                "cost_usd": 0.001,
            },
        )
        encoded = json.dumps(event, ensure_ascii=False)
        self.assertNotIn("secret-token-123", encoded)
        self.assertNotIn("用户任务原文", encoded)
        self.assertEqual(event["profile"]["evidence_count"], 1)
        self.assertEqual(event["task_chars"], len("用户任务原文 secret-token-123"))
        self.assertEqual(
            event["task_hash"],
            "sha256:" + __import__("hashlib").sha256(
                "用户任务原文 secret-token-123".encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(event["risk_level"], "low")

    def test_evidence_is_not_a_profile_field_in_events(self) -> None:
        event = self.build()
        with self.assertRaises(rs.RoutingShadowError):
            rs.validate_shadow_event(
                {
                    **event,
                    "profile": {**event["profile"], "evidence": ["原文"]},
                }
            )

    def test_task_id_must_be_opaque(self) -> None:
        with self.assertRaises(rs.RoutingShadowError) as caught:
            self.build(task_id="含有空格的用户原文")
        self.assertEqual(caught.exception.code, "shadow_event_invalid")

    def test_duplicate_actual_modules_are_rejected(self) -> None:
        with self.assertRaises(rs.RoutingShadowError):
            self.build(actual_modules=["code", "code"])

    def test_unknown_actual_module_is_rejected_with_registry(self) -> None:
        with self.assertRaises(rs.RoutingShadowError):
            self.build(actual_modules=["nope"])

    def test_low_confidence_profile_is_logged_as_clarify(self) -> None:
        event = self.build(profile=profile(confidence=0.2), actual_modules=[])
        self.assertTrue(event["profile"]["must_clarify"])
        self.assertEqual(event["profile"]["triggers"], ["clarify_required"])
        self.assertEqual(event["modules"], [])
        self.assertEqual(event["risk_level"], "unknown")

    def test_needed_modules_are_recorded(self) -> None:
        event = self.build(needed_modules=["code"], actual_modules=["code", "docs"])
        self.assertEqual(event["needed_modules"], ["code"])
        self.assertEqual(event["actual_modules"], ["code", "docs"])

    def test_risk_level_rolls_up_to_highest_module(self) -> None:
        event = self.build(
            profile=profile(intents=["plan_decision"], triggers=["plan_required"]),
            actual_modules=["plan"],
        )
        self.assertEqual(event["risk_level"], "high")

    def test_model_metadata_is_validated(self) -> None:
        with self.assertRaises(rs.RoutingShadowError):
            self.build(model={"name": "model with spaces", "version": "1"})
        with self.assertRaises(rs.RoutingShadowError):
            self.build(model={"version": "1"})
        event = self.build(model=None)
        self.assertIsNone(event["model"])

    def test_outcome_rework_enum_is_enforced(self) -> None:
        with self.assertRaises(rs.RoutingShadowError):
            self.build(outcome=outcome(rework=["unknown_rework"]))
        event = self.build(outcome=outcome(rework=["cancel", "scope_correction"]))
        self.assertEqual(event["outcome"]["rework"], ["cancel", "scope_correction"])

    def test_validated_snapshot_without_registry_is_supported(self) -> None:
        result = rc.validate_profile(profile(), self.registry)
        event = self.build(registry=None, profile=result.to_dict())
        self.assertEqual(event["modules"], ["code"])
        self.assertEqual(event["registry_fingerprint"], self.registry.fingerprint)

    def test_append_and_read_roundtrip(self) -> None:
        event = self.build(model={"name": "strong-router", "version": "1.0"})
        with tempfile.TemporaryDirectory() as tmp:
            path = rs.shadow_log_path(tmp, MOMENT)
            self.assertEqual(path.name, "shadow-2026-10.jsonl")
            rs.append_shadow_event(event, path)
            self.assertEqual((path.parent / ".gitignore").read_text(encoding="utf-8"), "*\n")
            loaded = rs.read_shadow_events(path)
        self.assertEqual(loaded, [event])

    def test_read_directory_merges_month_files_in_order(self) -> None:
        first = self.build(task_id="task-a")
        second = self.build(task_id="task-b")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "logs"
            directory.mkdir()
            rs.append_shadow_event(first, directory / "shadow-2026-10.jsonl")
            rs.append_shadow_event(second, directory / "shadow-2026-11.jsonl")
            loaded = rs.read_shadow_events(directory)
        self.assertEqual([item["task_id"] for item in loaded], ["task-a", "task-b"])

    def test_missing_log_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(rs.RoutingShadowError) as caught:
                rs.read_shadow_events(Path(tmp) / "missing.jsonl")
        self.assertEqual(caught.exception.code, "shadow_log_missing")

    def test_malformed_log_line_is_an_error(self) -> None:
        event = self.build()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shadow.jsonl"
            path.write_text(
                json.dumps(event, ensure_ascii=False) + "\n{broken\n", encoding="utf-8"
            )
            with self.assertRaises(rs.RoutingShadowError) as caught:
                rs.read_shadow_events(path)
        self.assertEqual(caught.exception.code, "shadow_log_line_invalid")
        self.assertEqual(caught.exception.details["line"], 2)

    def test_hand_written_event_with_prompt_is_rejected(self) -> None:
        event = self.build()
        event["prompt"] = "用户原文"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shadow.jsonl"
            path.write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(rs.RoutingShadowError) as caught:
                rs.read_shadow_events(path)
        self.assertEqual(caught.exception.code, "shadow_log_line_invalid")

    @REQUIRES_SYMLINK
    def test_symlink_log_path_is_rejected(self) -> None:
        event = self.build()
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.jsonl"
            real.write_text("", encoding="utf-8")
            link = Path(tmp) / "link.jsonl"
            link.symlink_to(real)
            with self.assertRaises(rs.RoutingShadowError):
                rs.append_shadow_event(event, link)
            with self.assertRaises(rs.RoutingShadowError):
                rs.read_shadow_events(link)


if __name__ == "__main__":
    unittest.main()
