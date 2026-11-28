# 收尾记录：多宿主防治标 Stop Hook 补装、Antigravity 防折叠验证与模拟图误触发收紧

- 日期：2026-11-28
- 验证层级：`focused_test`、`local_runtime`
- 运行态证据包：`.docs-harness/runtime/stop-hook-antigravity-self-contained/packet.json`（`runtime check` 退出码：0）
- 前台/后台验证说明：全程在后台进程执行单测、静态/资产检查与隔离临时目录多宿主命令重放，未弹出任何可见窗口、弹窗或抢夺焦点。

## 改动路径

- 仓库内文件（本任务范围，未触碰并发会话的其他未提交文件）：
  - `scripts/plan_root_cause_hook.py`：保留并验证已有未提交的 Antigravity 防折叠自包含修复（`_CHALLENGE_CHECKS` + `ANTIGRAVITY_CHALLENGE_REASON`）；新增 `NON_PLAN_ARTIFACT_NAME_RE`、`NON_PLAN_ARTIFACT_SUMMARY_RE` 与 `_is_non_plan_feedback_artifact`，在 `_classify_edit_tool` 中先判 `_is_plan_path`，再对 `RequestFeedback=true` 的非方案视觉模拟图/视觉预览/walkthrough 返回 `(False, False)`，避免误判为代码方案。
  - `tests/test_host_hooks.py`：保留已有 `ANTIGRAVITY_CHALLENGE_REASON` 断言，新增 `test_request_feedback_skips_visual_mockups_but_keeps_architecture_and_plan_paths`，覆盖视觉模拟图/视觉预览/walkthrough 放行、真正架构文档触发以及含 `prototype` 的 `docs/plans/*.md` 仍优先按方案触发；全文件控制在 600 行阈值内。
  - `docs/CODEMAP.md`：既有未提交改动已补充公开符号 `ANTIGRAVITY_CHALLENGE_REASON`；本次仅新增私有辅助函数，未重复改动。
  - `.docs-harness/reports/2026-11-28-stop-hook-multi-host-and-tighten.md`（本收尾记录，随仓入库）。
- 本机用户级配置与本地运行态证据（不入库）：
  - `C:/Users/freed/.docs-harness/hooks/plan_root_cause_hook.py`：通过 `host_hooks.install_host_hook` 同步至仓库最新真源（SHA-256 `8819352a56f5ba5b`，17,189 字节）。
  - `C:/Users/freed/.qoder-cn/settings.json`、`C:/Users/freed/.qoder/settings.json`：幂等补装 `hooks.Stop`（保留既有插件、MCP 与权限配置）。
  - `C:/Users/freed/.claude/settings.json`：幂等补装 `hooks.Stop`（保留既有语言、权限与模型配置）。
  - `C:/Users/freed/.codex/hooks.json`：幂等补装 `hooks.Stop`（带 `matcher=""`）。
  - `C:/Users/freed/.zcode/cli/config.json`：写入 `hooks.enabled=true` 与 `hooks.events.Stop`。
  - `C:/Users/freed/.gemini/config/hooks.json`：已配置指向统一副本，复检无漂移。
  - `.docs-harness/runtime/stop-hook-antigravity-self-contained/packet.json` 与 `evidence/live-hook-replay.log`。

## 根因细节与收尾自查

- **根因**：`_classify_edit_tool` 将所有带 `ArtifactMetadata.RequestFeedback=true` 的 `write_file`/`edit_file` 无差别归类为 `is_plan=True`，导致生成视觉模拟图或预览文档（真实会话 `14616f17` 的 `membership_ui_mockup.md` 与 `b2a3fc59` 的 `antiwave_extension_visual_preview.md`）时绕过意图校验直接触发代码治本反证。
- **根因自检结论**：① 修复落在唯一状态所有者 `_classify_edit_tool`（归类工具调用为 `is_plan`/`is_code`）而非消费者层补丁；② 所有携带 `ArtifactMetadata` 的编辑工具均经该分支，且 `_is_plan_path` 优先短路保护了 `docs/plans/*prototype*.md` 等正式方案；③ `_is_plan_path` 前置、文件名正则与摘要正则三者缺一即会漏掉对应真实样本（如中文摘要+通用文件名或正式原型方案），无多余改动；④ 全部规则均有真实会话记录作证（`14616f17`、`b2a3fc59` 为误触样本，`36bccbbc` 为架构文档正对照），无无证据兜底分支。
- **顺手发现未扩大范围的事项**：① 在 `11-18` 历史会话 `36bccbbc` 中观察到同轮先调 `ask_question` 后再写架构文档时，`state["asked_user"]` 仍会抑制触发；因安装后 160 个会话中未出现单纯因此漏触，按不顺手加固原则仅记入本报告；② 本机 DeepSeek Harness（`~/.dsh/profiles/{desktop,headless,web}` 与 `DeepSeek Harness/resources`）均未安装 `@deepseek-ai/dsh-hooks-claude-code` 桥接插件，因此未写入 `~/.dsh/cordis.patch.yml`，避免引用缺失插件影响启动。
- **搜过什么**：已检索 `scripts/plan_root_cause_hook.py`、`scripts/host_hooks.py`、`tests/test_host_hooks.py`、`docs/CODEMAP.md`、`docs/contracts.md`，以及本机 6 宿主配置文件、`~/.dsh/profiles`、`DeepSeek Harness/resources` 与 `2026-11-20` 以来 Antigravity 全部含 `RequestFeedback` 的轨迹。
1. **本次是否引入了重复逻辑？**
   没有。多宿主补装全部直接复用 `scripts/host_hooks.py` 的 `install_host_hook`；非方案文档过滤集中在 `scripts/plan_root_cause_hook.py` 单一真源，全部宿主共用一份脚本。
2. **本次新增抽象各自的职责是什么？**
   - `_is_non_plan_feedback_artifact`（`scripts/plan_root_cause_hook.py` 私有辅助函数）：仅基于文件基名与 `ArtifactMetadata.Summary` 判断非方案路径的 `RequestFeedback` 文档是否属于视觉模拟图/预览/walkthrough。

## 验证命令与退出码

- `python -X utf8 -m unittest tests.test_host_hooks tests.test_project_upgrade tests.test_cli_surface -v` —— 退出码：0（53 项通过，3 项按条件跳过，含 `test_host_hooks` 16/16；验证层级：`focused_test`）。
- 6 份本机已配置宿主真实命令冒烟 + 真实轨迹切片（`14616f17` 两轮模拟图、`af87730c` 冻结方案、`qoder-cn` Claude 协议）+ 异常输入探针重放 —— 退出码：0（`SCRIPT_SYNC` SHA-256 `8819352a56f5ba5b` 一致，6 项 `HOST_CMD_SMOKE`、`REPLAY_REAL_MOCKUP[0/1]`、`REPLAY_REAL_PLAN`、`REPLAY_QODER_CLAUDE_DIALECT` 与 3 项 `ADVERSARIAL_PROBE` 全通过；证据见 `.docs-harness/runtime/stop-hook-antigravity-self-contained/evidence/live-hook-replay.log`；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py runtime check --target . --packet .docs-harness/runtime/stop-hook-antigravity-self-contained/packet.json --json` —— 退出码：0（`status=passed`；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py structure check --target . --json` —— 退出码：0（`status=passed`，warnings 0 条；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py assets-check --target . --fast --json` —— 退出码：0（违规 0 条，警告 0 条；验证层级：`local_runtime`）。
- `python -X utf8 scripts/harness.py self-test --target . --json` —— 退出码：0（`status=passed`；验证层级：`focused_test`）。
- `git diff --check -- scripts/plan_root_cause_hook.py tests/test_host_hooks.py` —— 退出码：0（验证层级：`focused_test`）。
- `python -X utf8 scripts/harness.py report check --target . --path .docs-harness/reports/2026-11-28-stop-hook-multi-host-and-tighten.md --json` —— 退出码：0（`status=passed`）。

## 未覆盖项

- 未在 Qoder CN、Claude Code、Codex、ZCode 四个真实客户端 UI 内逐一新建会话验证宿主原生 Stop 回调触发（已在后台通过各宿主配置文件真实命令完成子进程冒烟与方言重放）。
- DeepSeek Harness（`~/.dsh`）因本机未安装 `@deepseek-ai/dsh-hooks-claude-code` 桥接插件，尚未写入 `~/.dsh/hooks.json` 与 `~/.dsh/cordis.patch.yml`。
- 未运行仓库级全量测试与 `dsh-plugin` 同步构建（工作区同时存在并发会话对 `runtime_check.py`/`agent_prompt.md` 等文件的未提交改动，本次严格收敛在 Stop Hook 域内，且未执行 `git commit`）。
