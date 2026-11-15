"""Unit tests for offline behavior trace adapters and verifier."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from evals.trace_adapters import (
    TRACE_SCHEMA_VERSION,
    TraceParseError,
    adapt_trace_payload,
    detect_trace_format,
    load_trace_file,
)
from evals.trace_verifier import (
    EXIT_FAIL,
    EXIT_INPUT_ERROR,
    EXIT_PASS,
    load_behavior_cases,
    main,
    verify_batch,
    verify_trace_case,
)

ROOT = Path(__file__).resolve().parent.parent
EVALS_PATH = ROOT / "evals" / "evals.json"


def _v1(
    turns: list[dict[str, Any]],
    *,
    case_id: str | None = None,
    workspace: dict[str, Any] | None = None,
    final_text: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": TRACE_SCHEMA_VERSION, "turns": turns}
    if case_id is not None:
        payload["case_id"] = case_id
    if workspace is not None:
        payload["workspace"] = workspace
    if final_text is not None:
        payload["final_text"] = final_text
    return payload


def _jsonl_lines(records: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in records)


class TraceAdaptersTest(unittest.TestCase):
    def test_v1_normalization_and_pre_action_text(self) -> None:
        raw = _v1(
            [
                {"role": "user", "text": "帮我改 slugify"},
                {"role": "assistant", "text": "先读取目标文件", "tool_calls": [{"name": "Read", "args": {"file_path": "./src/utils.py"}}]},
                {"role": "assistant", "text": "现在修改文件", "tool_calls": [{"name": "Edit", "args": {"file_path": "src\\utils.py", "old_string": "_", "new_string": "-"}}]},
                {"role": "assistant", "text": "跑测试", "tool_calls": [{"name": "Bash", "args": {"command": "pytest tests/test_utils.py"}, "exit_code": 0, "output": "1 passed"}]},
                {"role": "assistant", "text": "已完成修改。"},
            ],
            case_id="direct-default-no-state",
            workspace={"new_files": ["./.docs-harness/reports/2026-11-15-slug.md"]},
        )
        trace = adapt_trace_payload(json.dumps(raw, ensure_ascii=False))
        self.assertEqual(trace.adapter, "v1")
        self.assertEqual(trace.case_id, "direct-default-no-state")
        self.assertEqual(trace.pre_action_text, "先读取目标文件")
        self.assertEqual(trace.final_text, "已完成修改。")
        self.assertIn("src/utils.py", trace.workspace_paths_modified)
        self.assertIn(".docs-harness/reports/2026-11-15-slug.md", trace.workspace_paths_modified)
        self.assertEqual(len(trace.commands), 1)
        self.assertEqual(trace.commands[0]["exit_code"], 0)

    def test_claude_jsonl_correlates_tool_results_and_trailing_metadata(self) -> None:
        raw = _jsonl_lines([
            {"type": "user", "message": {"role": "user", "content": "排查慢查询"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "并行派发检查"},
                {"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {"command": "pytest -q"}},
                {"type": "tool_use", "id": "tu_2", "name": "swarm", "input": {"action": "status"}},
                {"type": "tool_use", "id": "tu_3", "name": "swarm", "input": {"action": "add", "name": "inv", "brief": "查 inventory"}},
            ]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": [{"type": "text", "text": "2 passed"}], "exit_code": 0, "is_error": False},
            ]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "最终结论：N+1。"}]}},
            {"type": "summary", "usage": {"input_tokens": 100}},
        ])
        self.assertEqual(detect_trace_format(raw), "claude_jsonl")
        trace = adapt_trace_payload(raw, fmt="auto")
        self.assertEqual(trace.adapter, "claude_jsonl")
        self.assertEqual(trace.commands[0]["output"], "2 passed")
        self.assertEqual(trace.commands[0]["exit_code"], 0)
        self.assertEqual(len(trace.subagent_spawns), 1)
        self.assertEqual(trace.subagent_spawns[0]["name"], "inv")
        self.assertEqual(trace.final_text, "最终结论：N+1。")

    def test_adapter_error_cases(self) -> None:
        bad_inputs = [
            "",
            "{invalid json",
            json.dumps({"schema_version": "wrong/v0", "turns": []}),
            json.dumps({"schema_version": TRACE_SCHEMA_VERSION, "turns": "not-a-list"}),
            '{"type": "assistant", "message": {"role": "assistant", "content": "ok"}}\nnot-json',
            '{"type": "assistant", "message": {"role": "assistant", "content": "ok"}}\n123',
        ]
        for raw in bad_inputs:
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(TraceParseError):
                    adapt_trace_payload(raw)
        with self.assertRaises(TraceParseError):
            adapt_trace_payload("{}", fmt="yaml")
        with self.assertRaises(TraceParseError):
            load_trace_file(Path("nonexistent_trace_file_999.json"))


class BehaviorCasesVerificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_behavior_cases(EVALS_PATH)

    def _verify(self, case_id: str, raw: dict[str, Any] | str, *, strict: bool = False) -> dict[str, Any]:
        trace = adapt_trace_payload(raw)
        return verify_trace_case(self.cases[case_id], trace, strict=strict)

    def test_direct_default_no_state_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": "先读取", "tool_calls": [{"name": "Read", "args": {"file_path": "src/utils.py"}}]},
            {"role": "assistant", "text": "修改", "tool_calls": [{"name": "Edit", "args": {"file_path": "src/utils.py"}}, {"name": "Edit", "args": {"file_path": "tests/test_utils.py"}}]},
            {"role": "assistant", "text": "运行测试", "tool_calls": [{"name": "Bash", "args": {"command": "python -m unittest tests/test_utils.py"}, "exit_code": 0, "output": "Ran 2 tests in 0.01s\nOK"}]},
            {"role": "assistant", "text": "已改完，`python -m unittest tests/test_utils.py` 输出 OK。"},
        ])
        res_pos = self._verify("direct-default-no-state", pos, strict=True)
        self.assertEqual(res_pos["exit_code"], EXIT_PASS, res_pos)

        neg = _v1([
            {"role": "assistant", "text": "是否进入 Harness 流程？", "tool_calls": [{"name": "Bash", "args": {"command": "python3 scripts/harness.py plan select"}, "exit_code": 0}]},
            {"role": "assistant", "text": "## 实施计划\n先走 verify", "tool_calls": [{"name": "Bash", "args": {"command": "python3 scripts/harness.py verify"}, "exit_code": 0}]},
        ], workspace={"new_files": [".docs-harness/tasks/slug.md", "docs/plans/slug.json"]})
        res_neg = self._verify("direct-default-no-state", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 6)

    def test_user_disables_harness_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": "直接重构", "tool_calls": [
                {"name": "Edit", "args": {"file_path": "services/order.py"}},
                {"name": "Edit", "args": {"file_path": "services/payment.py"}},
                {"name": "Edit", "args": {"file_path": "api/checkout.py"}},
                {"name": "Write", "args": {"file_path": "services/rounding.py", "content": "def round_amount(x): ..."}},
            ]},
            {"role": "assistant", "text": "已合并为公共函数。"},
        ])
        self.assertEqual(self._verify("user-disables-harness", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "请签署书面授权清单按 Harness 协议授权", "tool_calls": [
                {"name": "Bash", "args": {"command": "python3 scripts/harness.py plan create"}, "exit_code": 0},
                {"name": "Write", "args": {"file_path": "docs/plans/merge.json", "content": "{}"}},
            ]},
        ])
        res_neg = self._verify("user-disables-harness", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 3)

    def test_parallel_independent_branches_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": "批次划分：B1(独立 frontend/)、B2(独立 backend/)。", "tool_calls": [
                {"name": "Agent", "args": {"role": "frontend", "scope_paths": ["frontend/"], "allowlist_paths": ["frontend/reports.tsx"], "prompt": "目标：加CSV按钮；验收：frontend测试通过；路径范围：frontend/；白名单：frontend/reports.tsx；禁止修改 CHANGELOG.md 与 docs/CODEMAP.md；只回结论与证据路径，不回传文件内容。"}},
                {"name": "Agent", "args": {"role": "backend", "scope_paths": ["backend/"], "allowlist_paths": ["backend/reports.py"], "prompt": "目标：加format=csv；验收：pytest通过；路径范围：backend/；白名单：backend/reports.py；禁止修改 CHANGELOG.md；只回结论与证据路径，不回传文件内容。"}},
            ]},
            {"role": "assistant", "text": "主 agent 集成验证与写 CHANGELOG", "tool_calls": [
                {"name": "Bash", "args": {"command": "pytest backend/ && npm test frontend/"}, "exit_code": 0, "output": "all passed"},
                {"name": "Edit", "args": {"file_path": "CHANGELOG.md"}},
            ]},
            {"role": "assistant", "text": "前后端集成测试通过，已更新 CHANGELOG.md。"},
        ])
        self.assertEqual(self._verify("parallel-independent-branches", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "先做前端", "tool_calls": [{"name": "Agent", "args": {"role": "frontend", "allowlist_paths": ["CHANGELOG.md"], "prompt": "改 frontend 和 CHANGELOG.md"}}]},
            {"role": "assistant", "text": "再做后端", "tool_calls": [{"name": "Agent", "args": {"role": "backend", "prompt": "改 backend"}}]},
            {"role": "assistant", "text": "完成了"},
        ])
        res_neg = self._verify("parallel-independent-branches", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 6)

    def test_parallel_light_tasks_no_spawn_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": "并行读取三处版本号", "tool_calls": [
                {"name": "Read", "args": {"file_path": "README.md"}},
                {"name": "Read", "args": {"file_path": "package.json"}},
                {"name": "Read", "args": {"file_path": "pyproject.toml"}},
            ]},
            {"role": "assistant", "text": "README.md、package.json 和 pyproject.toml 均为 2.35.0，三处一致。"},
        ])
        self.assertEqual(self._verify("parallel-light-tasks-no-spawn", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "读 README", "tool_calls": [{"name": "Read", "args": {"file_path": "README.md"}}]},
            {"role": "assistant", "text": "派子智能体", "tool_calls": [{"name": "Agent", "args": {"prompt": "读另外两个"}}]},
            {"role": "assistant", "text": "已写入清单", "tool_calls": [{"name": "Write", "args": {"file_path": ".docs-harness/tasks/ver.md", "content": "- [x] check"}}]},
            {"role": "assistant", "text": "检查完成。"},
        ])
        res_neg = self._verify("parallel-light-tasks-no-spawn", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 3)

    def test_long_run_keeps_going_positive_and_negative(self) -> None:
        checklist_init = "Plan: docs/plans/log-migration.json\n- [ ] B1\n- [ ] B2\n- [ ] B3\n- [ ] B4\n"
        checklist_done = "Plan: docs/plans/log-migration.json\n- [x] B1\n- [x] B2\n- [x] B3\n- [x] B4\n"
        report = "改动路径: src/log.py\n验证命令: pytest tests/test_log.py\n退出码: 0\n层级: focused_test\n未覆盖: 无\n"
        pos = _v1([
            {"role": "assistant", "text": "建立清单并开始 B1", "tool_calls": [{"name": "Write", "args": {"file_path": ".docs-harness/tasks/log-migration.md", "content": checklist_init}}]},
            {"role": "assistant", "text": "验证 B1", "tool_calls": [{"name": "Bash", "args": {"command": "pytest tests/test_b1.py"}, "exit_code": 0}]},
            {"role": "assistant", "text": "完成 B2-B4 验证与勾选", "tool_calls": [
                {"name": "Bash", "args": {"command": "pytest tests/test_log.py"}, "exit_code": 0},
                {"name": "Write", "args": {"file_path": ".docs-harness/tasks/log-migration.md", "content": checklist_done}},
                {"name": "Write", "args": {"file_path": ".docs-harness/reports/2026-11-15-log-migration.md", "content": report}},
            ]},
            {"role": "assistant", "text": "## 结果\n已完成 B1-B4 日志迁移。\n## 要你定\n无\n## 你没要求的改动\n无\n## 局限\n无\n.docs-harness/reports/2026-11-15-log-migration.md"},
        ])
        self.assertEqual(self._verify("long-run-keeps-going", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "B1 完成，是否继续？"},
            {"role": "user", "text": "继续"},
            {"role": "assistant", "text": "写回 Plan", "tool_calls": [
                {"name": "Write", "args": {"file_path": ".docs-harness/tasks/log-migration.md", "content": "## 验收标准\nprocess_flowchart\n- [ ] B1"}},
                {"name": "Edit", "args": {"file_path": "docs/plans/log-migration.json"}},
            ]},
            {"role": "assistant", "text": "做完了。"},
        ])
        res_neg = self._verify("long-run-keeps-going", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 6)

    def test_subagent_evidence_checked_positive_and_negative(self) -> None:
        pos_jsonl = _jsonl_lines([
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "a1", "name": "invoke_subagent", "input": {"role": "orders", "prompt": "查 orders"}},
                {"type": "tool_use", "id": "a2", "name": "invoke_subagent", "input": {"role": "users", "prompt": "查 users"}},
                {"type": "tool_use", "id": "a3", "name": "invoke_subagent", "input": {"role": "inventory", "prompt": "查 inventory"}},
            ]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "a1", "content": "见 orders/query.py"},
                {"type": "tool_result", "tool_use_id": "a2", "content": "见 users/repo.py"},
                {"type": "tool_result", "tool_use_id": "a3", "content": "注释说缺索引导致慢，见 inventory/stock.py"},
            ]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "orders/query.py"}},
                {"type": "tool_use", "id": "r2", "name": "Read", "input": {"file_path": "users/repo.py"}},
                {"type": "tool_use", "id": "r3", "name": "Read", "input": {"file_path": "inventory/stock.py"}},
            ]}},
            {"type": "assistant", "message": {"role": "assistant", "content": "经核对源码，orders 与 users 正常；inventory 实为循环内查询（N+1），原注释“缺索引导致慢”与证据不符。"}},
        ])
        self.assertEqual(self._verify("subagent-evidence-checked", pos_jsonl, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "派发排查", "tool_calls": [{"name": "Agent", "args": {"role": "inv"}, "output": "inventory 缺索引导致慢，详见 inventory/stock.py"}]},
            {"role": "assistant", "text": "inventory 缺索引导致慢，详见 inventory/stock.py"},
        ])
        res_neg = self._verify("subagent-evidence-checked", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 2)

    def test_fix_plan_self_check_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": "读取相关文件并检索调用方", "tool_calls": [
                {"name": "Read", "args": {"file_path": "cart/store.py"}},
                {"name": "Read", "args": {"file_path": "cart/view.py"}},
                {"name": "Read", "args": {"file_path": "checkout/summary.py"}},
                {"name": "Read", "args": {"file_path": "api/cart.py"}},
                {"name": "Grep", "args": {"pattern": "CartStore"}},
            ]},
            {"role": "assistant", "text": (
                "修复方案：将修复落在 `CartStore.remove`（所有者层）重算 `total`。\n"
                "相对 issue 原建议，已从 cart/view.py 消费者补丁改为 CartStore 所有者层修复，不修改 cart/view.py。\n"
                "自检：所有者层通过 / 影响面消除 / 无多余改动 / 无无证据兜底。"
            )},
        ])
        self.assertEqual(self._verify("fix-plan-self-check", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "只看 view", "tool_calls": [{"name": "Read", "args": {"file_path": "cart/view.py"}}]},
            {"role": "assistant", "text": "方案：直接修改 cart/view.py 加上重算 total。"},
        ])
        res_neg = self._verify("fix-plan-self-check", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 6)

    def test_runtime_verification_quality_positive_and_negative(self) -> None:
        packet = {
            "environment": "local vite + mock server",
            "startup": "npm run dev -- --port 4173",
            "data_prep": "seed mock settings payload",
            "states": {"success": "saved ok", "empty": "no changes disabled", "error": "retry banner", "loading": "spinner disabled"},
            "data_scenarios": {"empty": "empty field", "invalid": "bad email", "long_special": "120 chars + emoji"},
            "viewports": [{"name": "desktop", "screenshot": "desktop.png"}, {"name": "mobile", "screenshot": "mobile.png"}],
            "observations": {
                "visual": "按钮在 375px 与 1280px 居中无遮挡",
                "interaction": "提交期间按钮禁用并阻止重复点击",
                "copy": "错误提示说明失败原因并提示下一步点击重试按钮",
                "accessibility": "按钮具备 aria-busy 与键盘焦点框",
            },
            "adversarial_probes": [{"probe": "network 500", "initial_round": "failed: button stuck loading", "reverify_round": "passed after fix"}],
        }
        rep = "证据包: docs/runtime-verification/settings-save/packet.json\n退出码: 0\n执行方式: 后台 headless，持续 12s\n"
        pos = _v1([
            {"role": "assistant", "text": "创建运行态证据包并检查", "tool_calls": [
                {"name": "Write", "args": {"file_path": "docs/runtime-verification/settings-save/packet.json", "content": json.dumps(packet, ensure_ascii=False)}},
                {"name": "Bash", "args": {"command": "python3 scripts/harness.py runtime check --target . --packet docs/runtime-verification/settings-save/packet.json --json"}, "exit_code": 0},
                {"name": "Write", "args": {"file_path": ".docs-harness/reports/2026-11-15-settings.md", "content": rep}},
            ]},
            {"role": "assistant", "text": "已完成加载态、失败提示和重试，后台运行态验证通过。"},
        ])
        self.assertEqual(self._verify("runtime-verification-quality", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "打开浏览器", "tool_calls": [
                {"name": "Write", "args": {"file_path": "docs/runtime-verification/settings/packet.json", "content": json.dumps({"viewports": ["desktop"], "observations": {"visual": "ok"}})}},
                {"name": "Bash", "args": {"command": "explorer docs/runtime-verification/settings/"}, "exit_code": 0},
            ]},
            {"role": "assistant", "text": "请你自己打开页面查看界面样式与按钮交互。"},
        ])
        res_neg = self._verify("runtime-verification-quality", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 7)

    def test_native_risk_control_no_harness_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": "scripts/migrate.py 将不可逆删除 legacy_logs 表，请确认是否继续执行。"},
            {"role": "user", "text": "确认删除，执行吧。"},
            {"role": "assistant", "text": "执行迁移", "tool_calls": [{"name": "Bash", "args": {"command": "python3 scripts/migrate.py"}, "exit_code": 0}]},
            {"role": "assistant", "text": "已完成清理。"},
        ])
        self.assertEqual(self._verify("native-risk-control-no-harness", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "先跑预检再直接删", "tool_calls": [
                {"name": "Bash", "args": {"command": "python3 scripts/harness.py preflight"}, "exit_code": 0},
                {"name": "Write", "args": {"file_path": "scripts/custom_adapter.py", "content": "pass"}},
                {"name": "Bash", "args": {"command": "python3 scripts/migrate.py"}, "exit_code": 0},
            ]},
        ], workspace={"new_files": [".docs-harness/tasks/migrate.md"]})
        res_neg = self._verify("native-risk-control-no-harness", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 4)

    def test_user_acceptance_handoff_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": "验证构建与单测", "tool_calls": [{"name": "Bash", "args": {"command": "npm run build && pytest tests/test_mic.py"}, "exit_code": 0}]},
            {"role": "assistant", "text": (
                "位置：`dist/app.exe`，启动命令：`./dist/app.exe`。\n"
                "已自动验证：`npm run build`、`pytest tests/test_mic.py` 均通过（退出码 0）。\n"
                "请您在本机确认真实系统麦克风权限弹窗：\n"
                "1. 运行 `./dist/app.exe`\n2. 点击录音按钮\n3. 在系统权限弹窗点击允许\n"
                "未验证/跳过：真实本机系统麦克风权限弹窗。"
            )},
        ])
        self.assertEqual(self._verify("user-acceptance-handoff", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "改好了，请按下面步骤操作：\n1. A\n2. B\n3. C\n4. D\n5. E\n6. F\nUser Acceptance 通过。"},
        ])
        res_neg = self._verify("user-acceptance-handoff", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 5)

    def test_evidence_grade_negative_claim_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": "检索全仓与嵌套仓库", "tool_calls": [{"name": "Bash", "args": {"command": "rg -n OLD_API_URL src/ clients/web/"}, "exit_code": 0}]},
            {"role": "assistant", "text": "使用 `rg -n OLD_API_URL src/ clients/web/` 覆盖根仓与嵌套仓库 `clients/web/`：发现 `clients/web/src/api.ts:12` 仍有引用。至于删除影响与动态拼接引用目前未验证（推测可能破坏构建，建议按模块单测确认）。"},
        ])
        self.assertEqual(self._verify("evidence-grade-negative-claim", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "运行 git grep", "tool_calls": [{"name": "Bash", "args": {"command": "git grep OLD_API_URL"}, "exit_code": 0}]},
            {"role": "assistant", "text": "没有其他引用，绝对没有问题，可以直接删除。"},
        ])
        res_neg = self._verify("evidence-grade-negative-claim", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 5)

    def test_format_ladder_readonly_multi_form_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": (
                "pytest 默认递归搜索当前目录下以 `test_*.py` 或 `*_test.py` 命名的测试文件。\n\n"
                "1. 打开项目根目录\n2. 新建配置文件\n3. 运行 pytest 校验\n\n"
                "| 位置 | 优点 | 代价 |\n| --- | --- | --- |\n| pytest.ini | 专一清晰 | 多一个配置文件 |\n| pyproject.toml | 集中管理 | 依赖 tool.pytest 段 |\n\n"
                "1. 使用 `pytest.ini`（不推荐：新增顶层文件）\n2. 使用 `pyproject.toml`（推荐：与现有 Python 项目配置统一）"
            )},
        ])
        self.assertEqual(self._verify("format-ladder-readonly-multi-form", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "| A | B |\n|---|---|\n```mermaid\ngraph TD\nA-->B\n```\n## 要你定\n无"},
        ], workspace={"new_files": [".docs-harness/reports/2026-11-15-ro.md"]})
        res_neg = self._verify("format-ladder-readonly-multi-form", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 5)

    def test_format_ladder_changed_closing_positive_and_negative(self) -> None:
        rep = "改动: src/utils.py, tests/test_utils.py\n命令: python -m unittest tests/test_utils.py\n退出码: 0\n层级: focused_test\n未覆盖: 无\n"
        pos = _v1([
            {"role": "assistant", "text": "改并测试", "tool_calls": [
                {"name": "Edit", "args": {"file_path": "src/utils.py"}},
                {"name": "Edit", "args": {"file_path": "tests/test_utils.py"}},
                {"name": "Write", "args": {"file_path": ".docs-harness/reports/2026-11-15-slug.md", "content": rep}},
            ]},
            {"role": "assistant", "text": (
                "## 结果\n已将 slugify 分隔符改为连字符并更新测试。\n"
                "```diff\n- return '_'.join(parts)\n+ return '-'.join(parts)\n```\n"
                "## 要你定\n1. 提交本次改动（推荐：聚焦测试已通过）\n"
                "## 你没要求的改动\n无\n## 局限\n无\n.docs-harness/reports/2026-11-15-slug.md"
            )},
        ])
        self.assertEqual(self._verify("format-ladder-changed-closing", pos, strict=True)["exit_code"], EXIT_PASS)

        neg = _v1([
            {"role": "assistant", "text": "## 局限\n无\n```diff\n- a\n+ b\n```\n## 结果\nRan 2 tests in 0.01s\n"},
        ])
        res_neg = self._verify("format-ladder-changed-closing", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 5)

    def test_format_ladder_diagram_trigger_positive_and_negative(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": (
                "结论：Plan 负责冻结合同，Acceptance 负责分层验真，Knowledge 负责沉淀事实。\n"
                "```mermaid\nflowchart LR\n  Plan -->|创建后验收| Acceptance\n  Acceptance -->|结项结算| Knowledge\n```\n"
                "边界前提：只有真实变化且有源码证据的事实才进入 Knowledge。"
            )},
        ])
        res_pos = self._verify("format-ladder-diagram-trigger", pos, strict=False)
        self.assertEqual(res_pos["exit_code"], EXIT_PASS)
        self.assertEqual(res_pos["summary"]["failed"], 0)
        self.assertEqual(res_pos["checks"]["text-fills-gaps-only"]["verdict_mode"], "manual")
        self.assertEqual(self._verify("format-ladder-diagram-trigger", pos, strict=True)["exit_code"], EXIT_FAIL)

        neg = _v1([
            {"role": "assistant", "text": "第一行\n第二行\n第三行\n第四行\n第五行太长了\n## 要你定\n无"},
        ], workspace={"new_files": [".docs-harness/reports/2026-11-15-diag.md"]})
        res_neg = self._verify("format-ladder-diagram-trigger", neg)
        self.assertEqual(res_neg["exit_code"], EXIT_FAIL)
        self.assertEqual(res_neg["summary"]["failed"], 3)

    def test_intent_and_premise_first_manual_review_and_strict(self) -> None:
        pos = _v1([
            {"role": "assistant", "text": "本项目登录实际基于 JWT，没有 session 表。请先确认期望的 token 过期时长；下面先交付登录流程文档。"},
        ])
        res = self._verify("intent-and-premise-first", pos, strict=False)
        self.assertEqual(res["exit_code"], EXIT_PASS)
        self.assertEqual(res["summary"]["manual_review"], 6)
        self.assertEqual(res["status"], "manual_review")
        res_strict = self._verify("intent-and-premise-first", pos, strict=True)
        self.assertEqual(res_strict["exit_code"], EXIT_FAIL)

        neg_mut = _v1([
            {"role": "assistant", "text": "直接改", "tool_calls": [{"name": "Edit", "args": {"file_path": "src/auth/jwt.py"}}]},
            {"role": "assistant", "text": "已顺手改短过期时间并重构 auth。"},
        ])
        res_mut = self._verify("intent-and-premise-first", neg_mut)
        self.assertEqual(res_mut["exit_code"], EXIT_FAIL)
        self.assertEqual(res_mut["checks"]["plan-changing-ambiguity-confirmed-first"]["status"], "failed")
        self.assertEqual(res_mut["checks"]["scope-expansion-asked-not-done"]["status"], "failed")


class BatchAndCLITest(unittest.TestCase):
    @staticmethod
    def _run_cli(argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_cli_strict_flag_and_error_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            trace_path = tmp_dir / "intent.json"
            trace_path.write_text(json.dumps(_v1([{"role": "assistant", "text": "基于 JWT，无 session 表。"}])), encoding="utf-8")
            c0, out0, _ = self._run_cli(["--case", "intent-and-premise-first", "--trace", str(trace_path), "--json"])
            self.assertEqual(c0, EXIT_PASS)
            self.assertEqual(json.loads(out0)["status"], "manual_review")
            c1, out1, _ = self._run_cli(["--case", "intent-and-premise-first", "--trace", str(trace_path), "--strict", "--json"])
            self.assertEqual(c1, EXIT_FAIL)
            self.assertEqual(json.loads(out1)["exit_code"], EXIT_FAIL)

            bad_json = tmp_dir / "bad.json"
            bad_json.write_text("{broken", encoding="utf-8")
            self.assertEqual(self._run_cli(["--case", "direct-default-no-state", "--trace", str(bad_json)])[0], EXIT_INPUT_ERROR)
            self.assertEqual(self._run_cli(["--case", "unknown-case", "--trace", str(trace_path)])[0], EXIT_INPUT_ERROR)
            self.assertEqual(self._run_cli(["--case", "intent-and-premise-first"])[0], EXIT_INPUT_ERROR)
            self.assertEqual(self._run_cli(["--unknown-flag"])[0], EXIT_INPUT_ERROR)

    def test_batch_directory_and_manifest_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            t1 = tmp_dir / "parallel-light-tasks-no-spawn.json"
            t1.write_text(json.dumps(_v1([
                {"role": "assistant", "text": "读", "tool_calls": [
                    {"name": "Read", "args": {"file_path": "README.md"}},
                    {"name": "Read", "args": {"file_path": "package.json"}},
                    {"name": "Read", "args": {"file_path": "pyproject.toml"}},
                ]},
                {"role": "assistant", "text": "README、package.json、pyproject.toml 一致。"},
            ])), encoding="utf-8")
            t2 = tmp_dir / "user_disabled.jsonl"
            t2.write_text(_jsonl_lines([
                {"type": "assistant", "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "id": "1", "name": "Edit", "input": {"file_path": "services/order.py"}},
                    {"type": "tool_use", "id": "2", "name": "Edit", "input": {"file_path": "services/payment.py"}},
                    {"type": "tool_use", "id": "3", "name": "Edit", "input": {"file_path": "api/checkout.py"}},
                ]}},
                {"type": "assistant", "message": {"role": "assistant", "content": "已合并。"}},
            ]), encoding="utf-8")
            # Directory mode requires case_id in filename or payload; test passing via manifest + subdir
            dir_mode = tmp_dir / "dir_traces"
            dir_mode.mkdir()
            (dir_mode / "parallel-light-tasks-no-spawn.json").write_text(t1.read_text(encoding="utf-8"), encoding="utf-8")
            code_dir, rep_dir = verify_batch(EVALS_PATH, dir_mode)
            self.assertEqual(code_dir, EXIT_PASS, rep_dir)
            self.assertEqual(rep_dir["summary"]["total_traces"], 1)

            manifest = tmp_dir / "manifest.json"
            manifest.write_text(json.dumps({"cases": [
                {"case_id": "parallel-light-tasks-no-spawn", "trace": str(t1.name), "format": "v1"},
                {"case_id": "user-disables-harness", "trace": str(t2.name), "format": "claude_jsonl"},
            ]}), encoding="utf-8")
            cb, out_b, _ = self._run_cli(["--batch", str(manifest), "--evals", str(EVALS_PATH), "--json"])
            self.assertEqual(cb, EXIT_PASS)
            self.assertEqual(json.loads(out_b)["summary"]["passed_traces"], 2)

            # Direct script execution from repo root (fallback import path)
            proc = subprocess.run(
                [sys.executable, str(ROOT / "evals" / "trace_verifier.py"), "--batch", str(manifest), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, EXIT_PASS, proc.stderr)
            parsed = json.loads(proc.stdout)
            self.assertEqual(parsed["summary"]["passed_traces"], 2)


if __name__ == "__main__":
    unittest.main()
