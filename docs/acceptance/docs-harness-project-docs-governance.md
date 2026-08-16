> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# 项目级文档治理验收（ADR 资产 + 脚手架与检查）

- 修订：2
- 关键符号：`adr_assets`、`ADR_SPEC`、`changelog_top_version`
- 资产指纹：`sha256:09563252779217fbde485cf4ff166fdf69ff5383bac4214a809f482f4792dbdd`
- 关联方案：`docs/plans/docs-harness-project-docs-governance.json`

## 验收目标

ADR 第四类受管资产生命周期跑通，CHANGELOG/TODO/README 脚手架与检查生效，全仓测试与检查全绿

## 验收标准

### `c1` 聚焦测试：adr 生命周期/篡改拒绝/脚手架幂等/release sync --strict/project check findings 用例全绿

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`tests/test_v2_direct.py`、`scripts/adr_assets.py`

### `c2` 全量 npm test 通过（新命令组 + config v10 公共契约）

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`tests/test_v2_direct.py`、`tests/test_release_version_sync.py`

### `c3` assets-check --strict 与 self-test 通过

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`scripts/asset_checks.py`、`scripts/harness.py`

### `c4` L3 冒烟：fresh init 四类骨架齐备且二次 init 幂等零覆盖；v9 项目 upgrade 到 v10 平滑

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`scripts/harness.py`、`scripts/managed_assets.py`、`CHANGELOG.md`
