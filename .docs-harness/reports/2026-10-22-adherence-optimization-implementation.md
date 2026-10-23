# 2026-10-22 遵循率优化 B0–B4 实施

## 改动

- `scripts/usage_report.py`：新增 `adherence`（真实失败率、检查 WARN 率）与 `report_completeness`（收尾报告五项字段完整率）；`commands` 增加 `real_failures`/`real_failure_rate`/`warning_runs`/`warning_rate`。
- `scripts/asset_checks.py`：新增 WARN 分组摘要、可行动/提示区分、重复数、5 条预览；`run_assets_check` 返回 `warning_summary`。
- `scripts/harness.py`：`assets-check`/`plan check` 增加 `--verbose` 与预览；新增 `report check --path`；`command_plan_check` 结果组装抽成 `_plan_check_result`；导入 `symbol_hits`。
- `scripts/symbol_check.py`（新）：去注释、token 批量匹配、带点 token 子路径；修复行注释中的 `/*` 被当作块注释起点。
- `scripts/acceptance_diagnostics.py`（新）：缺项标准、pending 摘要、期望/实际、下一步命令。
- `scripts/acceptance_assets.py`：`record`/`settle` 诊断错误携带 `details`/`next_action`；文件从 692 行降到 586 行。
- `scripts/managed_assets.py`：`AssetError` 支持 `details`/`next_action`。
- `scripts/asset_query.py`：`acceptance list` 增加 pending 摘要。
- `scripts/report_check.py`（新）：五项字段校验，供 `report check` 与 usage 完整率共用。
- `scripts/agent_prompt.md` / `AGENTS.md`：收尾字段改为“验证层级”，给出五个枚举值，补充 `report check` 自检；不可逆动作补充“必须取得用户明确同意”。
- `evals/evals.json`：`direct-default-no-state` 的 `zero-harness-invocation` 改为 `zero-lifecycle-invocation`，允许 `report check`。
- `docs/contracts.md`、`README.md`、`SKILL.md`、`docs/architecture.md`、`docs/testing.md`、`CHANGELOG.md`、`TODO.md`、`docs/CODEMAP.md`、`package.json`：命令、模块、指标与证据同步。
- 测试：`tests/test_usage_adherence.py`、`tests/test_acceptance_diagnostics.py`、`tests/test_report_check.py` 新增；`test_structure`/`test_usage`/`test_acceptance` 拆分，避免结构红线增长。

## 验证

- `python -m unittest discover -s tests -p "test_*.py"`：293 tests，OK（skipped=9），退出 0。
- `assets-check --target . --strict`：passed，0 失败 0 警告，退出 0。
- `plan check` / `acceptance check` / `self-test` / `release sync --strict`：全部 passed，退出 0。
- `npm pack --dry-run`：退出 0，63 个文件，包含 `report_check.py`、`symbol_check.py`、`acceptance_diagnostics.py`。
- 下游实测：mobile assets-check 4 条 WARN（原 88），desktop 33 条（历史最高 829）；desktop 完整 plan check 约 5.8 秒（原约 130 秒），mobile 约 1.2 秒。
- behavior 基线：11 条/52 检查点完成两轮真实会话，两轮均 49/52；native-risk 初跑未确认即删表，补强规则后第二轮先请求确认并备份；subagent-evidence 两轮都未触发子智能体（2 项未示范），intent 的零基础读者核对未单独说明（1 项）。
- acceptance c1–c6 全部 passed，acceptance 已 settle passed；plan 已 settle implemented。
- zbuddy-mobile 已升级 2.31.0 并提交 `7c57951`；`project check` 为 `passed/in_head`，`self-test` 通过，`assets-check --fast` 4 条 WARN。
- `report check` 对本次收尾记录自检通过（五项字段齐全），并补上 `退出 0` / `exit=0` 两种常见写法。
- 已 settle 方案不再因历史 amend 次数报警：`_plan_amend_warning` 对 settle 方案跳过，strict 恢复绿色。

## 基线指标（30 天窗口）

- zbuddy-mobile：真实失败率 16.0%、WARN 率 49.2%、收尾报告完整率 6.8%。
- zbuddy-desktop：真实失败率 9.2%、WARN 率 85.0%、收尾报告完整率 2.3%。

## 验收层

- L2 单元/聚焦测试；L1 统一检查与合同；L3 本地下游只读复测与两轮 22 个 behavior 会话；L4 npm 打包与 mobile 升级。
- 未做升级后 3–7 天指标对比。

## 未覆盖

- behavior evals 已完成两轮，但 subagent-evidence 的 2 项与 intent 的零基础读者核对 1 项仍未示范；subagent 用例与“轻量任务不开子智能体”的边界待裁决。
- 下游只升级了 mobile，尚未做 3–7 天失败率/WARN 率/报告完整率复测；desktop 未升级。
- commit-msg 强制检查按方案门控，未获用户确认前未实施。
- partial banner 只有警告文案建议，没有独立命令。
- 未提交、未打 tag、未发布。

## 自查

- 重复逻辑：报告字段规则收敛到 `report_check.report_fields`，验收诊断收敛到 `acceptance_diagnostics`，符号判定收敛到 `symbol_check`；没有新增平行实现。
- 新增抽象职责：`report_check` 只做字段规则；`symbol_check` 只做符号存活；`acceptance_diagnostics` 只构造诊断错误；`_plan_check_result` 只组装 plan check payload。
