# 收尾记录：下游新项目 memware-cloud 首次接入 Docs Harness 2.36.0

- 日期：2026-11-22
- 验证层级：`package_or_install`、`local_runtime`
- 前台/后台验证说明：全程后台命令行与文件工具执行（`pnpm typecheck` 输出重定向至 `$env:TEMP\memware-typecheck.log`），未弹出任何可见窗口、弹窗或抢夺焦点。

## 改动路径

- `D:/Project/memware-cloud` 提交 `d79efbb`（`main`，已推送 `origin/main` `b422cbe..d79efbb`）：
  - 通过 `project init --apply` 写入 58 项 Docs Harness 2.36.0 受管文件与目录骨架（`.docs-harness/config.json`、`AGENTS.md`、`CLAUDE.md`、`CHANGELOG.md`、`TODO.md`、`docs/INDEX.md`、`docs/CODEMAP.md`、`docs/{plans,knowledge,acceptance,adr}/`、`plan-templates/`、`scripts/` 与 `scripts/githooks/{pre-commit,setup.sh}`，以及 `.docs-harness/{inputs,tasks,reports,views,runtime}/` 与 `usage/` 忽略规则；共 53 个受管/骨架文件入库）。
  - 额外改动（用户未明确要求）：修改 `D:/Project/memware-cloud/.gitignore`，末尾追加 `__pycache__/` 与 `*.pyc`（避免运行 `scripts/harness.py` 生成的 Python 字节码缓存入库），并通过 `D:\Program Files\Git\bin\sh.exe` 在本机 `.git/hooks/pre-commit` 安装转发钩子。
- `D:/Project/docs-harness/docs/downstream.md`：在「维护中」表格新增 `memware-cloud`（`HackSing/memware-cloud`、`d79efbb`）登记行。
- `D:/Project/docs-harness/.docs-harness/reports/2026-11-22-memware-cloud-init.md`：本次收尾记录（随本仓提交，并一并提交上一任务收尾记录 `.docs-harness/reports/2026-11-22-remove-routing-shadow.md`）。

## 发现与说明

- 本机 `C:\Program Files\Git\bin\sh.exe` 不存在，改用同机实际安装路径 `D:\Program Files\Git\bin\sh.exe` 安装 pre-commit 转发钩子。
- `project init` 不会给非 Python 项目自动补充 `__pycache__/` 与 `*.pyc` 忽略规则；在 `memware-cloud` 运行 `self-test` 后生成了 25 个 `scripts/__pycache__/*.pyc` 文件，已从暂存区移出并清理，再通过 `.gitignore` 补齐忽略。

## 验证命令与退出码

- `python scripts/harness.py project init --target D:\Project\memware-cloud --apply --json` —— `.docs-harness/usage/2026-11.jsonl` 记录 `exit_code: 3`（`status="needs_delivery"`，无 `conflicts`，写入 58 项，githook 以 `100755` 登记暂存区；注：PowerShell 命令封装向外报告退出码 `1`；验证层级：`package_or_install`）。
- `& 'D:\Program Files\Git\bin\sh.exe' scripts/githooks/setup.sh`（在 `D:\Project\memware-cloud` 下执行）—— 退出码：0（输出「已安装 pre-commit 转发钩子：D:/Project/memware-cloud/.git/hooks/pre-commit」；验证层级：`local_runtime`）。
- `python scripts/harness.py assets-check --target D:\Project\memware-cloud --json` —— 退出码：0（`status="passed"`，`failures=[]`，`warnings=[]`；验证层级：`package_or_install`）。
- `python scripts/harness.py self-test --target . --json`（在 `D:\Project\memware-cloud` 下执行）—— 退出码：0（`status="passed"`，`version="2.36.0"`，11 项检查全部为 `true`；验证层级：`package_or_install`）。
- `pnpm -C D:\Project\memware-cloud typecheck` —— 退出码：0（`$ tsc --noEmit` 无错误，日志位于 `$env:TEMP\memware-typecheck.log`；验证层级：`local_runtime`）。
- `git -C D:\Project\memware-cloud status --short` 与 `git -C D:\Project\memware-cloud status --short --ignored scripts` —— 退出码：0（暂存区仅含 init 生成的 53 个文件与 `M .gitignore`，`scripts/` 下无 `__pycache__` 或未跟踪残留；`git ls-files -s scripts/githooks` 确认 `pre-commit` 与 `setup.sh` 均为 `100755`；验证层级：`local_runtime`）。
- `git -C D:\Project\memware-cloud commit ...` —— 退出码：0（触发本机 `pre-commit` 钩子并通过，生成提交 `d79efbb`；验证层级：`local_runtime`）。
- `python scripts/harness.py project check --target D:\Project\memware-cloud --json` —— 退出码：0（`status="passed"`，`delivery_status="in_head"`，`clone_ready=true`，`red=0`，`yellow=0`；验证层级：`package_or_install`）。
- `git -C D:\Project\memware-cloud push origin main` —— 退出码：0（`b422cbe..d79efbb  main -> main`；验证层级：`local_runtime`）。
- `python scripts/harness.py report check --path .docs-harness/reports/2026-11-22-memware-cloud-init.md --json` —— 退出码：0（`status="passed"`，5 项均通过；验证层级：`local_runtime`）。
- `python scripts/harness.py assets-check --target . --json` —— 退出码：0（`status="passed"`，违规 0 条、警告 0 条；验证层级：`local_runtime`）。

## 未覆盖项

- 没有为 `memware-cloud` 填充 `docs/CODEMAP.md` 业务模块映射内容。
- `memware-cloud` 的 GitHub Actions CI（`.github/workflows/ci.yml`）没有接入 harness 检查，当前仅依赖本机 `pre-commit` 钩子。
