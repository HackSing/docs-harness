> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# git 钩子 shim 共存模式与可执行位治理验收

- 修订：6
- 关键符号：`core.hooksPath`、`githook_drift`、`docs-harness-hook-shim`
- 资产指纹：`sha256:f89c1bc1b44f057937ba3b4a669271008e0422658325935f3aab1ade2db5426b`
- 关联方案：`docs/plans/githook-shim-coexistence.json`

## 验收目标

验证 setup.sh shim 化后与第三方钩子共存、旧 hooksPath 可迁移、project check 钩子健康 finding 与 uninstall 清理正确，且受影响模块回归全绿

## 验收标准

### `c1` shim 行为矩阵：安装/拦截/放行/共存/迁移/拒绝覆盖/幂等/worktree

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/githook-shim-coexistence/c1-shim-matrix.txt`

### `c2` project check 新增 finding（githook_index_mode / githook_hookspath_conflict）触发与不触发

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/githook-shim-coexistence/c2-c3-project-install-tests.txt`

### `c3` uninstall 按 marker 清理 shim 且不误删他人钩子

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/githook-shim-coexistence/c2-c3-project-install-tests.txt`

### `c4` 受影响模块回归：test_project_install.py 与 test_cli_surface.py 通过，assets-check 通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/githook-shim-coexistence/c4-regression.txt`
