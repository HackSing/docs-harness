> 状态：已实施-仅追溯（代码已是真源，2026-08-16 核对）
<!-- docs-harness:plan-document/v1 -->

# docs-check 更名为 plan check（直接删除旧命令，无兼容别名）

- 冻结合同：`sha256:6699ab402f395caf1e5501a11a3984303898227d20e10d719bad5a5d331a31db`
- 关键符号：`command_plan_check`、`plan_check_markdown_files`、`command_assets_check`、`add_check_options`

## 背景

docs-check 命名于只有 Plan 域检查的时期；2.6.0/2.7.0 后知识、验收各有 knowledge check / acceptance check，顶层另有统一编排 assets-check，docs-check 名不副实（只查 docs/plans 可发现性，不查整个 docs/），且与 <资产> check 模式不对称。用户决定不留兼容别名，直接删除旧命令。

## 目标

将顶级命令 docs-check 收编为 plan 子命令的 check action（plan check），与 knowledge check / acceptance check 对称；旧顶级命令 docs-check 直接删除，调用即 argparse 报错退出码 2；内部 helper/常量同步更名（docs_check_* → plan_check_*、DOCS_CHECK_* → PLAN_CHECK_*，含错误码 docs_check_unreadable → plan_check_unreadable）；所有用户可见文案、受管提示词、文档、测试、索引符号同步。

## 非目标

不改检查规则本身（C1-C7 语义、fast/strict 行为、退出码约定不变）；不改写历史文档正文（CHANGELOG 旧条目、docs/audit-2.3.0-lifecycle.md、历史 plan 文档均为已实施-仅追溯的历史记录，其中 docs-check 字样保持原样）；pre-commit 钩子与 CI 已只调 assets-check，无需改动。

## 成功标准

plan check 退出码与 JSON 负载和原 docs-check 一致（summary 文案为 plan check）；harness 全仓（除历史文档正文）无 docs_check/docs-check 残留；npm test 全绿；assets-check --strict 与 self-test 通过；AGENTS.md、CLAUDE.md 与 harness.py 受管入口文案逐字节一致；docs/INDEX.md 关键符号同步后 C5 零 WARN。

## 执行范围

scripts/harness.py（常量、helper、parser、dispatch、self-test、受管入口文案、输出文案）、tests/test_v2_direct.py、AGENTS.md、CLAUDE.md、SKILL.md、README.md、docs/testing.md、docs/INDEX.md、CHANGELOG.md、VERSION 及 release sync 传播面（package.json、plan-templates、evals）。

## 执行内容

批1 scripts/harness.py：① 常量 DOCS_CHECK_BANNER_MARKER/DOCS_CHECK_BANNER_STATES/DOCS_CHECK_ARCHIVE_EXEMPTION/DOCS_CHECK_EXCLUDED_DIRS/DOCS_CHECK_ARTIFACT_DIRS/DOCS_CHECK_SOURCE_SUFFIXES/DOCS_CHECK_STALE_DAYS/DOCS_CHECK_SYMBOL_MAX_FILE_BYTES（:131-141）更名 PLAN_CHECK_*；② helper docs_check_banner/docs_check_walk_files/docs_check_markdown_files（:3347-3379）更名 plan_check_*，全部调用点（:946/:1320/:1364/:1952 及自身）同步，错误码 docs_check_unreadable 同步更名；③ command_docs_check → command_plan_check，summary 文案 docs-check 改 plan check；④ plan parser action choices 增加 check，并补 --strict/--fast（与 add_check_options 同参数，plan 已有 add_target 不重复）；⑤ dispatch：plan_handlers 增加 check→command_plan_check；顶级 docs-check parser（:3824-3828）与 dispatch 分支（:3885-3886）整体删除；⑥ command_assets_check 的 plan_checker lambda（:3590）改调 command_plan_check；⑦ self-test：strict_parse_ok 循环（:3622）改为解析 [plan,check,--strict,--fast] 与 [assets-check,--strict,--fast]，command_parser 列表（:3630）移除 docs-check；⑧ PLAN_EPILOG 补 plan check 用法一行。批2 提示词与文档：harness.py 受管入口文案（:383）docs-check → plan check；AGENTS.md（:77）与 CLAUDE.md（:77）受管块逐字节同步；SKILL.md :121 用法示例改 plan check、:128 段落改写（plan check 为 Plan 域检查，不再提 docs-check）；README.md :151 流程、:275 命令表更新；docs/testing.md :72 L1 命令清单更新。批3 测试与索引：tests/test_v2_direct.py 的 run_cli("docs-check",...)（:382/:396/:503/:1018）改 run_cli("plan","check",...)，test_docs_check_* 函数更名 test_plan_check_*，:125 命令清单与 :989 文案同步；新增一条负向测试：docs-check 作为未知命令退出码 2；docs/INDEX.md :14-15 关键符号 command_docs_check 改 command_plan_check（否则 C5 符号存活 WARN）。批4 版本与变更：2.7.2 → 2.8.0（命令面破坏性变更），release sync --apply 传播 VERSION/package.json/plan-templates/evals，CHANGELOG 新增 2.8.0 条目明确 docs-check 已删除、无兼容别名。

## 验收方案

acceptance create 建立验收目标后逐条 record：① 聚焦测试 tests/test_v2_direct.py 改名相关用例全绿（含新增的 docs-check 负向用例）；② 全量 npm test（CLI 公共契约变更，满足仓库级全量触发条件）；③ assets-check --strict 通过（含 C5，验证 INDEX 符号同步）；④ self-test 通过；⑤ 手工冒烟：plan check 跑通、docs-check 确认退出码 2。最后 acceptance settle 与 plan settle 闭环。

## 是否需要 Acceptance 资产闭环

```json
true
```

## Knowledge 影响

unchanged

## 约束

检查逻辑零变更；内部更名必须一次 sweep 干净（grep 验证 scripts/ 与 tests/ 无 docs_check 残留）；受管块三处（harness.py 文案、AGENTS.md、CLAUDE.md）逐字节一致；历史文档正文不动，仅 docs/INDEX.md 关键符号随 C5 要求更新。

## 风险与回滚

风险：无兼容别名，任何外部脚本直接调 docs-check 会立即报错——已核实官方 pre-commit、CI、SKILL/README 现行用法均走 assets-check 或将同步更新，下游项目升级时随受管文档获知；CHANGELOG 2.8.0 条目显式声明破坏性变更。docs/INDEX.md 符号漏改触发 C5 WARN，由 assets-check --strict 验收兜住。回滚：全部本地文本编辑，git revert 即可。

<!-- docs-harness:plan-governance:start -->
## 资产治理

- 关联验收：`docs/acceptance/docs-harness-plan-check-rename.json`
- 需要 Acceptance：true
- Knowledge 影响：unchanged
<!-- docs-harness:plan-governance:end -->
