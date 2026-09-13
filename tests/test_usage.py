"""usage 观测基座：开关求值、事件投影、追加与读取，以及四类降级场景。

批 1 只覆盖 usage_log 与 main() 埋点；usage report 聚合在批 2 补充。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT

sys.path.insert(0, str(ROOT / "scripts"))

import harness  # noqa: E402
import usage_log  # noqa: E402
import usage_report  # noqa: E402


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def _iso(moment: dt.datetime) -> str:
    return moment.isoformat()


def _event(ts: str, command: str = "plan", action: str = "check") -> dict[str, object]:
    return {
        "v": usage_log.USAGE_SCHEMA_VERSION,
        "ts": ts,
        "event": "cmd.invoke",
        "command": command,
        "action": action,
        "exit_code": 0,
        "duration_ms": 1,
    }


def _readonly_enforced() -> bool:
    """root 与 Windows 上目录只读位不拦写入，只读降级现场搭不起来。"""
    if os.name == "nt":
        return False
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "ro"
        root.mkdir()
        os.chmod(root, 0o500)
        try:
            (root / "probe").write_text("x", encoding="utf-8")
        except OSError:
            return True
        finally:
            os.chmod(root, 0o700)
    return False


REQUIRES_READONLY = unittest.skipUnless(
    _readonly_enforced(), "当前环境（Windows 或 root）不强制目录只读位"
)


class UsageEnabledTest(HarnessTestBase):
    """L4(a)/(b)：没安装就没有观测面；开关关闭即完全静默。"""

    def write_config(self, value: object) -> Path:
        path = self.project / ".docs-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def test_missing_config_is_not_enabled(self) -> None:
        self.assertFalse(usage_log.is_enabled(self.project))

    def test_missing_directory_is_not_enabled(self) -> None:
        self.assertFalse(usage_log.is_enabled(self.project / "nowhere"))

    def test_explicit_true_is_enabled(self) -> None:
        self.write_config({"usage_log": {"enabled": True}})
        self.assertTrue(usage_log.is_enabled(self.project))

    def test_explicit_false_is_not_enabled(self) -> None:
        self.write_config({"usage_log": {"enabled": False}})
        self.assertFalse(usage_log.is_enabled(self.project))

    def test_missing_key_is_not_enabled(self) -> None:
        self.write_config({"schema_version": "docs-harness/project-config/v13"})
        self.assertFalse(usage_log.is_enabled(self.project))

    def test_broken_config_is_not_enabled(self) -> None:
        path = self.write_config({"usage_log": {"enabled": True}})
        path.write_text("{ not json", encoding="utf-8")
        self.assertFalse(usage_log.is_enabled(self.project))
        path.write_text("[]", encoding="utf-8")
        self.assertFalse(usage_log.is_enabled(self.project))
        path.write_text('{"usage_log": true}', encoding="utf-8")
        self.assertFalse(usage_log.is_enabled(self.project))

    def test_truthy_non_bool_is_not_enabled(self) -> None:
        self.write_config({"usage_log": {"enabled": 1}})
        self.assertFalse(usage_log.is_enabled(self.project))


class UsageStoreTest(HarnessTestBase):
    def usage_dir(self) -> Path:
        return self.project / usage_log.USAGE_DIR_RELATIVE

    def test_append_creates_month_file_and_nested_gitignore(self) -> None:
        self.assertTrue(usage_log.append_event(self.project, _event(_iso(_now()))))
        month = self.usage_dir() / f"{_now():%Y-%m}.jsonl"
        self.assertTrue(month.is_file())
        self.assertEqual(len(month.read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual((self.usage_dir() / ".gitignore").read_text(encoding="utf-8"), "*\n")

    def test_append_is_additive(self) -> None:
        for _ in range(3):
            self.assertTrue(usage_log.append_event(self.project, _event(_iso(_now()))))
        self.assertEqual(len(usage_log.read_events(self.project, 1)), 3)

    def test_read_events_without_directory_is_empty(self) -> None:
        self.assertEqual(usage_log.read_events(self.project, 30), [])

    def test_read_events_filters_by_window(self) -> None:
        usage_log.append_event(self.project, _event(_iso(_now() - dt.timedelta(days=10))))
        usage_log.append_event(self.project, _event(_iso(_now())))
        self.assertEqual(len(usage_log.read_events(self.project, 3)), 1)
        self.assertEqual(len(usage_log.read_events(self.project, 30)), 2)

    def test_read_events_skips_torn_and_foreign_lines(self) -> None:
        """L4(d)：撕裂行、未知 schema、坏时间戳都跳过，不废掉整个月文件。"""
        usage_log.append_event(self.project, _event(_iso(_now())))
        month = next(self.usage_dir().glob("*.jsonl"))
        with open(month, "a", encoding="utf-8", newline="\n") as handle:
            handle.write('{"v":"docs-harness/usage-event/v1","ts":"2026-0\n')
            handle.write(
                json.dumps({"v": "docs-harness/usage-event/v2", "ts": _iso(_now())}) + "\n"
            )
            handle.write(
                json.dumps({"v": usage_log.USAGE_SCHEMA_VERSION, "ts": "not-a-time"}) + "\n"
            )
            handle.write("[]\n")
        events = usage_log.read_events(self.project, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["command"], "plan")

    def test_read_events_tolerates_torn_multibyte_sequence(self) -> None:
        usage_log.append_event(self.project, _event(_iso(_now())))
        month = next(self.usage_dir().glob("*.jsonl"))
        with open(month, "ab") as handle:
            handle.write('{"v":"docs-harness/usage-event/v1","command":"知'.encode("utf-8")[:-1])
            handle.write(b"\n")
        self.assertEqual(len(usage_log.read_events(self.project, 1)), 1)

    @REQUIRES_READONLY
    def test_append_returns_false_when_directory_cannot_be_created(self) -> None:
        """L4(c)：写不进去就返回 False，不抛出、不留半个目录。"""
        parent = self.project / ".docs-harness"
        parent.mkdir(parents=True)
        os.chmod(parent, 0o500)
        try:
            self.assertFalse(usage_log.append_event(self.project, _event(_iso(_now()))))
        finally:
            os.chmod(parent, 0o700)
        self.assertFalse(self.usage_dir().exists())


class UsageEventProjectionTest(unittest.TestCase):
    """cmd.invoke 的字段投影：只出枚举白名单与计数，不出自由文本。"""

    def args(self, **overrides: object) -> argparse.Namespace:
        base: dict[str, object] = {
            "command": "acceptance",
            "action": "record",
            "target": ".",
            "json": True,
            "status": None,
            "reaccept": False,
            "dry_run": False,
            "strict": False,
            "fast": False,
            "user_confirmed": False,
        }
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_base_fields_always_present(self) -> None:
        event = harness.usage_invoke_event(self.args(), 0, {}, 12)
        self.assertEqual(event["v"], usage_log.USAGE_SCHEMA_VERSION)
        self.assertEqual(event["event"], "cmd.invoke")
        self.assertEqual(event["command"], "acceptance")
        self.assertEqual(event["action"], "record")
        self.assertEqual(event["exit_code"], 0)
        self.assertEqual(event["duration_ms"], 12)
        self.assertNotIn("flags", event)

    def test_action_key_absent_when_command_has_none(self) -> None:
        event = harness.usage_invoke_event(self.args(command="assets-check", action=None), 0, {}, 1)
        self.assertNotIn("action", event)

    def test_only_truthy_whitelisted_flags_are_recorded(self) -> None:
        event = harness.usage_invoke_event(
            self.args(reaccept=True, user_confirmed=True, dry_run=False), 0, {}, 1
        )
        self.assertEqual(event["flags"], {"reaccept": True, "user_confirmed": True})

    def test_status_enum_is_recorded(self) -> None:
        event = harness.usage_invoke_event(
            self.args(command="plan", action="settle", status="deprecated"), 0, {}, 1
        )
        self.assertEqual(event["flags"], {"status": "deprecated"})

    def test_free_text_arguments_are_never_recorded(self) -> None:
        args = self.args(query="机密查询词", input="docs/secret.json", replacement="secret-plan")
        serialized = json.dumps(harness.usage_invoke_event(args, 0, {}, 1), ensure_ascii=False)
        for leak in ("机密查询词", "docs/secret.json", "secret-plan"):
            self.assertNotIn(leak, serialized)

    def test_counts_derived_from_payload_lists_only(self) -> None:
        event = harness.usage_invoke_event(
            self.args(command="knowledge", action="query"), 0, {"facts": [1, 2, 3]}, 1
        )
        self.assertEqual(event["hits"], 3)
        self.assertNotIn("failures", event)
        self.assertNotIn("warnings", event)
        checked = harness.usage_invoke_event(
            self.args(command="assets-check", action=None), 1, {"failures": ["a"], "warnings": []}, 1
        )
        self.assertEqual(checked["failures"], 1)
        self.assertEqual(checked["warnings"], 0)
        self.assertNotIn("hits", checked)

    def test_non_list_payload_values_are_ignored(self) -> None:
        event = harness.usage_invoke_event(self.args(), 0, {"facts": "3", "failures": None}, 1)
        self.assertNotIn("hits", event)
        self.assertNotIn("failures", event)

    def test_payload_status_is_recorded_as_result(self) -> None:
        event = harness.usage_invoke_event(self.args(), 3, {"status": "pending"}, 1)
        self.assertEqual(event["result"], "pending")

    def test_non_string_status_is_not_recorded(self) -> None:
        self.assertNotIn("result", harness.usage_invoke_event(self.args(), 0, {"status": 1}, 1))
        self.assertNotIn("result", harness.usage_invoke_event(self.args(), 0, {}, 1))


class UsageCliTest(HarnessTestBase):
    def usage_dir(self) -> Path:
        return self.project / usage_log.USAGE_DIR_RELATIVE

    def install(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))

    def test_uninstalled_project_records_nothing(self) -> None:
        """L4(a)：非 harness 项目里跑命令，零写入。"""
        self.run_cli("structure", "check", "--target", str(self.project))
        self.assertFalse(self.usage_dir().exists())

    def test_install_records_itself_as_first_event(self) -> None:
        self.install()
        events = usage_log.read_events(self.project, 1)
        self.assertEqual([(e["command"], e.get("action")) for e in events], [("project", "init")])

    def test_subsequent_commands_append_events(self) -> None:
        self.install()
        self.run_cli("plan", "check", "--target", str(self.project))
        self.run_cli("structure", "check", "--target", str(self.project))
        recorded = [(e["command"], e.get("action")) for e in usage_log.read_events(self.project, 1)]
        self.assertIn(("plan", "check"), recorded)
        self.assertIn(("structure", "check"), recorded)

    def test_disabled_switch_stops_recording(self) -> None:
        """L4(b)：关掉开关后零新增。"""
        self.install()
        config_path = self.project / ".docs-harness" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["usage_log"]["enabled"] = False
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        before = len(usage_log.read_events(self.project, 1))
        self.run_cli("structure", "check", "--target", str(self.project))
        self.assertEqual(len(usage_log.read_events(self.project, 1)), before)

    def test_failed_command_is_recorded_with_exit_code(self) -> None:
        self.install()
        self.run_cli(
            "plan", "create", "--target", str(self.project), "--dry-run", expected=2
        )
        events = [e for e in usage_log.read_events(self.project, 1) if e["command"] == "plan"]
        self.assertTrue(events)
        self.assertEqual(events[-1]["exit_code"], 2)
        self.assertEqual(events[-1]["flags"], {"dry_run": True})

    def test_knowledge_query_records_hit_count(self) -> None:
        self.install()
        payload = self.run_cli(
            "knowledge", "query", "--target", str(self.project), "--query", "harness"
        )
        events = [e for e in usage_log.read_events(self.project, 1) if e["command"] == "knowledge"]
        self.assertEqual(events[-1]["hits"], len(payload["facts"]))

    def test_check_command_records_failure_and_warning_counts(self) -> None:
        self.install()
        payload = self.run_cli("plan", "check", "--target", str(self.project))
        events = [
            e for e in usage_log.read_events(self.project, 1)
            if e["command"] == "plan" and e.get("action") == "check"
        ]
        self.assertEqual(events[-1]["failures"], len(payload["failures"]))
        self.assertEqual(events[-1]["warnings"], len(payload["warnings"]))

    @REQUIRES_READONLY
    def test_unwritable_log_does_not_change_command_result(self) -> None:
        """L4(c) 命令层：日志写不进去，命令照常完成、退出码不变、零写入。"""
        self.install()
        month = next(self.usage_dir().glob("*.jsonl"))
        before = month.read_text(encoding="utf-8")
        os.chmod(month, 0o400)
        try:
            payload = self.run_cli("structure", "check", "--target", str(self.project))
        finally:
            os.chmod(month, 0o600)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(month.read_text(encoding="utf-8"), before)

    def config(self) -> dict:
        return json.loads(
            (self.project / ".docs-harness" / "config.json").read_text(encoding="utf-8")
        )

    def write_config(self, value: dict) -> None:
        (self.project / ".docs-harness" / "config.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def test_install_registers_usage_modules(self) -> None:
        self.install()
        config = self.config()
        self.assertEqual(config["schema_version"], "docs-harness/project-config/v13")
        self.assertEqual(config["usage_log"], {"enabled": True})
        for module in ("usage_log.py", "usage_report.py"):
            self.assertTrue((self.project / "scripts" / module).is_file())
            self.assertIn(module, config["installed_module_fingerprints"])

    def test_uninstall_removes_usage_modules(self) -> None:
        self.install()
        self.run_cli("project", "uninstall", "--target", str(self.project), "--apply")
        for module in ("usage_log.py", "usage_report.py"):
            self.assertFalse((self.project / "scripts" / module).exists())

    def test_upgrade_preserves_disabled_switch(self) -> None:
        self.install()
        config = self.config()
        config["usage_log"]["enabled"] = False
        self.write_config(config)
        self.run_cli("project", "upgrade", "--target", str(self.project), "--apply")
        upgraded = self.config()
        self.assertEqual(upgraded["schema_version"], "docs-harness/project-config/v13")
        self.assertEqual(upgraded["usage_log"], {"enabled": False})

    def test_upgrade_restores_missing_switch_to_default(self) -> None:
        self.install()
        config = self.config()
        del config["usage_log"]
        self.write_config(config)
        self.run_cli("project", "upgrade", "--target", str(self.project), "--apply")
        self.assertEqual(
            self.config()["usage_log"], {"enabled": usage_log.USAGE_LOG_DEFAULT_ENABLED}
        )

    def test_project_check_flags_broken_usage_log_config(self) -> None:
        self.install()
        for broken in ({"enabled": "yes"}, {}, {"enabled": True, "extra": 1}, []):
            config = self.config()
            config["usage_log"] = broken
            self.write_config(config)
            payload = self.run_cli(
                "project", "check", "--target", str(self.project), expected=1
            )
            self.assertIn(
                "usage_log_invalid", [f["code"] for f in payload["findings"]], f"{broken}"
            )

    def test_usage_directory_is_git_ignored_without_root_gitignore(self) -> None:
        # 先安装再 git init：装进已有 git 仓库时 project init 会要求先提交交付物（退出码 3），
        # 与本用例要验证的忽略规则无关。
        self.install()
        self.structure_git("init")
        self.assertFalse((self.project / ".gitignore").exists())
        month = next(self.usage_dir().glob("*.jsonl"))
        relative = month.relative_to(self.project).as_posix()
        result = subprocess.run(
            ["git", "check-ignore", relative],
            cwd=self.project,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"{relative} 未被忽略：{result.stdout}{result.stderr}")


class UsageReportTest(HarnessTestBase):
    """A-F 六组聚合：每组各造一批事件，核对计数与手工数出来的一致。"""

    def seed(self, **fields: object) -> None:
        event = _event(_iso(_now()))
        event.update(fields)
        self.assertTrue(usage_log.append_event(self.project, event))

    def report(self, days: int = 30) -> dict:
        return usage_report.build_report(self.project, days)

    def test_empty_window_reports_zeroes(self) -> None:
        report = self.report()
        self.assertEqual(report["event_count"], 0)
        self.assertEqual(report["commands"], {})
        self.assertEqual(report["checks"], {})
        self.assertEqual(report["acceptance_rework"]["records"], 0)
        self.assertEqual(
            report["asset_lifecycle"]["plan"], {"create": 0, "settle": 0}
        )
        self.assertIn("summary", report)
        self.assertIn("limitations", report)

    def test_group_a_command_adoption(self) -> None:
        self.seed(command="plan", action="check", exit_code=0)
        self.seed(command="plan", action="check", exit_code=1)
        self.seed(command="assets-check", action=None, exit_code=0)
        adoption = self.report()["commands"]
        self.assertEqual(adoption["plan check"]["calls"], 2)
        self.assertEqual(adoption["plan check"]["exit_codes"], {"0": 1, "1": 1})
        self.assertEqual(adoption["plan check"]["active_days"], 1)
        self.assertIn("assets-check", adoption)
        self.assertLessEqual(adoption["plan check"]["first"], adoption["plan check"]["last"])

    def test_group_a_buckets_exit_codes_without_labelling_failure(self) -> None:
        for code in (0, 1, 2, 3):
            self.seed(command="project", action="upgrade", exit_code=code)
        entry = self.report()["commands"]["project upgrade"]
        self.assertEqual(entry["exit_codes"], {"0": 1, "1": 1, "2": 1, "3": 1})
        self.assertNotIn("failed", json.dumps(entry))

    def test_group_b_excludes_dry_run_and_failures(self) -> None:
        self.seed(command="plan", action="create", exit_code=0)
        self.seed(command="plan", action="create", exit_code=0, flags={"dry_run": True})
        self.seed(command="plan", action="create", exit_code=2)
        self.seed(command="knowledge", action="settle", exit_code=0)
        lifecycle = self.report()["asset_lifecycle"]
        self.assertEqual(lifecycle["plan"], {"create": 1, "settle": 0})
        self.assertEqual(lifecycle["knowledge"], {"create": 0, "settle": 1})
        self.assertEqual(lifecycle["adr"], {"create": 0, "settle": 0})

    def test_group_c_counts_exit_three_records_in_denominator(self) -> None:
        """acceptance record 退 3 = 记录已存入但整体验收未通过，必须计入分母。"""
        self.seed(command="acceptance", action="record", exit_code=0)
        self.seed(command="acceptance", action="record", exit_code=3)
        self.seed(command="acceptance", action="record", exit_code=3, flags={"reaccept": True})
        self.seed(
            command="acceptance", action="record", exit_code=3, flags={"user_confirmed": True}
        )
        self.seed(command="acceptance", action="record", exit_code=2)
        rework = self.report()["acceptance_rework"]
        self.assertEqual(rework["records"], 4)
        self.assertEqual(rework["reaccept"], 1)
        self.assertEqual(rework["user_confirmed"], 1)

    def test_group_d_plan_settlement_split(self) -> None:
        self.seed(command="plan", action="settle", exit_code=0, flags={"status": "implemented"})
        self.seed(command="plan", action="settle", exit_code=0, flags={"status": "deprecated"})
        self.seed(command="plan", action="settle", exit_code=3, flags={"status": "implemented"})
        self.assertEqual(
            self.report()["plan_settlement"], {"implemented": 1, "deprecated": 1}
        )

    def test_group_e_knowledge_zero_hit_rate(self) -> None:
        self.seed(command="knowledge", action="query", exit_code=0, hits=0)
        self.seed(command="knowledge", action="query", exit_code=0, hits=3)
        self.seed(command="knowledge", action="query", exit_code=2)
        query = self.report()["knowledge_query"]
        self.assertEqual(query, {"queries": 2, "zero_hit": 1})

    def test_group_f_check_totals(self) -> None:
        self.seed(command="assets-check", action=None, exit_code=0, failures=0, warnings=2)
        self.seed(command="assets-check", action=None, exit_code=1, failures=3, warnings=1)
        self.seed(command="plan", action="check", exit_code=0, failures=0, warnings=0)
        checks = self.report()["checks"]
        self.assertEqual(
            checks["assets-check"], {"calls": 2, "failures": 3, "warnings": 3, "clean": 1}
        )
        self.assertEqual(checks["plan check"]["clean"], 1)

    def test_window_excludes_older_events(self) -> None:
        old = _event(_iso(_now() - dt.timedelta(days=10)), command="adr", action="create")
        old["exit_code"] = 0
        usage_log.append_event(self.project, old)
        self.seed(command="adr", action="create", exit_code=0)
        self.assertEqual(self.report(3)["asset_lifecycle"]["adr"]["create"], 1)
        self.assertEqual(self.report(30)["asset_lifecycle"]["adr"]["create"], 2)
        self.assertEqual(self.report(3)["window_days"], 3)


class UsageReportCliTest(HarnessTestBase):
    def test_report_runs_in_both_formats(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        payload = self.run_cli("usage", "report", "--target", str(self.project))
        self.assertGreaterEqual(payload["event_count"], 1)
        self.assertIn("project init", payload["commands"])
        self.assertIsInstance(payload["summary"], str)
        self.assertIsInstance(payload["limitations"], str)
        self.assertIn("acceptance record 退出码 3", payload["limitations"])

    def test_report_text_output_carries_summary_and_limitations(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "harness.py"),
             "usage", "report", "--target", str(self.project)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("summary: ", result.stdout)
        self.assertIn("limitations: ", result.stdout)

    def test_report_rejects_non_positive_days(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        for days in ("0", "-5"):
            payload = self.run_cli(
                "usage", "report", "--target", str(self.project), "--days", days, expected=2
            )
            self.assertEqual(payload["code"], "invalid_request")

    def test_report_on_project_without_log_is_empty(self) -> None:
        payload = self.run_cli("usage", "report", "--target", str(self.project))
        self.assertEqual(payload["event_count"], 0)

    def test_result_field_is_recorded_from_payload_status(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.run_cli("structure", "check", "--target", str(self.project))
        events = [
            e for e in usage_log.read_events(self.project, 1) if e["command"] == "structure"
        ]
        self.assertEqual(events[-1]["result"], "passed")


if __name__ == "__main__":
    unittest.main()
