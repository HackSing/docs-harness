# Harness 剩余优化（R0-R2）收尾记录（2026-10-22）

Plan：`docs/plans/harness-remaining-optimizations.json`（settle implemented）
Acceptance：`docs/acceptance/harness-remaining-optimizations.json`（settle passed）
证据：`docs/acceptance/evidence/harness-remaining-optimizations/`

## 改动路径

- 新模块：`scripts/agent_prompt.md`（受管提示词模板）、`plan_selection.py`、`plan_check.py`、`acceptance_amend.py`、`acceptance_render.py`、`asset_query.py`、`cli_support.py`。
- `scripts/harness.py`：只读 `show/list` 接线；plan patch/dry-run；acceptance dry-run；dry-run action 白名单；`git_common_dir`；BOM；git 索引扫描；知识片段/source 缓存；HTML 解析器拆分后的编排。
- `scripts/acceptance_assets.py`：record/settle dry-run；render 移出；仍保持 593 行。
- `scripts/plan_amend.py`：`--patch`、`--dry-run`、内容加载/结果投影拆分。
- `scripts/plan_check.py`：progress 判定、C6 部分交付豁免、git 索引 Markdown 扫描。
- `scripts/plan_selection.py`：common git dir 缓存；`selection_warnings`。
- `scripts/structure_check.py`：此前已加的 `symbol_hit` / `--base` 继续复用。
- `docs/`：contracts、architecture、testing、CODEMAP、INDEX、contributing、README、SKILL、CHANGELOG、TODO。
- `package.json`、`tests/harness_test_base.py`、`tests/*`：新模块安装清单、show/list、patch/dry-run、progress/BOM 测试；大测试文件拆分。

## 验证

| 命令 | 结果 |
|---|---|
| `python -m unittest discover -s tests -p "test_*.py"` | 275 项 OK，跳过 9 |
| `python scripts/harness.py assets-check --target . --strict --json` | passed，0 failures，0 warnings |
| `python scripts/harness.py plan check --target . --json` | passed，0 failures，0 warnings |
| `python scripts/harness.py acceptance check --target . --json` | passed |
| `python scripts/harness.py release sync --target . --json` | consistent |
| `python scripts/harness.py self-test --target . --json` | passed |
| `plan list` / `acceptance show/list` / `knowledge show` / `adr show` | 只读返回，测试通过 |
| `plan amend --patch ... --dry-run` | dry_run_valid，未写盘；正式 patch 成功 |

验收层：L2 focused + L2 仓库全量 + L1 合同/自检。未执行 L4/L5。

## WARN

最终 `assets-check --strict` 为 0 failures / 0 warnings。过程性 WARN（已消除）包括 `harness.py` 体量、`acceptance_assets.py` 越 600 行、`acceptance_amend.amend`、`plan_amend.run_plan_amend` 与超大测试文件；已通过模块拆分/函数拆分/测试拆分清零。

## 未覆盖

- `npm pack` / fresh install / 下游项目升级未执行。
- 真实设备与用户可见验收未执行。
- 提示词只做了“维护者段移出 + 受管模板外置”，没有把全部资产细节拆成按需参考；完整分层仍可作为后续优化。
- C5 仍是“零命中”检查，未改成多数命中阈值；C8 已支持 `progress.remaining_steps`。
- 没有新增 `harness status` 聚合命令，只有各域 `show/list`。
- 版本仍为 2.30.0（工作区未提交）；若 2.30.0 已发布，需要把本轮行为变更移到新版本。

## 自查

- 重复逻辑：show/list 共用 `show_asset`/`list_assets`；plan check 的 Markdown 扫描与知识候选共用 git 索引思路但按目录/后缀分别过滤；新增模块没有复制资产指纹/原子写实现，继续复用 `managed_assets`。
- 新增抽象职责：`plan_selection`（选择合同/缓存）、`plan_check`（Plan 文档卫生）、`acceptance_amend`（pending 验收修订）、`acceptance_render`（Markdown 投影）、`asset_query`（只读查询）、`cli_support`（action flag 边界）、`agent_prompt.md`（受管提示词模板）。
