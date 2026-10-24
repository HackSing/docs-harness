"""plan_check.canonical_index_entry：正式条目优先于引用句与跨方案链接。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from plan_check import canonical_index_entry  # noqa: E402


class CanonicalIndexEntryTest(unittest.TestCase):
    def test_prefers_bullet_over_reference_line(self) -> None:
        entries = [
            "- `references/contracts/api.json`：配套方案见 `plans/foo.md`。",
            "- [其他方案](plans/other.md) — 状态：有效；关键符号：`x`、`y`",
            "- [正确方案](plans/foo.md) — 状态：有效；关键符号：`a`、`b`",
        ]
        self.assertTrue(
            canonical_index_entry(entries, "foo.md").startswith("- [正确方案]")
        )

    def test_inline_link_is_not_canonical(self) -> None:
        entries = [
            "- [上游方案](plans/upstream.md) — 后续以[本方案](plans/foo.md)为准。",
            "- [本方案](plans/foo.md) — 状态：有效；关键符号：`a`、`b`",
        ]
        self.assertTrue(
            canonical_index_entry(entries, "foo.md").startswith("- [本方案]")
        )

    def test_table_row_when_no_bullet(self) -> None:
        entries = [
            "| `plans/foo.md` | 方案说明；关键符号：`a`、`b` |",
        ]
        self.assertEqual(canonical_index_entry(entries, "foo.md"), entries[0])

    def test_falls_back_to_first_mention(self) -> None:
        entries = [
            "参见 plans/foo.md 的说明",
            "另一处 plans/foo.md 的引用",
        ]
        self.assertEqual(canonical_index_entry(entries, "foo.md"), entries[0])

    def test_empty_entries(self) -> None:
        self.assertEqual(canonical_index_entry([], "foo.md"), "")


if __name__ == "__main__":
    unittest.main()
