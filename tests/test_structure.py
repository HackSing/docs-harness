"""Structure 结构护栏：增量体量红线、CODEMAP 一致性与存量结构债报告。"""

from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import structure_check  # noqa: E402


class StructureGuardrailTest(HarnessTestBase):
    def test_structure_check_skips_non_git_target(self) -> None:
        payload = self.run_cli("structure", "check", "--target", str(self.project))
        self.assertEqual(payload["checked"], 0)
        self.assertEqual(payload["warnings"], [])
    def test_structure_check_warns_on_new_oversized_file_and_function(self) -> None:
        self.structure_git("init")
        self.write_lines("src/big.py", [f"x{i} = {i}" for i in range(601)])
        self.write_lines("src/long_func.py", ["def giant():"] + ["    pass"] * 70)
        payload = self.run_cli("structure", "check", "--target", str(self.project))
        self.assertTrue(
            any("src/big.py" in w and "超过 600 行结构评估阈值" in w for w in payload["warnings"]),
            payload["warnings"],
        )
        self.assertTrue(
            any("giant" in w and "超过 60 行结构评估阈值" in w for w in payload["warnings"]),
            payload["warnings"],
        )
    def test_structure_check_increment_growth_rules(self) -> None:
        self.structure_git("init")
        self.write_lines("mod.py", [f"a{i} = {i}" for i in range(580)])
        self.write_lines("fat.py", [f"b{i} = {i}" for i in range(620)])
        self.write_lines(
            "funcs.py",
            ["def stable():"] + ["    pass"] * 64 + ["def grower():"] + ["    pass"] * 54,
        )
        self.structure_commit_all()
        self.write_lines("mod.py", [f"a{i} = {i}" for i in range(620)])
        self.write_lines("fat.py", [f"b{i} = {i}" for i in range(680)])
        self.write_lines(
            "funcs.py",
            ["def stable():"] + ["    pass"] * 64 + ["def grower():"] + ["    pass"] * 69,
        )
        payload = self.run_cli("structure", "check", "--target", str(self.project))
        warnings = payload["warnings"]
        self.assertTrue(any("mod.py" in w and "突破 600 行结构评估阈值" in w for w in warnings), warnings)
        self.assertTrue(any("fat.py" in w and "仍净增" in w for w in warnings), warnings)
        self.assertTrue(any("grower" in w and "增长" in w for w in warnings), warnings)
        self.assertFalse(any("stable" in w for w in warnings), "未增长的超长函数不应因存量被点名")
    def test_structure_check_small_growth_stays_silent(self) -> None:
        self.structure_git("init")
        self.write_lines("fat.py", [f"b{i} = {i}" for i in range(620)])
        self.write_lines("funcs.py", ["def stable():"] + ["    pass"] * 64)
        self.structure_commit_all()
        self.write_lines("fat.py", [f"b{i} = {i}" for i in range(630)])
        self.write_lines("funcs.py", ["def stable():"] + ["    pass"] * 66)
        payload = self.run_cli("structure", "check", "--target", str(self.project))
        self.assertEqual(payload["warnings"], [], "小幅净增不应触发增量告警")
    def test_structure_check_codemap_consistency_and_registration(self) -> None:
        self.structure_git("init")
        self.write_lines("src/service.py", ["def serve():", "    pass"])
        self.structure_commit_all()
        self.write_lines("src/orphan.py", ["def orphan():", "    pass"])
        (self.project / "docs").mkdir(exist_ok=True)
        (self.project / "docs" / "CODEMAP.md").write_text(
            "# CODEMAP\n\n"
            "示例：- `src/example/module.py` — 职责：示例；公开接口：`main`\n\n"
            "- `src/service.py` — 职责：服务入口；公开接口：`serve`、`vanished_symbol`\n"
            "- `src/removed.py` — 职责：已删除模块；公开接口：`gone`\n",
            encoding="utf-8",
        )
        payload = self.run_cli("structure", "check", "--target", str(self.project))
        warnings = payload["warnings"]
        self.assertTrue(
            any("vanished_symbol" in w and "索引已失活" in w for w in warnings), warnings
        )
        self.assertTrue(any("src/removed.py" in w and "不存在" in w for w in warnings), warnings)
        self.assertTrue(any("src/orphan.py" in w and "未登记" in w for w in warnings), warnings)
        self.assertFalse(
            any("src/example/module.py" in w for w in warnings),
            "脚手架示例行不应被当作条目解析",
        )
    def test_structure_check_flags_unregistered_dart(self) -> None:
        self.structure_git("init")
        self.write_lines("lib/main.dart", ["void main() {}"])
        self.structure_commit_all()
        (self.project / "docs").mkdir(exist_ok=True)
        (self.project / "docs" / "CODEMAP.md").write_text("# CODEMAP\n", encoding="utf-8")
        self.write_lines("lib/spike_page.dart", ["class SpikePage {}"])
        payload = self.run_cli("structure", "check", "--target", str(self.project))
        self.assertTrue(
            any("lib/spike_page.dart" in w and "未登记" in w for w in payload["warnings"]),
            payload["warnings"],
        )
    def test_structure_report_lists_stock_debt(self) -> None:
        self.structure_git("init")
        self.write_lines("legacy.py", ["def whale():"] + ["    pass"] * 80 + [f"c{i} = {i}" for i in range(540)])
        self.structure_commit_all()
        payload = self.run_cli("structure", "report", "--target", str(self.project))
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["files_over_red_line"][0]["path"], "legacy.py")
        self.assertEqual(payload["functions_over_red_line"][0]["function"], "whale")
        self.assertFalse(payload["codemap"]["present"])
        self.assertIn("legacy.py", payload["codemap"]["unregistered_files"])
    def test_assets_check_carries_structure_warnings(self) -> None:
        self.run_cli("project", "init", "--target", str(self.project))
        self.structure_git("init")
        self.structure_commit_all()
        self.write_lines("src/huge.py", [f"h{i} = {i}" for i in range(601)])
        payload = self.run_cli("assets-check", "--target", str(self.project), "--fast")
        self.assertEqual(payload["status"], "passed", "Structure 只产 WARN，不应使检查失败")
        self.assertTrue(
            any(w.startswith("WARN: Structure:") and "src/huge.py" in w for w in payload["warnings"]),
            payload["warnings"],
        )
        self.assertGreaterEqual(payload["checked"]["structure"], 1)


class StructureFunctionLanguagesTest(HarnessTestBase):
    """2.12.0：函数级检查覆盖 Go 与 TS/JS。TS 用例需要目标目录可见的 typescript：
    仓库自身无 node_modules 时经 DOCS_HARNESS_TS_MODULE_DIR 指向任一含 typescript 的 node_modules，
    否则 TS 用例 skip 并说明。"""

    @staticmethod
    def _ts_available() -> bool:
        return bool(structure_check._ts_module_dirs(ROOT)) and shutil.which("node") is not None

    def test_function_language_dispatch(self) -> None:
        self.assertEqual(structure_check.function_language("a/b.py"), "python")
        self.assertEqual(structure_check.function_language("a/b.go"), "go")
        for suffix in (".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"):
            self.assertEqual(structure_check.function_language(f"a/b{suffix}"), "ts", suffix)
        self.assertIsNone(structure_check.function_language("a/b.rs"))

    def test_go_functions_receivers_closures_one_liners_and_generics(self) -> None:
        source = "\n".join([
            "package x",
            "",
            "func one() {}",
            "",
            "func (a *App) Run(ctx context.Context) error {",
            "\tgo func() {",
            "\t\tfor {",
            "\t\t}",
            "\t}()",
            "\treturn nil",
            "}",
            "",
            "func (App) Name() string {",
            "\treturn \"x\"",
            "}",
            "",
            "func (s *Store[T]) Get() T {",
            "\treturn s.value",
            "}",
        ])
        self.assertEqual(
            structure_check._go_functions(source),
            {"one": 1, "App.Run": 7, "App.Name": 3, "Store.Get": 3},
        )

    def test_function_warnings_apply_same_rules_to_all_languages(self) -> None:
        current = {"small": 10, "fresh": 80, "grown": 75, "stable": 70}
        old = {"grown": 61, "stable": 68}
        warnings = structure_check._function_warnings("x.ts", current, old, has_head=True)
        self.assertEqual(len(warnings), 2)
        self.assertIn("新增函数 fresh 共 80 行", warnings[0])
        self.assertIn("函数 grown 本次增长 14 行（61→75）", warnings[1])
        self.assertEqual(structure_check._function_warnings("x.ts", None, {}, has_head=True), [])
        self.assertEqual(structure_check._function_warnings("x.ts", {"f": 99}, None, has_head=True), [])

    def test_ts_parser_unavailable_is_a_warning_not_silence(self) -> None:
        with mock.patch.object(structure_check.shutil, "which", return_value=None):
            spans, reason = structure_check._ts_function_spans(ROOT, [("k", "a.ts", "const a = 1;")])
        self.assertEqual(spans, {})
        self.assertEqual(reason, "未找到 node")
        self.structure_git("init")
        self.write_lines("src/app.ts", ["export function f() {", "  return 1;", "}"])
        with mock.patch.object(structure_check.shutil, "which", return_value=None):
            payload = structure_check.check_structure(self.project)
        self.assertTrue(
            any("TS 函数级检查不可用" in w for w in payload["warnings"]), payload["warnings"]
        )
        # 纯 JS 项目没有"必然自带 typescript"的前提：不出 WARN，只在 notes 记录未做函数级。
        (self.project / "src" / "app.ts").unlink()
        self.write_lines("tools/build.cjs", ["module.exports = () => {", "  return 1;", "};"])
        with mock.patch.object(structure_check.shutil, "which", return_value=None):
            payload = structure_check.check_structure(self.project)
        self.assertEqual(payload["warnings"], [])
        self.assertTrue(any("tools/build.cjs" in note for note in payload.get("notes", [])), payload)

    def test_go_increment_check_warns_on_new_long_function(self) -> None:
        self.structure_git("init")
        self.write_lines("cmd/run.go", ["package cmd", "", "func Run() {"] + ["\tprintln(1)"] * 70 + ["}"])
        self.write_lines("cmd/run_test.go", ["package cmd", "", "func TestRun(t *testing.T) {"] + ["\tt.Log(1)"] * 70 + ["}"])
        payload = self.run_cli("structure", "check", "--target", str(self.project))
        warnings = payload["warnings"]
        self.assertTrue(any("cmd/run.go 新增函数 Run 共 72 行" in w for w in warnings), warnings)
        self.assertFalse(any("run_test.go" in w and "函数" in w for w in warnings), "测试文件不做函数级判定")

    def test_ts_parser_names_declarations_arrows_methods_callbacks_and_tsx(self) -> None:
        if not self._ts_available():
            self.skipTest(f"无可用 typescript：设置 {structure_check.TS_MODULE_DIR_ENV} 指向含 typescript 的 node_modules")
        spans, reason = structure_check._ts_function_spans(ROOT, [
            ("a", "sample.ts", "\n".join([
                "export function top(a: number): number {",
                "  return a;",
                "}",
                "const arrow = async (x: string) => {",
                "  await x;",
                "  return x;",
                "};",
                "class Store {",
                "  load(id: string) {",
                "    return id;",
                "  }",
                "}",
                "ipcMain.handle(\"chan\", (event) => {",
                "  return event;",
                "});",
            ])),
            ("b", "Comp.tsx", "export function Comp() {\n  const inner = () => {\n    return 1;\n  };\n  return <div onClick={inner} />;\n}\n"),
            ("c", "broken.ts", "function ( {"),
        ])
        self.assertIsNone(reason, reason)
        self.assertEqual(spans["a"], {"top": 3, "arrow": 4, "Store.load": 3, "ipcMain.handle#cb": 3})
        self.assertEqual(spans["b"], {"Comp": 6, "Comp.inner": 3})
        self.assertIsNone(spans["c"])

    def test_ts_increment_check_and_report_cover_functions(self) -> None:
        if not self._ts_available():
            self.skipTest(f"无可用 typescript：设置 {structure_check.TS_MODULE_DIR_ENV} 指向含 typescript 的 node_modules")
        module_dir = str(structure_check._ts_module_dirs(ROOT)[0])
        self.structure_git("init")
        self.write_lines("src/handlers.ts", ["export function register(): void {"] + ["  console.log(1);"] * 70 + ["}"])
        self.write_lines("src/handlers.test.ts", ["describe(() => {"] + ["  it(() => {});"] * 70 + ["});"])
        with mock.patch.dict(os.environ, {structure_check.TS_MODULE_DIR_ENV: module_dir}):
            payload = structure_check.check_structure(self.project)
            report = structure_check.structure_report(self.project)
        self.assertTrue(any("src/handlers.ts 新增函数 register 共 72 行" in w for w in payload["warnings"]), payload["warnings"])
        self.assertFalse(any("handlers.test.ts" in w and "函数" in w for w in payload["warnings"]))
        self.assertEqual(report["function_check_languages"], ["python", "go", "ts"])
        self.assertIn({"path": "src/handlers.ts", "function": "register", "lines": 72}, report["functions_over_red_line"])


if __name__ == "__main__":
    unittest.main()
