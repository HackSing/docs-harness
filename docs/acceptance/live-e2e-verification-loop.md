> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# 大任务全量实机闭环验证（live_e2e）验收

- 修订：2
- 关键符号：`LIVE_E2E_FIELDS`、`normalize_live_e2e_config`、`validate_acceptance_alignment`、`verify_record_runtime_evidence`
- 资产指纹：`sha256:f0a1e506357a5d57c5524e87262c646ae6b58f22f6a82ba595cd9e8d8659148a`
- 关联方案：`docs/plans/live-e2e-verification-loop.json`
- 关联知识：`docs/knowledge/runtime-verification-quality-gate.json`

## 验收目标

验证 Acceptance 冻结通过/失败判据与 live_e2e 契约、Runtime 实机证据包 100% 对齐与重部署校验、acceptance record/check 与 assets-check 联动门禁，以及 18 KB 受管入口预算和全仓回归均成立。

## 实机全量验收契约（live_e2e）

- 目标环境：Windows 11 本地 docs-harness 源仓与真实临时项目目录，无 mock 替代子进程执行
- 真实依赖（禁 mock）：本地真实 Python CLI 控制器进程（scripts/harness.py）、真实临时 Git 仓库与受管文件系统
- 隔离与清理：全部隔离实机探测写入系统临时目录并由脚本自动清理，不污染工作区既有资产
- 重部署方式：`python scripts/harness.py self-test --target . --json`
- 单缺陷熔断上限：3 轮
- 执行前确认门：否（已授权直接执行）

## 验收标准

### `c1` 合同：18 KB 受管入口预算、acceptance/runtime --help 字段说明与 release sync --strict 一致

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/live-e2e-verification-loop/contract-help.log`、`docs/acceptance/evidence/live-e2e-verification-loop/runtime-help.log`、`docs/acceptance/evidence/live-e2e-verification-loop/release-sync.log`

### `c2` 回归：仓库全量单元测试（含新增 test_live_e2e_verification）通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/live-e2e-verification-loop/full-tests.log`

### `c3` 实机闭环：真实 CLI 执行 live_e2e 正向全通、坏包拒绝与 assets-check 联动

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 通过标准：真实 CLI 运行本任务提交态 live_e2e 证据包返回 status=passed 且退出码 0，同时 mock=true、漏测 criterion_id 与未变更 deploy_ref 坏包均返回退出码 2 与对应错误码
- 失败判定：任一正向 CLI 校验失败、任一坏包未被拒绝（退出码 0）或报错未命中预期错误码均判失败
- 证据：`docs/runtime-verification/live-e2e-verification-loop/packet.json`、`docs/runtime-verification/live-e2e-verification-loop/evidence/live-valid.log`、`docs/runtime-verification/live-e2e-verification-loop/evidence/bad-mock.log`、`docs/runtime-verification/live-e2e-verification-loop/evidence/bad-gap-deploy.log`、`docs/runtime-verification/live-e2e-verification-loop/evidence/bad-tamper.log`

### `c4` 打包与资产门禁：self-test、npm pack --dry-run 与 assets-check --strict 通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L4
- 证据：`docs/acceptance/evidence/live-e2e-verification-loop/self-test.log`、`docs/acceptance/evidence/live-e2e-verification-loop/npm-pack.log`
