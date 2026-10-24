# Qoder UserPromptSubmit hook 原型

状态：原型，默认关闭，未安装到任何项目。详细契约、安装与限制见 `docs/routing.md` §10。

## 做什么

Qoder 在用户提交 prompt 后、主 Agent 处理前触发 `UserPromptSubmit`。本目录的 `route_hook.py` 用 `command` handler：

1. 从 stdin 读取 hook 输入；
2. 加载 `routing/registry.json`；
3. 通过 `_route_task` 取得路由画像（当前是 `fake_profile.json`，后续替换为真实低上下文模型调用）；
4. 用 `validate_profile` 校验；
5. 写 `.docs-harness/routing/shadow-YYYY-MM.jsonl`；
6. 向 stdout 输出 `hookSpecificOutput.additionalContext`，只包含选中的模块契约。

失败不阻断用户任务：写入 stderr 和 `.docs-harness/routing/hook-errors.jsonl` 后退出 0。

## 文件

- `route_hook.py`：hook 脚本，`_route_task` 是真实模型调用的替换点。
- `fake_profile.json`：静态 code_task 画像，只用于链路测试。
- `settings.example.json`：Qoder hooks 配置片段。

## 测试

```bash
python3 -m unittest tests.test_qoder_hook -v
```

独立冒烟：

```bash
echo '{"hook_event_name":"UserPromptSubmit","session_id":"demo","cwd":"'"$PWD"'","prompt":"修改 routing/registry.json 并跑测试"}' | \
  QODER_PROJECT_DIR="$PWD" DOCS_HARNESS_ROUTER_ENABLED=1 \
  python3 routing/hosts/qoder/route_hook.py
```

## 安装

项目级测试：把 `settings.example.json` 的 `hooks` 块合并到 `.qoder/settings.local.json`，确认项目有 `routing/registry.json`，然后新建 Qoder 会话提交一个 code_task 提示。`.qoder/settings.local.json` 不入库。

用户级测试：复制 `route_hook.py` 到 `~/.qoder-cn/hooks/`，在 hook 的 `env` 设置 `DOCS_HARNESS_ROOT` 指向本仓，并把 `command` 指向复制后的脚本。

回滚：删除 hook 条目或对应 settings 文件。

## 限制

- fake profile 是静态的；真实模型接入前，启用它会把所有提示按 code_task 注入。只用于匹配提示的链路测试。
- 没有真实模型、token/cost 和真实路由质量数据。
- Hook 只能追加 context，不能移除已加载的 AGENTS.md；token 收益仍需内核/模块契约拆分。
- Qoder Desktop 真实会话触发尚未验证。
