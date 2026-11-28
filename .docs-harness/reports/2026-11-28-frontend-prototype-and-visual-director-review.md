# 收尾记录：前端可点击 HTML 原型确认门与产品视觉总监子智能体审查

- 日期：2026-11-28
- 任务：为前端较大改动（新增页面/核心弹窗/布局或交互大改/视觉改版）增加先出可点击单文件 HTML 原型（`.docs-harness/views/<task>-prototype.html`）待用户确认再推进的阶段门，并在运行态质量门落地只读子智能体以「产品视觉总监」身份实读双视口截图按六维分级裁决（`ui.visual_review`）的结构化硬校验。
- 关联方案：`docs/plans/frontend-prototype-and-visual-director-review.json`
- 关联知识：`docs/knowledge/runtime-verification-quality-gate.json`（修订至 rev 3）
- 进度清单：`.docs-harness/tasks/frontend-prototype-and-visual-director-review.md`

## 改动路径

- 方案模板：`plan-templates/profiles/frontend-ui.json`（新增必填字段 `interactive_prototype`，并在 `runtime_acceptance.guidance` 补齐产品视觉总监子智能体六维评审、`P0`/`P1`/`P2` 分级、2–3 轮止损与 `fallback_self` 诚实声明细则）。
- 运行态硬校验：
  - `scripts/runtime_packet.py`（447 行）：新增 `UI_OPTIONAL_FIELDS`、`ALLOWED_UI_FIELDS`、`VISUAL_REVIEW_FIELDS`、`VISUAL_REVIEW_REQUIRED_FIELDS`、`VISUAL_REVIEWERS`、`VISUAL_REVIEW_VERDICTS`、`VISUAL_REVIEW_MAX_ROUNDS = 3` 与 `validate_ui_visual_review`，更新 `RUNTIME_PACKET_EXAMPLE`（并按 Python 3.9 511 字节词法行长守卫拆行）。
  - `scripts/runtime_check.py`（592 行，<=600）：`_validate_ui` 改用 `ALLOWED_UI_FIELDS` 并禁止非 UI 任务填写 `ui.visual_review`；`_validate_ui_details` 收集双视口真图映射并调用 `validate_ui_visual_review`（关联 `acceptance_ref` 的 UI 包强制必填 `ui.visual_review`，无关联历史 UI 包保持向后兼容且不发 WARN）。
- 受管入口与文档：
  - `scripts/agent_prompt.md` 与 `AGENTS.md`：新增 1 条「前端原型与视觉审查」触发规则（渲染受管块 LF 17,635 B / CRLF 17,750 B <= 18,000 B；完整 `AGENTS.md` 17,907 B <= 24,000 B）。
  - `docs/contracts.md`、`docs/CODEMAP.md`、`SKILL.md`、`docs/testing.md`、`docs/runtime-verification/README.md`、`docs/INDEX.md`、`docs/knowledge/runtime-verification-quality-gate.json` / `.md`、`docs/plans/frontend-prototype-and-visual-director-review.json` / `.md`。
- 测试：`tests/test_runtime_check.py`（新增 3 项 `ui.visual_review` 通过/降级/拒绝/关联强制测试）、`tests/test_plan_lifecycle.py`（断言 `interactive_prototype` 与产品视觉总监 guidance）、`tests/test_agent_prompt_verification.py`（断言入口与 `runtime --help` 新规则）。

## 验证命令、退出码与验证层级

- **验证层级（验收层）**：L1 合同检查 + `focused_test`（L2）+ `repository_full_test`（L2，触发条件：改动受管入口、`frontend-ui.json` 模板与 `runtime_check` 公共基础设施）+ `local_runtime`（L3）+ `package_or_install`（L4）
- 聚焦测试：`python -X utf8 -m unittest tests.test_runtime_check tests.test_live_e2e_verification tests.test_plan_lifecycle tests.test_plan_selection_show tests.test_agent_prompt_verification tests.test_agent_prompt_format tests.test_cli_surface -v` → 99 项通过（skipped=1），退出码：0
- 仓库全量测试：`python -X utf8 -m unittest discover -s tests -p "test_*.py"` → 519 项运行全通（skipped=12），退出码：0
- 运行态证据包校验：`python -X utf8 scripts/harness.py runtime check --target . --packet .docs-harness/runtime/frontend-prototype-and-visual-director-review/packet.json --json` → `status=passed`（0 错误 0 警告），退出码：0
- 合同与打包检查：`self-test`、`release sync --strict`、`npm pack --dry-run`、`checklist check`、`report check`、`git diff --check` 全部退出码：0；`assets-check`（非 strict）退出码：0（0 违规、1 条无关工作区既有警告：`tests/test_host_hooks.py` 486→617 行，非本次改动）；`assets-check --strict` 因该既有无关警告退出码：1，本次改动文件 0 违规 0 警告。

## 运行态与前后台验证说明

- 运行态证据包路径：`.docs-harness/runtime/frontend-prototype-and-visual-director-review/packet.json`
- `runtime check` 退出码：`0`（`status=passed`，实测 `plan select --level full --profile frontend_ui`、关联 `acceptance_ref` UI 包缺 `ui.visual_review` 拒绝退 2、补齐双视口真图视觉总监审查通过退 0）
- 前台/后台验证说明：全程后台无头进程执行，未弹出任何可见窗口、未抢焦点、未自动打开文件夹或图片查看器，前台持续时长 0 秒。

## 编码质量与根因自查

1. **复用与重复逻辑**：原型目录直接复用既有不入库的 `.docs-harness/views/`（未新增 `LOCAL_ONLY_DIRS`），视觉审查校验复用 `runtime_packet.object_field`/`required_fields`/`text`/`text_list` 原语；未引入重复状态机或重复逻辑。
2. **新增抽象职责**：`runtime_packet.validate_ui_visual_review` 专责 `ui.visual_review` 结构、角色降级诚实声明、终态 `approved` 与双视口真图归属校验；`VISUAL_REVIEW_MAX_ROUNDS = 3` 作为止损轮次常量单一来源。
3. **体量与向后兼容**：`scripts/runtime_check.py` 592 行（<=600）、`scripts/runtime_packet.py` 447 行（<=600），`structure check` 0 警告；无 `acceptance_ref` 的存量 UI 包零破坏且无额外 WARN。
4. **文档读者自检**：以零基础读者通读 `plan-templates/profiles/frontend-ui.json`、`docs/contracts.md`、`SKILL.md`、`docs/runtime-verification/README.md` 与 `runtime --help`，原型路径、触发豁免条件、六维评审与 `ui.visual_review` 字段形状均自包含无缺口。

## 未覆盖项

- 本次仅在 `docs-harness` 源仓（Windows 11 + Python 3.x）验证模板、受管入口与 `runtime check` 合同，尚未在含真实前端页面的下游业务项目中由真实多模态只读子智能体端到端实跑 HTML 原型与页面截图审查；
- 未在 macOS/Linux/Python 3.9 实机环境复测（Python 3.9 词法行长已由确定性单测守卫），全仓 519 项中有 12 项条件跳过；
- 本次暂未升版本号（`VERSION` 保持 `2.38.1`）、未自动 `git commit` 或同步升级 12 个下游项目。
