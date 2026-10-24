> 状态：有效（待验收）
<!-- docs-harness:acceptance-document/v1 -->

# 强力模型意图路由落地验收

- 修订：7
- 关键符号：`load_registry`、`validate_profile`、`summarize_shadow`、`coverage_check`
- 资产指纹：`sha256:480a5b28ca829b983470b3b5bf0b582b67f96c6c9957e9468a1971b66589ab71`
- 关联方案：`docs/plans/strong-model-routing-rollout.json`

## 验收目标

逐条验证路由注册表、纯校验、shadow 日志与指标、离线评分复用、默认关闭边界，以及 B2–B5 的真实放量证据。

## 验收标准

### `c1-registry` 注册表覆盖 7 意图/6 模块/10 触发项、映射、契约、风险级别与版本指纹，且与三份评测数据集一致

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/strong-model-routing-rollout/b1.json`

### `c2-validation` 非法标签、重复、未知字段、answer_only 冲突、模块越界、澄清形状与低置信都被确定性拒绝或降级，依赖闭包解析正确

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/strong-model-routing-rollout/b1.json`

### `c3-shadow-privacy` Shadow 事件只含白名单字段，不含任务原文/证据/路径，读写往返可还原决策，损坏日志显式失败

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/strong-model-routing-rollout/b1.json`

### `c4-metrics-coverage` 指标聚合输出关键漏配、过度路由、澄清、返工、p50/p95、token/cost 与分组告警，覆盖率缺失时阻断

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/strong-model-routing-rollout/b1.json`

### `c5-offline-reuse` 复用 score_cases 在诊断集与两组 held-out 上运行，gold profile 经注册表解析出期望模块，强模型本地预测可校验评分

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/strong-model-routing-rollout/b1.json`

### `c6-default-off` B1 未新增 CLI 命令、未改变执行行为、未进入 MANAGED_MODULE_RELATIVE_FILES 或下游安装面

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/strong-model-routing-rollout/b1.json`

### `c7-shadow-production` B2 真实任务 1–2 周内 100% 有路由决策日志，关键漏配和返工不高于基线，p95 延迟与 token 成本在预算内

- 状态：pending
- 类型：behavior_acceptance
- 层级：L3
- 证据：尚无

### `c8-canary-high-risk` B3/B4 低风险类 canary 可一键回滚，高风险类保留人工复核与覆盖率阻断，交叉场景合同测试通过

- 状态：pending
- 类型：behavior_acceptance
- 层级：L3
- 证据：尚无

### `c9-enforced-cleanup` B5 强制执行、旧 Jev/规则路径评估、Acceptance 逐条记录、Knowledge 更新与 ADR 定稿完成

- 状态：pending
- 类型：behavior_acceptance
- 层级：L3
- 证据：尚无
