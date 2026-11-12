# Antigravity `PreInvocation` Hook（意图路由）

状态：本机全局（`~/.gemini/config/hooks.json`）已安装，默认 `shadow` 阶段仅记录脱敏 Shadow 日志；`canary`/`enforced` 阶段通过 `injectSteps` 注入选中模块契约。

## 工作方式

Antigravity 在调用模型前触发 `PreInvocation` 生命周期钩子。本目录的 `route_hook.py` 复用 `evals/intent_routing/jev_predict.py` 与 `routing/hosts/qoder/route_hook.py` 的核心路由与校验逻辑，针对 Antigravity 宿主协议做适配：

1. 从 `stdin` 读取 Antigravity camelCase JSON（`conversationId`、`workspacePaths`、`lastUserInput`）；
2. 从 `lastUserInput` 提取 `<USER_REQUEST>...</USER_REQUEST>` 内的真实用户输入（剔除 `<ADDITIONAL_METADATA>` 等宿主附加块）；
3. 检查 `workspacePaths` 下是否存在 `routing/registry.json`；未接入项目直接向 `stdout` 输出 `{}` 并退出 0；
4. **同轮工具循环去重**：Antigravity 在单轮工具调用循环的每次模型调用前都会触发 `PreInvocation`（此时 `conversationId` 与 `lastUserInput` 不变）。`route_hook.py` 在 `.docs-harness/routing/sessions/<hash>.last` 记录最近一次已路由的输入哈希，同一用户消息的后续工具步直接输出 `{}` 并退出 0，不重复请求路由模型或重复写 Shadow 日志；
5. 新用户消息先查同会话路由缓存（`route_cache.py`），未命中时调用 `decisions` 后端（Google Gemini Decisions API，`gemini-decision-1`）；
6. 经 `validate_profile` 校验后写入 `.docs-harness/routing/shadow-YYYY-MM.jsonl`；
7. `shadow` 阶段输出 `{}`；`canary`/`enforced` 阶段输出 `{"injectSteps": [{"systemMessage": {"systemMessage": "<契约>"}}]}`。

任何异常均写入 `stderr` 与 `.docs-harness/routing/hook-errors.jsonl`，向 `stdout` 输出 `{}` 并以退出码 0 结束，不阻断 Antigravity 执行循环。

## 文件

- `route_hook.py`：Antigravity `PreInvocation` 钩子脚本，支持命令行参数 `--enabled`、`--phase`、`--backend`、`--model`、`--env-file`、`--root`（适配 Antigravity `hooks.json` 无 `env` 字段的 handler 结构）。
- `hooks.example.json`：全局 `~/.gemini/config/hooks.json` 或工作区 `.agents/hooks.json` 配置示例。

## 安装与回滚

- **全局安装（当前启用）**：配置位于 `~/.gemini/config/hooks.json`（Windows 为 `C:\Users\<用户>\.gemini\config\hooks.json`），通过 `--env-file` 指向 gitignored 的 `.docs-harness/inputs/gemini.env`，不在 `hooks.json` 中硬编码 API Key。
- **回滚**：在 `~/.gemini/config/hooks.json` 中将 `"docs-harness-router"` 的 `"enabled"` 设为 `false`，或直接删除 `hooks.json`。

## 验证命令

```bash
python3 -m unittest tests.test_antigravity_hook -v
```
