---
kind: error_handling
name: Docs Harness 错误处理体系：结构化异常与统一退出码
category: error_handling
scope:
    - '**'
source_files:
    - scripts/harness.py
    - tests/test_harness.py
---

## 1. 系统/方法概述
- 采用单一自定义异常类 `HarnessError`（继承自 Python 内置 `Exception`）作为全仓库统一的错误载体，所有业务校验失败、I/O 异常、外部命令超时等路径均通过 raise HarnessError(...) 抛出。
- CLI 入口 `main()` 使用 try/except HarnessError 集中捕获，将错误以 JSON 结构 `{status: "error", code, message}` 输出到 stdout，并返回对应的 `exit_code`，由 `raise SystemExit(main())` 驱动进程退出码。
- 错误分类通过 `code` 字段表达（如 `missing_file`、`invalid_json`、`git_preflight_timeout`、`unsafe_target`、`invalid_task_id`、`missing_work_package`、`missing_evidence` 等），并由调用方（测试与上层宿主）依据 code 做决策。
- 对可恢复的 I/O 或子进程异常，在工具函数内部捕获并包装为 `HarnessError`，保留原始异常链（`from exc`），便于调试。

## 2. 关键文件与位置
- `scripts/harness.py`：定义 `class HarnessError(Exception)`（含 `code`、`exit_code` 属性），并在大量输入校验、JSON 解析、Git 操作、任务状态读取处 raise；`main()` 中唯一 except HarnessError 分支负责统一输出与退出码。
- `tests/test_harness.py`：通过 `expected=...` 断言不同场景下的 exit_code 与 payload.code，覆盖 missing_file、invalid_json、git_remote_drift、high_risk_drift、unattributed_drift_overlap 等多种错误码路径。

## 3. 架构与约定
- 异常传播模型：底层工具函数（如 `read_json`、`load_input_file`、`git_command`、`safe_target`、`validate_task_id` 等）只抛 `HarnessError`，不吞异常；上层命令函数（command_run/command_context/command_verify 等）直接向上抛出，由 `main()` 统一收敛。
- 错误载荷结构：CLI 正常路径返回 `{status, ...}` 字典；错误路径返回 `{status: "error", code, message}`，并通过 `emit()` 以 JSON 或 key-value 形式打印。
- 退出码约定：`exit_code` 默认 2（参数/校验错误），部分 Git 预检失败使用 3，特定阻塞场景（如 git_remote_drift、high_risk_drift）在测试中被断言为 4，体现“失败关闭”策略。
- 原因码集合：代码内维护多组受限的原因码常量集（如 `KNOWN_LIMIT_CODES`、`TASK_DISPOSITION_REASON_CODES`、`BACKGROUND_TERMINAL_STATES`、`DELIVERY_LAYER_LIMIT_CODES` 等），错误码与领域语义一一对应，避免自由文本扩散。
- 无 panic/recover 模式：Python 侧未使用 `try/finally` 外的 recover 机制，所有异常均通过显式 raise + 顶层捕获处理。

## 4. 约定与约束（基于代码实现观察到的行为）
- 所有业务错误必须通过 `HarnessError` 抛出，且必须提供有意义的 `code` 字符串，以便调用方区分错误类型。
- 需要非零退出码的场景应在 `exit_code` 中显式指定（例如 Git 超时/预检失败使用 3，某些验证阻塞使用 4）。
- 输入校验失败（缺失文件、无效 JSON、非法 task-id、不安全目标目录、内联输入不支持等）一律转为 `HarnessError` 并返回对应 code。
- 外部命令（subprocess）异常被捕获后包装为 `HarnessError`，保留原始异常链，确保可追溯性。
- CLI 层不自行打印日志或堆栈，仅输出结构化 JSON 负载，保证机器可消费。
- 测试通过断言 `result.returncode` 与 `payload["code"]` 来强制约束错误路径的行为一致性。