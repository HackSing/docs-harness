# 收尾记录：修复 Antigravity 防治标 Stop Hook 同轮重复触发

- 日期：2026-11-25
- 验证层级：`focused_test`、`local_runtime`
- 运行态证据包：`.docs-harness/runtime/stop-hook-loop-guard/packet.json`（`runtime check` 退出码：0）
- 前台/后台验证说明：全程在后台进程执行单测、静态检查与隔离临时目录运行态重放脚本，未弹出任何可见窗口、弹窗或抢夺焦点。

## 改动路径

- `scripts/plan_root_cause_hook.py`：
  - 新增 `_entry_contains_challenge`；在 `_is_human_turn_entry` 中排除含 `CHALLENGE_REASON` 的注入 `user` 消息，避免覆盖人类提问锚点；
  - 在 `_extract_turn_summary` 的 `state` 中增加 `already_challenged` 与 `last_user_idx`，扫描 `turn_entries` 内非 `assistant`/`PLANNER_RESPONSE` 条目（含 Antigravity `SYSTEM_MESSAGE` 及合成 `user` 反馈条目）是否已含 `CHALLENGE_REASON`；
  - 新增 `_loop_guard_digest`，并在 `evaluate_stop` 中先以 `state["already_challenged"]` 短路放行，同时移除 `if dialect != "antigravity":` 限制，使全部 6 个宿主共用进程外单轮防重锁（键含 `conversationId`/`session_id` + `u{last_user_idx}:{user_text[:120]}`）。
- `tests/test_host_hooks.py`：
  - 隔离 `test_antigravity_dialect_triggers_once_and_respects_continuation_active` 的 `guard_cache_path`；
  - 新增 3 项回归测试：`test_antigravity_blocks_repeat_when_transcript_has_stop_system_message`、`test_antigravity_loop_guard_blocks_second_trigger_and_allows_new_user_turn`、`test_claude_dialect_ignores_injected_challenge_user_message_and_blocks_repeat`。
- `C:/Users/freed/.docs-harness/hooks/plan_root_cause_hook.py`（本机用户级安装副本，不入库）：通过 `host_hooks.install_host_hook("antigravity", ROOT)` 同步更新，字节与 `scripts/plan_root_cause_hook.py` 一致。
- `dsh-plugin/vendor/harness/scripts/plan_root_cause_hook.py`（gitignored 本地构建产物）：通过 `node scripts/seed-vendor.mjs` 刷新，字节与真源一致。

## 根因细节与收尾自查

- **根因**：① Antigravity 续跑后未向 Stop Hook 传递真值 `continuationActive`；② `_extract_turn_summary` 跳过了 `SYSTEM_MESSAGE` 等非助手条目，忽略了轨迹中已记录的打回消息；③ `evaluate_stop` 通过 `if dialect != "antigravity":` 将 Antigravity 排除在进程外防重锁之外；④ 模型按提示回复「确认已最小治本」命中 `PROPOSAL_REPLY_RE` 中的 `治本`，导致同轮连续打回至多 3 次。
- **搜过什么**：已检索 `C:/Users/freed/.gemini`、`.agents` 与本仓库 `hooks.json` 配置及 `scripts/plan_root_cause_hook.py`、`scripts/host_hooks.py`、`tests/test_host_hooks.py`、`dsh-plugin/.gitignore`、`agy-customizations/docs/hooks.md`。
1. **是否引入了重复逻辑？**
   没有。全部 6 个宿主继续共用 `scripts/plan_root_cause_hook.py` 单一状态所有者，进程外防重统一通过 `_loop_guard_digest` + `_loop_guard_seen` 处理，轨迹已拦截检测统一通过 `_entry_contains_challenge` 处理。
2. **新增抽象各自的职责是什么？**
   - `_entry_contains_challenge`：判断轨迹条目（`content` 或 `message.content`）是否包含 `CHALLENGE_REASON`；
   - `_loop_guard_digest`：基于会话标识与 `last_user_idx`/提问前缀生成单轮防重摘要。

## 验证命令与退出码

- `python -X utf8 -m unittest tests.test_host_hooks tests.test_project_upgrade tests.test_cli_surface -v` —— 退出码：0（运行 52 项全部通过，其中 3 项按条件跳过；含 3 项新增回归测试；验证层级：`focused_test`）。
- `python -X utf8 scripts/harness.py structure check --target . --json` —— 退出码：0（`status=passed`，checked 57，failures 0，warnings 0；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py assets-check --target . --fast --json` —— 退出码：0（`status=passed`，failures 0，warnings 0；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py self-test --target . --json` —— 退出码：0（`status=passed`；验证层级：`focused_test`）。
- `cmd /c` 真实 `C:/Users/freed/.gemini/config/hooks.json` 命令重放 `45cb3a00` 第 42/50/52/54 行切片及防重/边界/异常探针 —— 退出码：0（`SLICES: [(42, 0, 'continue'), (50, 0, None), (52, 0, None), (54, 0, None)]`、`GUARD: 0 continue -> 0 {}`、`EMPTY/BAD/MISSING: 0 {}`、`BOUNDARY: 0 continue -> 0 continue`；证据见 `.docs-harness/runtime/stop-hook-loop-guard/evidence/live-hook-replay.log`；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py runtime check --target . --packet .docs-harness/runtime/stop-hook-loop-guard/packet.json --json` —— 退出码：0（`status=passed`；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py report check --target . --path .docs-harness/reports/2026-11-25-stop-hook-antigravity-loop-guard.md --json` —— 退出码：0。

## 未覆盖项

- 未新开一个全新 Antigravity 对话由宿主客户端原生自动触发 Stop Hook 做端到端实况观察（因本地无外挂新会话控制接口，已通过真实 `hooks.json` 命令 + 真实会话 `45cb3a00` 轨迹切片与隔离 `TEMP` 重放覆盖）。
- 未运行仓库级全量测试（本次仅修改独立 Stop Hook 脚本与 `test_host_hooks.py`，未触及公共基础设施或跨模块契约）。
