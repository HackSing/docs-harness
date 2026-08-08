---
kind: error_handling
name: 统一 HarnessError 异常与 CLI 错误响应体系
category: error_handling
scope:
    - '**'
source_files:
    - scripts/harness.py
    - tests/test_harness.py
---

## 1. 采用的系统/方法

该仓库采用**单一自定义异常类型 + 顶层集中捕获**的错误处理模式，核心是 `scripts/harness.py` 中定义的 `HarnessError(Exception)`。所有业务校验、I/O 失败、Git 预检失败、JSON 解析错误等都被统一包装为 `HarnessError`，由 `main()` 函数在入口层统一捕获并输出结构化 JSON 错误响应，最后通过 `SystemExit(exit_code)` 返回进程退出码。

没有使用 Python 标准库的 `logging` 模块作为错误通道，也没有 `try/except` 分散式日志记录；错误信息通过异常携带并在顶层序列化后由 `emit()` 输出（支持 `--json` 开关）。未使用 `panic/recover`（Python 无此概念），也未定义其他业务异常类。

## 2. 关键文件与位置

- **`scripts/harness.py`**：唯一承载错误体系的源文件，包含 `HarnessError` 类定义（第 395–412 行）、各子命令中的 `raise HarnessError(...)` 调用点、以及 `main()` 中的顶层捕获（第 11520–11529 行）。
- **`tests/test_harness.py`**：通过 `assertRaises(HARNESS_MODULE.HarnessError)` 断言各类错误路径，验证 `code`、`exit_code`、`suggested_fix`、`missing_items`、`actual_vs_expected` 等字段是否按契约填充。

## 3. 架构与约定

### 3.1 `HarnessError` 数据结构

```python
class HarnessError(Exception):
    def __init__(self, message: str,
                 *, code: str = "invalid_request",
                 exit_code: int = 2,
                 suggested_fix: str | None = None,
                 missing_items: list[dict[str, Any]] | None = None,
                 actual_vs_expected: dict[str, Any] | None = None):
```

每个错误实例固定携带以下字段：
- `code`：机器可读的错误码（如 `missing_file`、`invalid_json`、`unsafe_target`、`git_preflight_timeout`、`invalid_task_id` 等），用于下游判断错误类别。
- `exit_code`：默认 2（参数/请求错误），Git 相关错误统一使用 3（运行时/外部依赖错误）。
- `suggested_fix`：面向用户的修复建议字符串，可选。
- `missing_items`：缺失项清单，可选。
- `actual_vs_expected`：实际值与期望值的对比字典，可选。

### 3.2 错误抛出位置与分类

| 场景 | 示例错误码 | 说明 |
|---|---|---|
| 文件 I/O | `missing_file`、`invalid_json` | `read_json()` 捕获 `FileNotFoundError` / `json.JSONDecodeError` |
| 输入校验 | `inline_input_not_supported`、`invalid_task_id` | `load_input_file()`、`validate_task_id()` |
| 安全限制 | `unsafe_target` | 拒绝根目录/用户主目录作为目标 |
| Git 预检 | `git_preflight_timeout`、`git_remote_unavailable`、`git_scope_required`、`invalid_git_scope`、`git_sync_scope_ambiguous`、`git_target_object_missing` | `git_command()` 超时、`git_scope_target()`、`git_preflight_contract()` |
| 状态校验 | `invalid_state` | JSONL 事件文件每行非对象或解析失败 |
| 任务/证据 | `missing_evidence`、`missing_work_package` | 子命令参数缺失 |

### 3.3 顶层捕获与响应格式

`main()` 中唯一的 `except HarnessError as exc:` 块将异常转换为如下 JSON 结构：

```json
{
  "status": "error",
  "code": "...",
  "message": "...",
  "suggested_fix": "...",   // 可选
  "missing_items": [...],   // 可选
  "actual_vs_expected": {...} // 可选
}
```

并通过 `emit(error_payload, args.json)` 输出，然后 `return exc.exit_code` 设置进程退出码。非 `HarnessError` 的未捕获异常会直接以 Python traceback 形式崩溃，表明仓库**要求所有可预期错误必须显式 raise HarnessError**。

### 3.4 中间层吞错策略

部分辅助函数（如 `git_preflight_contract`、`git_postcheck`）内部捕获 `HarnessError` 并将其降级为结构化结果（例如 `{"passed": False, "reason_code": exc.code, ...}`），以便上层流程继续执行后续检查而非立即终止。这是“局部容错 + 聚合报告”的模式，与顶层“统一报错”形成互补。

## 4. 约定与约束

- **所有可预期错误必须通过 `raise HarnessError(...)` 抛出**，禁止直接 `raise Exception` 或裸 `raise`。测试用例通过 `assertRaises(HarnessError)` 覆盖大量分支，构成事实上的强制约束。
- **错误码必须使用小写下划线风格**（如 `git_preflight_timeout`、`invalid_task_id`），且需具备机器可读性，供宿主方根据 `code` 做差异化处理。
- **Git 相关错误统一使用 `exit_code=3`**，普通参数/校验错误使用默认 `exit_code=2`，便于调用方区分错误层级。
- **用户提示必须通过 `suggested_fix` 提供**：当错误涉及路径/平台差异（如 Windows Git Bash 路径问题）时，必须附带可操作的修复建议，测试中明确断言 `suggested_fix` 存在。
- **JSON 解析/结构错误必须附带 `actual_vs_expected`**：用于向宿主展示“实际收到什么 vs 期望什么”，测试覆盖了证据格式错误的断言。
- **缺失项必须通过 `missing_items` 描述**：当输入缺少必要字段时，需提供结构化缺失清单。
- **不可预期的系统异常不应被吞掉**：只有明确标注的辅助函数（preflight/postcheck）才捕获 `HarnessError` 并转为结果；其余位置应让异常冒泡至 `main()`。
- **错误消息使用中文**：所有 `HarnessError` 的 `message` 均为人类可读的中文描述，配合英文 `code` 实现人机双读。

## 5. 适用性判定

本仓库是一个单文件 Python CLI（`scripts/harness.py`），错误处理完全集中在该文件中，通过统一的 `HarnessError` 异常类型和 `main()` 顶层捕获实现。虽然代码体量较大（~11500 行），但错误模型简单清晰、贯穿所有子命令，属于典型的“单一异常 + 集中出口”模式，因此本类别完全适用。