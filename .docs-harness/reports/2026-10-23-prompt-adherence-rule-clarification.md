# 2026-10-23 提示词遵循规则修订（子智能体边界 / 零基础核对）

## 改动

- `scripts/agent_prompt.md`：工作流第 5 条把「轻量任务不开子智能体」改为可判定边界——同一目录或同一模块内读取用并行工具调用；跨 2 个及以上模块且每模块需多步取证的排查、或文件范围不相交的实施/独立评审，必须同消息开子智能体。验收条款要求文档类交付在收尾回复写明零基础通读结论（补齐了哪些前提，或确认无缺口）。
- `AGENTS.md`：用 `harness.managed_agent_block` 重新渲染受管区块，与模板逐字一致。
- `docs/testing.md`：在行为用例运行记录中新增 2026-10-23 四条用例的结果。
- 发布 2.32.0：`scripts/harness.py` 的 `VERSION`、`VERSION`、`CHANGELOG.md`、`README.md` badge、`package.json`、`SKILL.md`、`plan-templates/*`、`evals/evals.json` 同步；`release sync --strict` 返回 consistent。
- 下游升级：dispatch、opc-skills、suiyi、zbuddy-mobile、onceright、awesome-llm-made-videos、avatanel、content-system 共 8 个项目升到 2.32.0，受管文件已提交并推送（`project check` 均 passed/in_head）。zbuddy-desktop 的远端修改过受管脚本（已确认 `scripts/plan_check.py`、`scripts/structure_check.py` 有上游没有的本地修复），安装器按契约拒绝覆盖，停留在 2.31.0；本地未提交的剪贴板存根已恢复并推送（GitHub 与 codeup 均为 `7e2f0043`）。

## 验证

- 聚焦回归：`python3 -m unittest tests.test_cli_surface tests.test_project_install tests.test_project_upgrade tests.test_evals tests.test_release_version_sync`，73 tests，OK，退出 0。
- 全量回归（提示词属于下游共享契约）：`npm test`，293 tests，OK（skipped=2），退出 0。首次在版本同步后运行发现 README badge 仍为 2.31.0，修正为 2.32.0 后复跑通过。
- 版本一致性：`python3 scripts/harness.py release sync --strict`，status=consistent，退出 0。
- 控制器自检：`python3 scripts/harness.py self-test --target . --json`，status=passed，退出 0。
- 资产检查：`python3 scripts/harness.py assets-check --strict --json`，failures=0、warnings=0，退出 0。
- `git diff --check`：退出 0。
- 下游升级：8 个项目的 `project upgrade --apply` 完成（各 30 个受管变更，退出 3 = needs_delivery 属正常），提交后 `project check` 均为 passed/in_head。zbuddy-desktop 的 `--apply` 返回 2：受管脚本指纹与允许值不符，未写入任何文件；按用户选择恢复并推送其本地存根，harness 版本保持 2.31.0。
- 下游推送：9 个项目均已推送并核对远端 ref；其中 avatanel 为 `master`，onceright 的 4 个 LFS 封面对象已上传；opc-skills 的 `.workbuddy/`、两个 `.tgz` 与 onceright 的 `.build/`、`_staging/` 按用户选择排除，仍为本地未跟踪文件。
- 行为复验（独立会话，fixture 在 `.docs-harness/evals/behavior-baseline/`，会话只收到工作目录与原 scenario prompt）：
  - `subagent-evidence-checked`：2/2。会话 `0e3c374d-7cdb-5705-aaad-0c66e9babb43`；主 agent 同消息开 3 个只读子智能体，返回后逐项重读证据文件并跑 `EXPLAIN QUERY PLAN`，最终把 inventory 判为 N+1，未原样转述。
  - `intent-and-premise-first`：6/6。会话 `b079b7a4-b938-53f4-af66-575dcd155760`；首句纠正 JWT 无 session 表，先问 TTL 再改，收尾写明「以零基础读者身份通读：补了两个前提……行号逐条对照源码，示例执行输出 u1」。
  - `parallel-light-tasks-no-spawn`：3/3。会话 `62c7c93e-0b72-54bd-a025-4fb024d93edd`；三个配置文件同轮读取，未开子智能体，直接给出版本差异。
  - `parallel-independent-branches`：6/6。会话 `d939d76d-5abb-54f9-ad8b-3ad7f132c559`；B1/B2 并行、B3 依赖两者；子智能体只回改动/命令/退出码；主 agent 复跑两侧测试、做浏览器运行态验证并修正字符集问题，最后串行写 CHANGELOG、CODEMAP。
- 收尾记录自检：`python3 scripts/harness.py report check --path .docs-harness/reports/2026-10-23-prompt-adherence-rule-clarification.md`，status=passed，退出 0。

## 验证层级

- focused_test（73 项）
- repository_full_test（293 项）
- local_runtime（4 个独立模型会话 + fixture 内测试/检查）
- package_or_install（8 个下游升级到 2.32.0 + 1 个下游内容推送与升级拒绝诊断）
- 未做 real_device 层。

## 未覆盖

- 只重跑了受规则影响的四条 behavior 用例（合计 17/17），其余 7 条未重跑；每条仅 1 轮，未做稳定性采样。
- 子智能体任务书原文不由会话轨迹暴露，`subagent-brief-has-path-scope` 按子智能体回报的路径边界与主 agent 批次说明推断；`same-message-parallel-tool-calls` 的消息边界按工具顺序推断。
- 独立会话从 docs-harness 工作区启动，通过绝对路径进入 fixture；与 2026-10-22 基线方法一致，但不是独立的 workspace。
- `AskUserQuestion` 由宿主按推荐项代答，不代表真实用户选择。
- fixture 为临时目录，判定后已删除，可用同一 setup 重建。
- 源仓提示词修订提交 `9cbbcfb` 已在 `origin/main`（宿主自动提交并推送）；2.32.0 发布提交 `33762e5`、记录修正 `8f2df97` 及本次记录更新仅在本地，未推送源仓。
- `zbuddy-desktop` 未升到 2.32.0：需要先把它远端对 `plan_check.py`、`structure_check.py` 的本地修复上游化，或由用户确认放弃这些修复。
- `ai_study` 在本机没有克隆，未升级；暂停维护的 dsh-buddy、dsh、dsh-plugin 按登记表不升级。
- 下游未做 3–7 天失败率/WARN 率/报告完整率复测。
- 内容提交均为用户既有未提交改动（awesome 数据/脚本、avatanel 文档、onceright 素材、zbuddy-desktop 存根），未额外运行构建或测试。

## 自查

- 重复逻辑：无新增逻辑；规则只有 `scripts/agent_prompt.md` 一处源文本，`AGENTS.md` 由既有渲染函数生成，未手写第二份。
- 新增抽象：无。
