---
kind: logging_system
name: 基于结构化 JSON 输出的 CLI 日志策略（无专用日志框架）
category: logging_system
scope:
    - '**'
source_files:
    - scripts/harness.py
    - tests/test_harness.py
    - tests/test_release_version_sync.py
---

## 1. 系统/方案概述

该仓库是一个 Python CLI 工具（`scripts/harness.py`），**没有引入任何第三方日志框架**（未 `import logging`、`loguru`、`structlog` 等）。所有“日志”输出统一通过标准库的 `print()` 写入 stdout，并以 **JSON 结构体** 作为唯一对外契约。错误路径则通过抛出自定义异常 `HarnessError`，由顶层 `main()` 捕获后序列化为统一的错误 JSON 并写入 stdout，同时返回非零退出码。

因此，本仓库的“日志系统”实质上是：**结构化 JSON 事件流 + 结构化错误负载 + 进程退出码** 的组合，而非传统意义上的分级日志框架。

## 2. 关键文件与位置

- `scripts/harness.py`：唯一的入口脚本，集中实现所有命令（`run` / `context` / `progress` / `verify` / `task` / `ledger` / `knowledge` / `background` / `project` / `authorization` / `release` / `self-test`）以及输出逻辑。
- `tests/test_harness.py`、`tests/test_release_version_sync.py`：测试断言依赖的是 stdout 的 JSON 解析结果，间接验证了输出格式契约。
- `docs/plans/v1.7.3-minimal-host-flow-verify.py`、`docs/plans/v1.7.3-v3-shadow-acceptance.py`：辅助验证脚本使用 `print(f"[PASS] ...")` / `print(f"[FAIL] ...")` 这类人类可读标记，但仅用于验收脚本，不属于 harness 主流程。

## 3. 架构与约定

### 3.1 统一输出入口 `emit(payload, as_json)`
位于 `scripts/harness.py` 第 11967–11973 行：
- 当 `as_json=True` 时，调用 `json.dumps(payload, ensure_ascii=False, indent=2)` 并 `print()`；
- 当 `as_json=False` 时，逐键打印 `key: value` 形式的人类可读文本。
所有成功路径的命令函数都返回 `(code, payload)` 元组，最终由 `main()` 调用 `emit(payload, args.json)` 输出。

### 3.2 成功响应结构
每个命令返回的 `payload` 是纯字典，字段名由各命令定义（如 `task_id`、`next_action`、`next_command_argv`、`status` 等）。`enrich_next_step_response()` 会在必要时注入宿主侧需要的 next-step 信息。

### 3.3 错误处理与结构化错误负载
- 业务层通过抛出 `HarnessError`（定义于第 380–399 行）表达错误，携带 `code`、`exit_code`、`suggested_fix`、`missing_items`、`actual_vs_expected`、`extra_payload` 等结构化字段。
- `main()` 中 `except HarnessError as exc` 分支（第 12042–12053 行）将错误包装为固定结构的 JSON：`{"status": "error", "code": ..., "message": ..., 可选字段...}`，并通过同一 `emit()` 输出到 stdout。
- 退出码由 `exc.exit_code` 决定（默认 2，Git 预检失败为 3），供宿主进程判断成败。

### 3.4 子进程输出不直接打印
所有 `subprocess.run(..., capture_output=True, text=True)` 的 `stdout` / `stderr` 均被捕获并在内部处理，**不会直接透传到 stdout**。这保证了 harness 的 stdout 只承载自身定义的 JSON 事件。

### 3.5 事件持久化（类日志）
运行期状态以 JSONL 文件追加写入（`append_jsonl`，第 551–556 行），例如 `events.jsonl`、`context-receipts.jsonl`、`authorization-receipts.jsonl` 等。这些文件充当可审计的持久化“日志”，每条记录用 `canonical_json(value) + "\n"` 序列化并 `fsync`。

## 4. 约定与约束

| 约定 | 说明 | 依据 |
|---|---|---|
| 禁止在 stdout 上输出任意文本 | 所有命令必须通过 `emit()` 输出 JSON 或 key:value 文本；子进程输出必须捕获 | `main()` → `emit()` 是唯一出口，`git_command` 等封装强制 `capture_output=True` |
| 错误必须走 `HarnessError` 异常链 | 业务错误不直接 `print`，而是抛出自定义异常，由顶层统一格式化 | `main()` 的 `except HarnessError` 分支 |
| 错误负载包含 `status="error"` + `code` + `message` | 宿主通过解析 JSON 字段判断错误类型 | `main()` 错误分支构造的固定 schema |
| 退出码区分语义 | 默认 2 表示请求/校验错误，3 表示 Git 预检超时等运行时错误 | `HarnessError.__init__` 默认值及 `git_preflight_timeout` 处显式设置 |
| 持久化事件使用 JSONL + fsync | 保证每条事件落盘 | `append_jsonl` 实现 |
| 人类可读模式仅用于调试 | `--json` 关闭时输出 `key: value` 文本，便于终端阅读 | `emit()` 双分支 |

## 5. 结论

该仓库**不存在传统意义上的日志框架**，其“日志系统”是一套轻量但严格的约定：CLI 通过 `print(json.dumps(...))` 输出结构化 JSON 事件，错误通过 `HarnessError` 转为结构化错误负载，运行期事件以 JSONL 持久化。这套设计使 harness 的输出完全可被机器解析，适合被宿主进程（Claude/Codex 等）消费，而不是给人读日志。
