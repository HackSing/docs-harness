# Harness P0/P1 修复收尾记录（2026-10-21）

Plan：`docs/plans/harness-p0-p1-fixes.json`（已 settle implemented）
Acceptance：`docs/acceptance/harness-p0-p1-fixes.json`（已 settle passed）
验收证据：`docs/acceptance/evidence/harness-p0-p1/`

## 改动路径

- `scripts/harness.py`：完整 `execution_projection`；`plan show`；`plan create` 直接选择；selection v3 合同指纹与 `content_template`；错误 envelope 与聚合；action flag 边界；`plan check` 投影/索引交叉校验；`structure --base` 接线；README/SKILL 版本源与自检键。
- `scripts/plan_governance.py`：`plan amend` 允许带 reason 修改治理声明；`plan settle` 拒绝仅 deprecated/superseded 的验收集合。
- `scripts/plan_amend.py`：amend 返回新的 `execution_projection`。
- `scripts/acceptance_assets.py`：新增 `amend`；`_next_revision` 记录 amend_reason；新增资源状态标签。
- `scripts/knowledge_assets.py`：受管事实排序、`source_ok`、create/update 即时冲突、`omitted`。
- `scripts/adr_assets.py`：`active_constraints`，为 knowledge query 提供活跃 ADR 决策。
- `scripts/structure_check.py`：`symbol_hit` 定义级匹配；`--base` 支持；旧版本按基线读取。
- `scripts/managed_assets.py`：Markdown 横幅与 INDEX 状态和 JSON 对齐（WARN）。
- `tests/test_plan_lifecycle.py`、`tests/test_eval_cli_cases.py`（未改）、`tests/test_plan_amend.py`、`tests/test_plan_governance.py`、`tests/test_acceptance.py`、`tests/test_knowledge.py`、`tests/test_structure.py`、`tests/test_cli_surface.py`、`tests/test_release_version_sync.py`：新增/更新覆盖。
- 文档：`AGENTS.md`（受管区块同步）、`SKILL.md`、`README.md`、`docs/architecture.md`、`docs/contracts.md`、`docs/testing.md`、`docs/CODEMAP.md`、`CHANGELOG.md`、`TODO.md`。
- 新资产：`docs/plans/harness-p0-p1-fixes.*`、`docs/acceptance/harness-p0-p1-fixes.*`、`docs/acceptance/evidence/harness-p0-p1/`。

工作区在本次开始前已有未提交的 2.30.0 改动（HEAD 为 2.28.0）。本次改动叠加在这些改动之上，未回退用户内容；`git diff --stat` 中的 `VERSION`、`package.json`、模板、`test_adr.py`、`test_project_*`、`docs/downstream.md`、`evals/evals.json` 等属于既有工作。

## 验证

| 命令 | 结果 |
|---|---|
| `python -m unittest discover -s tests -p "test_*.py"` | 265 项 OK，跳过 9 |
| `test_plan_lifecycle` / `test_acceptance` / `test_knowledge` / `test_structure` / `test_cli_surface` 等聚焦套件 | 全部退出码 0（见证据文件） |
| `python scripts/harness.py plan check --target . --json` | passed，0 failures，0 warnings |
| `python scripts/harness.py acceptance check --target . --json` | passed，0 failures，0 warnings |
| `python scripts/harness.py assets-check --target . --fast --json` | passed，0 failures，7 warnings（Structure） |
| `python scripts/harness.py release sync --target . --json` | consistent |
| `python scripts/harness.py self-test --target . --json` | passed |
| `python scripts/harness.py plan settle ... --status implemented` | implemented，0 warnings |
| `python scripts/harness.py acceptance settle ... --status passed` | passed |

验收层：L2 focused test + L2 仓库全量 + L1 合同/自检；未执行 L4 包/安装与 L5 真实设备。

## WARN

`assets-check --fast` 的 7 条均为 Structure WARN：

1. `scripts/acceptance_assets.py` 582→648 行，越过 600 行阈值。
2. `scripts/harness.py` 5,034→5,613 行，存量体量债。
3. `tests/test_acceptance.py` 646→749 行。
4. `tests/test_plan_lifecycle.py` 795→951 行。
5. `scripts/harness.py` `build_parser` 165→182 行。
6. `scripts/harness.py` `command_project` 224→234 行（工作区既有 2.30.0 改动）。
7. `scripts/harness.py` 新增 `record_unlinked_acceptance` 68 行。

`assets-check --strict` 因 WARN 转失败；这是已知的 Structure 债务，拆分任务已登记 `TODO.md`，不在本次 P0/P1 范围内强行拆分。

## 未覆盖

- `npm pack` / fresh install / 下游项目升级未执行。
- 真实设备与用户可见验收未执行；本任务为工具链修复，未声明 L4/L5。
- `assets-check --strict` 仍为红（仅 WARN，无 FAIL）；需 P2 拆分 `harness.py`、`acceptance_assets.py` 与超大测试文件后清零。

## 自查

- 重复逻辑：`plan show` 与 `plan settle` 共用 `plan_settle_paths`；选中构建、错误聚合、投影检查、符号匹配、ADR 约束分别抽成函数；未平行复制。`_action_flags` 是唯一 action→flag 映射。
- 新增抽象职责：`plan_selection_contract_fingerprint`（合同身份）、`plan_selection_diff`（差异证据）、`plan_show`（只读恢复）、`raise_aggregated_errors`（多错误 envelope）、`validate_action_flags`（CLI 边界）、`record_unlinked_acceptance`（未关联记录投影）、`plan_projection_warnings`（INDEX/横幅/JSON 一致性）、`symbol_hit`（定义级存活）、`active_constraints`（ADR → knowledge constraints）。

## 更正

审查阶段曾把“deprecated Acceptance 满足 Plan 门禁”列为普通路径漏洞。复核 `acceptance_assets.settle` 的归档分支会移除 Plan 反向引用，因此该路径只经手工/不一致引用可达；本次仍保留 `prepare_settlement` 的“至少一份 passed/failed”门禁作为防御，并在 `test_plan_v3_rejects_only_deprecated_terminal_acceptance` 中用手工状态验证。
