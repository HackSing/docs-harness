> 状态：有效（现行决策）
<!-- docs-harness:adr-document/v1 -->

# Structure 的 TS/JS 函数级解析借用目标项目的 typescript 编译器，harness 自身保持零依赖

- 关键符号：`_ts_parser_command`、`_ts_module_dirs`、`TS_PARSER_UNAVAILABLE_WARNING`
- 资产指纹：`sha256:210e5742305b9abe982eb1775b36475194daca634880314c7f9e9ddf5bb85bc6`

## 背景

2.11.0 的结构护栏为保持 harness 纯 Python 零依赖，函数级检查只做 Python；下游 TS/Go 为主的项目（ZBuddy）因此对 500 行级别的 TS 函数完全失明，assets-check 全绿。备选：Python 侧括号匹配启发式（模板串/正则/JSX 误判会摧毁 WARN 可信度）、给 harness 打包 tree-sitter 或 typescript（违背零依赖分发）、经子进程借用目标项目 node_modules 里已有的 typescript 编译器。

## 决策

采用子进程借用：scripts/structure_ts_functions.cjs 在目标项目的 node_modules（或 */node_modules、DOCS_HARNESS_TS_MODULE_DIR 指定目录）里加载 typescript 解析源码，Python 侧只经 _ts_function_spans 一处调用；node 或 typescript 缺失时降级为文件级检查并输出 TS_PARSER_UNAVAILABLE_WARNING，不静默。Go 采用 gofmt 约定的行级匹配而不引入 go 工具链子进程。

## 影响

收益：TS/JS 函数级解析精确、harness 包不新增任何依赖、下游零配置生效；代价：TS 函数级检查依赖目标项目环境，缺失时只剩文件级；Go 启发式对未 gofmt 文件只影响预警粒度；回调按 callee#cb 命名，增长比对为尽力而为。
