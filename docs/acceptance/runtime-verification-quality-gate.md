> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# 运行态验证证据包与质量门验收

- 修订：6
- 关键符号：`check_packet`、`RUNTIME_PACKET_SCHEMA`、`RUNTIME_VERIFICATION_RELATIVE`
- 资产指纹：`sha256:473e3cf0895931d52289eb8562749251cd91a44c6c95f368c605c0379eeed596`
- 关联方案：`docs/plans/runtime-verification-quality-gate.json`

## 验收目标

建立所有运行态任务可用的证据包与硬校验：真实流程、状态矩阵、数据场景、UI 视觉/交互/文案/可访问性观察、对抗性探测、缺陷修复复验都有可拒绝的证据；复杂或 UI 证据可提交复查，普通改动本地留存。

## 验收标准

### `c1` 合同：schema 常量、runtime check CLI、安装清单与本地证据目录生效

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/runtime-verification-quality-gate/contract-runtime-help.log`、`docs/acceptance/evidence/runtime-verification-quality-gate/self-test.log`、`docs/acceptance/evidence/runtime-verification-quality-gate/release-sync.log`

### `c2` 行为：聚焦测试覆盖通过包与空泛观察/缺证据/缺状态/UI 单视口/无探测/缺陷未复验等坏包拒绝

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/runtime-verification-quality-gate/focused-tests.log`

### `c3` 运行态：真实 demo 证据包通过 runtime check，坏包复现失败

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/runtime-verification-quality-gate/task-packet-check.log`、`docs/runtime-verification/runtime-verification-quality-gate/packet.json`、`docs/runtime-verification/runtime-verification-quality-gate/evidence/good.log`、`docs/runtime-verification/runtime-verification-quality-gate/evidence/repetitive-before-fix.log`、`docs/runtime-verification/runtime-verification-quality-gate/evidence/repetitive-after-fix.log`、`docs/runtime-verification/runtime-verification-quality-gate/evidence/missing.log`

### `c4` 安装：npm pack 包含新模块，临时项目 init 后 runtime check 可运行

- 状态：passed
- 类型：behavior_acceptance
- 层级：L4
- 证据：`docs/acceptance/evidence/runtime-verification-quality-gate/npm-pack-summary.log`、`docs/acceptance/evidence/runtime-verification-quality-gate/npm-pack.json`、`docs/acceptance/evidence/runtime-verification-quality-gate/installed-runtime-check.log`
