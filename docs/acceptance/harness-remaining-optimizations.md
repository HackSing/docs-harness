> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# Harness 剩余优化验收

- 修订：5
- 关键符号：`plan_check`、`acceptance_show`、`knowledge_index`、`agent_prompt`
- 资产指纹：`sha256:33598b0779b15333dbb77dd0700ffd5d88af014d5150da2570e03313be3bbf9d`
- 关联方案：`docs/plans/harness-remaining-optimizations.json`

## 验收目标

验证 P0/P1/P2 剩余优化：严格门禁、状态查询、amend/dry-run、性能/知识质量、提示词与平台兼容。

## 验收标准

### `r0.strict_gate` R0 模块拆分与 assets-check --strict 通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/harness-remaining-optimizations/r0-strict-gate.txt`

### `r1.state_and_amend` R1 状态查询、amend/dry-run 与 CLI/检查器测试通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/harness-remaining-optimizations/r1-state-and-amend.txt`

### `r2.scale_and_prompt` R2 性能、知识检索、提示词与平台测试通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/harness-remaining-optimizations/r2-scale-and-prompt.txt`
