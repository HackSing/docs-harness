# 2026-10-25 2.34.0 合并评审与发布清单

## 评审范围

- 分支：`feat/strong-model-routing`，相对 `main`（`35ba7de`）共 13 个提交。
- 本轮新增提交：`afc0d31`（路由收尾）、`6fb9127`（运行态质量门）、`4e25def`（共享文档索引）。
- 评审方式：逐项读 diff、运行聚焦/全量/安装/运行态/资产检查；未合并、未推送、未打 tag。

## 评审结论

- **运行态质量门：通过。** `runtime check` 对有效、重复空泛、缺失证据分别返回通过/拒绝/结构化错误；`scripts/runtime_check.py` 579 行、`scripts/runtime_packet.py` 154 行，职责分离；本任务证据包通过，安装副本与 npm 包包含新模块。没有发现阻塞合并的代码问题。
- **路由收尾：行为通过，发布需注明边界。** 新增通知过滤、非法画像脱敏诊断、plan 缓存任务切换信号；`tests/test_qoder_hook.py` 与 `tests/test_routing_signals.py` 共 36 项通过。路由仍为 shadow，B2 的 0 漏配门槛未达到，不能在 2.34.0 发布说明里写成“已完成强制路由”。
- **结构存量债：不阻塞当前 CI，但建议单独处理。** `tests/test_qoder_hook.py` 689 行，超过 600 行结构评估阈值；提交后干净树不再触发增量检查，`assets-check --strict` 当前通过。已登记 TODO，建议后续按 hook 契约与缓存/诊断信号拆分。
- **发布状态：尚未进入 2.34.0。** 版本真源仍为 2.33.0，CHANGELOG 顶部仍是 2.33.0，只有 Unreleased 段落；本轮按用户选择只提交功能分支，未合并 main、未推送、未打 tag。

## 验证

- `python -m unittest tests.test_qoder_hook tests.test_routing_signals -v`：36 项通过（skipped=2），退出码 0；验证层级：focused_test。
- `python -m unittest tests.test_runtime_check tests.test_cli_surface tests.test_project_install.LocalOnlyDirectoryTest -v`：44 项通过（skipped=1），退出码 0；验证层级：focused_test。
- `python -m unittest discover -s tests -p "test_*.py"`：472 项通过（skipped=12），退出码 0；验证层级：repository_full_test。
- `python scripts/harness.py runtime check --target . --packet docs/runtime-verification/runtime-verification-quality-gate/packet.json --json`：status=passed，退出码 0；验证层级：local_runtime。
- `python -m unittest tests.test_project_install.ProjectInstallTest.test_installed_controller_runs_runtime_check -v`：1 项通过，退出码 0；`npm pack --dry-run --json`：97 个文件，退出码 0；验证层级：package_or_install。
- `python scripts/harness.py assets-check --target . --strict --json`：0 失败 0 警告，退出码 0；`plan check`、`acceptance check`、`knowledge check`：均 passed，退出码 0；验证层级：focused_test。
- 提交后 `git status`：功能分支 ahead 3，仅有 `.docs-harness/inputs/` 与 `.docs-harness/tasks/` 本地目录未跟踪；远端未更新。

## 2.34.0 发布清单（未执行）

1. 确认发布范围：路由 shadow 收尾 + 运行态质量门；发布说明明确“路由仍 shadow、B2 0 漏配门槛未达”。
2. 版本同步：`VERSION`、`scripts/harness.py`、`SKILL.md`、`package.json`、`plan-templates/*`、`evals/evals.json`、README badge 统一到 2.34.0；CHANGELOG 顶部改为 `## 2.34.0 - 2026-10-25` 并合并 Unreleased 内容；重新渲染 AGENTS.md 受管区块。
3. 发布验证：`release sync --strict`、`self-test`、仓库全量测试、`npm pack --dry-run`、临时项目 fresh install、下游升级（至少 onceright；zbuddy 由用户决定）。
4. 合并与发布：评审通过后合并 main、推送 origin、创建 `v2.34.0` tag；分支和 tag 的删除需用户明确同意。
5. 下游同步：按 `docs/downstream.md` 升级记录逐一确认，不把未提交的下游 `routing/` 当成已交付。

## 未覆盖

- 运行态质量门没有在真实浏览器或桌面端走查 UI；UI 证据仅由合成测试夹具覆盖。
- 新增 `runtime-verification-quality` behavior 用例尚未跑真实会话，没有模型遵循率样本。
- 只在 Windows 本机实测运行态命令；macOS 未实跑。
- 路由仍为 shadow，缺少 1–2 周真实任务采样；B2 0 漏配门槛未达，不能据此宣称强制路由已就绪。
- `tests/test_qoder_hook.py` 689 行的结构存量债未在本轮拆分。
- 未合并、未推送、未打 tag；2.34.0 尚未发布。
