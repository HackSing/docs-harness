# TODO

条目格式：`- [ ] 事项（owner，YYYY-MM-DD）`；完成后改为 `- [x]` 并保留在「已完成」。

## 待办

- [ ] Structure checker 的「新增代码文件未登记 docs/CODEMAP.md」WARN 对 harness 受管文件误报：2.16.0 升级 10 个下游项目时 suiyi/opc-skills/zbuddy-desktop 均报 `scripts/usage_log.py`、`scripts/usage_report.py`、`scripts/structure_ts_functions.cjs` 未登记，但这些文件由安装器写入、下游 CODEMAP 本不该登记；应在 `_codemap_registration_warnings` 排除 `scripts/harness.py` 与 `MANAGED_MODULE_RELATIVE_FILES`（或由安装器代登记），复现：任一下游 `project upgrade --apply` 后 `structure check`（aiware，2026-09-13）
- [ ] `package.json` `files` 含死条目 `tests/test_v2_direct.py`（文件不存在）；2.16.0 新增的守卫 `test_package_files_cover_every_managed_module` 只查受管模块漏项不查死项，需补一条「files 每项都存在」的断言并清理死条目（aiware，2026-09-13）
- [ ] `.docs-harness/task-inputs/` 在 `LEGACY_RUNTIME_NAMES` 内会被 `project upgrade` 清理，但 `acceptance record`/`plan create` 等又要求输入 JSON 位于项目内；2.16.0 任务为此三次重建备份，且清理后短暂触发 `legacy_document_system_active`。需要给一次性输入 JSON 一个既在项目内、又不被清理、又不入库的约定位置（aiware，2026-09-13）
- [ ] usage_log 在 config v13 默认开启，下游 `project upgrade` 后即开始记录，但升级输出里没有一次性提示，告知只在 CHANGELOG/contracts §9/ADR；评估是否在 upgrade payload 增加一条 `usage_log_enabled_notice`（aiware，2026-09-13）
- [ ] `scripts/harness.py` 存量体量债 4674 行（`project_findings` 266 行、`command_plan_check` 240 行、`command_project` 217 行），每次改动必撞 Structure WARN 使本仓库 `assets-check --strict` 在未提交状态恒退 1；以 `structure report` 开专门整理任务，候选拆分方向：安装/升级编排、plan check、usage 埋点各自成模块（aiware，2026-09-13）
- [ ] `tests/test_project_install.py::test_project_check_flags_non_executable_githook_index_mode` 在本机（git 2.50.1 Apple Git-155，core.filemode=true）于 2.11.1 干净工作树上也失败：第二次 `structure_commit_all` 因 `update-index --chmod=+x` 后索引与 HEAD 一致而 `nothing to commit` 退出 1，说明首个提交已按 100755 入库、用例假设的 100644 现场未出现；2026-08-28 证据记录该用例通过，需核对是 git 版本行为变化还是用例假设依赖平台，与 2.15.0 改动无关（aiware，2026-09-05）

## 已完成
