---
kind: logging_system
name: 日志系统 — 基于标准输出与结构化 JSON 的 CLI 输出机制
category: logging_system
scope:
    - '**'
source_files:
    - scripts/harness.py
---

该仓库未使用任何第三方日志框架（如 Python `logging`、`loguru`、`structlog` 等），也没有独立的日志模块或配置文件。整个 Docs Harness 的“日志”行为完全由单一入口脚本 `scripts/harness.py` 中的 `emit()` 函数承担，通过标准输出 `print()` 以两种格式向外暴露：

1. **JSON 模式**（`--json` 标志）：所有命令执行结果以 `json.dumps(payload, ensure_ascii=False, indent=2)` 输出为结构化的 JSON 对象，包含 `status`、`code`、`message`、`task_id`、`next_action`、`reason_code` 等字段，供宿主程序解析。
2. **人类可读模式**：逐行打印 `key: value` 形式，其中 dict/list 类型会再次序列化为 JSON 字符串。

错误处理统一通过自定义异常 `HarnessError` 捕获，在 `main()` 中转换为 `{"status": "error", "code": exc.code, "message": str(exc)}` 并通过 `emit()` 输出，同时返回对应的 `exit_code`（默认 2）。这意味着：**所有对外可见的输出都经过 `emit()` 单点出口，没有分散的 `print`/`sys.stderr.write` 调用**。

该实现遵循以下约定：
- 无日志级别概念（INFO/WARN/ERROR 等），仅区分成功 payload 与错误 payload；
- 无文件日志、无控制台颜色、无异步写入；
- 所有诊断信息均内嵌于结构化 payload 的字段中（如 `reason_code`、`checks`、`changed_refs` 等）；
- 调试信息通过扩展 payload 字段传递，而非独立日志流。

由于这是一个纯 CLI 工具且被宿主进程直接调用，其设计目标是提供可机器解析的结构化输出，而非传统意义上的“日志记录”。