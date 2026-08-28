> 状态：有效（现行事实）
<!-- docs-harness:knowledge-document/v1 -->

# Docs Harness 四资产治理与双机械检查执行机制

- 修订：7
- 关键符号：`run_assets_check`、`check_structure`、`knowledge_impact`、`ADR_SPEC`
- 资产指纹：`sha256:30c4007caa62e0e739f711decccb504c6a2e0c9ada430b9614e3d5fd5e7d698f`

## 摘要

2.7.0 对 Plan、Knowledge、Acceptance 建立统一检查、反向关系和分层提交防线；2.8.0 新增 ADR 第四类受管资产与项目级文档脚手架/检查；2.9.0 新增 ScriptHygiene 第五 checker；2.10.0 上游合入 dsh-buddy 证据准入加固与最新记录语义，install_conflict 改为聚合报错；2.11.0 新增 Structure 结构护栏第六 checker（增量体量 + CODEMAP 能力索引）与 structure 命令组。；2.11.1 修复 git 钩子安装（shim 共存 + 可执行位治理）。

## 事实

### `assets.check.execution`

assets-check 聚合四类资产、ScriptHygiene 与 Structure 两个机械 checker 及跨资产关系；pre-commit 使用 fast，GitHub CI 使用 strict。

证据：`scripts/asset_checks.py`、`scripts/githooks/pre-commit`、`.github/workflows/assets-check.yml`

### `plan.governance.v3`

Full Plan 使用 acceptance_required 和单字段 knowledge_impact，Acceptance 反向登记由 Harness 自动维护，结算顺序为 Knowledge、Acceptance、Plan；2.11.0 起 Full 模板另有必填 module_interfaces 冻结模块划分与接口骨架，实施骨架先行。

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

### `structure.guardrails.checker`

Structure（scripts/structure_check.py）是 assets-check 的第六个 checker，全部 WARN 级：增量体量检查只对本次改动（工作区+暂存+未跟踪 vs HEAD）归责——新文件超 600 行、既有文件突破 600 行、超标文件单次净增 ≥50 行、Python 新增函数超 60 行或超标函数单次增长 ≥10 行（ast 测量，仅 Python 有函数级）；CODEMAP（docs/CODEMAP.md，纯 Markdown 非受管资产）校验登记路径存在、公开接口符号存活、新增代码文件登记提醒（测试文件豁免），无 CODEMAP 的项目整体跳过；存量结构债经 structure report 按需报告供定期整理任务；阈值常量单一来源于 structure_check.py；非 git 目标 checked=0；文件红线 2.11.1 起由 500 放宽至 600；功能于 2.11.0 交付（曾在本地分支以 2.10.0 号实现，收敛重标），安装配置为 project-config/v12。

证据：`scripts/structure_check.py`、`scripts/asset_checks.py`、`docs/CODEMAP.md`、`docs/adr/structure-guardrails-as-checker.md`

### `githook.shim.coexistence`

2.11.1 起 git 钩子安装改为 shim 共存模式：setup.sh 不再设置 core.hooksPath（替换语义会静默屏蔽 .git/hooks 下 LFS/husky 等第三方钩子），经 --git-common-dir 向真实钩子目录安装带 docs-harness-hook-shim 标记的转发 shim（拒绝覆盖他人 pre-commit、幂等、兼容 worktree），并迁移清除旧 hooksPath；受管钩子入库模式修正为 100755；project check 新增 yellow finding githook_index_mode（索引模式非 100755）与 githook_hookspath_conflict（hooksPath 屏蔽冲突）；uninstall 按标记清理 shim。

证据：`scripts/githooks/setup.sh`、`scripts/harness.py`、`docs/plans/githook-shim-coexistence.md`
