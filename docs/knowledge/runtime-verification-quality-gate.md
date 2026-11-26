> 状态：有效（现行事实）
<!-- docs-harness:knowledge-document/v1 -->

# 运行态验证证据包与质量门

- 修订：2
- 关键符号：`check_packet`、`RUNTIME_PACKET_SCHEMA`、`RUNTIME_VERIFICATION_RELATIVE`、`validate_acceptance_alignment`
- 资产指纹：`sha256:9a0d894fc1ebd9c4e8128c3778209647bc4fd94449efdfd1aabe7f0db51b328e`

## 摘要

所有运行态任务用结构化证据包和 runtime check 硬校验，大任务通过 Acceptance live_e2e 冻结判据与 Runtime 证据包联动闭环并接入 assets-check。

## 事实

### `runtime.packet.schema`

runtime check 使用 docs-harness/runtime-verification/v1 证据包，要求 environment、flows、states、data、ui、probes、defects、iterations、uncovered 与 conclusion，并支持可选 acceptance_ref、flows[].criterion_id、iterations[].deploy_ref 与 rechecked_criteria；UI 任务还要求至少两个视口的截图和视觉/交互/文案/可访问性四组观察。

证据：`scripts/runtime_packet.py`、`scripts/runtime_check.py`、`docs/contracts.md`

### `runtime.check.rejections`

runtime check 拒绝空泛或照抄的 expected/observed、缺失或过小的证据文件、必需状态/数据场景缺失、UI 单视口或重复截图、无对抗探测、缺陷未闭环、mock 未声明限制、未知字段以及不符合约定的路径和 task；关联带 live_e2e 的冻结 Acceptance 时额外硬拒 environment.mock=true、漏测任一实机 criterion_id、缺少或修复后未变更 deploy_ref、终轮缺少 rechecked_criteria 及篡改的 Acceptance 指纹。

证据：`scripts/runtime_check.py`、`scripts/runtime_packet.py`、`tests/test_runtime_check.py`、`tests/test_live_e2e_verification.py`

### `runtime.storage.risk`

复杂、UI 或 live_e2e 运行态交付的证据包放在 docs/runtime-verification/<task>/packet.json 且 risk=complex，随仓库提交并由 assets-check 统一校验；普通小改动放在 .docs-harness/runtime/<task>/packet.json 且 risk=simple，由 project init/upgrade 生成的嵌套 .gitignore 忽略。

证据：`scripts/runtime_check.py`、`scripts/asset_checks.py`、`scripts/harness.py`、`docs/contracts.md`

### `runtime.live_e2e.acceptance_gate`

Acceptance 支持可选 pass_criteria/fail_criteria 与顶层 live_e2e 契约（默认 confirm_before_run=true、max_fix_rounds=3）；acceptance record/settle/check 联动校验引用的运行态证据包，live_e2e 实机标准 passed 必须附带关联本验收且通过 runtime check 的提交态 packet.json。

证据：`scripts/acceptance_assets.py`、`scripts/acceptance_diagnostics.py`、`scripts/harness.py`、`tests/test_live_e2e_verification.py`
