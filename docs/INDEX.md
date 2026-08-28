# Docs Harness 文档索引

## 当前产品文档

- [文档地图](README.md)
- [产品合同](contracts.md)
- [架构](architecture.md)
- [代码能力索引](CODEMAP.md)
- [测试与验收](testing.md)
- [当前待办](todo.md)

<!-- docs-harness:plans-index:start -->
## 任务方案

- [Docs Harness v2.0.0：Codex 直接执行、按需知识与真实验收方案](plans/docs-harness-v2.0.0-direct-first-plan.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-14 核对）；关键符号：`plan_create`、`command_plan_check`、`command_acceptance_record`
- [Docs Harness 完整方案管理生命周期实施方案](plans/docs-harness-plan-lifecycle-management-plan.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-14 核对）；关键符号：`plan_create`、`apply_project_install`、`command_plan_check`、`PLAN_INDEX_BEGIN`
- [Docs Harness Plan、Knowledge、Acceptance 资产全生命周期方案](plans/docs-harness-asset-lifecycle-plan.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-14 核对）；关键符号：`knowledge_create`、`knowledge_settle`、`acceptance_create`、`acceptance_settle`
- [Docs Harness 2.7.0 三资产多重执行保障方案](plans/docs-harness-assets-governance-2.7.0.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-15 核对）；关键符号：`command_assets_check`、`acceptance_refs`、`knowledge_impact`、`validate_plan_governance`
- [docs-check 更名为 plan check（直接删除旧命令，无兼容别名）](plans/docs-harness-plan-check-rename.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-16 核对）；关键符号：`command_plan_check`、`plan_check_markdown_files`、`command_assets_check`、`add_check_options`
- [Docs Harness 项目级文档治理：ADR 受管资产 + CHANGELOG/TODO/README 脚手架与检查](plans/docs-harness-project-docs-governance.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-17 核对）；关键符号：`adr_assets`、`ADR_SPEC`、`changelog_top_version`、`apply_project_install`
- [dsh 插件 UI 优化：设置页迁移 settings.section 与交互打磨](plans/dsh-plugin-ui-settings-section-plan.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-21 核对）；关键符号：`HarnessSettingsCard`、`settings.section`、`HarnessSettingsStore`、`NoticeBarView`
- [上游合入 dsh-buddy 证据加固补丁并改进 install_conflict 报错（2.10.0）](plans/docs-harness-2.10.0-evidence-upstream-install-conflict-plan.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-23 核对）；关键符号：`assert_evidence_usable`、`git_ignored_refs`、`_validate_live_refs`、`install_conflicts`
- [Docs Harness 2.10.0 结构护栏：增量体量检查、CODEMAP 能力索引与骨架先行](plans/docs-harness-structure-guardrails.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-27 核对）；关键符号：`check_structure`、`structure_report`、`CODEMAP_RELATIVE`、`module_interfaces`
- [Docs Harness 2.11.0 收敛：结构护栏在主仓 converge-2.11 分支重建到 2.10.2 之上](plans/docs-harness-2.11-convergence.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-27 核对）；关键符号：`check_structure`、`command_structure`、`_managed_content`、`LEGACY_PLAN_TEMPLATE_FINGERPRINTS`
- [git 钩子安装改为转发 shim 共存模式并补齐可执行位治理](plans/githook-shim-coexistence.md) — 状态：已实施-仅追溯（代码已是真源，2026-08-28 核对）；关键符号：`core.hooksPath`、`githook_drift`、`GIT_HOOK_RELATIVE_FILES`、`docs-harness-hook-shim`
<!-- docs-harness:plans-index:end -->

## 历史边界

`docs/history/` 只用于追溯旧产品事实，不作为当前实现依据。

<!-- docs-harness:knowledge-index:start -->
## 项目知识

- [Docs Harness 四资产治理与双机械检查执行机制](knowledge/docs-harness-assets-governance.md) — 状态：有效（现行事实）；关键符号：`run_assets_check`、`check_structure`、`knowledge_impact`、`ADR_SPEC`
<!-- docs-harness:knowledge-index:end -->

<!-- docs-harness:acceptance-index:start -->
## 验收资产

- [Docs Harness 2.7.0 三资产治理实施验收](acceptance/docs-harness-assets-governance-2.7.0.md) — 状态：已验收-仅追溯；关键符号：`command_assets_check`、`acceptance_refs`、`knowledge_impact`、`validate_plan_governance`
- [docs-check 更名为 plan check 验收](acceptance/docs-harness-plan-check-rename.md) — 状态：已验收-仅追溯；关键符号：`command_plan_check`、`plan_check_markdown_files`、`command_assets_check`
- [项目级文档治理验收（ADR 资产 + 脚手架与检查）](acceptance/docs-harness-project-docs-governance.md) — 状态：已验收-仅追溯；关键符号：`adr_assets`、`ADR_SPEC`、`changelog_top_version`
- [dsh 插件 UI 优化验收：settings.section 设置页、覆盖重置、通知条重试与气泡 pin](acceptance/dsh-plugin-ui-settings-section.md) — 状态：已验收-仅追溯；关键符号：`HarnessSettingsCard`、`settings.section`、`HarnessSettingsStore`、`NoticeBarView`
- [2.10.0 证据准入加固与升级冲突聚合报错治理验收](acceptance/docs-harness-2.10.0-evidence-upstream-install-conflict.md) — 状态：已验收-仅追溯；关键符号：`assert_evidence_usable`、`acceptance_evidence_ignored`、`install_conflicts`
- [Docs Harness 2.10.0 结构护栏验收（Structure checker、CODEMAP、骨架先行模板）](acceptance/docs-harness-structure-guardrails.md) — 状态：已验收-仅追溯；关键符号：`check_structure`、`structure_report`、`CODEMAP_RELATIVE`、`module_interfaces`
- [git 钩子 shim 共存模式与可执行位治理验收](acceptance/githook-shim-coexistence.md) — 状态：已验收-仅追溯；关键符号：`core.hooksPath`、`githook_drift`、`docs-harness-hook-shim`
<!-- docs-harness:acceptance-index:end -->

<!-- docs-harness:adr-index:start -->
## 架构决策

- [项目级文档采用分层治理](adr/layered-doc-governance.md) — 状态：有效（现行决策）；关键符号：`ADR_SPEC`、`adr_assets`、`project_doc_scaffolds`
- [新增 ScriptHygiene 作为 assets-check 第五个 checker，不建独立资产类型](adr/script-hygiene-as-checker.md) — 状态：有效（现行决策）；关键符号：`script_hygiene`、`run_assets_check`、`SCRIPT_GLOBS`
- [Structure 增量检查作为 assets-check 第六 checker，CODEMAP 采用纯 Markdown 文档形态](adr/structure-guardrails-as-checker.md) — 状态：有效（现行决策）；关键符号：`check_structure`、`structure_report`、`CODEMAP_SCAFFOLD`
<!-- docs-harness:adr-index:end -->
