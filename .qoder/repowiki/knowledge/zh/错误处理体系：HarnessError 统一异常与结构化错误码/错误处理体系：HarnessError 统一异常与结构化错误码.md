---
kind: error_handling
name: 错误处理体系：HarnessError 统一异常与结构化错误码
category: error_handling
scope:
    - '**'
source_files:
    - scripts/harness.py
    - tests/test_harness.py
---

该仓库采用集中式 Python 异常类 `HarnessError` 作为统一的错误处理机制，所有 CLI 命令和内部函数均通过抛出此异常来传递错误信息、错误码和退出码，测试层通过子进程调用并解析 JSON 输出进行断言验证。

**核心异常类型与结构**
- `HarnessError(Exception)` 定义于 `scripts/harness.py:395`，构造函数接受 `message`、`code`（默认 `invalid_request`）、`exit_code`（默认 2）、`suggested_fix`、`missing_items`、`actual_vs_expected` 等参数，用于携带结构化错误上下文。
- 错误码采用小写下划线命名约定，如 `missing_file`、`invalid_json`、`inline_input_not_supported`、`git_preflight_timeout`、`git_remote_unavailable`、`unsafe_target`、`invalid_task_id` 等，覆盖文件操作、JSON 解析、Git 预检、输入校验等场景。
- 退出码语义化：2 表示请求/参数错误，3 表示 Git 相关错误，4 表示验证失败（见测试中 `expected=4` 的使用）。

**错误传播模式**
- 底层 IO 函数（`read_json`、`load_input_file`、`load_json_object_file`、`read_jsonl`）捕获 `FileNotFoundError`、`json.JSONDecodeError`、`OSError`、`UnicodeError`、`ValueError` 等原生异常，包装为 `HarnessError` 后重新抛出，使用 `from exc` 保留原始异常链。
- 工具函数（`safe_target`、`validate_task_id`、`git_command` 等）直接构造并抛出 `HarnessError`，不依赖 try/except 包裹。
- 高层逻辑（如 `git_preflight_contract`）在 except HarnessError 分支中将错误转换为结构化 reason_code 列表返回，实现“异常转数据”的契约式错误传播。

**错误分类与约束**
- 已知限制码集合 `KNOWN_LIMIT_CODES`、`TASK_DISPOSITION_REASON_CODES`、`DELIVERY_LAYER_LIMIT_CODES` 等常量字典定义了受控的错误原因空间，防止随意新增未记录的原因码。
- 输入校验错误（如 `looks_like_inline_input`、`load_input_file`）区分“内联内容不支持”和“文件不存在/过大”等不同语义，提供精确的 `error_code`。
- Git 操作错误统一通过 `git_command` 封装，超时返回 exit_code=3 的 `git_preflight_timeout`，其他失败通过 `HarnessError` 传递具体原因。

**测试覆盖策略**
- `tests/test_harness.py` 通过 `subprocess.run(..., expected=N)` 断言退出码，并通过解析 stdout JSON 中的 `code`、`reason_code`、`result` 等字段验证错误路径。
- 测试覆盖了 missing_file、invalid_json、git_remote_drift、high_risk_drift、unattributed_drift_overlap、read_set_drift 等多种错误场景，确保错误码与用户提示的一致性。

**设计决策**
- 不使用 Python 标准库的 `logging` 模块或第三方错误框架，保持单文件脚本的简洁性。
- 不依赖 `try/except` 全局捕获，而是显式在每个可能失败的函数入口处转换异常，保证错误可追踪。
- 错误消息使用中文描述，便于开发者快速定位问题；同时提供 `suggested_fix` 字段指导修复。
- 通过 `--json` 标志统一输出结构化结果，CLI 层不直接打印人类可读错误，由上层宿主负责格式化展示。