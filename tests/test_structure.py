"""Structure 结构护栏：增量体量红线、CODEMAP 一致性与存量结构债报告。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase


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


if __name__ == "__main__":
    unittest.main()
