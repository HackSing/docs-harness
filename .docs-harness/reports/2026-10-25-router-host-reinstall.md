# 2026-10-25 用户级路由 hook 重建（Windows）

## 背景

zbuddy-mobile 与 zbuddy-desktop 项目内的 `routing/registry.json` 都在，但本机已没有用户级路由 hook：`~/.qoder-cn/settings.json` 无 `hooks.UserPromptSubmit`，`~/.qoder-cn/docs-harness-router/` 不存在，旧 hook 指向的 `D:/AIWareTop/Agent/docs-harness` 也已删除。本次按 `docs/routing.md` §10 重建宿主侧配置，仍为 `shadow` 只记录。

## 改动路径

- `C:/Users/freed/.qoder-cn/settings.json`：新增 `hooks.UserPromptSubmit`，命令为 `C:/Windows/py.exe -3 D:/Project/docs-harness/routing/hosts/qoder/route_hook.py`；env 设 `DOCS_HARNESS_ROOT`、`DOCS_HARNESS_ROUTER_ENABLED=1`、`DOCS_HARNESS_ROUTER_PHASE=shadow`、`DOCS_HARNESS_ROUTER_BACKEND=cli`、`DOCS_HARNESS_QODER_CLI`、`DOCS_HARNESS_QODER_CONFIG_DIR`、`DOCS_HARNESS_QODER_EMPTY_DIR`。原文件备份为 `C:/Users/freed/.qoder-cn/settings.json.bak-20261025213317`。
- `C:/Users/freed/.qoder-cn/docs-harness-router/cn-config`：新建，复制 `~/.qoder-cn/.auth` 与 `~/.qoder-cn/.models` 继承登录。
- `C:/Users/freed/.qoder-cn/docs-harness-router/empty`：新建，作为 CLI 路由的空工作目录。
- `.docs-harness/runtime/router-host-reinstall/`：本地运行态证据包与 evidence，未入库；`.docs-harness/runtime/.gitignore` 写入 `*`，保持该目录本地化。
- 未修改仓库受跟踪文件，未修改两个下游的仓库文件或注册表。

## 验证

- `python` 解析 `C:/Users/freed/.qoder-cn/settings.json` 并读取 hook 字段：退出码 0，`phase=shadow`、`backend=cli`、`root=D:/Project/docs-harness`；验证层级：contract_check。
- `qoderclicn.exe --version` 返回 1.1.78，退出码 0；`qoderclicn.exe --config-dir cn-config --list-models` 返回模型列表，退出码 0；验证层级：package_or_install。
- 以 settings 中的完整命令和 env 调用 `routing/hosts/qoder/route_hook.py`：
  - fake backend 代码任务：退出码 0，stdout/stderr 0 字节，写出 `phase=shadow`、`modules=["code"]` 事件；验证层级：local_runtime。
  - 真实 CLI backend 代码任务：退出码 0，写出 `modules=["code"]`、`model=auto`、`latency_ms=22930.0` 事件；验证层级：local_runtime。
  - 同会话第二条消息：退出码 0，命中 `route-cache`、`cache_hit=true`、延迟 0.0ms；验证层级：local_runtime。
  - 无 `routing/registry.json` 项目：退出码 0，stdout/stderr 0 字节，不创建 `.docs-harness/routing`；验证层级：local_runtime。
  - `stdin=not-json`：退出码 0，stderr 输出 `invalid hook input`，不新增 shadow 事件；验证层级：local_runtime。
  - `DOCS_HARNESS_ROUTER_BACKEND=bogus`：退出码 0，`hook-errors.jsonl` 写入 `unknown_router_backend`，stdout 0 字节；验证层级：local_runtime。
  - `<task-notification>` 通知正文：退出码 0，shadow 行数不变；验证层级：local_runtime。
  - 570 字中文、含换行与特殊字符的边界任务：退出码 0，`task_chars=570`、`modules=["bugfix","code"]`、`latency_ms=13042.9`；验证层级：local_runtime。
- 真实 Qoder 新会话 `4a93f589-2fa2-5f59-addd-ccba47118871`（zbuddy-desktop workspace）：首条元提示被模型判为 `direct_override` 且缺少意图，hook 记录 `profile_invalid` 并退出 0；第二条带新任务标记的 answer_only 问题写出 `phase=shadow`、`modules=[]`、`model=auto`、`latency_ms=8743.2`、`credits=0.10474508` 事件，stdout 为空；验证层级：local_runtime。
- 两个下游注册表：`load_registry` 均返回 `version=1.0.0`，指纹与源仓一致；验证层级：contract_check。
- 两个下游真实 CLI 路由：zbuddy-desktop 与 zbuddy-mobile 均退出码 0、写出 `modules=["code"]` 事件；验证后删除本次生成的合成 `.docs-harness/routing` 目录；验证层级：local_runtime。
- `python scripts/harness.py runtime check --target . --packet .docs-harness/runtime/router-host-reinstall/packet.json --json`：`status=passed`、错误 0、警告 0，退出码 0；验证层级：contract_check。
- `python scripts/harness.py assets-check --json`：`status=passed`、失败 0、警告 0，退出码 0；验证层级：contract_check。
- `python scripts/harness.py report check --path .docs-harness/reports/2026-10-25-router-host-reinstall.md`：`status=passed`，退出码 0；验证层级：contract_check。

## 自查

- 复用：继续使用现有 `route_hook.py`、`routing_contract.py` 和 Qoder CLI，没有新增代码、脚本或抽象；只做宿主配置重建。
- 没有重复逻辑：宿主设置只新增一组 hook 条目，项目门禁、校验、缓存和日志仍由既有 `route_hook.py` 单点负责。
- 没有新增仓库依赖或受跟踪文件改动；两个下游保持干净，测试生成的 shadow 日志已删除。
- 当前会话不会加载新 hook；需要新建 Qoder 会话才会生效。

## 未覆盖

- 只有 zbuddy-desktop 走过真实 Qoder 新会话；zbuddy-mobile 只通过命令行真实 CLI 验证，未新建移动端会话。
- 首条真实会话元提示得到 `direct_override` 且缺少意图的非法画像，hook 按契约记录 `profile_invalid`；该模型输出偏差未修复，属于路由准确率采样问题。
- 真实 CLI 路由耗时本次为 8–23 秒，单次约 0.1 Credits；未校准延迟与成本阈值，也未做 1–2 周真实任务采样。
- 未验证上下文压缩后的缓存命中、canary/enforced 注入路径和回滚演练。
- 本次未运行仓库测试；没有改动仓库代码，运行态与配置检查已覆盖本次改动面。
