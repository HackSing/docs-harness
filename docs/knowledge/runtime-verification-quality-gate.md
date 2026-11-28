> 状态：有效（现行事实）
<!-- docs-harness:knowledge-document/v1 -->

# 运行态验证证据包与质量门

- 修订：3
- 关键符号：`check_packet`、`RUNTIME_PACKET_SCHEMA`、`RUNTIME_VERIFICATION_RELATIVE`、`validate_ui_visual_review`
- 资产指纹：`sha256:6879a59ad24226e138797627ff280357256023c0e948e647ee4cca2b4acd3e45`

## 摘要

所有运行态任务用结构化证据包和 runtime check 硬校验，大任务通过 Acceptance live_e2e 冻结判据与 Runtime 证据包联动闭环，UI 交付由产品视觉总监子智能体实读双视口截图审查并记入 ui.visual_review。

## 事实

### `runtime.packet.schema`

runtime check 使用 docs-harness/runtime-verification/v1 证据包，要求 environment、flows、states、data、ui、probes、defects、iterations、uncovered 与 conclusion，并支持可选 acceptance_ref、flows[].criterion_id、iterations[].deploy_ref、rechecked_criteria 与 ui.visual_review；UI 任务要求至少两个视口的截图和视觉/交互/文案/可访问性四组观察。

证据：`scripts/runtime_packet.py`、`scripts/runtime_check.py`、`docs/contracts.md`

### `runtime.check.rejections`

runtime check 拒绝空泛或照抄的 expected/observed、缺失或过小的证据文件、必需状态/数据场景缺失、UI 单视口或重复截图、ui.visual_review 未通过/未覆盖双视口真图/空泛评语、无对抗探测、缺陷未闭环、mock 未声明限制、未知字段以及不符合约定的路径和 task；关联带 live_e2e 的冻结 Acceptance 时额外硬拒 environment.mock=true、漏测任一实机 criterion_id、缺少或修复后未变更 deploy_ref、终轮缺少 rechecked_criteria 及篡改的 Acceptance 指纹；关联 acceptance_ref 的 UI 包强制必填 ui.visual_review。

证据：`scripts/runtime_check.py`、`scripts/runtime_packet.py`、`tests/test_runtime_check.py`、`tests/test_live_e2e_verification.py`

### `runtime.storage.risk`

复杂、UI 或 live_e2e 运行态交付的证据包放在 docs/runtime-verification/<task>/packet.json 且 risk=complex，随仓库提交并由 assets-check 统一校验（--fast 增量校验本次改动或带 acceptance_ref 的包，全量对存量无关联坏包报 WARN）；普通小改动放在 .docs-harness/runtime/<task>/packet.json 且 risk=simple，由 project init/upgrade 生成的嵌套 .gitignore 忽略。

证据：`scripts/runtime_check.py`、`scripts/asset_checks.py`、`scripts/harness.py`、`docs/contracts.md`

### `runtime.live_e2e.acceptance_gate`

Acceptance 支持可选 pass_criteria/fail_criteria 与顶层 live_e2e 契约（默认 confirm_before_run=true、max_fix_rounds=3）；acceptance record/settle/check 联动校验引用的运行态证据包，live_e2e 实机标准 passed 必须附带关联本验收且通过 runtime check 的提交态 packet.json。

证据：`scripts/acceptance_assets.py`、`scripts/acceptance_diagnostics.py`、`scripts/harness.py`、`tests/test_live_e2e_verification.py`

### `runtime.ui.prototype_and_director_review`

前端新增页面、核心弹窗或布局/交互大改先在 .docs-harness/views/<task>-prototype.html 输出可点击单文件 HTML 原型待用户确认后再推进方案（frontend_ui 模板必填 interactive_prototype，小样式/文案豁免）；UI 视觉审查由独立只读子智能体以产品视觉总监身份实读双视口截图按六维分级裁决（最多 2-3 轮）并写入 ui.visual_review，无读图/子智能体能力时须诚实声明 fallback_self 与 fallback_reason。

证据：`plan-templates/profiles/frontend-ui.json`、`scripts/runtime_packet.py`、`scripts/runtime_check.py`、`scripts/agent_prompt.md`
