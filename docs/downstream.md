# 下游项目

docs-harness 发版后需要同步升级的下游项目。本文只记项目名和远端仓库，不记本地路径：各机器、各系统的克隆位置不同，升级时按本机实际位置操作。

## 维护中

| 项目 | 远端仓库 | 备注 |
|---|---|---|
| dispatch | `HackSing/dispatch` | |
| opc-skills | `HackSing/opc-skills` | Windows 上克隆会因超长文件名失败；需要模拟下游时改用 dispatch |
| suiyi | `HackSing/suiyi` | |
| zbuddy-mobile | `HackSing/zbuddy-mobile` | 2026-10-25 以干净 worktree 升级到 2.34.0（main `06dd5b0`）；本机克隆仍在 `feat/membership`，未改动。仓库内存在 585 字符路径，Windows 完整 worktree 会失败；升级时用临时稀疏克隆排除 `docs/external/`。 |
| zbuddy-desktop | `HackSing/zbuddy-desktop` | 2026-10-25 升级到 2.34.0（main `09f75d0b`）；本机 main 落后 1 个提交，需 pull。`origin` 配了 GitHub 与 codeup 两个 pushurl，推送 `origin` 会同时推两边；推送前先 `git config --get-all remote.origin.pushurl` 确认。codeup 一律走 SSH（`git@codeup.aliyun.com:6819b146f9ff7623b1eca75a/zbuddy-desktop.git`）：HTTPS 在没有终端的会话里取不到凭据，推送会失败。pushurl 还是 HTTPS 的机器，先删 HTTPS 那条：`git remote set-url --push --delete origin 'codeup\.aliyun\.com'`，再加 SSH：`git remote set-url --push --add origin git@codeup.aliyun.com:6819b146f9ff7623b1eca75a/zbuddy-desktop.git`，最后用 `git push --dry-run origin main` 确认输出两行结果。脚本里推送可加 `GIT_SSH_COMMAND="ssh -o BatchMode=yes"`，缺钥匙时直接报错，不会卡在密码提示上 |
| ai_study | `HackSing/ai_study` | 2026-09-24 以 2.21.1 接入 main。功能分支 `feat/theorem-formula-rules` 也新增过 `CLAUDE.md`，合并 main 时会出现双方新增冲突：保留分支版本，再跑一次 `project upgrade --apply` 补回受管区块 |
| onceright | `HackSing/onceright` | 2026-09-27 以 2.24.0 接入 main；2026-10-03 升级到 2.25.0，删掉 `CLAUDE.md` 块外自己写的 `@AGENTS.md`，改由受管区块导入，受管正文只加载一遍；2026-10-23 升级到 2.33.0 并加入路由 shadow 灰度（`routing/registry.json`，Windows 用户级 hook）；2026-10-25 以干净 worktree 升级到 2.34.0，`routing/` 注册表提交 `78fd240`（harness 升级为 `44437be`），本机未提交的视频改动未触碰，main 落后 2 个提交，需 pull |
| awesome-llm-made-videos | `HackSing/awesome-llm-made-videos` | 2026-09-27 以 2.24.0 接入 main。公开仓库 |
| avatanel | `HackSing/avatanel` | 默认分支是 `master`，推送用 `git -C <下游目录> push origin master`。`.docs-harness/inputs/` 里有早期提交入库的一次性输入文件，2.16.1 起该目录带嵌套 `.gitignore`，会出现旧文件受跟踪、新文件被忽略的混合状态，处置待定 |
| content-system | `HackSing/content-system` | 2026-10-06 以 2.28.0 接入 main（原仅本地 git，现已配置 GitHub 远端）。接入时删掉了 `CLAUDE.md` 里自己写的 `@AGENTS.md`，改由受管区块导入（同 onceright），`@TODO.md` 保留。2026-11-26 本机工作区有大量未提交改动且与远端分叉，升级通过临时浅克隆仅同步远端 `origin/main` |
| memware-cloud | `HackSing/memware-cloud` | 2026-11-22 以 2.36.0 接入 main（`d79efbb`）。Next.js + Cloudflare 项目，CI 不跑 harness 检查，只靠本机 pre-commit。接入时补了 .gitignore 的 __pycache__/ 与 *.pyc |
| antiwave | `HackSing/antiwave` | 2026-11-22 以 2.36.0 接入 main（`40d3358`），在临时 worktree 中完成。本机克隆目录名曾为 `aiwavetop`（当前本机已有 `d:\Project\antiwave`），接入时补了 .gitignore 的 __pycache__/ 与 *.pyc |

### 2026-11-28 批量升级（2.39.1）

| 项目 | 升级前 | 新提交 | 结果 |
|---|---|---|---|
| dispatch | 2.39.0 | `79f67258` | 本机干净 `main` 原地升级，pushed，`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN：`other`×1、`plan.stale`×1） |
| suiyi | 2.39.0 | `6208e04d` | 本机干净 `main` 原地升级，pushed，`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 1 WARN：`structure.codemap`×1） |
| memware-cloud | 2.39.0 | `e59246bb` | 本机干净 `main` 原地升级，pushed，`project check` passed/in_head（`red=0, yellow=0`） |
| antiwave | 2.39.0 | `45a8b88b` | 临时 worktree，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| zbuddy-desktop | 2.39.0 | `6a35378c` | 临时 worktree，GitHub 与 `codeup`（HTTPS 补推）均已推送且哈希一致，`project check` passed/in_head（`red=0`） |
| ai_study | 2.39.0 | `4b11ba09` | 临时 worktree，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| content-system | 2.39.0 | `259c84e1` | 临时 worktree，pushed（`main`），`project check` passed/in_head（`red=0, yellow=1` 既有 TODO 格式） |
| opc-skills | 2.39.0 | `de740dcd` | 临时 worktree（`core.longpaths=true`），pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN：`other`×2） |
| zbuddy-mobile | 2.39.0 | `68d8a0a0` | 临时稀疏浅克隆（排除 `docs/external/`），pushed（仅 GitHub `main`），`project check` passed/in_head（`red=0, yellow=1` 既有 TODO 格式；`assets-check --fast` 4 WARN：`structure.codemap`×3、`plan.stale`×1） |
| onceright | 2.39.0 | `47cb1107` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 1 WARN：`entry.budget`×1） |
| awesome-llm-made-videos | 2.39.0 | `83efb69e` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| avatanel | 2.39.0 | `7fa9b507` | 临时浅克隆，push `master`，`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN：`other`×1、`plan.stale`×1） |

十二个维护中项目的远端配置版本均读回 2.39.1（`zbuddy-desktop` GitHub 与 `codeup` 哈希均为 `6a35378c`）。有未提交改动或非 `main` 分支的本机工作区（`antiwave`、`zbuddy-desktop`、`ai_study`、`content-system`、`opc-skills`、`zbuddy-mobile`）均未触碰。

### 2026-11-28 批量升级（2.39.0）

| 项目 | 升级前 | 新提交 | 结果 |
|---|---|---|---|
| dispatch | 2.38.1 | `8116570d` | 本机干净 `main` 原地升级，pushed，`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN：`other`×1、`plan.stale`×1） |
| suiyi | 2.38.1 | `f27ad111` | 本机干净 `main` 原地升级，pushed，`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 1 WARN：`structure.codemap`×1） |
| memware-cloud | 2.38.1 | `02ae6489` | 本机干净 `main` 原地升级，pushed，`project check` passed/in_head（`red=0, yellow=0`） |
| antiwave | 2.38.1 | `5177d795` | 临时 worktree，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| zbuddy-desktop | 2.38.1 | `37d52954` | 临时 worktree，GitHub 与 `codeup` 均已推送（哈希一致），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 7 WARN，含 `entry.budget`×1） |
| ai_study | 2.38.1 | `d03e89d1` | 临时 worktree，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| content-system | 2.38.1 | `9db5b5e9` | 临时 worktree，pushed（`main`），`project check` passed/in_head（`red=0, yellow=1` 既有 TODO 格式） |
| opc-skills | 2.38.1 | `852716fd` | 临时 worktree（`core.longpaths=true`），pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN） |
| zbuddy-mobile | 2.38.1 | `1da91613` | 临时稀疏浅克隆（排除 `docs/external/`），pushed（仅 GitHub `main`），`project check` passed/in_head（`red=0, yellow=1` 既有 TODO 格式；`assets-check --fast` 4 WARN：`structure.codemap`×3、`plan.stale`×1） |
| onceright | 2.38.1 | `e35dbc20` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 1 WARN：`entry.budget`×1） |
| awesome-llm-made-videos | 2.38.1 | `e3af7966` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| avatanel | 2.38.1 | `39668574` | 临时浅克隆，push `master`，`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN：`other`×1、`plan.stale`×1） |

十二个维护中项目的远端配置版本均读回 2.39.0（`zbuddy-desktop` GitHub 与 `codeup` 哈希均为 `37d52954`）。有未提交改动的本机工作区（`antiwave`、`zbuddy-desktop`、`ai_study`、`content-system`、`opc-skills`、`zbuddy-mobile`）均未触碰。

### 2026-11-27 批量升级（2.38.1）

| 项目 | 升级前 | 新提交 | 结果 |
|---|---|---|---|
| dispatch | 2.37.0 → 2.38.0 → 2.38.1 | `382e8ca0` | 本机干净 `main` 原地升级，pushed，`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN：`other`×1、`plan.stale`×1） |
| suiyi | 2.37.0 → 2.38.0 → 2.38.1 | `9120826d` | 本机干净 `main` 原地升级，pushed，`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 1 WARN：`structure.codemap`×1） |
| memware-cloud | 2.37.0 → 2.38.0 → 2.38.1 | `91d68ef1` | 本机干净 `main` 原地升级，pushed，`project check` passed/in_head（`red=0, yellow=0`） |
| antiwave | 2.37.0 → 2.38.0 → 2.38.1 | `c10c50bd` | 临时 worktree，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| zbuddy-desktop | 2.37.0 | `a21276a6` | 临时 worktree，GitHub 与 `codeup` 均已推送（哈希一致），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 7 WARN，含 `entry.budget`×1） |
| ai_study | 2.37.0 → 2.38.0 → 2.38.1 | `055a993f` | 临时 worktree，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| content-system | 2.37.0 → 2.38.0 → 2.38.1 | `f3900c6d` | 临时 worktree，pushed（`main`），`project check` passed/in_head（`red=0, yellow=1` 既有 TODO 格式） |
| opc-skills | 2.37.0 | `a0c425a1` | 临时 worktree（`core.longpaths=true`），pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN） |
| zbuddy-mobile | 2.37.0 | `001554cc` | 临时稀疏浅克隆（排除 `docs/external/`），pushed（仅 GitHub `main`），`project check` passed/in_head（`red=0, yellow=1` 既有 TODO 格式；`assets-check --fast` 3 WARN） |
| onceright | 2.37.0 | `477d428d` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 1 WARN：`entry.budget`×1） |
| awesome-llm-made-videos | 2.37.0 | `e3f847ad` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| avatanel | 2.37.0 | `83d35607` | 临时浅克隆，push `master`，`project check` passed/in_head（`red=0, yellow=0`） |

十二个维护中项目的远端配置版本均读回 2.38.1（`zbuddy-desktop` GitHub 与 `codeup` 哈希均为 `a21276a6`；首次升级 `2.38.0` 在 `zbuddy-desktop` 77 个历史运行态包上发现逐文件 `git check-ignore` 超时后当场发布 `2.38.1` 修复并全量重升）。有未提交改动的本机工作区（`antiwave`、`zbuddy-desktop`、`ai_study`、`content-system`、`opc-skills`、`zbuddy-mobile`）均未触碰。

### 2026-11-26 批量升级（2.37.0）

| 项目 | 升级前 | 新提交 | 结果 |
|---|---|---|---|
| dispatch | 2.35.0 | `9e212c4e` | pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN） |
| suiyi | 2.35.0 | `781196f9` | pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| memware-cloud | 2.36.0 | `422c3420` | pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| antiwave | 2.36.0 | `96911efa` | pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| zbuddy-mobile | 2.36.0 | `aacb7467` | pushed（仅 GitHub `main`），`project check` passed/in_head（`red=0, yellow=1` 既有 TODO 格式；`assets-check --fast` 3 WARN） |
| zbuddy-desktop | 2.36.0 | `cd8cdd36` | 临时 worktree，GitHub 与 `codeup` 均已推送，`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 7 WARN，含 `entry.budget`×1） |
| ai_study | 2.35.0 | `b311a680` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| opc-skills | 2.35.0 | `6862851c` | 临时浅克隆（`core.longpaths=true`），pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 2 WARN） |
| content-system | 2.33.0 | `cdc92295` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=1` 既有 TODO 格式） |
| onceright | 2.35.0 | `8dffa4f9` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`；`assets-check --fast` 1 WARN：`entry.budget`×1） |
| awesome-llm-made-videos | 2.35.0 | `c493c72b` | 临时浅克隆，pushed（`main`），`project check` passed/in_head（`red=0, yellow=0`） |
| avatanel | 2.35.0 | `6123e8a7` | 临时浅克隆，push `master`，`project check` passed/in_head（`red=0, yellow=0`） |

十二个维护中项目的远端配置版本均读回 2.37.0（`zbuddy-desktop` GitHub 与 `codeup` 提交哈希一致）。有未提交改动的本机工作区（`zbuddy-desktop`、`ai_study`、`opc-skills`、`content-system`）均未触碰。

### 2026-11-04 批量升级（2.35.0）

| 项目 | 升级前 | 新提交 | 结果 |
|---|---|---|---|
| dispatch | 2.30.0 | `4b72ddd` | pushed，`project check` passed/in_head |
| suiyi | 2.30.0 | `f1bdc51` | pushed，passed/in_head |
| ai_study | 2.30.0 | `81db027` | 临时 worktree，pushed，passed/in_head |
| opc-skills | 2.30.0 | `ff6a768` | 临时 worktree，pushed，passed/in_head |
| onceright | 2.34.0 | `4ccf529` | 临时 worktree，pushed，passed/in_head |
| zbuddy-desktop | 2.34.0 | `a16eea56` | 临时 worktree，GitHub 与 codeup 均已推送，passed/in_head |
| zbuddy-mobile | 2.34.0 | `179ccb3` | 跳过 LFS smudge 的临时浅克隆，GitHub 已推送，passed/in_head，yellow=1（既有 TODO 格式） |
| avatanel | 2.33.0 | `42f01ff` | 浅克隆，push master，passed/in_head |
| awesome-llm-made-videos | 2.33.0 | `b982cd4` | 浅克隆，pushed，passed/in_head |
| content-system | 2.28.0 | — | 未升级：本机无克隆且无远端 |

九个项目的远端配置版本均读回 2.35.0。有未提交改动的本地工作区未触碰；ai_study、opc-skills、onceright、zbuddy-desktop 使用基于 `origin/main` 的临时 worktree，zbuddy-mobile 使用跳过 LFS smudge 的临时浅克隆。

## 暂停维护

以下项目自 2026-09-24 起暂停维护，发版时不升级、不检查。项目本身和其中已安装的 harness 保留，未卸载。恢复维护时移回上表。

| 项目 | 停留版本 | 说明 |
|---|---|---|
| dsh-buddy | 2.21.0 | 远端 `HackSing/dsh-buddy` |
| dsh | 2.21.0 | 非 git 仓，原地安装 |
| dsh-plugin | 2.12.3 | 本仓 `dsh-plugin/` 子目录，随 DSH Buddy 预装；`vendor/` 的引擎同步（`npm run seed-vendor` + `extract-block`）一并搁置 |

## 升级步骤

**2.30.0 起**：从低于 2.30.0 的版本升级时，`project upgrade` 预览与 `--apply` 会在输出末尾打印分隔线 **「重要提示（请读）」**，内容为 Harness Plan 与 IDE Plan 的区分及 Full 方案新字段；`AGENTS.md` 受管区块同步写入相同语义。

源仓发版并推送后，对上表每个维护中的项目执行（`<下游目录>` 换成本机克隆位置）：

1. 确认工作区干净并与远端同步：`git -C <下游目录> status -sb`；落后时先 `git -C <下游目录> pull --ff-only`。有未提交改动且与远端提交重叠时，改在基于 `origin/main` 的临时 worktree 里升级。
2. 在源仓根目录运行升级：`python3 scripts/harness.py project upgrade --target <下游目录> --apply`。受管文件已写入、等待提交时退出码为 3（`needs_delivery`），属正常状态，脚本里不要用 `set -e` 把它当失败。
3. 提交受管文件，提交信息格式：`chore(harness): 升级 Docs Harness <旧版本> → <新版本> — <一句话摘要>`。受管 pre-commit 会执行 `assets-check --fast`。
4. 复核：`python3 scripts/harness.py project check --target <下游目录>`，期望 `status: passed`、`delivery_status: in_head`。
5. 推送：`git -C <下游目录> push origin main`（默认分支不是 `main` 的项目见上表备注）。

新项目首次接入改用 `project init --target <下游目录> --apply`，不带 `--apply` 时只预览（2.21.1 及更早的 `init` 没有预览模式，不带 `--apply` 也会直接写入）。目标工作区有未提交改动时，先基于 `origin/main` 建干净的 worktree 再接入。2.23.0 起，在 Windows（`core.filemode=false`）上接入时安装器会自动把钩子以 `100755` 登记进暂存区；用更早版本接入、钩子已按 `100644` 提交的仓库，`project check` 会报 `githook_index_mode` 并给出修复命令，或直接 `upgrade --apply` 一次即可修正。

每次升级都会在下游 `AGENTS.md`/`CLAUDE.md` 上产生一次受管区块 diff；`.docs-harness/tasks/.gitignore` 等本地约定目录不入库，不需要提交。
