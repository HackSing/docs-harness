from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "scripts" / "harness.py"


def load_harness_module():
    spec = importlib.util.spec_from_file_location("docs_harness_controller", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseVersionConsistencyTest(unittest.TestCase):
    """发版门禁回归：四处版本真源与 evals 版本保持一致。"""

    def test_version_sources_and_evals_are_consistent(self) -> None:
        module = load_harness_module()
        version = module.VERSION
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), version)
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], version)
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"version: {version}", skill_text)
        evals = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        self.assertEqual(evals["version"], version)


if __name__ == "__main__":
    unittest.main()
