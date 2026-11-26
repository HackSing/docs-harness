# 收尾记录：大任务全量实机闭环验证（live_e2e）

- 日期：2026-11-26
- 任务：将大任务「先冻结全量通过/失败标准 → 真实测试环境逐项实机执行（禁 mock）→ 修复重部署复测闭环 → 输出报告」落入 `docs-harness` 受管体系（复用 `Acceptance` + `Runtime` + `assets-check`，零新增状态机与受管文件）
- 关联方案：`docs/plans/live-e2e-verification-loop.json`
- 关联验收：`docs/acceptance/live-e2e-verification-loop.json`
- 关联知识：`docs/knowledge/runtime-verification-quality-gate.json`（修订至 rev 2）
- 进度清单：`.docs-harness/tasks/live-e2e-verification-loop.md`

## 改动路径

- 核心逻辑：
  - `scripts/runtime_packet.py`（366 行）：新增 `LIVE_E2E_*` 常量、默认熔断/确认门单一真源常量、`ALLOWED_*_FIELDS`、`is_runtime_packet_ref`、`is_live_e2e_criterion`、`validate_criterion_expectations`、`normalize_live_e2e_config`、`validate_live_e2e_criteria`、`load_linked_acceptance`、`validate_acceptance_alignment` 及更新 `RUNTIME_PACKET_EXAMPLE`
  - `scripts/runtime_check.py`（596 行，<=600）：支持 `acceptance_ref`、`flows[].criterion_id`、`iterations[].deploy_ref`/`rechecked_criteria` 并接入 `validate_acceptance_alignment`
  - `scripts/acceptance_diagnostics.py`（173 行）：新增 `verify_record_runtime_evidence` 联动 `check_packet` 与 `live_e2e` 提交态证据包强制绑定
  - `scripts/acceptance_assets.py`（585 行，<=600）：支持 `pass_criteria`/`fail_criteria` 与 `live_e2e` 校验，在 `record`/`_apply_settle_records`/`_validate_live_refs` 接入 `verify_record_runtime_evidence`
  - `scripts/acceptance_amend.py`：修订 pending Acceptance 时同步保留/更新 `live_e2e`
  - `scripts/acceptance_render.py`：渲染 `## 实机全量验收契约（live_e2e）` 与逐条 `- 通过标准：` / `- 失败判定：`
  - `scripts/asset_checks.py`：在 `check_cross_asset_relations` 中新增 `_check_committed_runtime_packets` 校验所有 `docs/runtime-verification/*/packet.json`，`_warning_group` 增 `runtime.verification`
  - `scripts/harness.py`：新增 `assert_runtime_packets_valid` 接入 `build_stored_acceptance_record`，同步 `ACCEPTANCE_TARGET_INPUT_EXAMPLE` / `NOTES`
- 受管入口与文档：
  - `scripts/agent_prompt.md` 与 `AGENTS.md`：新增「大任务全量实机闭环」触发与熔断条款（受管块 LF 17,263 B / CRLF 17,377 B <= 18,000 B；完整 `AGENTS.md` 17,535 B <= 24,000 B）
  - `docs/contracts.md`、`docs/CODEMAP.md`、`SKILL.md`、`docs/testing.md`、`docs/runtime-verification/README.md`、`docs/INDEX.md`
- 资产与测试：
  - `tests/test_live_e2e_verification.py`（新增，7 项合同/端到端/拒绝用例）、`tests/test_agent_prompt_verification.py`（增 `live_e2e` 入口与 `--help` 守卫）
  - `docs/plans/live-e2e-verification-loop.json` / `.md`、`docs/acceptance/live-e2e-verification-loop.json` / `.md`、`docs/knowledge/runtime-verification-quality-gate.json` / `.md`
  - `docs/runtime-verification/live-e2e-verification-loop/packet.json` 及 `evidence/*.log`、`docs/acceptance/evidence/live-e2e-verification-loop/*.log`

## 验证命令、退出码与验证层级

- **验证层级（验收层）**：`focused_test`（L2）+ `repository_full_test`（L2，触发条件：改动公共 `acceptance`/`runtime`/`asset_checks`/`harness`/受管入口基础设施）+ `local_runtime`（L3）+ `package_or_install`（L4）+ L1 合同检查
- 聚焦测试：`python -m unittest tests.test_live_e2e_verification tests.test_runtime_check tests.test_acceptance tests.test_acceptance_amend tests.test_assets_check tests.test_agent_prompt_verification tests.test_agent_prompt_format -v` → 86 项通过，退出码：0
- 仓库全量测试：`python -m unittest discover -s tests -p test_*.py` → 514 项运行全通（skipped=12），退出码：0（证据：`docs/acceptance/evidence/live-e2e-verification-loop/full-tests.log`）
- 运行态证据包校验：`python scripts/harness.py runtime check --target . --packet docs/runtime-verification/live-e2e-verification-loop/packet.json --json` → `status=passed`（0 错误 0 警告），退出码：0
- 合同与打包检查：`acceptance --help`、`runtime --help`、`python scripts/harness.py release sync --target . --strict --json`、`python scripts/harness.py self-test --target . --json`、`npm pack --dry-run` → 全部退出码：0
- 统一资产与结构检查：`python scripts/harness.py assets-check --target . --strict --json`（0 违规 0 警告）、`python scripts/harness.py checklist check --target . --path .docs-harness/tasks/live-e2e-verification-loop.md --json`、`python scripts/harness.py report check --target . --path .docs-harness/reports/2026-11-26-live-e2e-verification-loop.md --json`、`git diff --check` → 全部退出码：0

## 运行态与前后台验证说明

- 运行态证据包路径：`docs/runtime-verification/live-e2e-verification-loop/packet.json`
- `runtime check` 退出码：`0`（`status=passed`，关联 `docs/acceptance/live-e2e-verification-loop.json`，`mock=false`，覆盖 `c3` 正向实机与 4 类对抗拒绝探测）
- 前台/后台验证说明：全程后台无头进程执行，未弹出任何可见窗口、未抢焦点、未打开文件夹或图片查看器，前台持续时长 0 秒。

## 编码质量与根因自查

1. **复用与重复逻辑**：检索并直接复用了 `managed_assets.fingerprint`、`acceptance_assets` 冻结/修订/结算状态机与 `runtime_check.check_packet`；未引入重复冻结状态机，`live_e2e` 配置与判据校验统一收口在 `scripts/runtime_packet.py` 单一来源（常量 `LIVE_E2E_DEFAULT_MAX_FIX_ROUNDS=3`、`LIVE_E2E_CONFIRM_DEFAULT=True`）。
2. **新增抽象职责**：`runtime_packet.py` 承担跨 Acceptance/Runtime 的纯 Schema 原语、冻结 Acceptance 加载与对齐校验；`acceptance_diagnostics.verify_record_runtime_evidence` 承担记录级运行态证据包硬绑定；`asset_checks._check_committed_runtime_packets` 承担提交态运行态证据包巡检；`harness.assert_runtime_packets_valid` 承担 CLI 记录入口即时拦截。
3. **体量与消费链**：`scripts/runtime_check.py`（596 行）与 `scripts/acceptance_assets.py`（585 行）均低于 600 行红线，所有新增函数 <=60 行，`structure check` 0 警告；消费链覆盖 `acceptance create/amend/record/settle/check`、`runtime check`、`assets-check` 与受管入口预算守卫。
4. **文档读者自检**：已以零基础读者通读 `docs/contracts.md`、`SKILL.md`、`docs/runtime-verification/README.md` 与 `acceptance/runtime --help`，所有字段名、默认值（`max_fix_rounds=3`、`confirm_before_run=true`）和报错下一步指引均自包含无缺口。

## 未覆盖项

- 本次仅在 `docs-harness` 源仓（Windows 11 + Python 3.x）验证框架与 CLI 契约，未在下游业务项目（如含真实云端大模型 API、真实数据库与浏览器/桌面 UI 的项目）执行升级与业务端到端实跑；
- 未在 macOS/Linux/Python 3.9 环境实跑，且 12 项依赖 symlink 或本地外部环境的既有测试按条件跳过；
- 未升 `VERSION`、未改 `CHANGELOG.md` 顶部版本、未自动 `git commit` 或同步升级下游项目（待用户确认是否发版并同步下游）。
