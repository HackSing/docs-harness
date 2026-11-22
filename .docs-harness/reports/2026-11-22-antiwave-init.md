# 收尾记录：下游新项目 antiwave 首次接入 Docs Harness 2.36.0

- 日期：2026-11-22
- 验证层级：`package_or_install`、`local_runtime`
- 前台/后台验证说明：全程后台命令行与文件工具执行，未弹出任何可见窗口、弹窗或抢夺焦点；因本机主克隆 `D:/Project/aiwavetop` 存在未提交改动且另有并发编辑，全程在基于 `origin/main`（`0c3afe1`）的临时 detached worktree（`C:/Users/freed/AppData/Local/Temp/antiwave-harness-wt`）内操作，未触碰主克隆工作区。

## 改动路径

- `https://github.com/HackSing/antiwave.git`（本机克隆 `D:/Project/aiwavetop`，提交于临时 worktree 并推送 `main` `0c3afe1..40d3358`）：
  - 通过 `project init --apply` 写入 59 项 Docs Harness 2.36.0 受管文件与目录骨架（包括原仓缺失的 `README.md` 骨架，共 54 个新增受管/骨架文件入库；`.docs-harness/{inputs,tasks,reports,views,runtime}/` 与 `usage/` 含 `.gitignore`）。
  - 额外改动（用户未明确要求）：修改 `.gitignore` 末尾追加 `__pycache__/` 与 `*.pyc`；新增 `README.md` 骨架并将其第 1 行标题从临时目录名改为 `# antiwave`；通过 `D:\Program Files\Git\bin\sh.exe` 在共享钩子目录安装 `D:/Project/aiwavetop/.git/hooks/pre-commit` 转发钩子（主克隆未 pull 前缺失 `scripts/githooks/pre-commit`，shim 会直接退出 0 不影响主克隆提交）。
- `D:/Project/docs-harness/docs/downstream.md`：在「维护中」表格新增 `antiwave`（`HackSing/antiwave`、`40d3358`）登记行。
- `D:/Project/docs-harness/.docs-harness/reports/2026-11-22-antiwave-init.md`：本次收尾记录（随本仓提交）。

## 发现与说明

- 在临时 worktree（`antiwave-harness-wt`）里执行 `project init` 时，由于原仓没有 `README.md`，`scripts/harness.py:800` 的 `project_doc_scaffolds` 按 `target.resolve().name` 生成了 `# antiwave-harness-wt` 标题；已手工改为 `# antiwave`（与 `package.json` `"name"` 一致），安装器代码本次未改。
- `project init` 不会为非 Python 项目自动补充 `__pycache__/` 与 `*.pyc` 忽略规则，已在 `antiwave` 的 `.gitignore` 中手工补齐（安装器代码本次未改）。
- 本机 `C:\Program Files\Git\bin\sh.exe` 不存在，改用同机实际路径 `D:\Program Files\Git\bin\sh.exe` 运行 `scripts/githooks/setup.sh`。

## 验证命令与退出码

- `git -C D:\Project\aiwavetop worktree add --detach C:\Users\freed\AppData\Local\Temp\antiwave-harness-wt origin/main` —— 退出码：0（HEAD 为 `0c3afe1`，`status --short` 为空；验证层级：`local_runtime`）。
- `python scripts/harness.py project init --target C:\Users\freed\AppData\Local\Temp\antiwave-harness-wt --apply --json` —— `.docs-harness/usage/2026-11.jsonl` 记录 `exit_code: 3`（`status="needs_delivery"`，`conflicts=[]`，`findings=[]`，写入 59 项；PowerShell 包装层通常将非零显示为 1，本次 `$LASTEXITCODE=3`；验证层级：`package_or_install`）。
- `Select-String` 检查 `$wt` 下 `README.md`、`AGENTS.md`、`CLAUDE.md`、`CHANGELOG.md`、`TODO.md`、`.docs-harness\config.json`、`docs\*.md`、`docs\*\*.md` 是否残留 `antiwave-harness-wt` —— 退出码：0（`hits_count=0`；验证层级：`local_runtime`）。
- `& 'D:\Program Files\Git\bin\sh.exe' scripts/githooks/setup.sh`（在 `$wt` 下执行）—— 退出码：0（安装 `D:/Project/aiwavetop/.git/hooks/pre-commit`；验证层级：`local_runtime`）。
- `python scripts/harness.py assets-check --target C:\Users\freed\AppData\Local\Temp\antiwave-harness-wt --json` —— 退出码：0（`status="passed"`，`failures=[]`，`warnings=[]`；验证层级：`package_or_install`）。
- `python scripts/harness.py self-test --target . --json`（在 `$wt` 下执行）—— 退出码：0（`status="passed"`，`version="2.36.0"`，11 项检查全为 `true`；验证层级：`package_or_install`）。
- `git -C $wt add -A` + `git -C $wt status --short` + `git -C $wt status --short --ignored scripts` + `git -C $wt ls-files -s scripts/githooks` —— 退出码：0（共 55 项：54 个 `A` 含 `README.md` + `M .gitignore`；`!! scripts/__pycache__/` 已忽略；githooks 两文件均为 `100755`；验证层级：`local_runtime`）。
- `git -C $wt commit ...` —— 退出码：0（触发 `pre-commit` 并通过，提交短哈希 `40d3358`；验证层级：`local_runtime`）。
- `python scripts/harness.py project check --target $wt --json` —— 退出码：0（`status="passed"`、`delivery_status="in_head"`、`clone_ready=true`、`red=0`、`yellow=0`；验证层级：`package_or_install`）。
- `git -C $wt push origin HEAD:main` —— 退出码：0（快进推送 `0c3afe1..40d3358  HEAD -> main`；验证层级：`local_runtime`）。
- `git -C D:\Project\aiwavetop worktree remove $wt` + `worktree list` + 主克隆 `status --porcelain` 复核 —— 退出码：0（临时 worktree 已删除；`worktree list` 仅剩主克隆 `D:/Project/aiwavetop 0c3afe1 [main]`；主克隆 `status --porcelain` 条目数从 33 变为 35，查时间戳确认系 21:48:42–21:49:22 并发编辑 `src/app/api/playground/route.ts`、`src/__tests__/playground-trial.test.ts` 等文件所致，与 `40d3358` 文件清单 0 重叠；验证层级：`local_runtime`）。
- `python scripts/harness.py report check --path .docs-harness/reports/2026-11-22-antiwave-init.md --json` —— 退出码：0（`status="passed"`，5 项均通过；验证层级：`local_runtime`）。
- `python scripts/harness.py assets-check --target . --json` —— 退出码：0（`status="passed"`，违规 0 条、警告 0 条；验证层级：`local_runtime`）。

## 未覆盖项

- 未在临时 worktree 中运行 `pnpm typecheck` 与 `pnpm test`（因 worktree 无 `node_modules`，且 `tsconfig.json` 的 `include` 仅覆盖 `**/*.ts` 与 `**/*.tsx`，新增 `.py`/`.cjs`/`.md` 不会进入 `tsc`）。
- 没有为 `antiwave` 填充 `docs/CODEMAP.md` 业务模块映射内容。
- `antiwave` 的 GitHub CI 未接入 harness 检查，pull 后仅依赖本机 `pre-commit` 钩子。
- 本机主克隆 `D:/Project/aiwavetop` 尚未执行 `git pull --ff-only`（因其工作区正有进行中的并发修改，未触碰）。


## 2026-11-22 追加：主克隆快进合并

- 改动路径：`D:/Project/aiwavetop`（主克隆本地 `main` 从 `0c3afe1` 快进至 `40d3358`，工作区 35 条并发改动原样保留未动）、`D:/Project/docs-harness/docs/downstream.md`、`D:/Project/docs-harness/.docs-harness/reports/2026-11-22-antiwave-init.md`。
- 验证命令与退出码（验证层级：`local_runtime`）：
  - `git -C D:\Project\aiwavetop fetch origin`、路径交集核对（`overlap_count=0`）、`git -C D:\Project\aiwavetop merge --ff-only origin/main` —— 退出码：0（`Updating 0c3afe1..40d3358`，`Fast-forward` 55 个文件）。
  - 合并后状态核查（`status -sb` 首行 `## main...origin/main`、`log --oneline -1` 为 `40d3358`、`status --porcelain` 计数仍为 `35`、`worktree list` 仅 1 行无残留 worktree）—— 退出码：0。
  - `python scripts/harness.py project check --target D:\Project\aiwavetop --json` —— 退出码：0（`status="passed"`、`delivery_status="in_head"`、`clone_ready=true`、`red=0`、`yellow=0`）。
  - `python scripts/harness.py report check --path .docs-harness/reports/2026-11-22-antiwave-init.md --json` —— 退出码：0（`status="passed"`）。
- 未覆盖项：用户 35 条未提交改动未提交。
