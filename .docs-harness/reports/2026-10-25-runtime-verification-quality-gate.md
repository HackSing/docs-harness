# 2026-10-25 运行态验证证据包与质量门

## 改动路径

- `scripts/runtime_packet.py`：运行态证据包 schema 原语、状态/数据覆盖矩阵、空泛文本与 expected/observed 照抄检查。
- `scripts/runtime_check.py`：`check_packet` 编排、路径/风险规则、证据文件存在与 git 忽略判定、UI 视口与视觉/交互/文案/可访问性校验、缺陷复验闭环。
- `scripts/harness.py`：新增 `runtime check` 子命令、`RUNTIME_VERIFICATION_RELATIVE` 本地目录、受管模块与安装清单接入。
- `scripts/agent_prompt.md`、`AGENTS.md`：受管入口新增运行态质量门；收尾记录要求写证据包路径与 `runtime check` 退出码。
- `plan-templates/profiles/frontend-ui.json`：状态矩阵、可访问性、视觉响应式、文案与运行态验收 guidance。
- `docs/contracts.md`、`docs/testing.md`、`docs/CODEMAP.md`、`docs/README.md`、`docs/runtime-verification/README.md`、`SKILL.md`、`README.md`、`CHANGELOG.md`：合同、验证矩阵、模块索引、命令说明与未发布变更记录。
- `package.json`、`tests/harness_test_base.py`：新模块进入 npm 包与安装测试清单。
- `tests/test_runtime_check.py`：22 项合同测试；`tests/test_project_install.py`：安装副本 `runtime check` 用例；`tests/test_cli_surface.py`、`tests/test_evals.py`：CLI 与评测登记同步；`evals/evals.json`：新增 `runtime-verification-quality` behavior 用例。
- `docs/plans/runtime-verification-quality-gate.json`：Full/architecture 方案；`docs/adr/runtime-verification-evidence-packet.json`：证据包决策；`docs/acceptance/runtime-verification-quality-gate.json`：四项验收；`docs/knowledge/runtime-verification-quality-gate.json`：三项可复用事实。
- `docs/runtime-verification/runtime-verification-quality-gate/packet.json` 与 `evidence/`：本任务的真实运行态证据包，包含有效包、重复空泛词修复前/后、缺失包四组日志。

## 验证

- `python -m unittest tests.test_runtime_check tests.test_cli_surface tests.test_project_install.LocalOnlyDirectoryTest -v`：44 项通过（skipped=1），退出码 0；验证层级：focused_test。
- `python -m unittest discover -s tests -p "test_*.py"`：472 项通过（skipped=12），退出码 0；验证层级：repository_full_test。
- `python scripts/harness.py runtime check --target . --packet docs/runtime-verification/runtime-verification-quality-gate/packet.json --json`：status=passed，flows=3/states=3/data=4/probes=2/iterations=2/defects=1，退出码 0；验证层级：local_runtime。
- `python -m unittest tests.test_project_install.ProjectInstallTest.test_installed_controller_runs_runtime_check -v`：1 项通过，退出码 0；验证层级：package_or_install（安装副本命令可用）。
- `npm pack --dry-run --json`：97 个文件，包含 `scripts/runtime_check.py`、`scripts/runtime_packet.py` 与 `docs/runtime-verification/README.md`，退出码 0；验证层级：package_or_install。
- `python scripts/harness.py self-test --target . --json`：status=passed，退出码 0；验证层级：focused_test。
- `python scripts/harness.py release sync --target . --strict --json`：status=consistent，六处版本源一致，退出码 0；验证层级：focused_test。
- `python scripts/harness.py acceptance check --target . --json`：status=passed，退出码 0；`plan check`：status=passed，退出码 0；`knowledge check`：status=passed，退出码 0；验证层级：focused_test。
- `python scripts/harness.py assets-check --target . --strict --json`：失败 0 条、警告 1 条，退出码 1；唯一警告是工作区既有 `tests/test_qoder_hook.py` 从 557 行增至 689 行的结构体量问题，属于并行路由改动，不在本任务修改范围；验证层级：focused_test。

## 根因

运行态验证此前只有受管入口的原则性要求，`report check` 只校验五项收尾字段，`local_runtime` 验收只校验方法非空、证据文件存在和层级匹配。状态覆盖、数据边界、视觉与交互观察、文案质量、缺陷修复复验都没有可拒绝的交付物，因此“已走查”可以只写一句结论。新增证据包把运行态验证从叙述变成可检查的观察、覆盖矩阵、证据文件和缺陷闭环。

## 自查

- 是否引入重复逻辑：没有。`RUNTIME_PACKET_SCHEMA` 只定义在 `runtime_packet.py`，`runtime_check.py` 与 harness 导入；`RUNTIME_VERIFICATION_RELATIVE` 只定义在 `runtime_check.py`，harness 导入；证据引用、文本质量和字段校验各自只有一份实现。
- 新增抽象职责：`runtime_packet.py` 只负责 schema 原语、覆盖矩阵和文本质量；`runtime_check.py` 只负责路径、文件证据、git 忽略与校验编排；`add_runtime_parser` 只负责 CLI 参数注册。
- 未顺手加固：没有修改无关模块；并行路由工作产生的 `tests/test_qoder_hook.py` 警告只记录，未改动。
- 抽象证据：证据包 schema 与文件证据是两类独立变化方向，拆分后 `scripts/runtime_check.py` 579 行、`runtime_packet.py` 154 行，均低于 600 行红线。

## 未覆盖

- 未在真实浏览器或桌面端走查 UI 分支；UI 多视口、视觉/交互/文案/可访问性只由合成测试夹具验证，未提供真实页面截图。
- 未由用户确认真实视觉与交互体验；`runtime check` 只证明证据结构和观察覆盖成立，不能证明截图与实际页面一致。
- 新增 `runtime-verification-quality` behavior 用例尚未跑真实会话，没有模型遵循率样本。
- 只在 Windows 本机执行了运行态命令；macOS 未在本轮实测，尽管实现只使用 Python 标准库与跨平台路径处理。
- `assets-check --strict` 因工作区既有 `tests/test_qoder_hook.py` 结构警告返回 1；本任务自身的结构警告已消除。
- 未发版、未 bump 版本；CHANGELOG 记录在 Unreleased，版本真源仍为 2.33.0。

## 追加：提交后复跑（2026-10-25）

- `python scripts/harness.py assets-check --target . --strict --json`：0 失败 0 警告，退出码 0。此前唯一的 `tests/test_qoder_hook.py` WARN 是未提交路由测试触发的增量检查；提交后干净树不再触发。该文件 689 行的存量体量债仍建议单独整理。
- `python scripts/harness.py plan check`、`acceptance check`、`knowledge check`：均 passed，退出码 0。
- 本轮只提交到 `feat/strong-model-routing` 功能分支：`afc0d31`（路由收尾）、`6fb9127`（运行态质量门）、`4e25def`（共享文档索引）；未合并 main、未推送、未打 tag。
