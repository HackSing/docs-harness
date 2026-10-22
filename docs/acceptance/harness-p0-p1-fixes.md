> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# Harness P0/P1 修复验收

- 修订：6
- 关键符号：`execution_projection`、`plan_show`、`acceptance_amend`、`symbol_hit`
- 资产指纹：`sha256:0ca9889f365a0866d0c5fb6f7deb8e252bcf4418b59d1118531033199b66dc31`
- 关联方案：`docs/plans/harness-p0-p1-fixes.json`

## 验收目标

验证 P0/P1 修复：完整执行投影、一步 plan 创建、验收闭环、知识检索、检查器与诊断改进。

## 验收标准

### `b1.plan_flow` B1 执行投影、plan show 与选择流程通过聚焦测试

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/harness-p0-p1/b1-plan-flow.txt`

### `b2.acceptance_flow` B2 验收闭环与 amend 通过聚焦测试

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/harness-p0-p1/b2-acceptance-flow.txt`

### `b3.knowledge_checks` B3 知识检索与检查器通过聚焦测试

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/harness-p0-p1/b3-knowledge-checks.txt`

### `b4.diagnostics_docs` B4 诊断、CLI 参数边界与文档基线通过检查

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/harness-p0-p1/b4-diagnostics-docs.txt`
