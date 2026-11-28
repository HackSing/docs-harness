# 2026-11-28 十二个下游项目升级到 2.39.1

- 前台/后台验证说明：全程在后台进程非交互执行（统一设置 `GIT_TERMINAL_PROMPT=0`、`GCM_INTERACTIVE=never`、`GIT_LFS_SKIP_SMUDGE=1`、`GIT_SSH_COMMAND="ssh -o BatchMode=yes"`，升级传 `--host skip`），未弹出任何可见窗口、弹窗或抢夺焦点，前台持续时长 0 秒。
- 发布版本：`v2.39.1`（`f78e46e`，合并远端文档提交 `0b0dfcb` 后 `main` 为 `a3c97b7`；含 `9840301` Antigravity 受管全局规则自动安装 `scripts/host_rules.py` 与 Windows 隔离桌面合同）。

## 改动路径

- 源仓记录与索引：`docs/downstream.md`、`.docs-harness/reports/2026-11-28-downstream-2.39.1.md`。
- 12 个维护中下游仓库（各自仅暂存 `project upgrade` 返回的 `required_commit_paths`，并将 `scripts/githooks/{pre-commit,setup.sh}` 登记为 `100755`）：
  - 本机干净克隆原地升级（3 项）：`dispatch`、`suiyi`、`memware-cloud`。
  - 本机有未提交改动/分叉工作区改用临时隔离区升级远端（6 项，本机工作区未触碰）：`antiwave`、`zbuddy-desktop`、`ai_study`、`content-system`、`opc-skills`（临时 worktree）；`zbuddy-mobile`（排除 `docs/external/` 的临时稀疏浅克隆）。
  - 无本机克隆走临时浅克隆升级远端（3 项）：`onceright`、`awesome-llm-made-videos`、`avatanel`（`master`）。

## 升级结果

| 项目 | 升级前 | 新远端提交 | `project check` | `assets-check --fast` | 方式与备注 |
|---|---|---|---|---|---|
| `dispatch` | 2.39.0 | `79f67258` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（2 WARN：`other`×1、`plan.stale`×1） | 本机干净 `main` 原地升级 |
| `suiyi` | 2.39.0 | `6208e04d` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（1 WARN：`structure.codemap`×1） | 本机干净 `main` 原地升级 |
| `memware-cloud` | 2.39.0 | `e59246bb` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 本机干净 `main` 原地升级 |
| `antiwave` | 2.39.0 | `45a8b88b` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 临时 worktree（已清理）；原工作区未触碰 |
| `zbuddy-desktop` | 2.39.0 | `6a35378c` | `passed`/`in_head`（`red=0`） | `passed`（`failures=0`） | 临时 worktree（已清理）；`codeup` SSH 缺 `known_hosts` 后改走 `codeup` HTTPS 补推，GitHub 与 `codeup` 哈希一致 |
| `ai_study` | 2.39.0 | `4b11ba09` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 临时 worktree（已清理）；原工作区未触碰 |
| `content-system` | 2.39.0 | `259c84e1` | `passed`/`in_head`（`red=0, yellow=1`） | `passed`（0 WARN） | 临时 worktree（已清理）；`yellow` 为既有 `TODO.md` 95 条格式不符 |
| `opc-skills` | 2.39.0 | `de740dcd` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（2 WARN：`other`×2） | `-c core.longpaths=true` 临时 worktree（已清理）；原工作区未触碰 |
| `zbuddy-mobile` | 2.39.0 | `68d8a0a0` | `passed`/`in_head`（`red=0, yellow=1`） | `passed`（4 WARN：`structure.codemap`×3、`plan.stale`×1） | 临时稀疏浅克隆（排除 `docs/external/`，已清理）；仅推 GitHub `origin`，`yellow` 为既有 `TODO.md` 17 条格式不符 |
| `onceright` | 2.39.0 | `47cb1107` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（1 WARN：`entry.budget`×1） | 临时浅克隆（已清理） |
| `awesome-llm-made-videos` | 2.39.0 | `83efb69e` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 临时浅克隆（已清理） |
| `avatanel` | 2.39.0 | `7fa9b507` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（2 WARN：`other`×1、`plan.stale`×1） | 临时浅克隆（已清理），推送 `master` |

## 验证命令与退出码

- `python -X utf8 d:\Project\docs-harness\scripts\harness.py project upgrade --target <dir> --apply --host skip --json`：12 次均返回 `status="needs_delivery"`（退出码 3）；验证层级：`package_or_install`。
- `python -X utf8 d:\Project\docs-harness\scripts\harness.py assets-check --target <dir> --fast --json`：12 次均返回 `status="passed"`、failures=0（退出码 0）；验证层级：`package_or_install`。
- 提交后 `python -X utf8 d:\Project\docs-harness\scripts\harness.py project check --target <dir> --json`：12 次均 `status="passed"`、`delivery_status="in_head"`、`red=0`（退出码 0）；验证层级：`package_or_install`。
- 推送后读回 `origin/<branch>:.docs-harness/config.json` 与 `git ls-remote`：12 个项目远端配置版本均为 `2.39.1` 且远端分支哈希与新提交一致（`zbuddy-desktop` GitHub 与 `codeup` 均为 `6a35378c2b1c30dc2864700c5f6d76899e1dfc20`）；验证层级：`package_or_install`。
- 源仓收尾自检：`report check`、`assets-check --strict --json` 与 `git diff --check` 均退出码 0；验证层级：`focused_test`。

## 编码质量自查

1. **是否引入了重复逻辑及依据**：没有。12 个下游同步全部复用源仓 `scripts/harness.py` 的 `project upgrade`/`assets-check`/`project check` 既有 CLI 接口；未修改任何下游业务代码。
2. **新增抽象各自的职责**：无新增产品代码抽象（一次性批量编排脚本置于会话 scratch 目录，未入库）。

## 未覆盖项

- `antiwave`、`zbuddy-desktop`、`ai_study`、`content-system`、`opc-skills`、`zbuddy-mobile` 六个本机有未提交改动或独立分支的工作区未触碰，需在各自处理完本地改动后拉取远端 `2.39.1` 提交。
- `zbuddy-mobile` 的 `codeup` 远端未同步推送，本次仅更新了 GitHub `origin/main`；`zbuddy-desktop` 因本机 `~/.ssh/known_hosts` 无 `codeup.aliyun.com` 主机指纹改用已有凭证的 `codeup` HTTPS 推送完成。
- 暂停维护的 `dsh-buddy`（2.21.0）、`dsh`（2.21.0）、`dsh-plugin`（2.12.3）按约定未升级。
- 本次批量同步传 `--host skip`，故本机 `~/.gemini/config/rules/` 尚未切换为受管 `docs-harness-*.md`（也未删除旧手工副本 `builtin-subagents-only.md` / `windows-real-desktop-gui-launch.md`）。
- 未运行任何下游项目的业务测试与构建；仅验证 Docs Harness 安装、`assets-check --fast`、`project check` 与远端版本读回。
