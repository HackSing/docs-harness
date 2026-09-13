# CODEMAP：代码能力索引

动手写代码前先查本索引定位可复用模块；新增代码文件或公开接口变化时同步更新条目。
条目格式：`模块路径` — 职责：一句话；公开接口：`符号`。测试文件不必登记。

## 控制器

- `scripts/harness.py` — 职责：CLI 控制器与安装/升级/发布编排，聚合各受管模块为 knowledge/plan/acceptance/adr/project/release/structure/assets-check 命令；公开接口：`main`、`build_parser`、`command_assets_check`、`command_structure`、`apply_project_install`、`is_source_package`（源包/下游判定，Structure 排除集的依据）、`git_hook_directory`、`check_githook_health`、`resolve_plan_selection_path`（--selection 的 sha256 指纹解析）、`inspect_plan_create`/`dry_run_plan_create`（--dry-run 整体校验）、`usage_invoke_event`/`record_usage_invoke`（main() 出口的 cmd.invoke 旁路埋点）、`command_usage`

## 受管模块（随 project init/upgrade 安装）

- `scripts/managed_assets.py` — 职责：受管资产通用层——AssetSpec 定义、指纹密封、原子写入、受管索引区块渲染；公开接口：`AssetSpec`、`AssetError`、`load_asset`、`seal_asset`、`atomic_write_text`、`atomic_write_json`
- `scripts/asset_checks.py` — 职责：assets-check 统一编排——六 checker 聚合、跨资产关系校验、FAIL/WARN 汇总；公开接口：`run_assets_check`、`check_cross_asset_relations`、`ASSET_STALE_DAYS`
- `scripts/plan_governance.py` — 职责：Plan v3 治理合同——冻结指纹、bugfix 校验合同、结算校验与遗留模板指纹；公开接口：`validate_plan`、`collect_bugfix_plan_errors`（收集全部合同错误，validate_bugfix_plan_contract 抛首个）、`legacy_plan_template_fingerprints`、`PLAN_SCHEMA_V3`、`PLAN_GOVERNANCE_INPUT_SCHEMA`
- `scripts/knowledge_assets.py` — 职责：Knowledge 资产生命周期——输入校验、创建/更新/结项与检查；公开接口：`KNOWLEDGE_SPEC`、`KNOWLEDGE_INPUT_SCHEMA`、`KNOWLEDGE_SETTLE_STATUSES`
- `scripts/acceptance_assets.py` — 职责：Acceptance 资产生命周期——验收目标/记录/结项的输入校验与层级映射；公开接口：`ACCEPTANCE_SPEC`、`ACCEPTANCE_EVIDENCE_LAYERS`、`ACCEPTANCE_SETTLE_INPUT_SCHEMA`、`collect_input_errors`/`collect_create_errors`（--dry-run 错误收集器，validate_input 抛首个）
- `scripts/adr_assets.py` — 职责：ADR 资产生命周期——架构决策创建（定稿不可改）、废弃/被替代结项与检查；公开接口：`ADR_SPEC`、`ADR_INPUT_SCHEMA`、`ADR_SETTLE_STATUSES`
- `scripts/script_hygiene.py` — 职责：脚本卫生检查——tracked 脚本混合行尾字节级扫描（assets-check 第五 checker）；公开接口：`check_script_line_endings`、`SCRIPT_GLOBS`
- `scripts/structure_check.py` — 职责：结构护栏——增量体量预警与 CODEMAP 一致性（assets-check 第六 checker）、存量结构债报告，函数级覆盖 Python（ast）、Go（gofmt 行级匹配）与 TS/JS（经 structure_ts_functions.cjs 借用目标项目 typescript）；公开接口：`check_structure`、`structure_report`、`CODEMAP_SCAFFOLD`、`FILE_RED_LINE`
- `scripts/usage_log.py` — 职责：本地 usage 事件的追加与读取，以及 `usage_log.enabled` 开关求值；旁路观察面，写入失败不改变任何命令的行为与退出码；公开接口：`USAGE_SCHEMA_VERSION`、`USAGE_DIR_RELATIVE`、`USAGE_LOG_DEFAULT_ENABLED`、`is_enabled`、`append_event`、`read_events`
- `scripts/usage_report.py` — 职责：usage 事件的纯聚合，输出契约沿用 `structure report`（返回 dict 交由 harness 既有 `emit` 呈现，本模块不带渲染器）；公开接口：`USAGE_REPORT_DEFAULT_DAYS`、`build_report`
- `scripts/structure_ts_functions.cjs` — 职责：Structure 的 TS/JS 函数体量解析子进程（stdin JSON 源码批 → stdout 函数限定名→行数），在目标项目 node_modules 或 DOCS_HARNESS_TS_MODULE_DIR 目录加载 typescript，harness 自身零依赖；公开接口：`collectSpans`、`functionName`（命令行调用，无模块导出）
