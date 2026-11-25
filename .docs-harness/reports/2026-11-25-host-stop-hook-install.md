# 收尾记录：安装/升级流程集成多宿主防治标 Stop Hook

- 日期：2026-11-25
- 验证层级：`focused_test`、`local_runtime`、`package_or_install`
- 运行态证据包：`.docs-harness/runtime/host-stop-hook-install/packet.json`（`runtime check` 退出码：0）
- 前台/后台验证说明：全程在后台进程执行单测、打包检查、静态检查与隔离临时目录运行态脚本，未弹出任何可见窗口、弹窗或抢夺焦点。

## 改动路径

- `scripts/plan_root_cause_hook.py`（新增受管模块）：跨宿主统一防治标 Stop Hook，自动识别 Antigravity（`continuationActive` + `decision=continue`）与 Claude Code / Codex / Qoder / ZCode / DeepSeek Harness 兼容协议（`stop_hook_active` + `decision=block`），内置进程外单轮防重缓存兜底与中文紧凑方案阈值（`MIN_CHAT_PLAN_CHARS=140`）。
- `scripts/host_hooks.py`（新增受管模块）：六宿主用户级 Stop Hook 探测、活跃环境提示、交互式编号环境选择、幂等配置写入与 `project init/upgrade` 协调入口。
- `scripts/harness.py`：在 `MANAGED_MODULE_RELATIVE_FILES` 注册两新模块；在 `project init/upgrade` 的 preview 与 apply 路径接入 `reconcile_project_host_hook` 并通过 `add_host_argument` 注册 `--host`（净增控制在结构红线阈值内，不改动 `.docs-harness/config.json` schema 与 `notices` 契约）。
- `scripts/cli_support.py`：为 `("project", "init")` 与 `("project", "upgrade")` 放行 `--host`，拒绝其他 action 误传。
- `package.json`、`tests/harness_test_base.py`：同步打包清单与 `MANAGED_MODULES`。
- `tests/test_host_hooks.py`（新增）：12 项测试覆盖 6 宿主幂等安装与原配置保留、损坏 JSON fail-closed、交互选择与 EOF 跳过、活跃宿主缺失探测、双协议与桥接防重兜底、隔离 `DOCS_HARNESS_HOST_HOME` 子进程 CLI 端到端闭环。
- `docs/CODEMAP.md`、`docs/contracts.md`、`SKILL.md`、`README.md`、`CHANGELOG.md`：同步模块索引、安装合同、使用指引与 `## Unreleased` 记录。

## 收尾自查

1. **本次是否引入了重复逻辑？**
   没有。六个宿主共用一份 `scripts/plan_root_cause_hook.py` 钩子脚本（而非按宿主复制 6 份）；Claude Code / Codex / Qoder 三者共用 `_write_claude_family_config` 与 `_merge_stop_list`；原子落盘复用 `managed_assets.py` 的 `atomic_write_json` / `atomic_write_text`。
2. **本次新增的抽象各自的职责是什么？**
   - `scripts/plan_root_cause_hook.py`：只负责 Stop 钩子运行态判定（stdin 协议识别、轨迹解析、防重锁、输出决策 JSON），零宿主配置文件写入逻辑；
   - `scripts/host_hooks.py`：只负责用户级宿主环境探测、终端交互选择、各宿主配置文件幂等合并及 CLI 协调，零 Stop 判定逻辑。

## 验证命令与退出码

- `python -X utf8 -m unittest tests.test_host_hooks tests.test_project_upgrade tests.test_cli_surface tests.test_release_version_sync tests.test_assets_check -v` —— 退出码：0（64 项通过，3 项按条件跳过；验证层级：`focused_test`）。
- `python -X utf8 -m unittest tests.test_project_install -v` —— 退出码：0（31 项通过，1 项 Windows 无 symlink 权限跳过；验证层级：`focused_test`、`package_or_install`）。
- `python -X utf8 scripts/harness.py structure check --target . --json` —— 退出码：0（`status=passed`，warnings 0 条；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py release sync --target . --strict --json` —— 退出码：0（`status=consistent`；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py self-test --target . --json` —— 退出码：0（`status=passed`；验证层级：`focused_test`）。
- `npm run pack:check` —— 退出码：0（新模块已纳入打包清单；验证层级：`package_or_install`）。
- `python -X utf8 scripts/harness.py runtime check --target . --packet .docs-harness/runtime/host-stop-hook-install/packet.json --json` —— 退出码：0（验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py assets-check --target . --fast --json` —— 退出码：0（违规 0 条；`--strict` 唯一余留 WARN 为并发会话未结算方案 `docs/plans/agents-md-24kb-budget.md`，与本次改动无关）。
- `npm test`（`dsh-plugin/`） —— 退出码：1（归因：`pre_existing`；`seed-vendor.mjs` 自 2.15.2 起仅复制 `*.py`/`*.cjs` 未复制受管 `scripts/agent_prompt.md`，导致 `extract-managed-block.mjs` 报错 `invalid_source`；本次新增的两 `.py` 模块已被正常复制）。
- `python -X utf8 scripts/harness.py checklist check --target . --path .docs-harness/tasks/host-stop-hook-install.md --json` —— 退出码：0。
- `python -X utf8 scripts/harness.py report check --target . --path .docs-harness/reports/2026-11-25-host-stop-hook-install.md --json` —— 退出码：0。

## 未覆盖项

- 未在 Antigravity、Claude Code、Codex、Qoder、ZCode、DeepSeek Harness 六个真实宿主应用内逐一新建会话做端到端 UI 触发实测（运行态仅通过隔离目录与真实子进程覆盖协议层与配置落盘）。
- 未修改 `dsh-plugin/scripts/seed-vendor.mjs` 既有 `agent_prompt.md` 漏复制问题（按“不顺手加固”保留在既有归因中）。
- 未修改并发工作区中的 `agents-md-24kb-budget` 相关文件（工作区同时存在该方案的未提交变更）。

---

## 追加收尾：本机迁移至统一钩子路径 + 修复 `dsh-plugin` 引擎种子与 `project init --apply`（2026-11-25）

- 验证层级：`focused_test`、`local_runtime`、`package_or_install`
- 前台/后台验证说明：全程后台进程执行，未弹出可见窗口、未抢焦点。

### 改动路径

- 本机用户配置（不入库）：
  - `C:/Users/freed/.docs-harness/hooks/plan_root_cause_hook.py`：写入最新统一跨宿主 Stop Hook 脚本。
  - `C:/Users/freed/.gemini/config/hooks.json`：`"plan-root-cause-challenge"` 切换为 `python -X utf8 C:/Users/freed/.docs-harness/hooks/plan_root_cause_hook.py`（未删除旧文件 `C:/Users/freed/.gemini/config/hooks/plan_root_cause_stop_hook.py`）。
- 仓库内改动：
  - `scripts/host_hooks.py`：`_hook_command_parts` 改用 `script_path.as_posix()`，`_hook_command_string` 仅在路径含空格时加双引号（修复 Windows 上宿主经 `["cmd", "/c", command]` 执行带反斜杠双引号路径报 `[Errno 22] Invalid argument` 的缺陷）。
  - `tests/test_host_hooks.py`：新增经真实 `["cmd", "/c", cmd]`（POSIX 为 `["sh", "-c", cmd]`）执行 `hooks.json` 写入命令的回归断言。
  - `dsh-plugin/scripts/seed-vendor.mjs`：`engineScripts` 改为直接解析 `../scripts/harness.py` 的 `MANAGED_MODULE_RELATIVE_FILES` 单一真源（不再按 `.py`/`.cjs` 后缀猜，根治漏复制 `scripts/agent_prompt.md` 及未来非脚本受管文件）。
  - `dsh-plugin/scripts/extract-managed-block.mjs`、`dsh-plugin/src/host/project-ops.js`：补齐 `project init --apply`（适配 2.22.0 起 `init` 默认预览契约）。
  - `dsh-plugin/scripts/verify-package.mjs`：`REQUIRED_FILES` 补齐 `agent_prompt.md`、`host_hooks.py`、`plan_root_cause_hook.py`。
  - `CHANGELOG.md`：`## Unreleased` 补充本次 `dsh-plugin` 修复记录。

### 收尾自查

1. **本次是否引入了重复逻辑？**
   没有。`seed-vendor.mjs` 直接读取 `scripts/harness.py` 的 `MANAGED_MODULE_RELATIVE_FILES`，消除了扩展名手写过滤与受管清单的双源漂移；本机迁移直接复用 `host_hooks.install_host_hook`。
2. **本次新增的抽象各自的职责是什么？**
   无新增模块；仅将 `seed-vendor.mjs` 的 `engineScripts` 改为单源解析，并在 `host_hooks.py` 统一 POSIX 路径命令序列化。

### 验证命令与退出码

- 本机真实 `hooks.json` 经 `["cmd", "/c", cmd]` 冒烟执行 —— 退出码：0（输出 `{}`，命令为 `python -X utf8 C:/Users/freed/.docs-harness/hooks/plan_root_cause_hook.py`；验证层级：`local_runtime`）。
- `python -X utf8 -m unittest tests.test_host_hooks -v` —— 退出码：0（12 项通过，含 Windows `cmd /c` 真实命令回归；验证层级：`focused_test`）。
- `npm test && npm run verify`（`dsh-plugin/`） —— 退出码：0（164 项通过 / 24 suites + `verify-package: @aiwaretop/dsh-docs-harness is publishable`；验证层级：`focused_test`、`package_or_install`）。
- `python -X utf8 scripts/harness.py structure check --target . --json` —— 退出码：0（warnings 0 条）。
- `python -X utf8 scripts/harness.py assets-check --target . --fast --json` —— 退出码：0（failures 0 条，warnings 0 条）。
- `python -X utf8 scripts/harness.py self-test --target . --json` —— 退出码：0（`status=passed`）。
- `python -X utf8 scripts/harness.py report check --target . --path .docs-harness/reports/2026-11-25-host-stop-hook-install.md --json` —— 退出码：0。

- 清理确认：经用户明确确认，已删除旧脚本 `C:/Users/freed/.gemini/config/hooks/plan_root_cause_stop_hook.py`，并复测 `C:/Users/freed/.gemini/config/hooks.json` 指向统一路径 `C:/Users/freed/.docs-harness/hooks/plan_root_cause_hook.py` 经 `cmd /c` 执行返回 `{}`（退出码：0）。
