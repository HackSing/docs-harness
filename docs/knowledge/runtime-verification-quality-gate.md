> 状态：有效（现行事实）
<!-- docs-harness:knowledge-document/v1 -->

# 运行态验证证据包与质量门

- 修订：1
- 关键符号：`check_packet`、`RUNTIME_PACKET_SCHEMA`、`RUNTIME_VERIFICATION_RELATIVE`
- 资产指纹：`sha256:9910bdaff28a394270bfb928fc7fbcf5e7e12b685a9e8507dab3c33d7549a2d8`

## 摘要

所有运行态任务用结构化证据包和 runtime check 硬校验，拒绝空泛观察、覆盖缺口和未闭环缺陷。

## 事实

### `runtime.packet.schema`

runtime check 使用 docs-harness/runtime-verification/v1 证据包，要求 environment、flows、states、data、ui、probes、defects、iterations、uncovered 与 conclusion；UI 任务还要求至少两个视口的截图和视觉/交互/文案/可访问性四组观察。

证据：`scripts/runtime_packet.py`、`scripts/runtime_check.py`、`docs/contracts.md`

### `runtime.check.rejections`

runtime check 拒绝空泛或照抄的 expected/observed、缺失或过小的证据文件、必需状态/数据场景缺失、UI 单视口或重复截图、无对抗探测、缺陷未闭环、mock 未声明限制、未知字段以及不符合约定的路径和 task。

证据：`scripts/runtime_check.py`、`scripts/runtime_packet.py`、`tests/test_runtime_check.py`

### `runtime.storage.risk`

复杂或 UI 运行态交付的证据包放在 docs/runtime-verification/<task>/packet.json 且 risk=complex，随仓库提交；普通小改动放在 .docs-harness/runtime/<task>/packet.json 且 risk=simple，由 project init/upgrade 生成的嵌套 .gitignore 忽略。

证据：`scripts/runtime_check.py`、`scripts/harness.py`、`docs/contracts.md`
