> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# 本地 Usage Log 与 Usage Report 观测能力验收

- 修订：6
- 关键符号：`usage_log`、`append_event`、`USAGE_SCHEMA_VERSION`
- 资产指纹：`sha256:460a9b7ca62a6b45444dcc439f71abf22f6ad1a43cc4de26699397549eee3b4e`
- 关联方案：`docs/plans/usage-observability.json`

## 验收目标

逐层验证本地 usage 埋点与聚合出口：合同层机械检查全绿、运行层事件真实落盘并被 usage report 正确聚合、安装层 config v13 与两个新受管模块完成单向迁移、降级层在无 config／开关关闭／目录只读／日志损坏四种情况下均不改变任何命令的行为与退出码。

## 验收标准

### `contract.suite` 合同层：全量 unittest、assets-check 与 self-test 全绿

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/usage-observability/contract-suite.txt`

### `runtime.events` 运行层：真实命令序列逐条落盘，字段与白名单 flag 正确，usage report 聚合与手工计数相符

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/usage-observability/runtime-events.txt`

### `install.surface` 安装层：project init/upgrade/check/uninstall 覆盖 config v13 与两个新受管模块

- 状态：passed
- 类型：behavior_acceptance
- 层级：L4
- 证据：`docs/acceptance/evidence/usage-observability/install-surface.txt`

### `degrade.safety` 降级层：无 config、开关关闭、目录只读、日志损坏四种情况下命令行为与退出码不变

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/usage-observability/degrade-safety.txt`
