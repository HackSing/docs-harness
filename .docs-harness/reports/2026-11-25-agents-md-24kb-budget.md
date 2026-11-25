# 收尾记录：AGENTS.md 24 KB 字节预算与受管入口瘦身

- 日期：2026-11-25
- 关联方案：`docs/plans/agents-md-24kb-budget.json`（已 settle 为 `implemented`）
- 进度清单：`.docs-harness/tasks/agents-md-24kb-budget.md`
- 运行态证据包：`.docs-harness/runtime/agents-md-24kb-budget/packet.json`（`runtime check` 退出码 0）
- 前台/后台验证说明：全程在后台进程非交互执行，无任何前台弹窗、焦点切换或自动打开资源管理器/浏览器行为。

## 改动路径

### 本次任务改动
- `scripts/agent_prompt.md`：外置低频 CLI/字段细则并去冗，体积由 27,157 字节降至 16,578 字节（`managed_agent_block(ROOT)` 为 16,641 B LF / 16,754 B CRLF）；`## 呈现形式` 与 `## 收尾` 逐字保留，全部占位符与验证短语保留。
- `AGENTS.md`：通过 `harness.managed_agent_block` + `replace_managed_block` 同步受管区块，保留末尾块外段落 `## 本仓库例外：收尾记录入库`，总大小 16,913 字节（距 24,000 字节上限余 7,087 字节）。
- `scripts/harness.py`：补齐 `KNOWLEDGE_EPILOG`、`PLAN_EPILOG`（修正 `plan amend` 陈旧文案并补充 `process_flowchart`/`ux_journey`/结算顺序/符号判定纪律）、`ACCEPTANCE_EPILOG`；改由 `report_check.add_report_parser` 注册 `report` 子命令。
- `scripts/checklist_check.py`：新增 `_CHECKLIST_EPILOG` 并接入 `add_checklist_parser`。
- `scripts/report_check.py`：新增 `_REPORT_EPILOG` 与 `add_report_parser`（从 `scripts/harness.py` 迁出以消除 `structure.size` WARN）。
- `scripts/asset_checks.py`：新增 `AGENTS_FILE_MAX_BYTES = 24_000`、`MANAGED_PROMPT_MAX_BYTES = 18_000`、`check_agents_file_budget`，接入 `_warning_group`（`entry.budget`）与 `run_assets_check`（含 `--fast`）。
- `docs/CODEMAP.md`、`docs/contracts.md`、`docs/INDEX.md`、`docs/plans/agents-md-24kb-budget.json`、`docs/plans/agents-md-24kb-budget.md`：同步接口索引、24 KB 门禁契约与 `brief` 级方案结算状态。
- `tests/test_agent_prompt_verification.py`、`tests/test_assets_check.py`：新增 18 KB/24 KB 预算守卫、`--help` 外置细则覆盖测试与 `assets-check` 超限 WARN/边界单测。

### 工作区既有并发脏文件（非本次修改，未触碰）
- `CHANGELOG.md`、`README.md`、`SKILL.md`、`package.json`、`scripts/cli_support.py`、`scripts/host_hooks.py`、`scripts/plan_root_cause_hook.py`、`tests/harness_test_base.py`、`tests/test_host_hooks.py`（以及 `scripts/harness.py`、`docs/CODEMAP.md`、`docs/contracts.md` 中并发任务负责的 `host_hooks` / `--host` 段落）。

## 验证命令与退出码

| 验证层级 | 命令 | 退出码 | 结果摘要 |
|---|---|---|---|
| `focused_test` | `python -m unittest tests.test_agent_prompt_format tests.test_agent_prompt_verification tests.test_assets_check tests.test_cli_surface tests.test_checklist_check tests.test_project_upgrade` | 0 | 73 tests OK (skipped=3) |
| `repository_full_test` | `python -m unittest discover -s tests -p test_*.py` | 1 | 503 tests 中 502 通过/跳过（skipped=12），仅 1 项既有时间漂移失败：`tests/test_asset_checks_semantics.py:68`（`test_recent_amend_does_not_warn` 硬编码 `2026-10-20`，在当前日期 2026-11-25 超过 30 天宽限期，与本次改动无关） |
| `local_runtime` | `python scripts/harness.py runtime check --target . --packet .docs-harness/runtime/agents-md-24kb-budget/packet.json --json` | 0 | passed（2 flows、3 states、4 data、1 probe、4 evidence files，0 errors，0 warnings） |
| `package_or_install` | `python scripts/harness.py self-test --target . --json` | 0 | passed（11/11 checks true） |
| `package_or_install` | `python scripts/harness.py release sync --target . --strict --json` | 0 | consistent（VERSION/controller/skill/package/templates/evals 均为 2.36.0，changelog_top_version=2.36.0） |
| `package_or_install` | `npm pack --dry-run` | 0 | docs-harness-2.36.0.tgz，total files: 108 |
| `focused_test` | `python scripts/harness.py assets-check --target . --strict --json` | 0 | passed（strict=true，0 failures，0 warnings） |
| `focused_test` | `python scripts/harness.py checklist check --target . --path .docs-harness/tasks/agents-md-24kb-budget.md --json` | 0 | passed（mode=plan_linked） |
| `focused_test` | `python scripts/harness.py plan settle --target . --plan docs/plans/agents-md-24kb-budget.json --status implemented --json` | 0 | implemented，warnings=[] |
| `focused_test` | `git diff --check` | 0 | 无空白/行尾格式错误 |

## 编码质量自查

1. **是否引入了重复逻辑及依据**：没有。`add_report_parser` 对称复用 `scripts/checklist_check.py` 的 `add_checklist_parser` 模式，且为第 2 个同类实现（按规则两次保持原样、第 3 次再抽公共 parser 工厂）；`AGENTS_FILE_MAX_BYTES` 与 `MANAGED_PROMPT_MAX_BYTES` 仅在 `scripts/asset_checks.py` 单点定义，测试直接导入引用。
2. **新增抽象各自的职责**：
   - `asset_checks.check_agents_file_budget(target)`：单点检测目标仓库 `AGENTS.md` 磁盘字节数是否超过 `AGENTS_FILE_MAX_BYTES`（24,000 B）并返回标准化 WARN。
   - `report_check.add_report_parser(commands)`：注册 `report` 子命令解析器及 `_REPORT_EPILOG` 帮助说明，避免继续扩大 `scripts/harness.py` 的 `build_parser`。

## 未覆盖项

- `tests/test_asset_checks_semantics.py::PlanAmendWarningTest::test_recent_amend_does_not_warn` 因硬编码 `2026-10-20` 在 `2026-11-25` 超过 30 天宽限期而失败（既有测试时间依赖问题，未越界修改）。
- Windows 无管理员权限创建符号链接触发 `WinError 1314`，真实 symlink 跳过分支未在无特权 Windows 实机覆盖（仅由 `not path.is_symlink()` 守卫覆盖）。
- Antigravity 下一新会话重启加载 `AGENTS.md` 后尾部 `## 收尾` 与块外规则不再被截断的效果，以及 macOS/Linux 环境实跑尚未执行；12 个下游项目本次按约定未升级。

---

## 追加收尾：修复 test_asset_checks_semantics 时间漂移并按要求暂缓分批提交与发版（2026-11-25）

- 改动路径：`tests/test_asset_checks_semantics.py`（`PlanAmendWarningTest` 改用基于 `dt.datetime.now(dt.timezone.utc)` 与 `PLAN_AMEND_GRACE_DAYS` 的相对夹具日期），已独立提交为 `3e3d4e4`（未推送远端）。
- 工作区状态处置：按用户指示暂缓两批改动分批提交及 2.37.0 发版同步下游，已取消 Phase 2 暂存并从备份原样恢复 `scripts/harness.py`、`docs/CODEMAP.md`、`docs/contracts.md`，工作区保持 `3e3d4e4` 之后的完整未提交改动。
- 验证命令与退出码：
  - `python -m unittest tests.test_asset_checks_semantics -v` —— 退出码 0（10 项通过；验证层级：`focused_test`）。
  - `python -m unittest tests.test_asset_checks_semantics tests.test_agent_prompt_verification tests.test_assets_check` —— 退出码 0（33 项通过；验证层级：`focused_test`）。
  - `python scripts/harness.py assets-check --target . --strict --json` —— 退出码 0（0 failures，0 warnings；验证层级：`focused_test`）。
- 前台/后台验证说明：全程后台进程执行，无任何前台弹窗或焦点切换。
- 未覆盖项：修复 `tests/test_asset_checks_semantics.py` 后未重跑全仓 503 项单测；`3e3d4e4` 未推送远端；两批工作区改动（`host_hooks`+`dsh-plugin` 与 `agents-md-24kb-budget`）尚未提交、未发版 2.37.0、未同步 12 个下游项目。
