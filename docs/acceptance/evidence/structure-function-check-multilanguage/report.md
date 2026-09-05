# Structure 函数级检查扩展到 Go 与 TS/JS 验收证据（2.15.0，2026-09-05）

> 版本重标：本功能 2026-09-05 在本地分支以 2.12.0 号完成开发与验收；该编号后被主线（frontend_ui 模板，2.12.0~2.12.3）占用，合入时重标 2.15.0，下文版本号已同步替换。
>
> 方案：`docs/plans/structure-function-check-multilanguage.md` · 验收：`docs/acceptance/structure-function-check-multilanguage.json` · ADR：`docs/adr/structure-ts-parser-borrowed-from-target.md`

## 改动

- `scripts/structure_check.py`：`function_language` 分派（python/go/ts）、`_go_functions`（gofmt 行级匹配，闭包计入外层，泛型接收者可识别）、`_ts_module_dirs`/`_ts_parser_command`/`_ts_function_spans`（子进程借用目标项目 typescript）、`_collect_function_spans`（按文件批量收集当前与 HEAD 跨度，TS 一次子进程）、`_function_warnings` 改为接收跨度对所有语言同规则；测试文件不做函数级判定；解析器缺失时 .ts/.tsx 出 WARN、纯 JS 记入 `notes`；`structure_report` 新增 `function_check_languages`。
- `scripts/structure_ts_functions.cjs`（新增受管模块）：stdin JSON 源码批 → stdout 函数限定名→行数；声明/方法/变量或属性赋值取名，调用实参匿名函数 `callee#cb`，类方法 `Class.method`，语法诊断非空返回 null。
- `scripts/harness.py`：`MANAGED_MODULE_RELATIVE_FILES` 增加 `.cjs`，`VERSION` 2.15.0；`package.json` files 补录 `script_hygiene.py`、`structure_check.py`（既有遗漏）与 `.cjs`；`tests/harness_test_base.py` MANAGED_MODULES 同步；`tests/test_structure.py` 新增 7 用例。
- 治理：Knowledge `docs-harness-assets-governance` 事实 `structure.guardrails.checker` 更新至 revision 9；新增 ADR；CHANGELOG 2.15.0；`docs/testing.md` 第 10 节；`TODO.md` 登记既有失败用例。

## c1 L1 契约检查

| 命令 | 结果 |
|---|---|
| `python3 scripts/harness.py release sync --target . --strict --json` | consistent（VERSION/controller/skill/package/templates/evals 六处 2.15.0，CHANGELOG 顶部 2.15.0） |
| `python3 scripts/harness.py self-test --target . --json` | passed，2.15.0，checks 全 true |
| `npm pack --dry-run --json` | 49 文件；scripts/ 含 harness.py、7 个 .py 受管模块与 structure_ts_functions.cjs（修复前缺 script_hygiene.py 与 structure_check.py） |
| `python3 scripts/harness.py assets-check --target . --strict --json` | passed，0 failures，0 warnings |
| `python3 scripts/harness.py project check --target . --json` | 无 red/yellow finding（仅 needs_delivery 待提交） |

## c2 L2 聚焦与全量测试

| 命令 | 结果 |
|---|---|
| `DOCS_HARNESS_TS_MODULE_DIR=<zbuddy>/node_modules python3 -m unittest tests.test_structure` | 14 用例通过（含 Go 接收者/闭包/单行/泛型、TS 声明/箭头/类方法/回调/TSX/语法错误、解析器缺失 WARN 与纯 JS notes、Go 增量 WARN 与测试文件豁免、TS 增量与 report） |
| `python3 -m unittest tests.test_structure`（无 typescript） | 12 通过 + 2 skip（skip 原因指明设置 DOCS_HARNESS_TS_MODULE_DIR） |
| `npm test`（全量 111 项，发布触发） | 110 通过，1 error：`test_project_install.test_project_check_flags_non_executable_githook_index_mode` 在 2.11.1 HEAD 干净工作树上同样失败（git 2.50.1 Apple Git-155 下第二次提交 nothing to commit），既有环境相关失败，已登记 TODO，与本次改动无关 |

## c3 L2 下游 zbuddy-desktop 升级

- 下游先恢复 2.11.1 安装版并删除本地补丁副本，再以上游控制器执行 `project upgrade --source <docs-harness> --apply`：预览无 install_conflict，写入 harness.py、structure_check.py、新建 .cjs、受管入口块、8 个模板与 config。
- 升级后：`self-test` passed 2.15.0；`project check` 无 red（两条 yellow 为既有 hooksPath 与根 TODO 格式）；`structure check` 报出 7 条 WARN，含此前漏检的 createAgentStreamRegistry 531 行、registerSmartClawIpc 367 行、registerFilesIpc 184 行、registerAgentIpc 150 行；`assets-check --fast` passed；下游 structure_check.py 与上游逐字一致。

## 未覆盖

- 其他 9 个装有本 harness 的项目尚未升级到 2.15.0。
- Go 解析对未 gofmt 文件的跨度粒度未做真实项目验证（smartclaw 存量报告 68 个 Go 超线函数与此前 go/ast 扫描的 67 个一致，差 1 为方法名归并口径）。
