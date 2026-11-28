"""多宿主防治标 Stop Hook：6 宿主配置、双协议运行时与 project init/upgrade 集成测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harness_test_base import HARNESS, HarnessTestBase, ROOT  # noqa: E402
from host_hooks import (  # noqa: E402
    HOME_OVERRIDE_ENV,
    HOST_IDS,
    HostHookError,
    canonical_hook_script_path,
    inspect_host_hooks,
    install_host_hook,
    is_host_configured,
    reconcile_host_hook,
)
from host_rules import antigravity_rules_dir  # noqa: E402
from plan_root_cause_hook import (  # noqa: E402
    ANTIGRAVITY_CHALLENGE_REASON,
    CHALLENGE_REASON,
    evaluate_stop,
)


class HostHooksConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_all_six_hosts_install_detect_and_are_idempotent(self) -> None:
        # 预置既有设置，验证所有宿主写入均保留原有字段且幂等
        (self.home / ".gemini" / "config").mkdir(parents=True)
        (self.home / ".gemini" / "config" / "hooks.json").write_text(
            json.dumps({"other-hook": {"enabled": True, "SessionStart": []}}),
            encoding="utf-8",
        )
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "settings.json").write_text(
            json.dumps({"language": "zh", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]}}),
            encoding="utf-8",
        )
        (self.home / ".codex").mkdir(parents=True)
        (self.home / ".codex" / "config.toml").write_text("[features]\nhooks = false\n", encoding="utf-8")
        (self.home / ".qoder-cn").mkdir(parents=True)
        (self.home / ".qoder").mkdir(parents=True)
        (self.home / ".zcode" / "cli").mkdir(parents=True)
        (self.home / ".zcode" / "cli" / "config.json").write_text(
            json.dumps({"theme": "dark"}), encoding="utf-8",
        )
        (self.home / ".dsh").mkdir(parents=True)
        (self.home / ".dsh" / "cordis.patch.yml").write_text(
            "# user patch\n[]\n", encoding="utf-8",
        )

        for host in HOST_IDS:
            self.assertFalse(is_host_configured(host, self.home), host)
            first = install_host_hook(host, ROOT, home_dir=self.home)
            self.assertEqual(first["status"], "configured")
            self.assertTrue(first["changed"], host)
            self.assertTrue(is_host_configured(host, self.home), host)
            second = install_host_hook(host, ROOT, home_dir=self.home)
            self.assertEqual(second["changed"], [], f"{host} should be idempotent")

        self.assertTrue(canonical_hook_script_path(self.home).is_file())
        # 验证保留原有字段
        agy = json.loads((self.home / ".gemini" / "config" / "hooks.json").read_text(encoding="utf-8"))
        self.assertIn("other-hook", agy)
        self.assertIn("plan-root-cause-challenge", agy)

        claude = json.loads((self.home / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(claude["language"], "zh")
        self.assertIn("PreToolUse", claude["hooks"])
        self.assertEqual(len(claude["hooks"]["Stop"]), 1)

        codex_res = install_host_hook("codex", ROOT, home_dir=self.home)
        self.assertTrue(any("hooks = false" in note for note in codex_res["notes"]))
        codex_cfg = json.loads((self.home / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(codex_cfg["hooks"]["Stop"][0]["matcher"], "")

        # Qoder 双目录均存在时两处同步写入
        for qdir in (".qoder-cn", ".qoder"):
            qcfg = json.loads((self.home / qdir / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(len(qcfg["hooks"]["Stop"]), 1)

        zcfg = json.loads((self.home / ".zcode" / "cli" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(zcfg["theme"], "dark")
        self.assertIs(zcfg["hooks"]["enabled"], True)
        self.assertEqual(len(zcfg["hooks"]["events"]["Stop"]), 1)

        dsh_hooks = json.loads((self.home / ".dsh" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(len(dsh_hooks["Stop"]), 1)
        dsh_patch = (self.home / ".dsh" / "cordis.patch.yml").read_text(encoding="utf-8")
        self.assertIn("@deepseek-ai/dsh-hooks-claude-code", dsh_patch)
        self.assertNotIn("\n[]\n", dsh_patch)

    def test_dsh_appends_to_existing_yaml_entries_without_overwriting(self) -> None:
        (self.home / ".dsh").mkdir(parents=True)
        (self.home / ".dsh" / "cordis.patch.yml").write_text(
            "- id: locale\n  name: '@deepseek-ai/dsh-client-locale'\n",
            encoding="utf-8",
        )
        install_host_hook("deepseek-harness", ROOT, home_dir=self.home)
        text = (self.home / ".dsh" / "cordis.patch.yml").read_text(encoding="utf-8")
        self.assertIn("- id: locale", text)
        self.assertIn("- id: hooks-claude-code", text)

    def test_corrupted_host_json_raises_without_overwriting(self) -> None:
        cfg = self.home / ".claude" / "settings.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("{broken json", encoding="utf-8")
        with self.assertRaises(HostHookError) as ctx:
            install_host_hook("claude-code", ROOT, home_dir=self.home)
        self.assertEqual(ctx.exception.code, "host_hook_invalid_config")
        self.assertEqual(cfg.read_text(encoding="utf-8"), "{broken json")

    def test_interactive_selection_retries_invalid_and_installs_chosen_host(self) -> None:
        (self.home / ".claude").mkdir(parents=True)
        answers = iter(["99", "2"])
        outputs: list[str] = []
        result = reconcile_host_hook(
            action="init",
            target=self.home / "proj",
            source_root=ROOT,
            apply=True,
            selected_host=None,
            as_json=False,
            interactive=True,
            home_dir=self.home,
            environ={},
            input_fn=lambda _: next(answers),
            output_fn=outputs.append,
        )
        self.assertEqual(result["status"], "configured")
        self.assertEqual(result["host"], "claude-code")
        self.assertTrue(is_host_configured("claude-code", self.home))
        self.assertTrue(any("无效选择" in line for line in outputs))

    def test_interactive_eof_returns_skipped(self) -> None:
        def _eof(_: str) -> str:
            raise EOFError()

        result = reconcile_host_hook(
            action="init",
            target=self.home / "proj",
            source_root=ROOT,
            apply=True,
            selected_host=None,
            as_json=False,
            interactive=True,
            home_dir=self.home,
            environ={},
            input_fn=_eof,
            output_fn=lambda _: None,
        )
        self.assertEqual(result["status"], "skipped")
        self.assertFalse(canonical_hook_script_path(self.home).exists())

    def test_active_env_not_configured_still_marks_missing(self) -> None:
        install_host_hook("antigravity", ROOT, home_dir=self.home)
        info_plain = inspect_host_hooks(home_dir=self.home, environ={})
        self.assertEqual(info_plain["status"], "already_configured")
        info_claude = inspect_host_hooks(home_dir=self.home, environ={"CLAUDECODE": "1"})
        self.assertEqual(info_claude["status"], "missing")
        self.assertEqual(info_claude["active_host_hint"], "claude-code")

    def test_antigravity_rules_platform_filter_preserves_user_rules_and_idempotent(self) -> None:
        rules_dir = antigravity_rules_dir(self.home)
        rules_dir.mkdir(parents=True)
        custom = rules_dir / "my-custom-rule.md"
        custom.write_text("# user rule\n", encoding="utf-8")

        win_res = install_host_hook("antigravity", ROOT, home_dir=self.home, is_windows=True)
        sub_rule = rules_dir / "docs-harness-antigravity-subagents.md"
        gui_rule = rules_dir / "docs-harness-windows-gui-launch.md"
        self.assertEqual(win_res["rule_paths"], [str(sub_rule), str(gui_rule)])
        self.assertTrue(sub_rule.read_text(encoding="utf-8").startswith("---\ntrigger: always_on\n---"))
        self.assertIn("netstat -ano", gui_rule.read_text(encoding="utf-8"))
        self.assertEqual(custom.read_text(encoding="utf-8"), "# user rule\n")
        self.assertEqual(install_host_hook("antigravity", ROOT, home_dir=self.home, is_windows=True)["changed"], [])

        # 非 Windows 只写配额规则，不写 Windows 桌面启动规则；其他宿主不碰 rules 目录
        posix_home = Path(self._tmp.name) / "posix_home"
        posix_res = install_host_hook("antigravity", ROOT, home_dir=posix_home, is_windows=False)
        posix_rules = antigravity_rules_dir(posix_home)
        self.assertEqual(posix_res["rule_paths"], [str(posix_rules / "docs-harness-antigravity-subagents.md")])
        self.assertTrue((posix_rules / "docs-harness-antigravity-subagents.md").is_file())
        self.assertFalse((posix_rules / "docs-harness-windows-gui-launch.md").exists())
        claude_home = Path(self._tmp.name) / "claude_home"
        claude_res = install_host_hook("claude-code", ROOT, home_dir=claude_home, is_windows=True)
        self.assertEqual(claude_res["rule_paths"], [])
        self.assertFalse(antigravity_rules_dir(claude_home).exists())

    def test_antigravity_preview_lists_rules_and_upgrade_refreshes_missing_rules(self) -> None:
        preview = inspect_host_hooks(home_dir=self.home, environ={}, selected_host="antigravity", is_windows=True)
        self.assertTrue(any(p.endswith("docs-harness-antigravity-subagents.md") for p in preview["planned_files"]))
        self.assertTrue(any(p.endswith("docs-harness-windows-gui-launch.md") for p in preview["planned_files"]))
        self.assertFalse(antigravity_rules_dir(self.home).exists())

        # 模拟老版本已配 hooks.json 但尚无受管规则：再次 apply 自动补齐且二次幂等
        install_host_hook("antigravity", ROOT, home_dir=self.home, is_windows=True)
        sub_rule = antigravity_rules_dir(self.home) / "docs-harness-antigravity-subagents.md"
        sub_rule.unlink()
        refreshed = reconcile_host_hook(
            action="upgrade", target=self.home / "proj", source_root=ROOT, apply=True,
            selected_host=None, as_json=True, interactive=False,
            home_dir=self.home, environ={}, is_windows=True,
        )
        self.assertEqual(refreshed["status"], "already_configured")
        self.assertEqual(refreshed["rules_updated"], [str(sub_rule)])
        self.assertTrue(sub_rule.is_file())
        again = reconcile_host_hook(
            action="upgrade", target=self.home / "proj", source_root=ROOT, apply=True,
            selected_host=None, as_json=True, interactive=False,
            home_dir=self.home, environ={}, is_windows=True,
        )
        self.assertEqual(again["rules_updated"], [])


class UnifiedStopHookRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.guard = self.tmp_dir / "guard.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_jsonl(self, name: str, entries: list[dict]) -> str:
        path = self.tmp_dir / name
        with path.open("w", encoding="utf-8") as handle:
            for item in entries:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        return str(path)

    def test_antigravity_dialect_triggers_once_and_respects_continuation_active(self) -> None:
        reply = (
            "排查结论与修复方案：仓库旧注释说明底层 connect() 无法中断 15 秒超时，"
            "建议修改配对控制器，先把 UI phase 提前改成 scanning 并丢弃过期回调，"
            "分两步修改 lib/ble/pairing_controller.dart 并补充状态机单测。"
            "这样无需改动底层蓝牙插件即可避免页面卡死。" * 2
        )
        tpath = self._write_jsonl("agy.jsonl", [
            {"type": "USER_INPUT", "content": "<USER_REQUEST>\n配对页重扫卡住 15 秒，帮我看看怎么回事\n</USER_REQUEST>"},
            {"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "read_file", "args": {"Path": '"lib/ble/pairing_controller.dart"'}}]},
            {"type": "PLANNER_RESPONSE", "content": reply},
        ])
        first = evaluate_stop(
            {
                "hookEventName": "Stop",
                "terminationReason": "NO_TOOL_CALL",
                "fullyIdle": True,
                "continuationActive": False,
                "transcriptPath": tpath,
                "lastUserInput": "配对页重扫卡住 15 秒，帮我看看怎么回事",
            },
            guard_cache_path=self.guard,
        )
        self.assertEqual(first, {"decision": "continue", "reason": ANTIGRAVITY_CHALLENGE_REASON})
        self.assertIn("Worked for", first["reason"])
        self.assertIn("自包含", first["reason"])
        self.assertNotIn("用 1–2 句给出依据直接确认", first["reason"])
        second = evaluate_stop(
            {
                "hookEventName": "Stop",
                "terminationReason": "NO_TOOL_CALL",
                "fullyIdle": True,
                "continuationActive": True,
                "transcriptPath": tpath,
                "lastUserInput": "配对页重扫卡住 15 秒，帮我看看怎么回事",
            },
            guard_cache_path=self.tmp_dir / "guard_cont.json",
        )
        self.assertEqual(second, {})

    def test_antigravity_blocks_repeat_when_transcript_has_stop_system_message(self) -> None:
        followup = (
            "确认已最小治本：唯一真源调整与单一门禁已核验无遗漏入口，无需追加额外补丁，"
            "等待你确认后直接开始执行全部改动并补充对应回归测试。" * 2
        )
        for label, injected_reason in (
            ("antigravity", ANTIGRAVITY_CHALLENGE_REASON),
            ("legacy", CHALLENGE_REASON),
        ):
            tpath = self._write_jsonl(f"agy_challenged_{label}.jsonl", [
                {"type": "USER_INPUT", "content": "<USER_REQUEST>\n检查下原因并给方案\n</USER_REQUEST>"},
                {"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "read_file", "args": {"Path": '"scripts/a.py"'}}]},
                {"type": "PLANNER_RESPONSE", "content": "修复方案：直接调整状态所有者层。" + ("说明。" * 60)},
                {"type": "SYSTEM_MESSAGE", "content": f"<SYSTEM_MESSAGE>\nStop hook blocked termination: {injected_reason}\n</SYSTEM_MESSAGE>"},
                {"type": "PLANNER_RESPONSE", "content": followup},
            ])
            for extra in ({"continuationActive": False}, {}):
                res = evaluate_stop(
                    {
                        "hookEventName": "Stop",
                        "terminationReason": "NO_TOOL_CALL",
                        "fullyIdle": True,
                        "transcriptPath": tpath,
                        "lastUserInput": "检查下原因并给方案",
                        **extra,
                    },
                    guard_cache_path=self.tmp_dir / f"guard_{label}_{len(extra)}.json",
                )
                self.assertEqual(res, {}, msg=f"Should skip when challenged in transcript ({label}): {extra}")

    def test_antigravity_loop_guard_blocks_second_trigger_and_allows_new_user_turn(self) -> None:
        prompt = "排查一下为什么这里报错，怎么修比较好"
        reply = "修复方案：定位到状态所有者层缺失去重判断，补充单点拦截与测试覆盖。" + ("详情。" * 50)
        entries = [
            {"type": "USER_INPUT", "content": f"<USER_REQUEST>\n{prompt}\n</USER_REQUEST>"},
            {"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "read_file", "args": {"Path": '"src/a.py"'}}]},
            {"type": "PLANNER_RESPONSE", "content": reply},
        ]
        tpath = self._write_jsonl("agy_guard.jsonl", entries)
        payload = {
            "hookEventName": "Stop",
            "terminationReason": "NO_TOOL_CALL",
            "fullyIdle": True,
            "continuationActive": False,
            "conversationId": "conv-agy-1",
            "transcriptPath": tpath,
            "lastUserInput": prompt,
        }
        first = evaluate_stop(payload, guard_cache_path=self.guard)
        self.assertEqual(first, {"decision": "continue", "reason": ANTIGRAVITY_CHALLENGE_REASON})
        second = evaluate_stop(payload, guard_cache_path=self.guard)
        self.assertEqual(second, {})

        # 同一会话内用户以完全相同的文本发起下一轮提问，因 last_user_idx 递增应重新允许触发 1 次
        entries.extend([
            {"type": "USER_INPUT", "content": f"<USER_REQUEST>\n{prompt}\n</USER_REQUEST>"},
            {"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "read_file", "args": {"Path": '"src/b.py"'}}]},
            {"type": "PLANNER_RESPONSE", "content": reply},
        ])
        tpath = self._write_jsonl("agy_guard.jsonl", entries)
        third = evaluate_stop(payload, guard_cache_path=self.guard)
        self.assertEqual(third, {"decision": "continue", "reason": ANTIGRAVITY_CHALLENGE_REASON})

    def test_claude_dialect_ignores_injected_challenge_user_message_and_blocks_repeat(self) -> None:
        followup = (
            "确认已最小治本：已经读取全部相关源码并确认唯一根因与状态所有者，无需多余补丁。" * 2
        )
        tpath = self._write_jsonl("claude_challenged.jsonl", [
            {"type": "user", "message": {"role": "user", "content": "给我一个修复方案，先别改代码"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "src/service.py"}},
            ]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "修复方案：" + ("步骤。" * 60)},
            ]}},
            {"type": "user", "message": {"role": "user", "content": CHALLENGE_REASON}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": followup},
            ]}},
        ])
        res = evaluate_stop(
            {
                "hook_event_name": "Stop",
                "session_id": "sess-challenged",
                "stop_hook_active": False,
                "transcript_path": tpath,
                "last_assistant_message": followup,
            },
            guard_cache_path=self.tmp_dir / "guard_claude_clean.json",
        )
        self.assertEqual(res, {})

    def test_claude_dialect_handles_tool_result_user_blocks_and_fallback_loop_guard(self) -> None:
        reply = "修复方案：通过新增重试队列和状态同步补丁绕过底层超时限制。" + ("详细步骤与影响说明。" * 28)
        tpath = self._write_jsonl("claude.jsonl", [
            {"type": "user", "message": {"role": "user", "content": "给我一个修复方案，先别改代码"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "src/service.py"}},
            ]}},
            # Claude JSONL 中 tool_result 也以 role=user 出现，不能覆盖人类提问
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "def run(): pass"},
            ]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": reply},
            ]}},
        ])
        payload = {
            "hook_event_name": "Stop",
            "session_id": "sess-1",
            "stop_hook_active": False,
            "transcript_path": tpath,
            "last_assistant_message": reply,
        }
        first = evaluate_stop(payload, guard_cache_path=self.guard)
        self.assertEqual(first, {"decision": "block", "reason": CHALLENGE_REASON})
        # 模拟桥接插件漏传 stop_hook_active=true：进程外防重兜底仍阻断第二次触发
        second = evaluate_stop(payload, guard_cache_path=self.guard)
        self.assertEqual(second, {})

    def test_codex_message_only_fallback_and_already_edited_skip(self) -> None:
        proposal = "推荐方案：在控制器层缓存上一次状态并加定时器重试。" + ("改动步骤与验证路径。" * 28)
        res = evaluate_stop(
            {
                "hook_event_name": "Stop",
                "session_id": "codex-1",
                "turn_id": "turn-1",
                "stop_hook_active": False,
                "last_assistant_message": proposal,
            },
            guard_cache_path=self.guard,
        )
        self.assertEqual(res.get("decision"), "block")

        edited_msg = "已完成修改，修复方案已落地并通过全部单测，退出码：0。" + ("改动列表说明。" * 30)
        res2 = evaluate_stop(
            {
                "hook_event_name": "Stop",
                "session_id": "codex-1",
                "turn_id": "turn-2",
                "stop_hook_active": False,
                "last_assistant_message": edited_msg,
            },
            guard_cache_path=self.guard,
        )
        self.assertEqual(res2, {})

    def test_installed_script_runs_as_subprocess_for_both_dialects(self) -> None:
        home = self.tmp_dir / "home"
        install_host_hook("antigravity", ROOT, home_dir=home)
        script = canonical_hook_script_path(home)
        tpath = self._write_jsonl("sub.jsonl", [
            {"type": "USER_INPUT", "content": "帮我出个修复方案"},
            {"type": "PLANNER_RESPONSE", "tool_calls": [{"name": "read_file", "args": {"Path": '"a.py"'}}]},
            {"type": "PLANNER_RESPONSE", "content": "修复方案：" + ("详细设计步骤。" * 40)},
        ])
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(script)],
            input=json.dumps({
                "hookEventName": "Stop",
                "terminationReason": "NO_TOOL_CALL",
                "fullyIdle": True,
                "continuationActive": False,
                "transcriptPath": tpath,
                "lastUserInput": "帮我出个修复方案",
            }, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        parsed_stdout = json.loads(proc.stdout)
        self.assertEqual(parsed_stdout["decision"], "continue")
        self.assertEqual(parsed_stdout["reason"], ANTIGRAVITY_CHALLENGE_REASON)

        # 验证写入 hooks.json 的真实 command 字符串可被宿主 shell 直接拉起（含 Windows cmd /c）
        cfg = json.loads((home / ".gemini" / "config" / "hooks.json").read_text(encoding="utf-8"))
        cmd = cfg["plan-root-cause-challenge"]["Stop"][0]["command"]
        shell_argv = ["cmd", "/c", cmd] if os.name == "nt" else ["sh", "-c", cmd]
        shell_proc = subprocess.run(
            shell_argv,
            cwd=str(home / ".gemini" / "config"),
            input=json.dumps({
                "hookEventName": "Stop",
                "terminationReason": "NO_TOOL_CALL",
                "fullyIdle": True,
                "continuationActive": True,
            }),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(shell_proc.stdout), {})

    def test_request_feedback_skips_visual_mockups_but_keeps_architecture_and_plan_paths(self) -> None:
        def _run_artifact(tag: str, path_val: str, summary: str, prompt: str, reply: str) -> dict:
            meta = json.dumps({"RequestFeedback": True, "Summary": summary, "UserFacing": True}, ensure_ascii=False)
            tpath = self._write_jsonl(f"agy_{tag}.jsonl", [
                {"type": "USER_INPUT", "content": f"<USER_REQUEST>\n{prompt}\n</USER_REQUEST>"},
                {"type": "PLANNER_RESPONSE", "tool_calls": [
                    {"name": "read_file", "args": {"Path": '"app/lib/ui/page.dart"'}},
                    {"name": "write_file", "args": {"Path": json.dumps(path_val), "ArtifactMetadata": meta}},
                ]},
                {"type": "PLANNER_RESPONSE", "content": reply},
            ])
            return evaluate_stop(
                {
                    "hookEventName": "Stop", "terminationReason": "NO_TOOL_CALL",
                    "fullyIdle": True, "continuationActive": False,
                    "conversationId": f"conv-{tag}", "transcriptPath": tpath, "lastUserInput": prompt,
                },
                guard_cache_path=self.tmp_dir / f"guard_{tag}.json",
            )

        # 1. 视觉模拟图 / 视觉预览 / walkthrough 带 RequestFeedback=true 不应误判为代码方案
        non_plans = (
            ("mockup", r"C:\u\brain\c1\membership_ui_mockup.md", "录音卡 v2 视觉重设计模拟图", "先用生图功能生成一个模拟图"),
            ("preview", r"C:\u\brain\c2\extension_visual_preview.md", "插件统一视觉改版预览集", "把新版界面预览图整理一下"),
            ("walkthrough", r"C:\u\brain\c3\walkthrough.md", "改动走查说明", "整理一下走查结果"),
        )
        for tag, path_val, summary, prompt in non_plans:
            self.assertEqual(_run_artifact(tag, path_val, summary, prompt, "已整理视觉模拟图请查看。" * 8), {}, tag)

        # 2. 真正的架构文档与正式方案路径（即便文件名含 prototype）仍触发 Antigravity 自包含反证
        for tag, path_val, summary, prompt in (
            ("arch", r"C:\u\brain\c4\bidirectional-architecture.md", "全矩阵双向对接开放平台架构设计", "梳理一下对接架构"),
            ("proto_plan", "docs/plans/frontend-prototype-review.md", "前端交互原型与视觉审查方案", "冻结原型与视觉审查方案"),
        ):
            self.assertEqual(
                _run_artifact(tag, path_val, summary, prompt, "已完成方案文档，请审阅。"),
                {"decision": "continue", "reason": ANTIGRAVITY_CHALLENGE_REASON},
                tag,
            )


class ProjectInitUpgradeHostHookCliTest(HarnessTestBase):
    def setUp(self) -> None:
        super().setUp()
        self._home_tmp = tempfile.TemporaryDirectory()
        self.fake_home = Path(self._home_tmp.name)

    def tearDown(self) -> None:
        self._home_tmp.cleanup()
        super().tearDown()

    def _run_with_home(self, *args: str, env_extra: dict[str, str] | None = None, expect_code: int = 0) -> dict:
        env = dict(os.environ)
        env[HOME_OVERRIDE_ENV] = str(self.fake_home)
        for key in list(env.keys()):
            if any(key.startswith(p) or key == p for p in (
                "ANTIGRAVITY_", "AGY_", "CLAUDECODE", "CLAUDE_CODE_",
                "CODEX_", "QODER_", "QODERCN_", "ZCODE_", "DSH_",
            )):
                env.pop(key, None)
        if env_extra:
            env.update(env_extra)
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(HARNESS), *args, "--json"],
            cwd=str(ROOT),
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, expect_code, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_preview_apply_needs_selection_then_configure_and_reuse(self) -> None:
        (self.fake_home / ".gemini" / "config").mkdir(parents=True)
        preview = self._run_with_home("project", "init", "--target", str(self.project))
        self.assertEqual(preview["host_hook"]["status"], "missing")
        self.assertFalse(canonical_hook_script_path(self.fake_home).exists())

        applied = self._run_with_home("project", "init", "--target", str(self.project), "--apply")
        self.assertNotIn("notices", applied)
        self.assertEqual(applied["host_hook"]["status"], "needs_host_selection")
        self.assertEqual(applied["host_hook"]["available_hosts"], [*HOST_IDS, "skip"])
        self.assertIn("--host", applied["host_hook"]["next_action"])

        configured = self._run_with_home(
            "project", "upgrade", "--target", str(self.project), "--apply", "--host", "antigravity"
        )
        self.assertEqual(configured["host_hook"]["status"], "configured")
        self.assertEqual(configured["host_hook"]["host"], "antigravity")
        self.assertTrue(is_host_configured("antigravity", self.fake_home))
        rules_dir = antigravity_rules_dir(self.fake_home)
        self.assertTrue((rules_dir / "docs-harness-antigravity-subagents.md").is_file())
        self.assertEqual((rules_dir / "docs-harness-windows-gui-launch.md").is_file(), os.name == "nt")

        # 新项目再次安装时检测到用户级已配置，不再要求选择，规则也已最新
        second_project = Path(self.temp.name) / "project2"
        second_project.mkdir()
        second = self._run_with_home("project", "init", "--target", str(second_project), "--apply")
        self.assertEqual(second["host_hook"]["status"], "already_configured")
        self.assertIn("antigravity", second["host_hook"]["configured_hosts"])
        self.assertEqual(second["host_hook"]["rules_updated"], [])

    def test_host_flag_rejected_on_non_install_actions(self) -> None:
        self._run_with_home("project", "init", "--target", str(self.project), "--apply", "--host", "skip")
        err = self._run_with_home(
            "project", "check", "--target", str(self.project), "--host", "antigravity", expect_code=2
        )
        self.assertEqual(err["code"], "unsupported_flag")


if __name__ == "__main__":
    unittest.main()
