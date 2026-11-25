"""asset_checks 的 amend 提示：宽限期、过期与异常时间。"""

from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from asset_checks import (  # noqa: E402
    PLAN_AMEND_GRACE_DAYS,
    _plan_amend_warning,
    plan_amend_recently,
)

NOW = dt.datetime(2026, 10, 23, 12, 0, tzinfo=dt.timezone.utc)


def _log(last: str) -> list[dict[str, str]]:
    return [
        {
            "amended_at": "2026-10-17T05:56:33+00:00",
            "reason": "first",
            "fingerprint_before": "a",
            "fingerprint_after": "b",
        },
        {
            "amended_at": "2026-10-17T06:01:04+00:00",
            "reason": "second",
            "fingerprint_before": "b",
            "fingerprint_after": "c",
        },
        {
            "amended_at": last,
            "reason": "third",
            "fingerprint_before": "c",
            "fingerprint_after": "d",
        },
    ]


class PlanAmendGraceTest(unittest.TestCase):
    def test_recent_amend_is_within_grace(self) -> None:
        governance = {"last_amended_at": "2026-10-17T10:44:43+00:00"}
        self.assertTrue(plan_amend_recently(governance, NOW))

    def test_old_amend_is_outside_grace(self) -> None:
        governance = {"last_amended_at": "2026-09-01T00:00:00+00:00"}
        self.assertFalse(plan_amend_recently(governance, NOW))

    def test_future_amend_is_not_grace(self) -> None:
        governance = {"last_amended_at": "2026-11-01T00:00:00+00:00"}
        self.assertFalse(plan_amend_recently(governance, NOW))

    def test_falls_back_to_amend_log(self) -> None:
        governance = {"amend_log": _log("2026-10-20T00:00:00+00:00")}
        self.assertTrue(plan_amend_recently(governance, NOW))

    def test_invalid_time_is_not_grace(self) -> None:
        governance = {"last_amended_at": "not-a-time"}
        self.assertFalse(plan_amend_recently(governance, NOW))

    def test_missing_value_is_not_grace(self) -> None:
        self.assertFalse(plan_amend_recently(None, NOW))


class PlanAmendWarningTest(unittest.TestCase):
    def test_recent_amend_does_not_warn(self) -> None:
        recent = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)
        ).replace(microsecond=0).isoformat()
        plan = {"amend_log": _log(recent)}
        self.assertIsNone(_plan_amend_warning(plan, None, "docs/plans/foo.json"))

    def test_old_amend_warns(self) -> None:
        old = (
            dt.datetime.now(dt.timezone.utc)
            - dt.timedelta(days=PLAN_AMEND_GRACE_DAYS + 20)
        ).replace(microsecond=0).isoformat()
        plan = {"amend_log": _log(old)}
        warning = _plan_amend_warning(plan, None, "docs/plans/foo.json")
        self.assertIsNotNone(warning)
        self.assertIn("amend 已达 3 次", warning or "")

    def test_settled_plan_does_not_warn(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        old = (now - dt.timedelta(days=PLAN_AMEND_GRACE_DAYS + 20)).replace(microsecond=0).isoformat()
        settled = (now - dt.timedelta(days=PLAN_AMEND_GRACE_DAYS + 19)).replace(microsecond=0).isoformat()
        governance = {
            "last_amended_at": old,
            "governance_settled_at": settled,
        }
        plan = {"amend_log": _log(old)}
        self.assertIsNone(_plan_amend_warning(plan, governance, "docs/plans/foo.json"))

    def test_below_threshold_does_not_warn(self) -> None:
        old = (
            dt.datetime.now(dt.timezone.utc)
            - dt.timedelta(days=PLAN_AMEND_GRACE_DAYS + 20)
        ).replace(microsecond=0).isoformat()
        plan = {"amend_log": _log(old)[:2]}
        self.assertIsNone(_plan_amend_warning(plan, None, "docs/plans/foo.json"))


if __name__ == "__main__":
    unittest.main()
