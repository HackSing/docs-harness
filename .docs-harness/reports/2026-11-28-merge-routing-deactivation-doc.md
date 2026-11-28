# 2026-11-28 合并路由 B2 Shadow 试点停用记录到 main

- 日期：2026-11-28
- 验证层级：`focused_test`
- 前台/后台验证说明：纯文档同步与仓库资产检查，全程通过命令行后台执行，未弹出可见窗口、弹窗或抢夺焦点，前台持续时长 0 秒。

## 改动路径

- `docs/routing.md`：将本地旧分支 `feat/strong-model-routing` 提交 `b7db803` 中的 2026-11-02（macOS）停用记录合并到最新 `main`（2.39.0），保留既有 `onceright` 试点、zbuddy-desktop 30 条标注与 2026-10-25 召回实验记录，同步引用 `.docs-harness/reports/2026-11-22-remove-routing-shadow.md` 的 Windows 清理记录，并补齐试点期与停用后的时间线前提（第 6、10、11、12 节及顶部状态）。
- `.docs-harness/reports/2026-11-28-merge-routing-deactivation-doc.md`：本次任务收尾记录。

## 验证命令与退出码

- `git merge --ff-only origin/main` —— 退出码：0（本地 `main` 从 `35ba7de` 快进更新到 `68c0ea7` / 2.39.0；验证层级：`focused_test`）。
- `grep -rn "routing.md" tests/ scripts/` —— 退出码：1（无任何测试或脚本硬编码引用 `docs/routing.md`；验证层级：`focused_test`）。
- `python3 scripts/harness.py assets-check --strict --json` —— 退出码：0（`status="passed"`，Plan/Knowledge/Acceptance/ADR/ScriptHygiene/Structure 全部通过，违规 0 条、警告 0 条；验证层级：`focused_test`）。
- 零基础读者通读检查：从头审阅 `docs/routing.md` 变更前后段落，确认顶部状态、B0 审计结论、第 10 节用户级安装说明、第 11 节试点接入与停用清理、第 12 节未覆盖与待定之间无状态矛盾，且已明确区分 macOS 已证实停用与 Windows 侧未核实范围。

## 编码质量自查

1. **是否引入了重复逻辑及依据**：没有。本次仅更新 `docs/routing.md` 文档与新增本收尾记录，未新增或修改代码逻辑。
2. **新增抽象各自的职责**：无新增代码抽象。

## 未覆盖项

- 未在 Windows 机器上核实 `onceright` 的 `routing/` 快照现状及 Windows 侧 Qoder 用户级 hook 是否已移除，已在 `docs/routing.md` 中显式标明未核实。
- 未验证 macOS 本机 `~/.qoder-cn/settings.json` 与 zbuddy 下游仓库当前远端状态，沿用 `b7db803` 中记录的 2026-11-02 历史事实（`zbuddy-mobile 9eb31e6`、`zbuddy-desktop 0fa81ec5`）。
- 尚未将本次 `main` 新提交推送到 `origin/main`，也未删除已合并的旧本地分支 `feat/strong-model-routing`（待用户确认）。
