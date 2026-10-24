# 2026-10-23 检查器修复上游化（2.32.1）

## 改动

- `scripts/plan_check.py`：新增 `canonical_index_entry`，INDEX 正式条目优先匹配行首链接或表格行，避免引用句/后继方案链接被当成条目。
- `scripts/harness.py`：C2 索引一致性检查改用 `canonical_index_entry`；版本升到 2.32.1。
- `scripts/codemap_check.py`（新）：CODEMAP 文本解析——`parse_codemap`、`codemap_interface_symbols`、`parse_codemap_index_entries`，区分当前索引行与历史「变更」行。
- `scripts/structure_check.py`：只校验当前索引条目；接口符号只取「公开接口」字段；目录模块扫描直接子文件（排除测试文件）；解析逻辑改为消费 `codemap_check`，文件从 606 行降到 549 行。
- `scripts/asset_checks.py`：新增 `plan_amend_recently`，最近 30 天内修订过的方案不立即提示 amend 次数；已结算方案不提示。
- `tests/test_plan_check_semantics.py`、`tests/test_structure_check_semantics.py`、`tests/test_asset_checks_semantics.py`：移植并适配 27 个单测。
- `docs/CODEMAP.md`：登记 `codemap_check.py` 与新公开接口。
- 版本与模块清单：`VERSION`、`package.json`、`SKILL.md`、`plan-templates/*`、`evals/evals.json`、`AGENTS.md`、`README.md`、`tests/harness_test_base.py`、`scripts/harness.py` 的安装清单同步到 2.32.1。
- 来源：zbuddy-desktop `cb884708` 的检查器修复；只上游化代码与测试，未带入 zbuddy 的 CODEMAP 内容更新和方案资产处置。

## 验证

- 新增单测：`python3 -m unittest tests.test_plan_check_semantics tests.test_structure_check_semantics tests.test_asset_checks_semantics`，27 tests，OK，退出 0。
- 聚焦回归：同 27 项 + `tests.test_assets_check`、`tests.test_structure`、`tests.test_plan_lifecycle`、`tests.test_plan_amend`、`tests.test_plan_governance`、`tests.test_cli_surface`、`tests.test_project_install`、`tests.test_project_upgrade`，176 tests，OK（skipped=2），退出 0。
- 全量回归：`npm test`，320 tests，OK（skipped=2），退出 0。
- 结构检查：`structure check --target .`，passed，0 WARN，退出 0；`structure_check.py` 606→549 行。
- 发布检查：`self-test` 退出 0；`assets-check --strict` failures=0、warnings=0，退出 0；`release sync --strict` status=consistent，退出 0；`git diff --check` 退出 0。
- 下游升级：zbuddy-desktop 2.31.0→2.32.1；`project upgrade --apply` 写入 11 个受管文件（新增 `scripts/codemap_check.py`），提交 `3a874269`；`project check` passed/in_head；`assets-check --strict` failures=0、warnings=0，退出 0；本地三个检查器测试 5+12+10 项通过（适配测试提交 `ad5e102f`）。
- 其余 8 个下游从 2.32.0 升到 2.32.1，各写入 15 个受管文件，提交后 `project check` 均 passed/in_head，并已推送：dispatch `e0de512`、opc-skills `4a05ee0`、suiyi `098c3e9`、zbuddy-mobile `dcca377`、onceright `4d57055`、awesome-llm-made-videos `26d5dba`、avatanel `5600d52`（master）、content-system `481e092`。
- zbuddy-desktop 已推送 GitHub 与 codeup，两边均为 `ad5e102f`；其余 8 个远端 ref 与本地 HEAD 一致。

## 验证层级

- focused_test（27 项新增 / 176 项聚焦）
- repository_full_test（320 项）
- package_or_install（9 个下游升级到 2.32.1；zbuddy-desktop 另做严格检查）
- 未做 local_runtime 与 real_device 层。

## 未覆盖

- 9 个下游均已升级到 2.32.1；除 zbuddy-desktop 外只做了 `project check`，未分别跑 `assets-check --strict`。
- zbuddy-desktop 仍有既有的 `TODO.md` 格式 yellow 提示（2 条），本次未处理。
- 未做下游 3–7 天失败率/WARN 率/报告完整率复测。
- 30 天 amend 宽限是策略变化，未做长期方案逃逸观察。
- 源仓与下游只做本地/远端 Git 提交，未打 tag、未构建安装包。

## 自查

- 重复逻辑：CODEMAP 解析只有 `codemap_check.py` 一处实现，`structure_check.py` 消费它；未复制第二份。
- 新增抽象：`codemap_check.py` 只负责 CODEMAP 文本解析；`structure_check.py` 负责体量检查、目录扫描与告警编排。新抽象有明确职责，且把超红线文件降回 549 行。
- 30 天宽限是 zbuddy 修复的一部分，已由用户确认纳入上游。
