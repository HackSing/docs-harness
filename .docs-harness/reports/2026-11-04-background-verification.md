# 2026-11-04 验证默认后台

## 改动

- `scripts/agent_prompt.md`：新增“验证默认后台”规则，覆盖后台进程、隐藏窗口、离屏渲染、headless、禁止弹窗/抢焦点/自动打开文件夹，以及真实硬件、系统权限、原生弹窗的前台例外；收尾记录要求运行态任务补前台/后台验证说明。
- `AGENTS.md`：从受管模板重新渲染，规则同步到受管区块。
- `docs/contracts.md`：新增 4c 节，含分层默认做法表、分层细则、前台例外协议、批处理与完成判定。
- `docs/testing.md`、`docs/runtime-verification/README.md`、`SKILL.md`：增加后台验证要点与 4c 节指向。
- `tests/test_agent_prompt_verification.py`：新增 7 项规则与合同文本守卫测试。
- `evals/evals.json`：`runtime-verification-quality` 增加 `background-no-interruption` 判定项。
- `CHANGELOG.md`：新增 `## Unreleased` 条目；本任务未改版本号、未发版。

## 验证

- `python -m unittest tests.test_agent_prompt_verification tests.test_agent_prompt_format tests.test_evals -v`：19 项通过，退出码 0；验证层级：focused_test。
- `python -m unittest tests.test_project_install -v`：31 项通过（skipped=1，Windows 无 symlink 权限），退出码 0；验证层级：package_or_install。
- `python scripts/harness.py self-test --target . --json`：status=passed，退出码 0；验证层级：focused_test。
- `python scripts/harness.py assets-check --fast`：passed，0 失败 0 警告，退出码 0；验证层级：focused_test。
- `python scripts/harness.py assets-check --strict`：passed，0 失败 0 警告，退出码 0；验证层级：focused_test。
- `python scripts/harness.py release sync --target . --strict --json`：status=consistent，版本真源 2.34.0，退出码 0；验证层级：focused_test。
- `python scripts/harness.py project diff --target . --json`：AGENTS.md 不在差异中，退出码 0；仅剩仓库既有 config/.gitignore 差异。
- `python scripts/harness.py project check --target . --json`：status=failed，退出码 1；`required_commit_paths=[AGENTS.md, scripts/agent_prompt.md]` 是本次未提交改动；4 条红级与 1 条黄级属既有问题（工作区与 HEAD 的 config 版本均为 2.28.0，本次未触碰控制器、资产模块或方案模板）。
- `git diff --check`：退出码 0。

## 未覆盖

- 未运行 behavior 真实会话；`runtime-verification-quality` 的新判定项只登记，未执行。
- 未在真实 Web/Electron/WPF/模拟器项目复跑后台截图流程；合同的工具做法来自用户提议与本仓已有能力说明。
- 未修改 `runtime check` schema；检查器无法判断是否真的没有弹窗，前台/后台依赖收尾记录自述。
- 未发版、未 bump VERSION、未同步下游项目。
