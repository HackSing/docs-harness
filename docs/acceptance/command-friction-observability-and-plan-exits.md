> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# 命令摩擦治理验收：usage 错误码与最近一次检查计数、plan WARN 部分交付第三态、手写方案结算

- 修订：5
- 关键符号：`PLAN_PARTIAL_DELIVERY_RECHECK_DAYS`、`partial_delivery_checked_recently`、`last_warnings`、`error_codes`
- 资产指纹：`sha256:2bda34a36e030c55ec7a16d41d096d567a7345c6277718b9eeb5e72da157cda1`
- 关联方案：`docs/plans/command-friction-observability-and-plan-exits.json`

## 验收目标

首次失败可按错误码归因、检查告警按最近一次计数；部分交付仍有效的方案有带时效的核对出口；手写方案不经伪造冻结 JSON 即可结算。

## 验收标准

### `c1` 契约同步：合同 §3.3/§9、plan check 与 plan settle 的 --help、受管入口判定纪律、SKILL/README 与代码行为一致

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/command-friction-observability-and-plan-exits/c1-contract-sync.txt`

### `c2` 聚焦测试：test_usage、test_plan_lifecycle、test_cli_surface、test_release_version_sync 全部通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/command-friction-observability-and-plan-exits/c2-focused-tests.txt`

### `c3` 本地运行：新引擎对 zbuddy-desktop 本地克隆运行 usage report、部分交付标注后 plan check、手写方案 implemented 与 deprecated 结算，结果符合预期

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/command-friction-observability-and-plan-exits/runtime-summary.md`、`docs/acceptance/evidence/command-friction-observability-and-plan-exits/runtime-01-error-code-probe.json`、`docs/acceptance/evidence/command-friction-observability-and-plan-exits/runtime-02-usage-report.json`、`docs/acceptance/evidence/command-friction-observability-and-plan-exits/runtime-03-plan-check-before-mark.json`、`docs/acceptance/evidence/command-friction-observability-and-plan-exits/runtime-04-plan-check-after-mark.json`、`docs/acceptance/evidence/command-friction-observability-and-plan-exits/runtime-05-settle-handwritten-implemented.json`、`docs/acceptance/evidence/command-friction-observability-and-plan-exits/runtime-06-settle-handwritten-deprecated.json`、`docs/acceptance/evidence/command-friction-observability-and-plan-exits/runtime-07-plan-check-after-settle.json`
