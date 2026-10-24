"""B1 路由能力的 CLI 与安装面边界测试。"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harness_test_base import HARNESS, ROOT  # noqa: E402

import harness  # noqa: E402

ROUTING_MODULES = {
    "routing_registry.py",
    "routing_contract.py",
    "routing_shadow_fields.py",
    "routing_shadow.py",
    "routing_metrics.py",
}


class RoutingSurfaceTest(unittest.TestCase):
    def test_routing_modules_are_not_part_of_downstream_install(self) -> None:
        managed = set(harness.MANAGED_MODULE_RELATIVE_FILES)
        self.assertFalse(ROUTING_MODULES & managed)
        self.assertFalse(
            any("routing" in path.replace("\\", "/") for path in harness.portable_install_paths())
        )

    def test_cli_has_no_routing_command(self) -> None:
        result = subprocess.run(
            [sys.executable, str(HARNESS), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("routing", result.stdout.lower())

    def test_package_ships_routing_sources_but_not_as_managed_assets(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        files = set(package["files"])
        self.assertIn("routing/", files)
        for module in ROUTING_MODULES:
            with self.subTest(module=module):
                self.assertIn(f"scripts/{module}", files)


if __name__ == "__main__":
    unittest.main()
