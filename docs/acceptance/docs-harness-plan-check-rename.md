> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# docs-check 更名为 plan check 验收

- 修订：2
- 关键符号：`command_plan_check`、`plan_check_markdown_files`、`command_assets_check`
- 资产指纹：`sha256:81bb0cf7b954b0a17eec9b9b91f3f354c5cc197c8100709260c0698b4267b513`
- 关联方案：`docs/plans/docs-harness-plan-check-rename.json`

## 验收目标

plan check 行为等价原 docs-check，旧命令删除，全仓引用同步，测试与检查全绿

## 验收标准

### `c1` 改名相关聚焦测试全绿（含 docs-check 未知命令负向用例）

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`tests/test_v2_direct.py`

### `c2` 全量 npm test 通过（CLI 公共契约变更）

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`tests/test_v2_direct.py`、`tests/test_release_version_sync.py`

### `c3` assets-check --strict 通过（含 C5 符号存活，验证 INDEX 同步）

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/INDEX.md`、`scripts/harness.py`

### `c4` self-test 通过

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`scripts/harness.py`

### `c5` 冒烟：plan check 跑通且 docs-check 退出码 2

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`scripts/harness.py`、`CHANGELOG.md`
