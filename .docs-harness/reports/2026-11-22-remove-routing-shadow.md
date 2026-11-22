# 收尾记录：清理 Gemini 路由钩子配置与历史 shadow 数据

- 日期：2026-11-22
- 验证层级：`local_runtime`
- 前台/后台验证说明：全程后台命令行与文件读写工具执行，未弹出任何可见窗口、弹窗或抢夺焦点。

## 改动路径

- `C:/Users/freed/.gemini/config/hooks.json`：文件内仅存在 `"docs-harness-router"` 一个键（已设 `"enabled": false` 且指向不存在的 `routing/hosts/antigravity/route_hook.py`），将其覆盖为 `{}\n`，保留空 JSON 配置文件本身。
- `D:/Project/docs-harness/.docs-harness/routing`：删除整个历史 shadow 运行数据目录（9 个文件，18,958 字节，已被目录内 `.gitignore` 忽略）。
- `D:/Project/zbuddy-desktop/.docs-harness/routing`：删除整个历史 shadow 运行数据目录（15 个文件，116,187 字节）。
- `D:/Project/zbuddy-mobile/.docs-harness/routing`：删除整个历史 shadow 运行数据目录（8 个文件，10,986 字节）。
- 保留未动：三个项目 `.docs-harness/` 下的其余子目录（`reports`、`usage`、`runtime` 等），以及 `D:/Project/docs-harness` 仓库源码中的 `routing/`（含 `routing/registry.json` 与 `routing/hosts/qoder/`）和 `scripts/routing_*.py`。

## 验证命令与退出码

- `Get-Content 'C:\Users\freed\.gemini\config\hooks.json'; python -c "import json;print(json.load(open(r'C:\Users\freed\.gemini\config\hooks.json')))"` —— 退出码：0（两行均输出 `{}`；验证层级：`local_runtime`）。
- `Remove-Item -LiteralPath 'D:\Project\docs-harness\.docs-harness\routing' -Recurse -Force` —— 退出码：0（验证层级：`local_runtime`）。
- `Remove-Item -LiteralPath 'D:\Project\zbuddy-desktop\.docs-harness\routing' -Recurse -Force` —— 退出码：0（验证层级：`local_runtime`）。
- `Remove-Item -LiteralPath 'D:\Project\zbuddy-mobile\.docs-harness\routing' -Recurse -Force` —— 退出码：0（验证层级：`local_runtime`）。
- `Test-Path` 复核与仓库状态检查（`Test-Path` 三个 `.docs-harness\routing` 路径、检查 `D:\Project\docs-harness\routing\registry.json` 与 `git -C D:\Project\docs-harness status --short`）—— 退出码：0（三个 `.docs-harness\routing` 均返回 `False`；`routing/registry.json` 返回 `True`；`git status --short` 无新增变更或已跟踪文件删除；验证层级：`local_runtime`）。
- `python scripts/harness.py assets-check --target . --json` —— 退出码：0（`status="passed"`，违规 0 条、警告 0 条；验证层级：`local_runtime`）。
- `python scripts/harness.py report check --path .docs-harness/reports/2026-11-22-remove-routing-shadow.md --json` —— 退出码：0（`status="passed"`，5 项均通过；验证层级：`local_runtime`）。

## 未覆盖项

- 没有重启 Antigravity 来确认 `C:\Users\freed\.gemini\config\hooks.json` 已重新加载。
- 未检查 `D:\Project\zbuddy-desktop` 与 `D:\Project\zbuddy-mobile` 的 `git status`（删除前已在 `docs-harness` 检查 `.docs-harness/routing/*` 为 gitignore 忽略文件，且删除前后均仅操作 `.docs-harness/routing`）。
