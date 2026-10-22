> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# Docs Harness 遵循率优化验收

- 修订：8
- 关键符号：`run_assets_check`、`build_report`、`symbol_hit`、`plan_check_banner`
- 资产指纹：`sha256:3539e4b541eef9f2bd397a3d46c2c9e4152377d345e935b189c1beee19931b8b`
- 关联方案：`docs/plans/harness-adherence-optimization.json`

## 验收目标

验证下游数据驱动的遵循率优化：检查器降噪、验收闭环诊断、输出契约、plan check 性能与持续指标。

## 验收标准

### `c1.warn_noise` 检查器无新增误报，可行动 WARN 收敛

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/harness-adherence-optimization/c1-warn-noise.txt`

### `c2.acceptance_diagnostics` acceptance settle/record 一次给出缺项与下一步命令

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/harness-adherence-optimization/c2-acceptance-diagnostics.txt`

### `c3.output_contract` 收尾报告字段校验与模板可用

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/harness-adherence-optimization/c3-output-contract.txt`

### `c4.plan_check_perf` zbuddy-desktop 增量 plan check 不超过 30 秒

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/harness-adherence-optimization/c4-plan-check-perf.txt`

### `c5.usage_metrics` usage report 提供 WARN 率、真实失败率与报告完整率

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/harness-adherence-optimization/c5-usage-metrics.txt`

### `c6.behavior_baseline` behavior evals 11 条/52 检查点有基线记录与复测对比

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/harness-adherence-optimization/c6-behavior-baseline.md`
