# 2026-10-25 下游升级到 2.34.0

## 升级结果

| 项目 | 升级前 origin/main | 新 origin/main | project check | 备注 |
|---|---|---|---|---|
| onceright | `819c413` | `78fd240`（harness `44437be` + routing） | passed，`in_head` | 干净 worktree 升级；原工作区视频改动未触碰；本机 main 落后 2，需 pull |
| zbuddy-mobile | `829bfbb` | `06dd5b0` | passed，`in_head`；yellow：TODO.md 17 条格式不符（既有） | 临时稀疏克隆升级；原 `feat/membership` 未触碰；仓库含 585 字符路径，Windows 完整 worktree 失败 |
| zbuddy-desktop | `e575ec11` | `09f75d0b` | passed，`in_head` | 干净 worktree 升级；本机 main 落后 1，需 pull |

三个远端 `.docs-harness/config.json` 均读回 `version=2.34.0`。升级提交均为：

`chore(harness): 升级 Docs Harness 2.33.0 → 2.34.0 — 运行态质量门与路由收尾`

## 验证

- `python scripts/harness.py project upgrade --target <worktree> --apply --json`：三次均返回 `needs_delivery`（退出码 3），符合升级后待提交状态；验证层级：package_or_install。
- 提交后在三个 worktree 分别运行 `python scripts/harness.py project check --target <worktree> --json`：onceright 与 zbuddy-desktop `status=passed`、`delivery_status=in_head`、red=0/yellow=0；zbuddy-mobile `status=passed`、`delivery_status=in_head`、red=0/yellow=1（TODO 格式既有问题）；退出码均 0。
- `git push origin HEAD:main`（onceright、zbuddy-desktop）与 `git push <github-url> HEAD:main`（zbuddy-mobile）均成功；`git ls-remote` 复核远端 main 与新提交一致；验证层级：package_or_install。
- 升级后 `git show origin/main:.docs-harness/config.json`：三项目均 `version=2.34.0`。
- onceright 路由注册表单独提交 `78fd240`（`routing/README.md`、`routing/registry.json`，注册表 1.0.0，指纹 `sha256:c3b984d65a55111bdee379dbb666a52dea3d234fdd94b856ec179825835b912a`）；`load_registry` 通过，提交后 `project check` 在 `origin/main` 干净 worktree 复核为 passed/in_head，red=0/yellow=0。
- 原工作区复核：onceright 仍保留原有未提交视频改动；zbuddy-mobile 仍在 `feat/membership`；zbuddy-desktop 仍为干净 main。未纳入本次升级提交。

## 未覆盖

- 未重跑三个项目的业务测试、构建或真实运行态；只验证 harness 安装、提交、远端与 `project check`。
- 未验证升级后用户级路由 hook 在三项目新会话中的触发；路由仍为 shadow，真实数据继续采样。
- 其余维护中下游（dispatch、suiyi、ai_study、awesome-llm-made-videos、avatanel、content-system）未升级。
- zbuddy-mobile 的 TODO 格式 yellow 是既有问题，本次未修。
- 本机 onceright 的 main 落后远端 2 个提交、zbuddy-desktop 落后 1 个提交，需用户自行 `pull --ff-only`；onceright 有未提交视频改动，pull 前需先处理；zbuddy-mobile 的 `feat/membership` 未合并 main。
- onceright 的视频/引擎改动（21 个已跟踪文件 + 未跟踪产物）按用户选择未提交，不在远端。
