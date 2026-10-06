"""view 命令：Mermaid 页面渲染（纯函数）、落盘、CLI 错误码与 --open 接线。"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_test_base import HarnessTestBase, ROOT

sys.path.insert(0, str(ROOT / "scripts"))

import diagram_view  # noqa: E402
import harness  # noqa: E402

MERMAID_SCRIPT = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"
THREE_NODES = 'flowchart LR\n  A["x < y & z"] --> B --> C\n'


class RenderMermaidHtmlTest(unittest.TestCase):
    def test_page_loads_mermaid_and_escapes_source_and_title(self) -> None:
        page = diagram_view.render_mermaid_html(THREE_NODES, 'a<b> & "c"')
        self.assertIn(f'<script src="{MERMAID_SCRIPT}"></script>', page)
        self.assertIn('<meta charset="utf-8">', page)
        self.assertIn('<meta name="viewport"', page)
        self.assertIn('<pre class="mermaid">', page)
        self.assertIn("A[&quot;x &lt; y &amp; z&quot;] --&gt; B --&gt; C", page)
        self.assertNotIn("x < y", page)
        self.assertIn("<title>a&lt;b&gt; &amp; &quot;c&quot;</title>", page)
        self.assertIn("<h1>a&lt;b&gt; &amp; &quot;c&quot;</h1>", page)


class ViewTestBase(HarnessTestBase):
    def write_source(self, name: str = "flow.mmd", content: str = THREE_NODES) -> Path:
        path = self.project / "diagrams" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def main_in_process(self, *args: str) -> tuple[int, dict[str, object]]:
        """进程内跑 main()，让 mock 替换的打开函数生效；不真开浏览器。"""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = harness.main([*args, "--json"])
        return code, json.loads(out.getvalue())


class WriteViewTest(ViewTestBase):
    def test_writes_page_under_views_dir_creating_it(self) -> None:
        source = self.write_source()
        views = self.project / ".docs-harness" / "views"
        self.assertFalse(views.exists())
        written = diagram_view.write_view(self.project, source)
        self.assertEqual(written, views / "flow.html")
        page = written.read_text(encoding="utf-8")
        self.assertEqual(page, diagram_view.render_mermaid_html(THREE_NODES, "flow"))

    def test_missing_and_blank_sources_raise_distinct_errors(self) -> None:
        with self.assertRaises(FileNotFoundError):
            diagram_view.write_view(self.project, self.project / "nope.mmd")
        with self.assertRaises(FileNotFoundError):
            diagram_view.write_view(self.project, self.project)
        with self.assertRaises(ValueError):
            diagram_view.write_view(self.project, self.write_source("blank.mmd", " \n\t\n"))
        self.assertFalse((self.project / ".docs-harness").exists())


class ViewCliTest(ViewTestBase):
    def test_view_writes_page_and_reports_relative_path(self) -> None:
        source = self.write_source()
        payload = self.run_cli("view", str(source), "--target", str(self.project))
        self.assertEqual(
            payload, {"status": "written", "path": ".docs-harness/views/flow.html", "opened": False}
        )
        self.assertTrue((self.project / ".docs-harness/views/flow.html").is_file())

    def test_source_errors_exit_nonzero_with_error_codes(self) -> None:
        cases = {
            "view_source_missing": self.project / "diagrams" / "missing.mmd",
            "view_source_empty": self.write_source("empty.mmd", ""),
            "view_source_not_utf8": self.write_source("gbk.mmd"),
        }
        cases["view_source_not_utf8"].write_bytes("流程".encode("gbk"))
        for code, source in cases.items():
            with self.subTest(code=code):
                payload = self.run_cli("view", str(source), "--target", str(self.project), expected=2)
                self.assertEqual((payload["status"], payload["code"]), ("error", code))
        self.assertFalse((self.project / ".docs-harness").exists())

    def test_open_calls_browser_with_written_page(self) -> None:
        source = self.write_source()
        with mock.patch.object(harness, "open_in_browser") as opener:
            code, payload = self.main_in_process("view", str(source), "--target", str(self.project), "--open")
        self.assertEqual(code, 0)
        self.assertTrue(payload["opened"])
        opener.assert_called_once_with(self.project.resolve() / ".docs-harness/views/flow.html")

    def test_open_failure_exits_nonzero_and_keeps_written_page(self) -> None:
        source = self.write_source()
        failures = (
            OSError("no opener"),
            subprocess.CalledProcessError(1, ["xdg-open", "flow.html"]),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with mock.patch.object(harness, "open_in_browser", side_effect=failure):
                    code, payload = self.main_in_process(
                        "view", str(source), "--target", str(self.project), "--open"
                    )
                self.assertEqual(code, 2)
                self.assertEqual(payload["code"], "view_open_failed")
                self.assertEqual(payload["path"], ".docs-harness/views/flow.html")
                self.assertIn(".docs-harness/views/flow.html", payload["message"])
                self.assertTrue((self.project / payload["path"]).is_file())


class ViewsLocalOnlyTest(ViewTestBase):
    """views/ 走 LOCAL_ONLY_DIRS：init/upgrade 的嵌套 .gitignore 由 LocalOnlyDirectoryTest
    逐目录覆盖；这里端到端确认 view 写出的页面在安装后的项目里被 git 忽略。"""

    def test_page_written_after_init_is_git_ignored(self) -> None:
        self.assertIn(diagram_view.VIEWS_RELATIVE, harness.LOCAL_ONLY_DIRS)
        self.run_cli("project", "init", "--target", str(self.project), "--apply")
        gitignore = self.project / diagram_view.VIEWS_RELATIVE / ".gitignore"
        self.assertEqual(gitignore.read_text(encoding="utf-8"), "*\n")
        self.structure_git("init")
        page = self.run_cli("view", str(self.write_source()), "--target", str(self.project))["path"]
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", str(page)], cwd=self.project, capture_output=True, check=False
        )
        self.assertEqual(ignored.returncode, 0, "view 写出的页面必须被 git 忽略")


class OpenInBrowserTest(unittest.TestCase):
    def test_uses_platform_opener_and_propagates_failure(self) -> None:
        page = Path("/tmp/flow.html")
        for platform, opener in (("darwin", "open"), ("linux", "xdg-open")):
            with self.subTest(platform=platform), \
                    mock.patch.object(diagram_view.sys, "platform", platform), \
                    mock.patch.object(diagram_view.subprocess, "run") as run:
                diagram_view.open_in_browser(page)
                run.assert_called_once_with(
                    [opener, str(page)], check=True, stdout=subprocess.DEVNULL
                )
        failure = subprocess.CalledProcessError(3, ["xdg-open", str(page)])
        with mock.patch.object(diagram_view.sys, "platform", "linux"), \
                mock.patch.object(diagram_view.subprocess, "run", side_effect=failure):
            with self.assertRaises(subprocess.CalledProcessError):
                diagram_view.open_in_browser(page)


if __name__ == "__main__":
    unittest.main()
