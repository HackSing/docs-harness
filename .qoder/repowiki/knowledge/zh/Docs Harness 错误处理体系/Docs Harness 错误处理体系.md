---
kind: error_handling
name: Docs Harness 错误处理体系
category: error_handling
scope:
    - '**'
source_files:
    - scripts/harness.py
---

### 1. 系统/方法
Docs Harness 采用单一自定义异常类加结构化错误码的 Python 错误处理模式，所有业务错误统一通过 HarnessError 抛出，由顶层 main() 捕获并转换为统一的 JSON 响应。没有使用中间件、panic/recover 或第三方错误库。

### 2. 核心文件与包
- scripts/harness.py：唯一包含错误定义与处理的文件（约 10360 行），集中了 HarnessError 类、所有输入校验函数、Git 预检/后检查的错误转换，以及 main() 中的全局异常捕获。

### 3. 架构与约定
- 统一异常类型：class HarnessError(Exception)（第 392 行）携带三个字段：message: str（人类可读的错误描述，中文）、code: str（机器可读的错误码，默认 invalid_request）、exit_code: int（进程退出码，默认 2，部分场景覆盖为 3，如 Git 超时、Git 操作失败）
- 错误传播链：底层 I/O 函数（read_json、load_input_file、load_json_object_file、read_jsonl、safe_target、git_command 等）将 FileNotFoundError、json.JSONDecodeError、OSError、subprocess.TimeoutExpired 等原生异常包装为 HarnessError，并使用 from exc 保留原始异常链。
- 顶层捕获与输出：main()（第 10322 行）在 try/except HarnessError 中统一捕获，调用 emit({"status": "error", "code": exc.code, "message": str(exc)}, args.json) 输出结构化 JSON，并通过 return exc.exit_code 设置进程退出码。
- 错误码分类：代码中定义了多组受控错误码集合，包括 KNOWN_LIMIT_CODES、TASK_DISPOSITION_REASON_CODES、BACKGROUND_REASON_CODE_RE（正则约束格式 ^[a-z][a-z0-9_]{0,63}$）、DELIVERY_LAYER_LIMIT_CODES 等，确保错误码可枚举、可校验。
- 无中间件：错误处理不依赖中间件层，而是通过函数式封装（每个 IO/Git 操作函数内部 try/except 转换）和入口点统一捕获实现。

### 4. 约定与约束
- 所有业务错误必须通过 raise HarnessError(...) 抛出，禁止直接 sys.exit() 或打印错误信息。
- 错误码必须为小写字母、数字、下划线组成的字符串，且长度不超过 64（由 BACKGROUND_REASON_CODE_RE 及代码中各处赋值约定）。
- JSON 输入验证失败统一返回 invalid_json、invalid_state、inline_input_not_supported 等语义化错误码。
- 文件/路径相关错误统一映射为 missing_file、unsafe_target、missing_target 等，避免泄露具体路径细节。
- Git 操作失败统一映射为 git_preflight_timeout、git_preflight_failed、git_remote_unavailable、git_remote_ref_missing、git_scope_required、invalid_git_scope、git_sync_scope_ambiguous、git_target_object_missing 等，退出码固定为 3。
- 异常链保留：所有 raise HarnessError(...) from exc 形式确保原始异常可追溯，便于调试。
- CLI 入口统一出口：if __name__ == "__main__": raise SystemExit(main()) 保证所有错误路径都经过 main() 的 emit 输出，不会绕过错误处理。