# TODO

条目格式：`- [ ] 事项（owner，YYYY-MM-DD）`；完成后改为 `- [x]` 并保留在「已完成」。

## 待办

- [ ] `scripts/harness.py` 存量体量债 4800 行（2.16.1 实测）（`project_findings` 266 行、`command_plan_check` 240 行、`command_project` 221 行），每次改动必撞 Structure WARN 使本仓库 `assets-check --strict` 在未提交状态恒退 1；以 `structure report` 开专门整理任务，候选拆分方向：安装/升级编排、plan check、usage 埋点各自成模块（aiware，2026-09-13）

- [ ] usage 事件缺 `source` 字段：`assets-check --fast` 无法区分 pre-commit 触发与手动收尾触发，本次审计只能靠事件时间与 git log 人肉对齐才发现 09-13 以来 8 次提交零钩子事件；建议在 `usage_invoke_event` 加来源标记（kimi，2026-09-14）

## 已完成

- [x] plan check 符号命中 WARN 缺「部分交付但仍有效」第三态：zbuddy-desktop 实测 13 条 plan WARN 中 8 条属于代码已部分交付、文档自述有未完项、plan 合法保持「有效」的情形，WARN 只有 settle/deprecated 两个出口，长期悬挂会淹没真告警；候选方向：plan 侧显式「部分交付已核对」标记并在 check 中豁免；2.18.0 已落地：横幅写「有效-部分交付（YYYY-MM-DD 核对）」后 30 天内不报符号全命中 WARN，过期、非法或未来日期照常报，WARN 文案给出三个出口（kimi，2026-09-14）
- [x] 存量手写 plan 无官方补登路径：zbuddy-desktop 10 个直接落盘的 plan .md 无伴随 .json，`plan settle` 以 `invalid_plan_ref` 拒绝、`plan create` 遇同名 .md 报 `plan_document_conflict`；本次靠手工构造 .json + 补横幅标记完成补登，评估是否提供 `plan register` 类正式命令；2.18.0 已落地：不新增 register 命令，plan settle 直接接受无伴随 JSON 的手写方案，只改横幅与归档、不做治理终验，受管区块外的 INDEX 条目以 warnings 提示手工同步（kimi，2026-09-14）
- [x] `tests/test_project_install.py::test_project_check_flags_non_executable_githook_index_mode` 在本机（git 2.50.1 Apple Git-155，core.filemode=true）于 2.11.1 干净工作树上也失败：第二次 `structure_commit_all` 因 `update-index --chmod=+x` 后索引与 HEAD 一致而 `nothing to commit` 退出 1，说明首个提交已按 100755 入库、用例假设的 100644 现场未出现；2026-08-28 证据记录该用例通过，需核对是 git 版本行为变化还是用例假设依赖平台，与 2.15.0 改动无关；根因（2026-09-15 定位）：用例未钉死基线提交的钩子模式——core.filemode=true 的 macOS 按磁盘可执行位入库 100755，chmod 往返后索引与 HEAD 一致导致二次提交 nothing to commit；0578fef 为此删掉二次提交，又让 core.filemode=false 的 Windows（基线 100644）在 +x 后索引与 HEAD 不一致、project check 回 pending_commit 退 3。修复：用例内 git config core.filemode false 钉死基线为 100644，按真实修复路径 +x 后提交，两平台现场一致；Windows 本机通过，macOS 未实跑（aiware，2026-09-05）
- [x] 受管入口缺并行执行指引且首条措辞反向强化串行：模型无明确提示时不主动开子智能体，独立检索、多文件实现一律串行拉长流程；入口首条「默认由 agent 直接完成」本意是不经 Harness 流程，字面读却像要求主 agent 亲自串行干完，进一步抑制委派；候选方向：工作流规则增第 5 条「并行优先」，按分量分级——单点任务直接做；轻量独立子任务（同时读几个文件、几个独立检索）用同消息并行工具调用，不开子智能体；分支各自够重（多步调研/评审或文件范围不相交的实现）才同消息并行开子智能体，分支不重则 spawn 开销净亏；同一文件修改、共享受管文件更新、有依赖步骤与批次验证门保持串行，并同步消歧首条措辞；模板文案无测试断言耦合，成本主要在发版流程；2.18.0 已落地：入口首条消歧、工作流规则第 4 条重写、新增第 5 条并行优先、第 3 条与结构护栏第 5 条补句、contracts §1 同步、evals 补两条（glm，2026-09-15）
- [x] Structure checker 的「新增代码文件未登记 docs/CODEMAP.md」WARN 对 harness 受管文件误报：2.16.0 升级 10 个下游项目时 suiyi/opc-skills/zbuddy-desktop 均报 `scripts/usage_log.py`、`scripts/usage_report.py`、`scripts/structure_ts_functions.cjs` 未登记，但这些文件由安装器写入、下游 CODEMAP 本不该登记；应在 `_codemap_registration_warnings` 排除 `scripts/harness.py` 与 `MANAGED_MODULE_RELATIVE_FILES`（或由安装器代登记），复现：任一下游 `project upgrade --apply` 后 `structure check`（aiware，2026-09-13）
- [x] `package.json` `files` 含死条目 `tests/test_v2_direct.py`（文件不存在）；2.16.0 新增的守卫 `test_package_files_cover_every_managed_module` 只查受管模块漏项不查死项，需补一条「files 每项都存在」的断言并清理死条目（aiware，2026-09-13）
- [x] `.docs-harness/task-inputs/` 在 `LEGACY_RUNTIME_NAMES` 内会被 `project upgrade` 清理，但 `acceptance record`/`plan create` 等又要求输入 JSON 位于项目内；2.16.0 任务为此三次重建备份，且清理后短暂触发 `legacy_document_system_active`。需要给一次性输入 JSON 一个既在项目内、又不被清理、又不入库的约定位置（aiware，2026-09-13）
- [x] usage_log 在 config v13 默认开启，下游 `project upgrade` 后即开始记录，但升级输出里没有一次性提示，告知只在 CHANGELOG/contracts §9/ADR；评估是否在 upgrade payload 增加一条 `usage_log_enabled_notice`（aiware，2026-09-13）
