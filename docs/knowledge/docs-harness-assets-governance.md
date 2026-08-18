> 状态：有效（现行事实）
<!-- docs-harness:knowledge-document/v1 -->

# Docs Harness 四资产治理执行机制

- 修订：3
- 关键符号：`run_assets_check`、`acceptance_refs`、`knowledge_impact`、`ADR_SPEC`
- 资产指纹：`sha256:4680c4b379fae886fcb985e2a1cbbd024915a1ae47712f549bde5b5e539b21d0`

## 摘要

2.7.0 对 Plan、Knowledge、Acceptance 建立统一检查、反向关系和分层提交防线；2.8.0 新增 ADR 第四类受管资产与项目级文档脚手架/检查；2.9.0 新增 ScriptHygiene 脚本卫生检查并入 assets-check 第五个 checker。

## 事实

### `assets.check.execution`

assets-check 聚合四类资产、ScriptHygiene 脚本卫生扫描与跨资产关系；pre-commit 使用 fast，GitHub CI 使用 strict。

证据：`scripts/asset_checks.py`、`scripts/githooks/pre-commit`、`.github/workflows/assets-check.yml`

### `plan.governance.v3`

Full Plan 使用 acceptance_required 和单字段 knowledge_impact，Acceptance 反向登记由 Harness 自动维护，结算顺序为 Knowledge、Acceptance、Plan。

证据：`scripts/plan_governance.py`、`plan-templates/levels/full.json`、`docs/contracts.md`

### `adr.lifecycle`

ADR 是第四类受管资产：adr create/settle/check，定稿不可改（无 update），失效经 settle deprecated/superseded 归档；CHANGELOG/TODO 只做脚手架与 project check 检查，release sync --strict 强制 CHANGELOG 顶部版本与 VERSION 一致。

证据：`scripts/adr_assets.py`、`docs/contracts.md`、`docs/adr/layered-doc-governance.md`

### `script.hygiene.checker`

ScriptHygiene（scripts/script_hygiene.py）不是生命周期资产，是 assets-check 的第五个 checker：对 tracked 脚本（*.sh/*.iss/*.bat/*.cmd/*.ps1）做全仓字节级混合行尾扫描，同一文件混入 CRLF 与裸 LF 即 FAIL；非 git 目标 checked=0 且不产 WARN；安装配置随之升级为 project-config/v11。

证据：`scripts/script_hygiene.py`、`scripts/asset_checks.py`、`docs/contracts.md`
