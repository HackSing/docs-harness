# Qoder UserPromptSubmit hook 原型

状态：原型，默认关闭，未安装到任何项目。详细契约、安装与限制见 `docs/routing.md` §10。

## 做什么

Qoder 在用户提交 prompt 后、主 Agent 处理前触发 `UserPromptSubmit`。本目录的 `route_hook.py` 用 `command` handler：

1. 从 stdin 读取 hook 输入；
2. 加载 `routing/registry.json`；
3. 通过 `_route_task` 取得路由画像：`fake` backend 读 `fake_profile.json`，`cli` backend 调用 Qoder CLI 无头模式；
4. 用 `validate_profile` 校验；
5. 写 `.docs-harness/routing/shadow-YYYY-MM.jsonl`；
6. 向 stdout 输出 `hookSpecificOutput.additionalContext`，只包含选中的模块契约。

失败不阻断用户任务：写入 stderr 和 `.docs-harness/routing/hook-errors.jsonl` 后退出 0。

## 文件

- `route_hook.py`：hook 脚本；`_route_task` 分派 fake/cli backend。
- `route_cache.py`：同会话路由缓存，避免后续消息重复启动 CLI。
- `fake_profile.json`：fake backend 的静态 code_task 画像。
- `settings.example.json`：fake backend 的 Qoder hooks 配置片段。
- `settings.cli.example.json`：Qoder CLI backend 的配置片段。
- `user-hook.sh`：用户级 hook 入口，先检查项目是否使用 Docs Harness，再调用 `route_hook.py`。

## 测试

```bash
python3 -m unittest tests.test_qoder_hook -v
```

独立冒烟（fake backend）：

```bash
echo '{"hook_event_name":"UserPromptSubmit","session_id":"demo","cwd":"'"$PWD"'","prompt":"修改 routing/registry.json 并跑测试"}' | \
  QODER_PROJECT_DIR="$PWD" DOCS_HARNESS_ROUTER_ENABLED=1 \
  python3 routing/hosts/qoder/route_hook.py
```

## CLI backend

优先使用 **Qoder 国内版原生 CLI（`qoderclicn`）**，不是国际版 `@qoder-ai/qodercli`；npm 版 `qodercn` 只作 fallback。

安装与认证（宿主侧，不进仓库）：

```bash
curl -fsSL https://static.qoder.com.cn/qoder-cli-cn/install.sh | bash -s -- --skip-path
# 入口：~/.local/bin/qoderclicn
~/.qoder-cn/docs-harness-router/qoder-cn-cli
# 在 CLI 里执行 /login，完成后 /status 看国内账号与额度，再 /quit
```

npm 兼容安装：

```bash
npm install --prefix ~/.qoder-cn/docs-harness-router/cn @qodercn-ai/qoderclicn
```

`settings.cli.example.json` 会调用 `route_hook.py`，后者执行：

```bash
qoderclicn -p "<task>" --output-format json --max-turns 1 \
  --tools "" --permission-mode default --no-session-persistence \
  --cwd <empty> --config-dir <host-config> --system-prompt "<router prompt>"
```

默认不传 `--model`，使用你在 CLI `/model` 里选中的模型；只有设置 `DOCS_HARNESS_ROUTER_MODEL` 时才覆盖。原生版实测墙钟约 3.1s，其中模型约 2.0s、启动约 1.1s；npm 版墙钟约 4.1s，启动约 2.6s。

CLI JSON 的 `usage`、`duration_ms`、`total_credits`、`total_cost_usd`、`modelUsage` 会写入 Shadow 事件。hook 会移除 Qoder Desktop 注入的 SDK 环境变量和国际版 token，设置隔离的 `QODERCN_CONFIG_DIR`。

### 同会话缓存

`UserPromptSubmit` 每条消息都会触发。hook 按 `session_id` 缓存上一次成功路由：首条任务调用 CLI，后续消息复用缓存、不再启动 CLI。发送“新任务/换个任务/new task”等标记或 `/route-reset` 会强制重路由；缓存 TTL 默认 2 小时。若后续消息换了任务但没有标记，主 agent 需要从 `routing/registry.json` 读取新契约。

## 安装

用户级（当前采用）：

1. 在 `~/.qoder-cn/settings.json` 的 `hooks.UserPromptSubmit` 增加一组 command hook，`command` 指向本目录的 `user-hook.sh`。
2. `env` 设置 `DOCS_HARNESS_ROOT`、`DOCS_HARNESS_ROUTER_ENABLED=1`、`DOCS_HARNESS_ROUTER_BACKEND=cli`、`DOCS_HARNESS_QODER_CLI`、`DOCS_HARNESS_QODER_CONFIG_DIR`、`DOCS_HARNESS_QODER_EMPTY_DIR`。
3. `user-hook.sh` 只在项目含 `routing/registry.json` 时继续；旧版 docs-harness（只有 `.docs-harness/config.json`）和其他项目直接退出，不写日志、不启动 CLI、不改上下文。
4. 修改设置前备份；新建 Qoder 会话才会加载用户级 hook。

项目级（可选）：把 `settings.example.json`（fake）或 `settings.cli.example.json`（真实 Qoder 模型）的 `hooks` 块合并到 `.qoder/settings.local.json`，确认项目有 `routing/registry.json`，然后新建会话。

回滚：删除 `hooks.UserPromptSubmit` 中的 docs-harness 条目，新建会话。

## 限制

- fake backend 的 profile 是静态的；启用它会把所有提示按 code_task 注入。只用于匹配提示的链路测试。
- 国内原生 `qoderclicn` 已登录，`dfmodel` 完成真实路由；CLI 对该模型报告 0 tokens / 0 Credits。
- CLI 是完整 Agent Runtime：首条任务和重路由会多一次启动；同会话后续消息走缓存，不再每条启动。原生墙钟约 3.1s，npm 约 4.1s。
- Hook 只能追加 context，不能移除已加载的 AGENTS.md；token 收益仍需内核/模块契约拆分。
- 项目级 Desktop 已端到端验证；用户级 hook 已安装但需新会话复验；1–2 周真实 shadow 未开始。
