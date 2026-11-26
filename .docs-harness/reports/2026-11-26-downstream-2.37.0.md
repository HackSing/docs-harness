# 2026-11-26 十二个下游项目升级到 2.37.0

- 前台/后台验证说明：全程在后台进程非交互执行（统一设置 `GIT_TERMINAL_PROMPT=0`、`GCM_INTERACTIVE=never`、`GIT_LFS_SKIP_SMUDGE=1`，升级传 `--host skip`），未弹出任何可见窗口、弹窗或抢夺焦点。

## 改动路径

- 源仓记录与索引：`docs/downstream.md`、`.docs-harness/reports/2026-11-26-downstream-2.37.0.md`。
- 12 个维护中下游仓库（各自仅暂存 `project upgrade` 返回的 `required_commit_paths`，并将 `scripts/githooks/{pre-commit,setup.sh}` 登记为 `100755`）：
  - 本机干净克隆原地升级（5 项）：`dispatch`、`suiyi`、`memware-cloud`、`antiwave`、`zbuddy-mobile`。
  - 本机脏/分叉克隆改用临时隔离区升级远端（4 项，未触碰本机工作区）：`zbuddy-desktop`（基于 `origin/main` `068f944d` 的临时 worktree，因 GitHub 浅克隆 180s 超时切换）、`ai_study`、`opc-skills`、`content-system`。
  - 无本机克隆临时浅克隆升级远端（3 项）：`onceright`、`awesome-llm-made-videos`、`avatanel`（`master`）。

## 升级结果

| 项目 | 升级前 | 新远端提交 | `project check` | `assets-check --fast` | 方式与备注 |
|---|---|---|---|---|---|
| `dispatch` | 2.35.0 | `9e212c4e` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（2 WARN：`other`×1、`plan.stale`×1） | 本机干净 `main` 原地升级 |
| `suiyi` | 2.35.0 | `781196f9` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 本机干净 `main` 原地升级 |
| `memware-cloud` | 2.36.0 | `422c3420` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 本机干净 `main` 原地升级 |
| `antiwave` | 2.36.0 | `96911efa` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 本机干净 `main` 原地升级 |
| `zbuddy-mobile` | 2.36.0 | `aacb7467` | `passed`/`in_head`（`red=0, yellow=1`） | `passed`（3 WARN：`structure.codemap`×3） | 本机干净 `main` 原地升级；仅推 GitHub `origin`，`yellow` 为既有 `TODO.md` 格式 |
| `zbuddy-desktop` | 2.36.0 | `cd8cdd36` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（7 WARN：`plan.stale`×2、`structure.codemap`×2、`entry.budget`×1、`other`×1、`plan.amend`×1） | 临时 worktree（已清理）；GitHub 与 `codeup` HTTPS 双远端哈希一致 |
| `ai_study` | 2.35.0 | `b311a680` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 临时浅克隆（已清理）；原工作区未触碰 |
| `opc-skills` | 2.35.0 | `6862851c` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（2 WARN：`other`×2） | `-c core.longpaths=true` 临时浅克隆（已清理）；原工作区未触碰 |
| `content-system` | 2.33.0 | `cdc92295` | `passed`/`in_head`（`red=0, yellow=1`） | `passed`（0 WARN） | 临时浅克隆（已清理）；`yellow` 为既有 `TODO.md` 95 条格式不符 |
| `onceright` | 2.35.0 | `8dffa4f9` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（1 WARN：`entry.budget`×1） | 临时浅克隆（已清理） |
| `awesome-llm-made-videos` | 2.35.0 | `c493c72b` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 临时浅克隆（已清理） |
| `avatanel` | 2.35.0 | `6123e8a7` | `passed`/`in_head`（`red=0, yellow=0`） | `passed`（0 WARN） | 临时浅克隆（已清理），推送 `master` |

## 验证命令与退出码

- `python -X utf8 d:\Project\docs-harness\scripts\harness.py project upgrade --target <dir> --apply --host skip --json`：12 次均返回 `status="needs_delivery"`（退出码 3）；验证层级：`package_or_install`。
- `python -X utf8 d:\Project\docs-harness\scripts\harness.py assets-check --target <dir> --fast --json`：12 次均返回 `status="passed"`、failures=0（退出码 0）；`zbuddy-desktop` 与 `onceright` 各自 `AGENTS.md` 含项目自写区块导致总字节超 24 KB 触发 `entry.budget` WARN（已记录）；验证层级：`package_or_install`。
- 提交后 `python -X utf8 d:\Project\docs-harness\scripts\harness.py project check --target <dir> --json`：12 次均 `status="passed"`、`delivery_status="in_head"`、`red=0`（退出码 0）；验证层级：`package_or_install`。
- 推送后读回 `origin/<branch>:.docs-harness/config.json` 与 `git ls-remote`：12 个项目远端配置版本均为 `2.37.0` 且远端分支哈希与新提交一致（`zbuddy-desktop` GitHub 与 `codeup` 均为 `cd8cdd36fb971541dcd2f5fd983f490e0cea65d5`）；验证层级：`package_or_install`。
- 源仓收尾自检：`python -X utf8 scripts/harness.py checklist check --target . --path .docs-harness/tasks/release-2.37.0-and-downstream.md --json`、`report check`、`assets-check --strict --json` 与 `git diff --check` 均退出码 0；验证层级：`focused_test`。

## 编码质量自查

1. **是否引入了重复逻辑及依据**：没有。12 个下游同步全部复用源仓 `scripts/harness.py` 的 `project upgrade`/`assets-check`/`project check` 既有 CLI 接口；未修改任何产品代码。
2. **新增抽象各自的职责**：无新增产品代码抽象（临时批量编排脚本置于会话 scratch 目录，未进入仓库）。

## 未覆盖项

- `zbuddy-desktop`、`ai_study`、`opc-skills`、`content-system` 四个本机有未提交改动或分叉的工作区未触碰，其本地分支仍停在升级前提交（`content-system` 本地 `[ahead 2, behind 2]`），需在各自处理完本地改动后拉取/合并远端新提交。
- `zbuddy-mobile` 的 `codeup` 远端（滞留在 `cdc6c011`）未同步推送，本次仅更新了 GitHub `origin/main`。
- `zbuddy-desktop` 与 `onceright` 的 `assets-check --fast` 均报出 1 条 `entry.budget` WARN（因各自 `AGENTS.md` 块外项目自定义内容叠加受管区块后超过 24,000 B 上限），本次未越权精简下游项目块外规则。
- 暂停维护的 `dsh-buddy`（2.21.0）、`dsh`（2.21.0）、`dsh-plugin`（2.12.3）及非清单 worktree `zbuddy-recording-card-sdk`（2.24.0）按约定未升级。
- 未运行任何下游项目的业务测试、构建或运行态检查；仅验证 harness 安装、`assets-check --fast`、`project check` 与远端读回。
