# CODEMAP：代码能力索引

动手写代码前先查本索引定位可复用模块；新增代码文件或公开接口变化时同步更新条目。
条目格式：`模块路径` — 职责：一句话；公开接口：`符号`。测试文件不必登记。

## 控制器

- `scripts/harness.py` — 职责：CLI 控制器与安装/升级/发布编排，聚合各受管模块为 knowledge/plan/acceptance/adr/project/release/structure/assets-check 命令；公开接口：`main`、`build_parser`、`command_assets_check`、`command_structure`、`apply_project_install`

## 受管模块（随 project init/upgrade 安装）

- `scripts/managed_assets.py` — 职责：受管资产通用层——AssetSpec 定义、指纹密封、原子写入、受管索引区块渲染；公开接口：`AssetSpec`、`AssetError`、`load_asset`、`seal_asset`、`atomic_write_text`、`atomic_write_json`
- `scripts/asset_checks.py` — 职责：assets-check 统一编排——六 checker 聚合、跨资产关系校验、FAIL/WARN 汇总；公开接口：`run_assets_check`、`check_cross_asset_relations`、`ASSET_STALE_DAYS`
- `scripts/plan_governance.py` — 职责：Plan v3 治理合同——冻结指纹、bugfix 校验合同、结算校验与遗留模板指纹；公开接口：`validate_plan`、`legacy_plan_template_fingerprints`、`PLAN_SCHEMA_V3`、`PLAN_GOVERNANCE_INPUT_SCHEMA`
- `scripts/knowledge_assets.py` — 职责：Knowledge 资产生命周期——输入校验、创建/更新/结项与检查；公开接口：`KNOWLEDGE_SPEC`、`KNOWLEDGE_INPUT_SCHEMA`、`KNOWLEDGE_SETTLE_STATUSES`
- `scripts/acceptance_assets.py` — 职责：Acceptance 资产生命周期——验收目标/记录/结项的输入校验与层级映射；公开接口：`ACCEPTANCE_SPEC`、`ACCEPTANCE_EVIDENCE_LAYERS`、`ACCEPTANCE_SETTLE_INPUT_SCHEMA`
- `scripts/adr_assets.py` — 职责：ADR 资产生命周期——架构决策创建（定稿不可改）、废弃/被替代结项与检查；公开接口：`ADR_SPEC`、`ADR_INPUT_SCHEMA`、`ADR_SETTLE_STATUSES`
- `scripts/script_hygiene.py` — 职责：脚本卫生检查——tracked 脚本混合行尾字节级扫描（assets-check 第五 checker）；公开接口：`check_script_line_endings`、`SCRIPT_GLOBS`
- `scripts/structure_check.py` — 职责：结构护栏——增量体量预警与 CODEMAP 一致性（assets-check 第六 checker）、存量结构债报告；公开接口：`check_structure`、`structure_report`、`CODEMAP_SCAFFOLD`、`FILE_RED_LINE`
