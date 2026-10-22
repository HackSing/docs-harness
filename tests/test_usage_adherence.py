"""usage report 遵循率指标与收尾报告完整率。"""

from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT

sys.path.insert(0, str(ROOT / "scripts"))

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


class UsageAdherenceTest(HarnessTestBase):
    def seed(self, **fields: object) -> None:
        event = _event(_iso(_now()))
        event.update(fields)
        self.assertTrue(usage_log.append_event(self.project, event))

    def report(self, days: int = 30) -> dict:
        return usage_report.build_report(self.project, days)

    def test_adherence_rates_separate_expected_exit_three(self) -> None:
        self.seed(command="plan", action="check", exit_code=3)
        self.seed(command="plan", action="check", exit_code=1)
        self.seed(command="assets-check", action=None, exit_code=0, warnings=0)
        self.seed(command="assets-check", action=None, exit_code=0, warnings=2)
        report = self.report()
        self.assertEqual(report["adherence"]["real_failures"], 1)
        self.assertEqual(report["adherence"]["real_failure_rate"], 0.25)
        self.assertEqual(report["adherence"]["check_runs"], 2)
        self.assertEqual(report["adherence"]["warning_runs"], 1)
        self.assertEqual(report["adherence"]["warning_rate"], 0.5)
        self.assertEqual(report["commands"]["assets-check"]["warning_rate"], 0.5)
        self.assertEqual(report["commands"]["plan check"]["real_failure_rate"], 0.5)

    def test_report_completeness_counts_required_fields(self) -> None:
        reports_dir = self.project / ".docs-harness" / "reports"
        reports_dir.mkdir(parents=True)
        stamp = _now().date().isoformat()
        (reports_dir / f"{stamp}-complete.md").write_text(
            "## 改动路径\n`src/a.py`\n## 验证\n`python -m unittest`\n退出码 0\n"
            "验收层：L2\n## 未覆盖\n无\n",
            encoding="utf-8",
        )
        (reports_dir / f"{stamp}-partial.md").write_text(
            "## 改动路径\n`src/b.py`\n## 验证\n已人工检查\n",
            encoding="utf-8",
        )
        metrics = self.report()["report_completeness"]
        self.assertEqual(metrics["reports"], 2)
        self.assertEqual(metrics["complete"], 1)
        self.assertEqual(metrics["rate"], 0.5)
        self.assertEqual(metrics["fields"]["path"], 2)
        self.assertEqual(metrics["fields"]["exit"], 1)


if __name__ == "__main__":
    unittest.main()
