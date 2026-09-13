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


class StructureManagedFileExemptionTest(HarnessTestBase):
    """2.16.1：下游项目的 structure 检查排除 harness 自带文件，源包自身不排除。

    根因现场来自 2.16.0 升级 10 个下游：安装器写入的 scripts/harness.py 与受管模块被
    当成下游自己的代码，WARN 几乎全是下游既无法处置也不该处置的 harness 内部文件。
    源包不排除是守卫所在——排除了就丢掉"新增受管模块未登记 CODEMAP"这道检查。
    """

    MANAGED_SAMPLES = ("usage_log.py", "usage_report.py", "structure_ts_functions.cjs")
    HARNESS_OWN_PATHS = ("scripts/harness.py", *(f"scripts/{n}" for n in MANAGED_SAMPLES))

    def downstream_fixture(self) -> None:
        """HEAD 里是旧版 harness 自带文件，工作区是当前版本。

        复现真实升级现场：harness.py 变成 M 且净增数千行（触发超红线净增 WARN），
        2.16.0 新增的三个受管模块变成 A 且未登记 CODEMAP（触发未登记 WARN）。
        """
        self.run_cli("project", "init", "--target", str(self.project))
        scripts = self.project / "scripts"
        saved = {
            name: (scripts / name).read_bytes()
            for name in ("harness.py", *self.MANAGED_SAMPLES)
        }
        (scripts / "harness.py").write_text('VERSION = "0.0.0"\n', encoding="utf-8")
        for name in self.MANAGED_SAMPLES:
            (scripts / name).unlink()
        self.structure_git("init")
        self.structure_commit_all()
        for name, data in saved.items():
            (scripts / name).write_bytes(data)

    def make_source_package_markers(self) -> None:
        """补上源包独有的两个标记文件；两者都不是代码文件，自身不产生 WARN。"""
        (self.project / "SKILL.md").write_text(
            "---\nname: docs-harness\nversion: 9.9.9\n---\n\n# skill\n", encoding="utf-8"
        )
        self.write_json("evals/evals.json", {"version": "9.9.9"})

    def structure_warnings(self) -> list[str]:
        payload = self.run_cli("structure", "check", "--target", str(self.project))
        return list(payload["warnings"])

    def test_downstream_check_ignores_harness_own_files(self) -> None:
        self.downstream_fixture()
        self.assertEqual(self.structure_warnings(), [])

    def test_downstream_report_omits_harness_own_files(self) -> None:
        self.downstream_fixture()
        payload = self.run_cli("structure", "report", "--target", str(self.project))
        listed = (
            [item["path"] for item in payload["files_over_red_line"]]
            + [item["path"] for item in payload["functions_over_red_line"]]
            + list(payload["codemap"]["unregistered_files"])
        )
        for relative in self.HARNESS_OWN_PATHS:
            self.assertNotIn(relative, listed, payload)

    def test_downstream_still_reports_its_own_code(self) -> None:
        """排除只针对 harness 自带文件：下游自己的超红线文件照常 WARN。"""
        self.downstream_fixture()
        self.write_lines("src/huge.py", [f"h{i} = {i}" for i in range(601)])
        warnings = self.structure_warnings()
        self.assertTrue(any("src/huge.py" in w for w in warnings), warnings)
        self.assertFalse(any("scripts/harness.py" in w for w in warnings), warnings)

    def test_source_package_keeps_its_own_structure_warnings(self) -> None:
        self.downstream_fixture()
        self.make_source_package_markers()
        warnings = self.structure_warnings()
        self.assertTrue(
            any("scripts/harness.py" in w for w in warnings),
            f"源包不得排除自身文件，否则丢掉体量守卫：{warnings}",
        )
        self.assertTrue(
            any("scripts/usage_log.py" in w and "CODEMAP" in w for w in warnings),
            f"源包必须保留新增受管模块未登记 CODEMAP 的守卫：{warnings}",
        )

    def test_downstream_tolerates_invalid_package_json(self) -> None:
        """源包判定不读 package.json，下游的损坏 package.json 不进结构检查的失败面。

        整体复用 read_version_sources 会连带读 package.json 与 8 个模板 JSON，任一损坏就让
        structure check 与 pre-commit 的 assets-check --fast 因无关文件报错——这是 2.16.0
        没有的崩溃面（结构检查此前根本不读 package.json），本用例守住它不被重新引入。
        编辑中途的 package.json 在前端下游很常见。
        """
        self.downstream_fixture()
        (self.project / "package.json").write_text("{ not json", encoding="utf-8")
        self.assertEqual(self.structure_warnings(), [])
        self.run_cli("assets-check", "--target", str(self.project), "--fast")

    def test_unreadable_skill_marker_is_not_a_source_package(self) -> None:
        """非 UTF-8 的 SKILL.md：read_text 抛 UnicodeDecodeError，判为非源包而不是崩溃。"""
        self.downstream_fixture()
        self.make_source_package_markers()
        (self.project / "SKILL.md").write_bytes(b"\xff\xfe---\nversion: 9.9.9\n---\n")
        self.assertEqual(self.structure_warnings(), [])

    def test_unreadable_evals_marker_is_not_a_source_package(self) -> None:
        """非法 evals/evals.json：read_json 抛 HarnessError，同样判为非源包而不是崩溃。"""
        self.downstream_fixture()
        self.make_source_package_markers()
        (self.project / "evals" / "evals.json").write_text("{ not json", encoding="utf-8")
        self.assertEqual(self.structure_warnings(), [])

    def test_assets_check_structure_matches_structure_check(self) -> None:
        """两个入口走同一条排除判定，对同一目标逐字一致。"""
        self.downstream_fixture()
        self.write_lines("src/huge.py", [f"h{i} = {i}" for i in range(601)])
        direct = self.structure_warnings()
        payload = self.run_cli("assets-check", "--target", str(self.project), "--fast")
        prefix = "WARN: Structure: "
        via_assets = [w[len(prefix):] for w in payload["warnings"] if w.startswith(prefix)]
        self.assertEqual(via_assets, direct)
