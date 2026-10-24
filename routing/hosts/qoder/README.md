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

使用 **Qoder 国内版 CLI（`qodercn`）**，不是国际版 `@qoder-ai/qodercli`。

安装与认证（宿主侧，不进仓库）：

```bash
npm install --prefix ~/.qoder-cn/docs-harness-router/cn @qodercn-ai/qoderclicn
~/.qoder-cn/docs-harness-router/qoder-cn-cli
# 在 CLI 里执行 /login，完成后 /status 看国内账号与额度，再 /quit
```

`settings.cli.example.json` 会调用 `route_hook.py`，后者执行：

```bash
qodercn -p "<task>" --output-format json --max-turns 1 \
  --tools "" --permission-mode default --no-session-persistence \
  --cwd <empty> --config-dir <host-config> --system-prompt "<router prompt>"
```

默认不传 `--model`，使用你在 CLI `/model` 里选中的模型；只有设置 `DOCS_HARNESS_ROUTER_MODEL` 时才覆盖。

CLI JSON 的 `usage`、`duration_ms`、`total_credits`、`total_cost_usd`、`modelUsage` 会写入 Shadow 事件。hook 会移除 Qoder Desktop 注入的 SDK 环境变量和国际版 token，设置隔离的 `QODERCN_CONFIG_DIR`。

### 同会话缓存

`UserPromptSubmit` 每条消息都会触发。hook 按 `session_id` 缓存上一次成功路由：首条任务调用 CLI，后续消息复用缓存、不再启动 CLI。发送“新任务/换个任务/new task”等标记或 `/route-reset` 会强制重路由；缓存 TTL 默认 2 小时。若后续消息换了任务但没有标记，主 agent 需要从 `routing/registry.json` 读取新契约。

## 安装

项目级测试：把 `settings.example.json`（fake）或 `settings.cli.example.json`（真实 Qoder 模型）的 `hooks` 块合并到 `.qoder/settings.local.json`，确认项目有 `routing/registry.json`，然后新建 Qoder 会话提交一个 code_task 提示。`.qoder/settings.local.json` 不入库。

用户级测试：复制 `route_hook.py` 到 `~/.qoder-cn/hooks/`，在 hook 的 `env` 设置 `DOCS_HARNESS_ROOT` 指向本仓，并把 `command` 指向复制后的脚本。

回滚：删除 hook 条目或对应 settings 文件。

## 限制

- fake backend 的 profile 是静态的；启用它会把所有提示按 code_task 注入。只用于匹配提示的链路测试。
- 国内 CLI 已接入但尚未登录；真实模型、Credits、延迟和路由质量数据要等一次真实 `/login` 后测量。
- CLI 是完整 Agent Runtime：首条任务和重路由会多一次启动；同会话后续消息走缓存，不再每条启动。
- Hook 只能追加 context，不能移除已加载的 AGENTS.md；token 收益仍需内核/模块契约拆分。
- Qoder Desktop 真实会话触发尚未验证；Qoder CN 账号能否在 CLI 登录以 `/status` 为准。
