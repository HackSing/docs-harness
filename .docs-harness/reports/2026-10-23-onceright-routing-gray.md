# 2026-10-23 onceright 接入路由 shadow 灰度

## 改动路径

- `D:\AIWareTop\Agent\onceright\routing\registry.json`：从 docs-harness `routing/registry.json` 复制的 opt-in 快照，`version=1.0.0`，指纹 `sha256:c3b984d65a55111bdee379dbb666a52dea3d234fdd94b856ec179825835b912a`；未提交。
- `D:\AIWareTop\Agent\onceright\routing\README.md`：与 zbuddy 试点相同的 opt-in 说明；未提交。
- `docs/routing.md` §11：当前接入新增 onceright，补充 fake 与真实 Windows Desktop 会话证据，明确 shadow 灰度不等于 canary 注入。
- `docs/downstream.md`：onceright 行补记 2.33.0 升级与路由 shadow 灰度接入。
- onceright 本地 `.git/info/exclude`：增加 `.docs-harness/routing/`，只在本机生效，未改仓库文件。

## 验证

- `load_registry("D:/AIWareTop/Agent/onceright/routing/registry.json")`：返回 `version=1.0.0`、`fingerprint=sha256:c3b984d65a55111bdee379dbb666a52dea3d234fdd94b856ec179825835b912a`；文件 SHA-256 与 docs-harness 源文件一致（`9f6202c1…`）；退出码 0；验证层级：contract_check。
- fake backend 冒烟：在 onceright 运行 `route_hook.py`，退出码 0；Shadow 事件 `phase=shadow`、`modules=["code"]`、`actual_modules` 为全部 6 个模块；合成日志随后删除；验证层级：local_runtime。
- Qoder Desktop 真实会话 `aab05da4-39a3-5f93-a0b3-2e1182ffa98c`（onceright workspace）：新增 `phase=shadow`，只读提示无可选模块，`dfmodel` 4466.9ms、0 Credits；Qoder 日志 `source="user" success=true exit_code=0`；验证层级：local_runtime。
- onceright `git status`：只新增未跟踪的 `routing/`；用户既有的媒体/文档改动、`.docs-harness/inputs/` 与旧报告均未触碰；未修改 onceright 的 `AGENTS.md`、`scripts/` 或 `.docs-harness/config.json`；验证层级：contract_check。
- `python scripts/harness.py assets-check`（docs-harness）：status=passed，failures=[]，warnings=[]，退出码 0；验证层级：contract_check。

## 自查

- 复用：直接复用 docs-harness 的注册表快照与 zbuddy 的 opt-in README，没有新增路由代码、脚本或抽象。
- 门禁仍由现有 `route_hook.py` 依据 hook 输入的 `cwd` + 项目 `routing/registry.json` 完成；onceright 只是新增 opt-in 标记目录。
- 没有改动 onceright 的受管 docs-harness 文件；灰度阶段仍为 `shadow`，不注入 `additionalContext`，不改变执行。

## 未覆盖

- onceright 的 `routing/` 尚未提交；用户既有未提交改动与本次无关，未合并提交。
- 只验证了一次只读 Desktop 任务；1–2 周真实任务采样、代码任务模块选择、同会话缓存命中率和回滚演练未覆盖。
- 本次是 shadow 灰度，不是 canary/enforced 注入；如需 onceright 单独 canary，需要另加项目级 hook 并处理与用户级 shadow hook 的重复调用。
- onceright 的 `assets-check --fast` 未运行；其工作区有用户既有未提交改动，避免把既有状态混入本次验证。
