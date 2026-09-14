# TODO

条目格式：`- [ ] 事项（owner，YYYY-MM-DD）`；完成后改为 `- [x]` 并保留在「已完成」。

## 待办

- [ ] `scripts/harness.py` 存量体量债 4800 行（2.16.1 实测）（`project_findings` 266 行、`command_plan_check` 240 行、`command_project` 221 行），每次改动必撞 Structure WARN 使本仓库 `assets-check --strict` 在未提交状态恒退 1；以 `structure report` 开专门整理任务，候选拆分方向：安装/升级编排、plan check、usage 埋点各自成模块（aiware，2026-09-13）
- [ ] `tests/test_project_install.py::test_project_check_flags_non_executable_githook_index_mode` 在本机（git 2.50.1 Apple Git-155，core.filemode=true）于 2.11.1 干净工作树上也失败：第二次 `structure_commit_all` 因 `update-index --chmod=+x` 后索引与 HEAD 一致而 `nothing to commit` 退出 1，说明首个提交已按 100755 入库、用例假设的 100644 现场未出现；2026-08-28 证据记录该用例通过，需核对是 git 版本行为变化还是用例假设依赖平台，与 2.15.0 改动无关（aiware，2026-09-05）

- [ ] plan check 符号命中 WARN 缺「部分交付但仍有效」第三态：zbuddy-desktop 实测 13 条 plan WARN 中 8 条属于代码已部分交付、文档自述有未完项、plan 合法保持「有效」的情形，WARN 只有 settle/deprecated 两个出口，长期悬挂会淹没真告警；候选方向：plan 侧显式「部分交付已核对」标记并在 check 中豁免（kimi，2026-09-14）
- [ ] usage 事件缺 `source` 字段：`assets-check --fast` 无法区分 pre-commit 触发与手动收尾触发，本次审计只能靠事件时间与 git log 人肉对齐才发现 09-13 以来 8 次提交零钩子事件；建议在 `usage_invoke_event` 加来源标记（kimi，2026-09-14）
- [ ] 存量手写 plan 无官方补登路径：zbuddy-desktop 10 个直接落盘的 plan .md 无伴随 .json，`plan settle` 以 `invalid_plan_ref` 拒绝、`plan create` 遇同名 .md 报 `plan_document_conflict`；本次靠手工构造 .json + 补横幅标记完成补登，评估是否提供 `plan register` 类正式命令（kimi，2026-09-14）

## 已完成

- [x] Structure checker 的「新增代码文件未登记 docs/CODEMAP.md」WARN 对 harness 受管文件误报：2.16.0 升级 10 个下游项目时 suiyi/opc-skills/zbuddy-desktop 均报 `scripts/usage_log.py`、`scripts/usage_report.py`、`scripts/structure_ts_functions.cjs` 未登记，但这些文件由安装器写入、下游 CODEMAP 本不该登记；应在 `_codemap_registration_warnings` 排除 `scripts/harness.py` 与 `MANAGED_MODULE_RELATIVE_FILES`（或由安装器代登记），复现：任一下游 `project upgrade --apply` 后 `structure check`（aiware，2026-09-13）
- [x] `package.json` `files` 含死条目 `tests/test_v2_direct.py`（文件不存在）；2.16.0 新增的守卫 `test_package_files_cover_every_managed_module` 只查受管模块漏项不查死项，需补一条「files 每项都存在」的断言并清理死条目（aiware，2026-09-13）
- [x] `.docs-harness/task-inputs/` 在 `LEGACY_RUNTIME_NAMES` 内会被 `project upgrade` 清理，但 `acceptance record`/`plan create` 等又要求输入 JSON 位于项目内；2.16.0 任务为此三次重建备份，且清理后短暂触发 `legacy_document_system_active`。需要给一次性输入 JSON 一个既在项目内、又不被清理、又不入库的约定位置（aiware，2026-09-13）
- [x] usage_log 在 config v13 默认开启，下游 `project upgrade` 后即开始记录，但升级输出里没有一次性提示，告知只在 CHANGELOG/contracts §9/ADR；评估是否在 upgrade payload 增加一条 `usage_log_enabled_notice`（aiware，2026-09-13）
