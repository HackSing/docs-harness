> 状态：已实施-仅追溯（代码已是真源，2026-11-28 核对）
<!-- docs-harness:plan-document/v1 -->

# 前端可点击 HTML 原型确认门与产品视觉总监子智能体审查

- 冻结合同：`sha256:9d85c246fa693fad8169d2a0741eafff3d34cf8c5a73e868435fd6b628706413`
- 关键符号：`ALLOWED_UI_FIELDS`、`VISUAL_REVIEW_FIELDS`、`VISUAL_REVIEWERS`、`validate_ui_visual_review`

## 目标

为前端较大改动建立先出可点击单文件 HTML 原型（.docs-harness/views/<task>-prototype.html）经用户确认再推进的阶段门，并在运行态质量门落地「产品视觉总监」只读子智能体视觉审查的结构化校验（ui.visual_review），保持 18 KB 受管入口预算、600 行文件红线及下游 102 个历史 UI 证据包零破坏。

## 范围

plan-templates/profiles/frontend-ui.json（新增必填字段 interactive_prototype 并补充 runtime_acceptance.guidance）；scripts/runtime_packet.py（新增 ALLOWED_UI_FIELDS、VISUAL_REVIEW_* 常量与 validate_ui_visual_review，同步 RUNTIME_PACKET_EXAMPLE）；scripts/runtime_check.py（<=600 行，接入 ALLOWED_UI_FIELDS 与 validate_ui_visual_review）；scripts/agent_prompt.md 与 AGENTS.md（增 1 句触发规则且 <=18,000 B）；docs/contracts.md、docs/CODEMAP.md、SKILL.md、docs/testing.md、docs/runtime-verification/README.md 与 docs/knowledge/runtime-verification-quality-gate.json；tests/test_runtime_check.py、tests/test_plan_lifecycle.py、tests/test_agent_prompt_verification.py。

## 关键步骤

B1：更新 plan-templates/profiles/frontend-ui.json、scripts/runtime_packet.py 与 scripts/runtime_check.py；B2（依赖 B1）：更新 scripts/agent_prompt.md、AGENTS.md、合同/CODEMAP/SKILL/测试文档与 Knowledge；B3（依赖 B2）：补充模板、runtime check 与入口预算/文案测试，运行聚焦与全仓回归、self-test、release sync --strict、assets-check --strict、本任务 runtime check，结算 Plan 并写收尾报告。

## 约束与已知陷阱

工作区初始干净；不升 VERSION、不改 CHANGELOG 顶部版本、不新增受管文件或 LOCAL_ONLY_DIRS；scripts/runtime_check.py（现 582 行）须保持 <=600 行；scripts/agent_prompt.md 渲染受管块须同时满足 LF 与 CRLF <=18,000 B（当前 CRLF 17,377 B，仅余约 623 B）；ui.visual_review 对无 acceptance_ref 的存量 UI 包保持向后兼容且不发 WARN，避免误伤下游 102 个历史 UI 包；逐字保留 ## 呈现形式 与 ## 收尾。

## 验收方案

1) python -X utf8 -m unittest tests.test_runtime_check tests.test_live_e2e_verification tests.test_plan_lifecycle tests.test_plan_selection_show tests.test_agent_prompt_verification tests.test_agent_prompt_format tests.test_cli_surface -v（focused_test）；2) python -X utf8 -m unittest discover -s tests -p test_*.py（repository_full_test：触及受管入口、frontend-ui 模板与 runtime_check 公共基础设施）；3) python -X utf8 scripts/harness.py runtime check --target . --packet .docs-harness/runtime/frontend-prototype-and-visual-director-review/packet.json --json（local_runtime）；4) self-test、release sync --strict、assets-check --strict 与 npm pack --dry-run（package_or_install）。

<!-- docs-harness:plan-governance:start -->
## 资产治理

- 关联验收：无
<!-- docs-harness:plan-governance:end -->
