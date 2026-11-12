# 收尾记录：意图路由接入 Google Gemini Decisions（`gemini-decision-1`）

- 日期：2026-11-12
- 验证层级：`focused_test`、`local_runtime`
- 运行态证据包：`.docs-harness/runtime/gemini-decisions-router/packet.json`（`runtime check` 退出码：0）
- 前台/后台验证说明：全程后台进程执行（单测、本地 HTTPServer mock 联调、`assets-check` 与 `runtime check`），未弹出任何可见窗口或抢夺焦点，耗时约 18 秒。

## 改动路径

- `evals/intent_routing/jev_predict.py`
- `routing/hosts/qoder/route_hook.py`
- `routing/hosts/qoder/settings.decisions.example.json`
- `routing/hosts/qoder/README.md`
- `docs/CODEMAP.md`
- `docs/routing.md`
- `evals/intent_routing/README.md`
- `tests/test_jev_predict.py`
- `tests/test_qoder_hook.py`

## 复用检索与设计说明

- 动手前检索 `docs/CODEMAP.md`、`evals/intent_routing/jev_predict.py` 与 `routing/hosts/qoder/route_hook.py`，确认 `jev_predict.py` 已实现 1 个主意图 `choice` + 7 个副意图 `noul` + 3 个辅助 `noul`（`clarify_required`、`direct_override`、`code_verify`）及阈值映射逻辑。
- Google Gemini Decisions API（`gemini-decision-1`，`POST /v1beta/decisions`）与 TypeSafe Jev 同属 `choice` + `noul` 原语体系，区别仅在请求顶层字段为 `input`（字符串化 JSON）、`noul` 的 `criteria` 键名为 `true_description`/`false_description`、鉴权头为 `x-goog-api-key`（读取 `GEMINI_API_KEY` 或 `GOOGLE_API_KEY`），以及响应 `usage` 字段包含 `total_input_tokens`/`total_output_tokens`。
- 因此直接在 `evals/intent_routing/jev_predict.py` 中复用同一套问题定义与阈值规则，并通过 `route_prompt_with_decisions` 暴露给 `routing/hosts/qoder/route_hook.py` 的 `decisions` 后端调用。

## 收尾自查

1. **本次是否引入了重复逻辑？**
   没有。`call_systemone` 与 `call_gemini_decisions` 共用底层的 `_post_json_with_retry`；离线评测 `interpret_response` 与在线路由 `route_prompt_with_decisions` 共用 `answers_to_profile` 与 `extract_usage`；`GEMINI_QUESTIONS` 由 `_to_gemini_questions(QUESTIONS)` 自动派生，未复制粘贴任何问题定义或阈值逻辑。
2. **本次新增的抽象各自的职责是什么？**
   - `_to_gemini_questions` / `build_decisions_payload`：将共享问题集与输入状态转换为 Gemini Decisions API（`v1beta/decisions`）要求的请求格式。
   - `answers_to_profile` / `extract_usage`：纯函数，将模型返回的 `answers` 与 `usage` 解析为宿主可校验的路由画像与 token 计数。
   - `_post_json_with_retry` / `call_gemini_decisions`：负责带指数退避重试与本地回环代理绕过的 HTTP POST 调用。
   - `route_prompt_with_decisions` / `_route_task_decisions`：串联环境变量读取、Decisions API 调用、画像 `evidence` 长度收敛（`<= 8`）与成本估算（\$0.10 / 1M input tokens），向 `route_hook.py` 提供 `decisions` 后端。

## 验证命令与退出码

- `python -m unittest tests.test_jev_predict tests.test_qoder_hook tests.test_routing_contract tests.test_routing_shadow tests.test_routing_metrics tests.test_routing_offline tests.test_routing_signals tests.test_routing_surface tests.test_intent_routing_eval -v` — 退出码：0（127 项测试通过，3 项 Windows cmd.exe 包装器测试按原跳过规则跳过）
- `python scripts/harness.py runtime check --target . --packet .docs-harness/runtime/gemini-decisions-router/packet.json --json` — 退出码：0
- `python scripts/harness.py assets-check --strict --json` — 退出码：0（违规 0 条、警告 0 条）

## 未覆盖项

- 本机环境未配置真实 `GEMINI_API_KEY`，尚未在真实 Google Gemini Decisions 线上端点运行 100 条基线数据集（20 诊断 + 2×50 held-out）的准确率对标与线上延迟实测；配置 `GEMINI_API_KEY` 后可直接运行 `jev_predict.py --model gemini-decision-1` 与 `DOCS_HARNESS_ROUTER_BACKEND=decisions` 采集真实数据。

---

## 第二次收尾追加（真实 `GEMINI_API_KEY` 线上实测与证据包去 mock）

- 运行态证据包：`.docs-harness/runtime/gemini-decisions-router/packet.json`（已更新为 `mock: false`，`runtime check` 退出码：0）
- 前台/后台验证说明：后台执行 120 条线上评测与 `route_hook.py` 线上 Canary/Shadow 实测，无前台窗口，耗时约 35 秒。

### 改动路径

- `.docs-harness/runtime/gemini-decisions-router/packet.json`
- `.docs-harness/evals/gemini-decision-diagnostic.json`
- `.docs-harness/evals/gemini-decision-held-out-1.json`
- `.docs-harness/evals/gemini-decision-held-out-2.json`
- `.docs-harness/evals/gemini-decision-summary.json`
- `evals/intent_routing/README.md`
- `.docs-harness/reports/2026-11-12-gemini-decisions-router.md`

### 验证命令与退出码

- `python evals/intent_routing/jev_predict.py --model gemini-decision-1`（三组数据集共 120 条）+ `python evals/intent_routing/score.py` — 退出码：0
  - `cases.json`（20 条）：模块完全匹配 100.0%，关键漏配率 0.0%，错配率 0.0%，澄清准确率 100.0%（32,953 input tokens / 0 output tokens）。
  - `held_out_cases.json`（50 条）：模块完全匹配 80.0%，关键漏配率 4.0%（较 Jev 1.14.0 的 14.0% 下降 10 个百分点），错配率 20.0%，澄清准确率 100.0%（消除 Jev 的 6 条误澄清；82,054 input tokens / 0 output tokens）。
  - `held_out_cases_2.json`（50 条）：模块完全匹配 80.0%，关键漏配率 10.0%，错配率 20.0%，澄清准确率 98.0%（81,899 input tokens / 0 output tokens）。
- `python scripts/harness.py runtime check --target . --packet .docs-harness/runtime/gemini-decisions-router/packet.json --json` — 退出码：0
- `python scripts/harness.py report check --path .docs-harness/reports/2026-11-12-gemini-decisions-router.md --json` — 退出码：0
- `python scripts/harness.py assets-check --strict --json` — 退出码：0

### 未覆盖项

- 尚未在日常 Qoder 会话中开启 1–2 周 B2 Shadow 连续采样；多意图用例中次要意图阈值（当前沿用 Jev 的 `SECONDARY_INTENT_MIN = 0.8`）按冻结方案约束不在已消费 held-out 集上回调，留待真实 B2 Shadow 样本校准。

---

## 第三次收尾追加（还原 Qoder 配置并切换 Antigravity `PreInvocation` 开启日常 B2 Shadow 采样）

- 验证层级：`focused_test`、`local_runtime`
- 运行态证据包：`.docs-harness/runtime/gemini-decisions-router/packet.json`（`runtime check` 退出码：0）
- 前台/后台验证说明：全程后台进程执行（131 项单测与 Antigravity `hooks.json` 真实命令端到端实测），未弹出可见窗口或抢夺焦点，耗时约 11 秒。

### 改动路径

- `C:/Users/freed/.qoder-cn/settings.json`（已完整还原至修改前状态并清理临时备份）
- `C:/Users/freed/.gemini/config/hooks.json`（全局安装 Antigravity `PreInvocation` B2 Shadow 钩子）
- `routing/hosts/antigravity/route_hook.py`
- `routing/hosts/antigravity/hooks.example.json`
- `routing/hosts/antigravity/README.md`
- `evals/intent_routing/jev_predict.py`
- `docs/CODEMAP.md`
- `docs/routing.md`
- `tests/test_antigravity_hook.py`
- `tests/test_jev_predict.py`
- `.docs-harness/runtime/gemini-decisions-router/packet.json`
- `.docs-harness/reports/2026-11-12-gemini-decisions-router.md`

### 收尾自查

1. **本次是否引入了重复逻辑？**
   没有。`routing/hosts/antigravity/route_hook.py` 直接导入并复用 `routing/hosts/qoder/route_hook.py`、`route_cache.py`、`route_diagnostics.py`、`route_signals.py` 与 `evals/intent_routing/jev_predict.py` 的核心路由、缓存、校验和契约渲染函数，仅实现 Antigravity `PreInvocation` 的输入提取（剥离 `<USER_REQUEST>` 与附加元数据）、同轮工具调用去重及 `injectSteps` / `{}` JSON 输出适配。
2. **本次新增的抽象各自的职责是什么？**
   - `_gemini_api_key`（`jev_predict.py`）：统一解析 Gemini Decisions API 密钥来源（显式参数 → 环境变量 → `DOCS_HARNESS_GEMINI_ENV_FILE` 本地密钥文件），避免在 `hooks.json` 中硬编码密钥。
   - `extract_user_prompt` / `_is_same_turn_invocation` / `_emit_agy`（`routing/hosts/antigravity/route_hook.py`）：适配 Antigravity `PreInvocation` 生命周期协议，剥离 `<USER_REQUEST>` 标签、对单轮工具循环内的重复 `PreInvocation` 去重，并输出符合 Antigravity 合同的 `{}` 或 `injectSteps` JSON。

### 验证命令与退出码

- `python -m unittest tests.test_antigravity_hook tests.test_jev_predict tests.test_qoder_hook tests.test_routing_contract tests.test_routing_shadow tests.test_routing_metrics tests.test_routing_offline tests.test_routing_signals tests.test_routing_surface tests.test_intent_routing_eval -v` — 退出码：0（131 项通过，3 项跳过）
- 使用 `C:/Users/freed/.gemini/config/hooks.json` 中的 `cmd /c C:/Windows/py.exe -3 D:/Project/docs-harness/routing/hosts/antigravity/route_hook.py ...` 实测带 `routing/registry.json` 的工作区（首轮路由 + 同轮第 2 次工具步去重）与无 `registry.json` 的普通工作区 — 退出码：0（写出 1 条 `phase="shadow"`、`model.name="gemini-decision-1"`、`tokens_in=1632`、`latency_ms=1668.4` 事件；同轮第 2 次调用去重不重复请求；普通工作区返回 `{}` 且不建 `.docs-harness` 目录）
- 真实 Antigravity 会话 `PreInvocation` 自动触发验证：当前会话提交消息时自动写入 `.docs-harness/routing/shadow-2026-11.jsonl`（`task_id="task-e8e6c891bc83bee3"`、`phase="shadow"`、`model.name="gemini-decision-1"`、`tokens_in=1622`、`latency_ms=1123.5`、`cost_usd=0.0001622`）
- `python scripts/harness.py runtime check --target . --packet .docs-harness/runtime/gemini-decisions-router/packet.json --json` — 退出码：0
- `python scripts/harness.py report check --path .docs-harness/reports/2026-11-12-gemini-decisions-router.md --json` — 退出码：0
- `python scripts/harness.py assets-check --strict --json` — 退出码：0（违规 0 条、警告 0 条）

### 未覆盖项

- 已在 Antigravity 全局 `~/.gemini/config/hooks.json` 开启 B2 Shadow 日常采样；后续需在日常开发会话中积累 1–2 周真实样本，再用真实 Shadow 数据评估是否微调多意图次要意图阈值 `SECONDARY_INTENT_MIN`。

