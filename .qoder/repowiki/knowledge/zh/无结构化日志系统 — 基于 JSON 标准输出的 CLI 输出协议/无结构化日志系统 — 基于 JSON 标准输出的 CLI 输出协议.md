---
kind: logging_system
name: 无结构化日志系统 — 基于 JSON 标准输出的 CLI 输出协议
category: logging_system
scope:
    - '**'
source_files:
    - scripts/harness.py
    - tests/test_harness.py
    - package.json
---

## 1. 使用的系统/方法

仓库中**不存在**传统意义上的日志系统。`scripts/harness.py` 未导入 `logging`、`loguru`、`structlog` 等任何日志库，也没有定义 `logger` 实例或日志级别配置。整个应用是一个 Python CLI（通过 `argparse` 暴露 `run`/`verify`/`background`/`ledger`/`context`/`project`/`authorization`/`self-test` 等子命令），其“可观测性”完全通过 **JSON 格式的标准输出** 实现。

所有命令在调用时均附带 `--json` 参数（见测试中的 `run_harness` 助手：`subprocess.run(..., [sys.executable, str(HARNESS), *args, "--json"])`），期望 stdout 输出一行或多行 JSON 对象作为结构化结果；stderr 用于人类可读的错误信息，stdout 仅承载机器可读的 JSON payload。

## 2. 关键文件

- `scripts/harness.py`：唯一入口脚本，包含全部业务逻辑与 CLI 解析，无任何日志模块导入。
- `tests/test_harness.py`：通过 `subprocess` 启动 harness 并解析 `stdout` 的 JSON 来断言行为，是验证 CLI 输出契约的主要载体。
- `package.json`：声明 npm 包元数据，`scripts.test` 直接调用 `python3 -m unittest discover`，`scripts.self-test` 调用 `python3 scripts/harness.py self-test --target . --json`，体现以 JSON 为对外契约。

## 3. 架构与约定

- **输出即日志**：CLI 的所有“日志”实质是结构化 JSON 事件，由宿主进程（如 AI Agent 宿主）消费 stdout 的 JSON 对象，而非被本地 logger 写入文件或控制台。
- **错误路径**：当出现异常时，代码抛出 `HarnessError`（定义于 `scripts/harness.py` 第 395–412 行），该异常携带 `code`、`exit_code`、`suggested_fix`、`missing_items`、`actual_vs_expected` 等字段，最终由 argparse 顶层捕获并以非零退出码 + stderr 文本返回，不产生结构化日志条目。
- **事件持久化**：运行时产生的事件通过 `append_jsonl`（第 538–543 行）追加到 `events.jsonl`、`context-receipts.jsonl`、`authorization-receipts.jsonl` 等 JSON Lines 文件，这些文件位于 `runtime_root(target)`（`.docs-harness/runs/<task_id>/` 或 `docs-harness/runs/<task_id>/`）。这是仓库中唯一接近“结构化日志落盘”的行为，但它是任务执行产物而非通用日志框架。
- **指纹驱动的可观测性**：大量函数生成 SHA-256 指纹（`file_fingerprint`、`environment_fingerprint`、`document_route_fingerprint`、`package_fingerprint` 等），将运行环境、输入、产物的哈希嵌入 JSON payload，使外部消费者能校验一致性——这替代了传统日志中的“trace id / correlation id”角色。

## 4. 约定与约束

- **禁止使用 `print()` 输出非 JSON 内容到 stdout**：测试始终通过 `capture_output=True` 读取 stdout 并 `json.loads(result.stdout)`，若 stdout 混入非 JSON 文本会直接导致解析失败。因此所有面向宿主的输出必须严格为 JSON。
- **stderr 保留人类可读诊断**：测试断言中多次检查 `result.stderr` 的内容（例如 `self.assertEqual(result.returncode, expected, f"{result.stdout}\n{result.stderr}")`），说明 stderr 是调试与错误提示通道，不应被自动化消费。
- **结构化字段遵循 schema_version 前缀命名空间**：所有持久化的 JSON 事件都带 `schema_version` 字段并使用 `docs-harness/*` 命名空间（如 `docs-harness/event/v2`、`docs-harness/evidence-receipt/v2`、`docs-harness/context-receipt/v2`），这是仓库内事实上的“日志事件 schema”约定。
- **无日志级别概念**：由于没有日志框架，不存在 debug/info/warn/error 分级；所有输出要么是可执行的 JSON 结果，要么是 stderr 错误信息。
- **无集中式 sink 配置**：日志（事件）直接通过 `append_jsonl` 写入目标项目下的 `.docs-harness/runs/<task_id>/` 目录，由文件系统本身充当 sink，无配置文件控制输出目标或格式。

总结：该仓库没有传统日志系统；可观测性通过“JSON 标准输出 + JSON Lines 事件文件 + SHA-256 指纹”的组合实现，由宿主进程消费 stdout 的 JSON 作为主要交互通道，stderr 作为人类可读诊断通道。