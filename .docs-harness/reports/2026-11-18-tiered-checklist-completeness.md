# 2026-11-18 Docs Harness 2.36.0 三阶梯清单补齐（tasks / brief / full）

## 摘要与设计决策

针对中小改动与跨上下文/跨模型交接时各阶梯清单缺失的关键施工防呆字段，上游升版 `2.36.0`：
1. **阶梯 0（`.docs-harness/tasks/<任务>.md` + `checklist check`）**：受管入口新增「无 Plan 清单必须包含改动文件与符号、禁碰边界与脏文件、已知陷阱、验收命令与层级四项，有 Plan 清单只写 Plan 路径与勾选项」约定；新增受管模块 `scripts/checklist_check.py` 与命令 `checklist check --path <清单>`（对称 `report check`）。保留 1.x 旧 `task` 命令删除契约不变（`tests/test_cli_surface.py:105`、`docs/contracts.md:268`）。
2. **阶梯 1（`plan-templates/levels/brief.json`）**：新增必填字段 `constraints_and_pitfalls`（约束与已知陷阱），为 `scope`、`steps`、`acceptance` 补充可执行 `guidance`。
3. **阶梯 2（`plan-templates/levels/full.json`、`profiles/bugfix.json`、`scripts/plan_governance.py`）**：`full.json` 将 `constraints`（约束与已知陷阱）升级为 `required: true`、`module_interfaces.guidance` 补充既有调用方/消费链要求，并将结构化 `verification_scope`（支持可选 `layers[]`）从 `bugfix.json` 上提为全 `full` Profile 共用必填字段，在 `plan_governance.py` 统一校验。

## 改动路径

- 新增模块与测试：`scripts/checklist_check.py`、`tests/test_checklist_check.py`
- 模板与合同：`plan-templates/levels/brief.json`、`plan-templates/levels/full.json`、`plan-templates/profiles/bugfix.json`、`scripts/plan_governance.py`
- 控制器、参数与提示词：`scripts/harness.py`、`scripts/cli_support.py`、`scripts/agent_prompt.md`、`package.json`、`VERSION`、`evals/evals.json`、`AGENTS.md`、`.docs-harness/config.json`、`plan-templates/profiles/{architecture,backend-service,frontend-ui,general,migration-release}.json`
- 文档与测试夹具：`docs/CODEMAP.md`、`SKILL.md`、`docs/contracts.md`、`README.md`、`CHANGELOG.md`、`tests/harness_test_base.py`、`tests/test_cli_surface.py`、`tests/test_eval_cli_cases.py`、`tests/test_plan_selection_show.py`、`tests/test_plan_amend.py`、`tests/test_plan_lifecycle.py`、`tests/test_assets_check.py`、`tests/test_show_list.py`
- 运行态证据与本清单（本地/随仓）：`.docs-harness/tasks/tiered-checklist-completeness.md`、`.docs-harness/runtime/tiered-checklist-completeness/packet.json`（及 `evidence/01..03`）

## 验证命令、退出码与验证层级

- `python -m unittest tests.test_checklist_check -v`：6 项通过，退出码 0；验证层级：`focused_test`。
- `python -m unittest discover -s tests -p "test_*.py"`：487 项全部通过（skipped=12），退出码 0；验证层级：`repository_full_test`。
- `python scripts/harness.py release sync --target . --strict --json`：`status="consistent"`，退出码 0；验证层级：`focused_test`。
- `python scripts/harness.py self-test --target . --json`：`status="passed"`，退出码 0；验证层级：`focused_test`。
- `python scripts/harness.py assets-check --target . --strict --json`：`status="passed"`、`failures=[]`、`warnings=[]`，退出码 0；验证层级：`focused_test`。
- `python scripts/harness.py checklist check --target . --path .docs-harness/tasks/tiered-checklist-completeness.md --json`：`status="passed"`、`mode="standalone"`，退出码 0；验证层级：`local_runtime`。
- `python scripts/harness.py runtime check --target . --packet .docs-harness/runtime/tiered-checklist-completeness/packet.json --json`：`status="passed"`、`errors=[]`、`warnings=[]`，退出码 0；验证层级：`local_runtime`（全部后台 CLI 进程执行，0 前台窗口）。
- `cmd /c npm pack --dry-run`：生成 `docs-harness-2.36.0.tgz`（106 个文件含 `scripts/checklist_check.py`），退出码 0；验证层级：`package_or_install`。
- `git diff --check`：退出码 0；验证层级：`focused_test`。

## 未覆盖项

- 未执行 Git commit / tag / push，亦未升级其余 8 个维护中下游仓库（按用户确认的「先本地闭环」范围保留，待确认后统一发版同步）。
- `evals` 中 `behavior` 用例为人工多轮会话评审，本次未重跑真实会话（已通过新增确定性合同单测守卫规则与 CLI 行为）。
- 仅在 Windows Python 3.11 环境实测；macOS/Linux 与 Python 3.9 实机环境未覆盖。

## 编码质量自查

- **复用与检索**：改动前检索 `report_check`、`plan_governance`、`render_plan_markdown`、`validate_action_flags` 与 `test_cli_surface.py`；沿用 `report_check.py` 与 `command_report` 的接口形状与正则口径，但因两者语义不同（`report_check` 只查收尾五项、`checklist_check` 按 `docs/plans/` 引用分 `standalone`/`plan_linked` 双模式），故拆分为独立受管模块 `scripts/checklist_check.py`；未重复实现任何 Plan 字段校验，全部复用 `_validate_verification_scope` 与 `_err`。
- **是否引入重复逻辑**：无。全 `Full` 与 `bugfix` 共用 `_validate_verification_scope`，并拆出 `_err`、`_validate_full_regression_trigger` 与 `_validate_failure_attribution`，消除超过 60 行的函数并把 `plan_governance.py` 维持在 600 行阈值以内。
- **新增抽象职责**：`scripts/checklist_check.py` 专责 `.docs-harness/tasks/*.md` 双模式结构校验与 `checklist` 子命令解析；`_validate_verification_scope` 单点校验 Full Plan 的结构化 `verification_scope`（含可选 `layers` 枚举）。
