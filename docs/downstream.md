# 下游项目

docs-harness 发版后需要同步升级的下游项目。本文只记项目名和远端仓库，不记本地路径：各机器、各系统的克隆位置不同，升级时按本机实际位置操作。

## 维护中

| 项目 | 远端仓库 | 备注 |
|---|---|---|
| dispatch | `HackSing/dispatch` | |
| opc-skills | `HackSing/opc-skills` | Windows 上克隆会因超长文件名失败；需要模拟下游时改用 dispatch |
| suiyi | `HackSing/suiyi` | |
| zbuddy-mobile | `HackSing/zbuddy-mobile` | |
| zbuddy-desktop | `HackSing/zbuddy-desktop` | `origin` 配了 GitHub 与 codeup 两个 pushurl，推送 `origin` 会同时推两边；推送前先 `git config --get-all remote.origin.pushurl` 确认 |

## 暂停维护

以下项目自 2026-09-24 起暂停维护，发版时不升级、不检查。项目本身和其中已安装的 harness 保留，未卸载。恢复维护时移回上表。

| 项目 | 停留版本 | 说明 |
|---|---|---|
| dsh-buddy | 2.21.0 | 远端 `HackSing/dsh-buddy` |
| dsh | 2.21.0 | 非 git 仓，原地安装 |
| dsh-plugin | 2.12.3 | 本仓 `dsh-plugin/` 子目录，随 DSH Buddy 预装；`vendor/` 的引擎同步（`npm run seed-vendor` + `extract-block`）一并搁置 |

## 升级步骤

源仓发版并推送后，对上表每个维护中的项目执行（`<下游目录>` 换成本机克隆位置）：

1. 确认工作区干净并与远端同步：`git -C <下游目录> status -sb`；落后时先 `git -C <下游目录> pull --ff-only`。有未提交改动且与远端提交重叠时，改在基于 `origin/main` 的临时 worktree 里升级。
2. 在源仓根目录运行升级：`python3 scripts/harness.py project upgrade --target <下游目录> --apply`。受管文件已写入、等待提交时退出码为 3（`needs_delivery`），属正常状态，脚本里不要用 `set -e` 把它当失败。
3. 提交受管文件，提交信息格式：`chore(harness): 升级 Docs Harness <旧版本> → <新版本> — <一句话摘要>`。受管 pre-commit 会执行 `assets-check --fast`。
4. 复核：`python3 scripts/harness.py project check --target <下游目录>`，期望 `status: passed`、`delivery_status: in_head`。
5. 推送：`git -C <下游目录> push origin main`。

每次升级都会在下游 `AGENTS.md`/`CLAUDE.md` 上产生一次受管区块 diff；`.docs-harness/tasks/.gitignore` 等本地约定目录不入库，不需要提交。
