> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# Docs Harness 2.7.0 三资产治理实施验收

- 修订：7
- 关键符号：`command_assets_check`、`acceptance_refs`、`knowledge_impact`、`validate_plan_governance`
- 资产指纹：`sha256:3aa3890d726ef3afb87ab087079a759cb4364a705bfa80733926751025075de0`
- 关联方案：`docs/plans/docs-harness-assets-governance-2.7.0.json`

## 验收目标

验证统一资产检查、跨资产结算关系、兼容迁移和交付消费链真实成立。

## 验收标准

### `assets.check` 三类资产与跨资产检查按 FAIL/WARN/strict 合同运行

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/testing.md`、`tests/test_v2_direct.py`

### `plan.governance` Plan v3、Acceptance 反向登记与治理结算闭环成立

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/testing.md`、`scripts/plan_governance.py`、`tests/test_v2_direct.py`

### `compatibility.v2` Plan v2 与 2.6.0 资产保持兼容

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/testing.md`、`tests/test_v2_direct.py`

### `repository.regression` 仓库级全量回归通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/testing.md`

### `package.install` 打包与 fresh install 消费链通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L4
- 证据：`docs/testing.md`、`package.json`
