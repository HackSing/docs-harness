# 收尾记录：Antigravity 受管全局规则随 `--host antigravity` 自动安装与合同同步

- 日期：2026-11-28
- 验证层级：`focused_test`、`local_runtime`、`package_or_install`
- 进度清单：`.docs-harness/tasks/antigravity-host-rules.md`（`checklist check` 退出码：0）
- 运行态证据包：`.docs-harness/runtime/antigravity-host-rules/packet.json`（`runtime check` 退出码：0）
- 前台/后台验证说明：全程在后台进程执行单测、资产检查、打包检查、dsh-plugin 校验与隔离 HOME 的 CLI 子进程实测，未弹出任何可见窗口、弹窗或抢夺焦点。

## 改动路径

- `scripts/host_rules.py`（新增，122 行）：定义 Antigravity 用户级受管全局规则（全平台 `docs-harness-antigravity-subagents.md` 防 #1890 自定义 agent 4× 计费；仅 Windows `docs-harness-windows-gui-launch.md` 隔离桌面 GUI/托盘避坑与 `netstat -ano`），提供 `ANTIGRAVITY_RULES_RELATIVE`、`HostRuleSpec`、`ANTIGRAVITY_MANAGED_RULES`、`antigravity_rules_dir`、`planned_host_rule_paths`、`install_host_rules`，所有物理行均控制在 Python 3.9 tokenizer 511 字节阈值内。
- `scripts/host_hooks.py`（597 行 <= 600 行红线）：接入 `planned_host_rule_paths` 与 `install_host_rules`；`install_host_hook` 返回 `rule_paths` 并将改动规则合入 `changed`；`inspect_host_hooks` 在预览 `planned_files` 中列出计划写入规则；拆分 `_install_and_refresh` 与 `_refresh_configured_hosts` 保持 `reconcile_host_hook` 低于 60 行阈值，并在存量 `already_configured` 升级时自动幂等补齐/刷新已配置宿主的受管规则（返回 `rules_updated`）。
- `scripts/harness.py`：`MANAGED_MODULE_RELATIVE_FILES` 登记 `host_rules.py`。
- `package.json`：`files` 清单登记 `scripts/host_rules.py`。
- `dsh-plugin/scripts/verify-package.mjs`：`REQUIRED_FILES` 登记 `vendor/harness/scripts/host_rules.py`。
- `docs/contracts.md`：第 4c 节分层细则补记 Windows 隔离桌面终端避坑与 `netstat -ano`；第 7 节安装合同登记 `host_rules` 与 Antigravity 用户级受管规则自动安装/刷新契约。
- `docs/CODEMAP.md`：更新 `scripts/host_hooks.py` 摘要，新增 `scripts/host_rules.py` 索引条目。
- `SKILL.md`：项目安装说明同步提及 `--host antigravity` 同步写入 `~/.gemini/config/rules/docs-harness-*.md`。
- `tests/harness_test_base.py`：`MANAGED_MODULES` 登记 `host_rules.py`。
- `tests/test_host_hooks.py`（596 行 <= 600 行）：新增 Windows/非 Windows 平台过滤、用户既有规则保留、非 Antigravity 宿主隔离、预览 `planned_files`、缺损规则无 `--host` 自动自愈与 CLI 端到端断言。
- `.docs-harness/reports/2026-11-28-antigravity-host-rules.md`（本收尾记录，随仓入库）。

## 搜过什么与收尾自查

- **搜过什么**：检索 `scripts/host_hooks.py`、`scripts/harness.py`（`MANAGED_MODULE_RELATIVE_FILES` 与 `reconcile_project_host_hook`）、`scripts/checklist_check.py`、`scripts/runtime_packet.py`、`package.json`、`dsh-plugin/scripts/verify-package.mjs`、`dsh-plugin/package.json`、`docs/contracts.md`、`docs/CODEMAP.md`、`SKILL.md`、`tests/test_host_hooks.py`、`tests/test_cli_surface.py`、`tests/harness_test_base.py`、`tests/test_release_version_sync.py`。
- **体量评估**：`scripts/host_hooks.py` 为 597 行、`tests/test_host_hooks.py` 为 596 行、`scripts/host_rules.py` 为 122 行，均未触发 600 行文件红线或 60 行函数红线；通过拆出独立 `scripts/host_rules.py` 与 `_install_and_refresh`/`_refresh_configured_hosts`，隔离了“钩子配置合并”与“宿主规则落盘”两类职责。
1. **本次是否引入了重复逻辑？**
   没有。`scripts/host_rules.py` 单一真源承载规则文本、平台筛选与写入，同时服务 `inspect_host_hooks` 预览、`install_host_hook` 首次安装与 `_refresh_configured_hosts` 升级自愈；`_install_and_refresh` 同时消除了 `reconcile_host_hook` 中原有的两处重复安装+刷新逻辑。
2. **本次新增抽象各自的职责是什么？**
   - `scripts/host_rules.py`（`HostRuleSpec`、`planned_host_rule_paths`、`install_host_rules`、`antigravity_rules_dir`）：维护 Antigravity 用户级受管规则规格、按 `is_windows` 过滤并原子幂等写入 `~/.gemini/config/rules/docs-harness-*.md`。
   - `_install_and_refresh`（`scripts/host_hooks.py` 私有辅助）：封装单次宿主安装后回刷探测状态，复用在显式 `--host` 与交互选择两个分支。
   - `_refresh_configured_hosts`（`scripts/host_hooks.py` 私有辅助）：在存量已配置环境升级时统一刷新钩子脚本与已配置宿主的受管规则。

## 验证命令与退出码

- `python -X utf8 -m unittest tests.test_host_hooks tests.test_cli_surface tests.test_project_upgrade tests.test_eval_cli_cases tests.test_release_version_sync -v` —— 退出码：0（Ran 67 tests，OK，skipped=3 为 Windows 无符号链接权限条件跳过；验证层级：`focused_test`）。
- `python -X utf8 scripts/harness.py assets-check --target . --strict --json` —— 退出码：0（违规 0 条、警告 0 条；验证层级：`focused_test`）。
- `python -X utf8 scripts/harness.py self-test --target . --json` —— 退出码：0（`status=passed`；验证层级：`focused_test`）。
- `python -X utf8 scripts/harness.py checklist check --target . --path .docs-harness/tasks/antigravity-host-rules.md --json` —— 退出码：0（`status=passed`；验证层级：`focused_test`）。
- `npm pack --dry-run` —— 退出码：0（打包清单涵盖 `scripts/host_rules.py`；验证层级：`package_or_install`）。
- `npm --prefix dsh-plugin run extract-block && npm --prefix dsh-plugin run verify` —— 退出码：0（`verify-package: @aiwaretop/dsh-docs-harness is publishable`；验证层级：`package_or_install`）。
- 隔离临时 `DOCS_HARNESS_HOST_HOME` 真实 CLI 走查（预览、首次 `init --apply --host antigravity`、缺损规则无 `--host` `upgrade --apply` 自愈、二次升级幂等、损坏 `hooks.json` 拒绝覆盖） —— 退出码：0（证据见 `.docs-harness/runtime/antigravity-host-rules/evidence/`；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py runtime check --target . --packet .docs-harness/runtime/antigravity-host-rules/packet.json --json` —— 退出码：0（`status=passed`；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py report check --target . --path .docs-harness/reports/2026-11-28-antigravity-host-rules.md --json` —— 退出码：0（`status=passed`）。

## 未覆盖项

- 未在真实 macOS/Linux 宿主机实测非 Windows 仅写 1 条规则的路径（已通过单测 `is_windows=False` 覆盖）。
- 未在本机执行 `install_host_hook("antigravity", ...)` 替换当前手写文件 `C:/Users/freed/.gemini/config/rules/{builtin-subagents-only,windows-real-desktop-gui-launch}.md`（避免未经确认删除既有用户文件或导致重复注入）。
- 未运行仓库级全量测试（改动聚焦于宿主钩子/受管模块清单，已覆盖 `test_host_hooks`、`test_cli_surface`、`test_project_upgrade`、`test_eval_cli_cases`、`test_release_version_sync` 与 `self-test`/`assets-check --strict`），且未升版或执行 `git commit`。
