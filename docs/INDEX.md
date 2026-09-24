# Docs Harness 文档索引

## 当前产品文档

- [文档地图](README.md)
- [产品合同](contracts.md)
- [架构](architecture.md)
- [代码能力索引](CODEMAP.md)
- [测试与验收](testing.md)
- [当前待办](todo.md)
- [下游项目](downstream.md)

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
- [Harness 计划与验收创建体验优化及结算泄漏预警](plans/docs-harness-create-ux-and-settle-leak-warn.md) — 状态：已实施-仅追溯（代码已是真源，2026-09-11 核对）；关键符号：`plan_select`、`validate_plan_create_payload`、`--dry-run`、`check_cross_asset_relations`
- [Structure 函数级检查扩展到 Go 与 TS/JS](plans/structure-function-check-multilanguage.md) — 状态：已实施-仅追溯（代码已是真源，2026-09-05 核对）；关键符号：`_ts_function_spans`、`_go_functions`、`function_language`、`TS_MODULE_DIR_ENV`
- [本地 Usage Log 与 Usage Report 观测能力](plans/usage-observability.md) — 状态：已实施-仅追溯（代码已是真源，2026-09-13 核对）；关键符号：`usage_log`、`append_event`、`build_report`、`USAGE_SCHEMA_VERSION`
- [2.16.1 收尾四项：下游结构检查排除受管文件、包清单守卫、inputs 目录约定、usage 默认开启提示](plans/harness-2.16.1-followups.md) — 状态：已实施-仅追溯（代码已是真源，2026-09-13 核对）；关键符号：`is_source_package`、`TASK_INPUTS_RELATIVE`、`usage_enabled_notices`
- [命令摩擦治理：usage 错误码观测、plan WARN 部分交付第三态、手写方案结算路径](plans/command-friction-observability-and-plan-exits.md) — 状态：已实施-仅追溯（代码已是真源，2026-09-15 核对）；关键符号：`PLAN_PARTIAL_DELIVERY_RECHECK_DAYS`、`partial_delivery_checked_recently`、`last_warnings`、`error_codes`
<!-- docs-harness:plans-index:end -->

## 历史边界

`docs/history/` 只用于追溯旧产品事实，不作为当前实现依据。

<!-- docs-harness:knowledge-index:start -->
## 项目知识

- [Docs Harness 四资产治理与双机械检查执行机制](knowledge/docs-harness-assets-governance.md) — 状态：有效（现行事实）；关键符号：`run_assets_check`、`check_structure`、`knowledge_impact`、`ADR_SPEC`
- [Docs Harness 下游安装面：源包判定、Structure 排除与约定目录](knowledge/downstream-install-surface.md) — 状态：有效（现行事实）；关键符号：`is_source_package`、`structure_exempt_paths`、`TASK_INPUTS_RELATIVE`
- [Docs Harness 本地 usage 观测机制](knowledge/usage-observability.md) — 状态：有效（现行事实）；关键符号：`record_usage_invoke`、`USAGE_SCHEMA_VERSION`、`build_report`、`usage_log_invalid`
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
- [Structure 函数级检查扩展到 Go 与 TS/JS 验收](acceptance/structure-function-check-multilanguage.md) — 状态：已验收-仅追溯；关键符号：`_ts_function_spans`、`_go_functions`、`function_language`、`TS_MODULE_DIR_ENV`
- [本地 Usage Log 与 Usage Report 观测能力验收](acceptance/usage-observability.md) — 状态：已验收-仅追溯；关键符号：`usage_log`、`append_event`、`USAGE_SCHEMA_VERSION`
- [2.16.1 收尾四项验收：下游结构检查排除、包清单守卫、inputs 约定、usage 提示](acceptance/harness-2.16.1-followups.md) — 状态：已验收-仅追溯；关键符号：`is_source_package`、`TASK_INPUTS_RELATIVE`、`usage_enabled_notices`
- [命令摩擦治理验收：usage 错误码与最近一次检查计数、plan WARN 部分交付第三态、手写方案结算](acceptance/command-friction-observability-and-plan-exits.md) — 状态：已验收-仅追溯；关键符号：`PLAN_PARTIAL_DELIVERY_RECHECK_DAYS`、`partial_delivery_checked_recently`、`last_warnings`、`error_codes`
<!-- docs-harness:acceptance-index:end -->

<!-- docs-harness:adr-index:start -->
## 架构决策

- [项目级文档采用分层治理](adr/layered-doc-governance.md) — 状态：有效（现行决策）；关键符号：`ADR_SPEC`、`adr_assets`、`project_doc_scaffolds`
- [新增 ScriptHygiene 作为 assets-check 第五个 checker，不建独立资产类型](adr/script-hygiene-as-checker.md) — 状态：有效（现行决策）；关键符号：`script_hygiene`、`run_assets_check`、`SCRIPT_GLOBS`
- [Structure 增量检查作为 assets-check 第六 checker，CODEMAP 采用纯 Markdown 文档形态](adr/structure-guardrails-as-checker.md) — 状态：有效（现行决策）；关键符号：`check_structure`、`structure_report`、`CODEMAP_SCAFFOLD`
- [Structure 的 TS/JS 函数级解析借用目标项目的 typescript 编译器，harness 自身保持零依赖](adr/structure-ts-parser-borrowed-from-target.md) — 状态：有效（现行决策）；关键符号：`_ts_parser_command`、`_ts_module_dirs`、`TS_PARSER_UNAVAILABLE_WARNING`
- [本地 usage 观测只覆盖 harness 命令面、旁路 best-effort、不外发](adr/usage-log-local-command-face-only.md) — 状态：有效（现行决策）；关键符号：`record_usage_invoke`、`USAGE_FLAG_KEYS`、`is_enabled`
<!-- docs-harness:adr-index:end -->
