# TODO

条目格式：`- [ ] 事项（owner，YYYY-MM-DD）`；完成后改为 `- [x]` 并保留在「已完成」。

## 待办

- [ ] `tests/test_project_install.py::test_project_check_flags_non_executable_githook_index_mode` 在本机（git 2.50.1 Apple Git-155，core.filemode=true）于 2.11.1 干净工作树上也失败：第二次 `structure_commit_all` 因 `update-index --chmod=+x` 后索引与 HEAD 一致而 `nothing to commit` 退出 1，说明首个提交已按 100755 入库、用例假设的 100644 现场未出现；2026-08-28 证据记录该用例通过，需核对是 git 版本行为变化还是用例假设依赖平台，与 2.15.0 改动无关（aiware，2026-09-05）

## 已完成
