> 状态：有效（现行事实）
<!-- docs-harness:knowledge-document/v1 -->

# Docs Harness 四资产治理执行机制

- 修订：4
- 关键符号：`run_assets_check`、`acceptance_refs`、`assert_evidence_usable`、`install_conflicts`
- 资产指纹：`sha256:11571c7d193226287e25ee10db78459c18bd31c66e747eefce4aaa3d8ad8355a`

## 摘要

2.7.0 对 Plan、Knowledge、Acceptance 建立统一检查、反向关系和分层提交防线；2.8.0 新增 ADR 第四类受管资产与项目级文档脚手架/检查；2.9.0 新增 ScriptHygiene 脚本卫生检查并入 assets-check 第五个 checker；2.10.0 上游合入 dsh-buddy 证据准入加固与最新记录语义，install_conflict 改为聚合报错。

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

### `evidence.admission.guard`

2.10.0 上游合入 dsh-buddy fc3da39 生产验证补丁：harness.py 新增 git_ignored_refs()/assert_evidence_usable()，验收证据与失败归因证据两处登记入口共用同一校验——先查存在（缺失报 acceptance_evidence_missing）再经 git check-ignore 判定，git 忽略路径拒绝登记（acceptance_evidence_ignored），非 git 目标不被锁死。

证据：`scripts/harness.py`、`docs/contracts.md`、`docs/testing.md`

### `acceptance.latest.record.semantics`

2.10.0 起 _validate_live_refs 只对每个 criterion 的最新一条 record 校验证据存在性与用户确认，被 --reaccept 取代的历史记录为纯留痕不再卡 check；最新记录违规仍 FAIL，settled 豁免不变。

证据：`scripts/acceptance_assets.py`、`docs/contracts.md`、`docs/testing.md`

### `upgrade.install_conflict.aggregation`

2.10.0 起 upgrade preflight 指纹偏离类 install_conflict 不再先撞先报，一次性列出全部偏离文件并附恢复/上游合入/保持分叉三条出路，extra_payload.install_conflicts 携带 path/reason/actual_fingerprint/allowed_fingerprints 结构化清单；结构性错误（symlink、非常规文件、安装指纹无效）保持即时抛，code 与退出码不变。

证据：`scripts/harness.py`、`docs/contracts.md`、`docs/testing.md`
