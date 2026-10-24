"""structure_check 的 CODEMAP 校验：接口段解析、目录模块与反向用例。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from codemap_check import (  # noqa: E402
    codemap_interface_symbols,
    parse_codemap,
    parse_codemap_index_entries,
)
from structure_check import _codemap_consistency_warnings  # noqa: E402

INDEX_LINE = "- `pkg` — 职责：包说明；公开接口：`Alpha`、`Beta`"
CHANGE_LINE = "- `pkg` — 变更：新增公开接口 `OldSymbol`（已删除，由 `NewSymbol` 取代）"


class InterfaceSymbolsTest(unittest.TestCase):
    def test_parenthetical_replacement_is_not_interface(self) -> None:
        line = "- `x` — 职责：说明；公开接口：`A`、`B`（替代原 `Old`）"
        self.assertEqual(codemap_interface_symbols(line), ["A", "B"])

    def test_no_interface_skips_explanation(self) -> None:
        line = "- `x` — 职责：说明；公开接口：无（`init()` 给包级变量赋值）"
        self.assertEqual(codemap_interface_symbols(line), [])

    def test_package_internal_qualifier(self) -> None:
        line = "- `x` — 职责：说明；公开接口：（包内）`awaitTrayQuitFocusSettle`"
        self.assertEqual(codemap_interface_symbols(line), ["awaitTrayQuitFocusSettle"])

    def test_json_qualifier(self) -> None:
        line = "- `x` — 职责：说明；公开接口：（JSON）`profileId`、`agentVideoEditing`"
        self.assertEqual(codemap_interface_symbols(line), ["profileId", "agentVideoEditing"])

    def test_stops_at_semicolon(self) -> None:
        line = "- `x` — 职责：说明；公开接口：`A`；见 `B`"
        self.assertEqual(codemap_interface_symbols(line), ["A"])


class IndexEntrySelectionTest(unittest.TestCase):
    def test_change_lines_are_not_validated_as_index(self) -> None:
        text = "\n".join([INDEX_LINE, CHANGE_LINE])
        entries = parse_codemap_index_entries(text)
        self.assertEqual(entries, [("pkg", ["Alpha", "Beta"])])

    def test_registration_still_sees_change_lines(self) -> None:
        text = "\n".join([INDEX_LINE, CHANGE_LINE])
        self.assertEqual(len(parse_codemap(text)), 2)


class ConsistencyWarningsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_directory_module_scans_sibling_files(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir()
        (pkg / "a.go").write_text("package pkg\nfunc Alpha() {}\n", encoding="utf-8")
        (pkg / "b.go").write_text("package pkg\nfunc Beta() {}\n", encoding="utf-8")
        self.assertEqual(
            _codemap_consistency_warnings(self.root, [("pkg", ["Alpha", "Beta"])]), []
        )

    def test_directory_module_reports_missing_symbol(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir()
        (pkg / "a.go").write_text("package pkg\nfunc Alpha() {}\n", encoding="utf-8")
        warnings = _codemap_consistency_warnings(self.root, [("pkg", ["Gamma"])])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Gamma", warnings[0])

    def test_directory_module_ignores_test_files(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir()
        (pkg / "a_test.go").write_text("package pkg\nfunc Gamma() {}\n", encoding="utf-8")
        warnings = _codemap_consistency_warnings(self.root, [("pkg", ["Gamma"])])
        self.assertEqual(len(warnings), 1)

    def test_file_module_still_checks_symbols(self) -> None:
        module = self.root / "mod.ts"
        module.write_text("export const Alpha = 1;\n", encoding="utf-8")
        self.assertEqual(
            _codemap_consistency_warnings(self.root, [("mod.ts", ["Alpha"])]), []
        )
        warnings = _codemap_consistency_warnings(self.root, [("mod.ts", ["Missing"])])
        self.assertEqual(len(warnings), 1)

    def test_missing_module_still_warns(self) -> None:
        warnings = _codemap_consistency_warnings(self.root, [("gone.ts", ["Alpha"])])
        self.assertEqual(len(warnings), 1)
        self.assertIn("模块不存在", warnings[0])


if __name__ == "__main__":
    unittest.main()
