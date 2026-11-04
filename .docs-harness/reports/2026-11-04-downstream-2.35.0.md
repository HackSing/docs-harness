# 2026-11-04 下游升级到 2.35.0

## 升级结果

| 项目 | 升级前 | 新远端提交 | project check | 备注 |
|---|---|---|---|---|
| dispatch | 2.30.0 | `4b72ddd` | passed/in_head，red=0/yellow=0 | 本机干净 main 直接升级 |
| suiyi | 2.30.0 | `f1bdc51` | passed/in_head，red=0/yellow=0 | 本机干净 main 直接升级 |
| ai_study | 2.30.0 | `81db027` | passed/in_head，red=0/yellow=0 | 临时 worktree；原工作区未触碰 |
| opc-skills | 2.30.0 | `ff6a768` | passed/in_head，red=0/yellow=0 | 临时 worktree；原工作区未触碰 |
| onceright | 2.34.0 | `4ccf529` | passed/in_head，red=0/yellow=0 | 临时 worktree；原视频改动未触碰 |
| zbuddy-desktop | 2.34.0 | `a16eea56` | passed/in_head，red=0/yellow=0 | 临时 worktree；GitHub 与 codeup 两个 pushurl 均已推送 |
| zbuddy-mobile | 2.34.0 | `179ccb3` | passed/in_head，red=0/yellow=1 | 跳过 LFS smudge 的临时浅克隆；yellow 为既有 TODO 格式 |
| avatanel | 2.33.0 | `42f01ff` | passed/in_head，red=0/yellow=0 | 浅克隆，推送到 master |
| awesome-llm-made-videos | 2.33.0 | `b982cd4` | passed/in_head，red=0/yellow=0 | 浅克隆，推送到 main |

九项远端配置版本均读回 2.35.0（zbuddy-desktop 两个远端一致）。

## 验证

- `python scripts/harness.py project upgrade --target <下游> --apply --json`：九次均返回 `needs_delivery`（退出码 3），符合升级后待提交状态；验证层级：package_or_install。
- 提交后 `python scripts/harness.py project check --target <下游> --json`：九次均 `status=passed`、`delivery_status=in_head`；zbuddy-mobile 的 yellow=1 是既有 TODO 格式，其余 red=0/yellow=0；验证层级：package_or_install。
- 推送后 `git show origin/<branch>:.docs-harness/config.json`：九项均为 2.35.0；验证层级：package_or_install。
- `git ls-remote` 复核：zbuddy-desktop 的 GitHub 与 codeup 均为 `a16eea56`；zbuddy-mobile GitHub 为 `179ccb3`；验证层级：package_or_install。
- zbuddy-mobile 的 LFS：仓库有 1546 个 LFS 文件，主要在上游杰理视频 SDK 与 `test-assets/recordings/`；本次用 `GIT_LFS_SKIP_SMUDGE=1` 的浅克隆，只保留指针文件，未下载 LFS 大文件；验证层级：package_or_install。

## 未覆盖

- content-system 未升级：本机无克隆且无远端，只能等有本地副本的机器处理。
- zbuddy-recording-card-sdk 是 zbuddy-mobile 的独立 worktree（2.24.0，分支 `worktree-recording-card-sdk`），不在 `docs/downstream.md` 维护清单，未升级。
- 未重跑任何下游的业务测试、构建或运行态；只验证 harness 安装、提交、推送和 `project check`。
- ai_study、opc-skills、onceright、zbuddy-desktop 的本地 main 仍停在升级前提交，需各自 `pull --ff-only`；这些仓库原有未提交改动均未触碰。
- zbuddy-mobile 只推送了 GitHub，临时克隆里没有配置 codeup 远端，codeup 镜像未更新。
- 本机完整 zbuddy-mobile 克隆的 LFS 缓存为 318 MB，本次未清理。
