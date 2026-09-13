> 状态：已实施-仅追溯（代码已是真源，2026-09-13 核对）
<!-- docs-harness:plan-document/v1 -->

# 本地 Usage Log 与 Usage Report 观测能力

- 冻结合同：`sha256:06261c5598a84c5dde0add8ef1c63c2f8d716f391c3175d7d51c0c39ddbb17ef`
- 关键符号：`usage_log`、`append_event`、`build_report`、`USAGE_SCHEMA_VERSION`

## 背景

Docs Harness 2.x 已扩到 9 个一级命令、20 余个 action，但哪些命令真的被用上、哪些只活在文档里，目前没有任何事实来源。3.0 决定砍哪些能力时只能靠印象。本方案补上这份事实：一份不外发的本地命令调用日志，加一个只读聚合出口。

## 目标

为维护者提供各 harness 能力的采纳度与资产生命周期健康的本地证据，供判断哪些能力值得保留、简化或移除。两件交付物：(1) 本地 append-only 命令调用日志 .docs-harness/usage/YYYY-MM.jsonl，不遥测、不外发、不入库；(2) 只读出口 harness usage report，把日志聚合成命令采纳度与生命周期计数。跨仓库汇总路径唯一且显式：维护者在各仓库分别运行 usage report --json 后手工合并，harness 不做任何外发、不做跨仓库读取、不提供聚合服务。

## 非目标

- 不做任何外发：无网络、无遥测、无自动提交。
- 不做第二道门禁：日志是旁路观察，任何命令不得因日志内容或日志写入失败改变行为或退出码。
- 不监控默认直跑的普通任务：只覆盖 harness 自身命令面，不记录 agent 的其他工作。
- 不记自由文本：不记 query 原文、不记路径、不记资产名，只记枚举值与计数。
- 不记 argparse 参数错误：parser.parse_args() 在埋点作用域之外，命令行参数非法时 argparse 直接 SystemExit(2)，该类调用不产生事件。接受这一盲点，不为采集它重构参数解析。
- 不记未捕获异常：非 HarnessError 的崩溃不产生事件，也不加 try/finally 兜底——崩溃是 bug，不是使用。
- 不出方向性判断：report 只出数字。默认直跑哲学下多数任务本就不该走 plan，把低调用率印成缺陷是错的，解读留给维护者。
- 不做知识新鲜度指标：属知识质量检查，归 knowledge check，另开任务。
- 不做 CODEMAP 覆盖指标：structure_report 的 unregistered_files 与 dead_entry_warnings 已有实现，再算一遍违反先复用。
- 不新增文本渲染器：usage report 的输出契约完全沿用 structure report，呈现交给既有 emit()。
- 不改动 managed_assets.py / asset_checks.py / knowledge_assets.py / acceptance_assets.py 四个受管模块。
- usage report 不进受管入口模板 _managed_content：它是给维护者看的，不是 agent 工作流步骤，进模板会改动所有下游项目受管区块指纹。

## 成功标准

- 埋点只存在于 scripts/harness.py 的 main() 一处；四个既有受管模块 managed_assets.py / asset_checks.py / knowledge_assets.py / acceptance_assets.py 的 diff 为空，下游 upgrade 时这四个模块指纹不变。
- cmd.invoke 事件字段完整：v、ts、event、command、action、exit_code、duration_ms、flags（白名单 status/reaccept/dry_run/strict/fast/user_confirmed）、hits、failures、warnings；推导不出的字段不写键，不写 null。
- git check-ignore .docs-harness/usage/<YYYY-MM>.jsonl 命中，且用户根 .gitignore 的 diff 为空。
- 无 config.json、usage_log.enabled=false、usage 目录只读三种情况下，所有命令退出码与埋点前完全一致，且零日志写入。
- project init 产出 config schema_version=docs-harness/project-config/v13 且含 usage_log 键；project upgrade --apply 从 v12 单向迁移到 v13 并沿用既有 enabled 值；project check 零 finding；project uninstall 删除两个新模块。
- usage report 与 usage report --json 输出 A-F 六组计数，与手工计数逐项相符；非 json 模式经既有 emit() 按 key: value 输出，payload 含 summary 与 limitations 两个字符串键；恒退出 0。
- 全量 python3 -m unittest discover -s tests -p test_*.py 全绿；self-test status=passed；assets-check --strict 除预期 Structure WARN 外无 FAIL。

## 执行范围

- 新增 scripts/usage_log.py（受管模块）：事件追加、读取、enabled 开关。
- 新增 scripts/usage_report.py（受管模块）：事件聚合，不含渲染。
- 修改 scripts/harness.py：main() 埋点、usage 子解析器与 command_usage、MANAGED_MODULE_RELATIVE_FILES、CONFIG_SCHEMA v13、KNOWN_LEGACY_CONFIG_SCHEMAS range(1,13)、v2_config 新增 usage_log 键、project_findings 新增 usage_log_invalid、command_self_test 命令名元组、import time。
- 新增 tests/test_usage.py（unittest 模式，跟随 tests/harness_test_base.py）。
- 修改 tests/harness_test_base.py：MANAGED_MODULES 加两个新模块、CURRENT_CONFIG_KEYS 加 usage_log。
- 修改 tests/test_project_install.py:88 与 tests/test_project_upgrade.py:178,309：三处硬编码 docs-harness/project-config/v12 字面量升 v13。
- 修改 tests/test_cli_surface.py：public_commands 集合加 usage。
- 修改 docs/CODEMAP.md、docs/contracts.md、CHANGELOG.md；新建一条 usage 观测 Knowledge 资产。
- 范围外：不改任何既有受管模块、不改安装器对用户根 .gitignore 的行为（本就没有）、不改 _managed_content 受管入口模板、不重构 harness.py 存量体量债。

## 执行内容

- 批 1｜基座与埋点：新建 scripts/usage_log.py 与 scripts/usage_report.py 的接口骨架（后者批 1 只落 docstring 与空实现签名，满足安装面指纹校验，符合骨架先行）；harness.py 加 import time、main() 埋点（事件构造抽成模块级私有函数，main() 净增 ≤ 9 行——现为 57 行，增长 ≥10 即触发 FUNC_GROWTH_ALERT）；安装面 MANAGED_MODULE_RELATIVE_FILES 追加两个模块、CONFIG_SCHEMA 升 v13、KNOWN_LEGACY_CONFIG_SCHEMAS 扩到 range(1,13)、v2_config 增 usage_log 键（默认取 usage_log.USAGE_LOG_DEFAULT_ENABLED，升级沿用既有布尔值，复用该函数既有 docs_flag 写法）、project_findings 增 usage_log_invalid；测试面 harness_test_base.MANAGED_MODULES 与 CURRENT_CONFIG_KEYS、三处 v12 字面量；tests/test_usage.py 的 log 部分（含 L4 四个降级场景）。验证点：python3 -m unittest tests.test_usage tests.test_project_install tests.test_project_upgrade tests.test_cli_surface；self-test；structure check。改完验证锁定再进下一批。
- 批 2｜report：填充 scripts/usage_report.py 的 build_report 实现；harness.py 加 usage 子解析器与 command_usage（恒退出 0）、command_self_test 命令名元组加 usage（该项与 usage 子解析器同批，先加会让 self-test 红）；test_cli_surface.py 的 public_commands 加 usage；tests/test_usage.py 的 report 部分；运行层验收（scratch 项目真实命令序列 + usage report 双格式输出 + git check-ignore 命中）。验证点：全量 unittest discover。改完验证锁定再进下一批。
- 批 3｜文档收尾：docs/CODEMAP.md 登记两个新模块；docs/contracts.md 补 usage 观测合同（事件 schema、config v13 的 usage_log 键、usage report 命令契约、不外发边界）；CHANGELOG.md 登记用户可见新命令与安装面变化；新建 usage 观测 Knowledge 资产并 knowledge check；acceptance settle；plan settle --status implemented --governance-input（knowledge_impact=updated，附新建 Knowledge 引用）。验证点：assets-check --strict；plan check。
- 三批均不含不可逆动作：不删用户文件、不改用户根 .gitignore、不改既有受管模块。

## 模块划分与接口骨架

- scripts/usage_log.py（新增受管模块）— 职责：本地 usage 事件的追加与读取，以及 usage_log.enabled 开关读取，不含任何聚合逻辑。公开接口：USAGE_SCHEMA_VERSION = 'docs-harness/usage-event/v1'；USAGE_DIR_RELATIVE = '.docs-harness/usage'；USAGE_LOG_DEFAULT_ENABLED = True（业务默认值单一来源，harness.v2_config 写 config 时导入本常量）；is_enabled(target: Path) -> bool；append_event(target: Path, event: dict[str, Any]) -> bool；read_events(target: Path, days: int) -> list[dict[str, Any]]。
- usage_log.is_enabled 契约：读 <target>/.docs-harness/config.json，当且仅当 config['usage_log']['enabled'] is True 返回 True；文件不存在、非 JSON、非对象、键缺失、值非 True 一律 False。没安装就没有观测面，不做任何 fallback 默认。不复用 harness.project_config()，因为受管模块不能反向 import harness.py（循环），且 project_config() 在非对象时抛 HarnessError，与观察路径永不抛出的契约冲突；重复的只是一次三行 json 读取，不是逻辑。求值时刻是记录时刻，即命令执行完成之后：因此 project init 与 project upgrade --apply 产出 v13 config 后，会把自己记为该项目的第一条事件。
- usage_log.append_event 契约：best-effort，成功 True、写入失败 False，不抛出。这是对编码质量规范第 6 条错误不许吞的显式豁免，理由写进模块 docstring：附属观察路径不得卡断主命令。豁免范围收窄为只捕 OSError 与 UnicodeEncodeError，不捕裸 Exception，与仓库既有先例 harness.cache_plan_selection() 同口径。追加写用 open(..., 'a', encoding='utf-8', newline='\n') 单行写入，依赖 O_APPEND 对小行的原子性，不做锁；Windows 上该原子性不成立，并发场景仅 pre-commit 钩子加手动调用，接受偶发撕裂行，由 read_events 跳过不可解析行兜住。首次写入时在 USAGE_DIR_RELATIVE 内创建内容为 '*' 的 .gitignore，自包含、零安装面改动、不触碰用户根 .gitignore。
- usage_log.read_events 契约：按窗口选取覆盖的月文件，逐行 json.loads，跳过解析失败行与 v 不匹配行，按 ts 过滤窗口，返回事件列表。
- scripts/usage_report.py（新增受管模块）— 职责：usage 事件的纯聚合，不出方向性判断、不做输出渲染。公开接口：USAGE_REPORT_DEFAULT_DAYS = 30（业务默认值单一来源，build_parser 的 --days default 导入本常量）；build_report(target: Path, days: int) -> dict[str, Any]。输出契约完全沿用 structure report：build_report 返回的 dict 由 harness 既有 emit() 呈现——非 json 模式按 key: value 逐行输出，--json 模式输出整体 JSON。dict 内含两个字符串键 summary（一行计数摘要）与 limitations（固定局限性声明），其余键为 A-F 六组计数。不新增独立文本渲染器：仓库现有全部命令无一自带渲染器，新加一个是没有先例的抽象（编码质量规范第 10 条抽象同样要证据）。IO 委托给 usage_log.read_events，本模块不直接触文件系统。
- scripts/harness.py main()（修改）— 在命令分发外层包一层计时与埋点，只在正常返回与 HarnessError 返回两条路径各调一次记录函数，不加 try/finally；埋点先经 usage_log.is_enabled() 短路。事件构造抽成模块级私有函数（读 args、白名单过滤 flags、从 payload 推导计数是可独立测试的子步骤，与命令分发是两个职责），main() 净增 ≤ 9 行。复用现有代码路径：args 已持有 command/action/全部 flags，code 与 payload 已在手，无需任何模块新增出口。
- scripts/harness.py project_findings()（修改）— 新增 severity=red 的 usage_log_invalid finding，镜像既有 knowledge_mode_invalid 的写法（harness.py 约 3132-3143 行）：config['usage_log'] 必须是 dict、键集恰为 {'enabled'}、值为 bool，不满足即报。与 direct_mode_invalid / knowledge_mode_invalid 的严格键集校验同形，是新增顶层 config 键自带的检查面。
- scripts/harness.py build_parser() 与 command_usage(args)（新增）— usage 子解析器 action 仅 ('report',)，参数 --days（默认 USAGE_REPORT_DEFAULT_DAYS）、--target、--json（复用既有 add_target）；command_usage 与 command_structure 同形，只做 safe_target 加一次 build_report 调用并返回 (0, payload)，呈现交给 main() 既有的 emit()。恒返回退出码 0（旁路观察不做门禁）。
- cmd.invoke 事件字段（v1 唯一事件类型）：v（str，USAGE_SCHEMA_VERSION）；ts（str，UTC ISO8601，与 harness utc_now() 同口径）；event（str，恒为 'cmd.invoke'）；command（str，args.command）；action（str，getattr(args,'action',None)，assets-check 与 self-test 无 action 时该键缺省）；exit_code（int，main() 返回码）；duration_ms（int，time.monotonic() 差值取整）；flags（dict，白名单 status/reaccept/dry_run/strict/fast/user_confirmed，全部来自 argparse choices 或 store_true，无自由文本，取值为假或 None 的键不写入）；hits（int，len(payload['facts'])，仅 knowledge query）；failures（int，len(payload['failures'])）；warnings（int，len(payload['warnings'])）。空值表示单一：推导不出的字段不写键、不写 null，读侧统一 .get()。
- 放弃 asset.transition 事件的依据：main() 已同时持有 args、code 与 payload，草案四类事件的全部 report 需求都能从这一处推导——acceptance record --reaccept 退 0 即一次返工；plan settle --status deprecated 退 0 即一次废弃结算；knowledge query 命中数 = len(payload['facts'])（已核对 knowledge_query 返回值）；检查计数 = len(payload['failures']) / len(payload['warnings'])（已核对 run_assets_check、command_plan_check、check_structure、check_knowledge_assets 返回值均带这两个键，口径统一）。plan create / plan settle 不走 managed_assets.write_asset（直接调 atomic_write_json / atomic_write_text），且 write_asset 入参只有新 asset 与中文展示标签、拿不到旧状态，通用写入层无法推导资产动作——这是埋点必须落在 main() 而非资产模块出口的根因。代价是 per-checker 粒度拿不到（run_assets_check 把失败扁平成 'FAIL: Knowledge: …' 前缀字符串），v1 只记总数，本方案不做 by_checker 扩展。
- tests/test_usage.py（新增）— 职责：usage_log 与 usage_report 两个模块的单元与端到端覆盖，单文件不拆分。跟随 tests/harness_test_base.py 的 unittest 模式（本仓库测试框架是 unittest，package.json 的 test 脚本为 python3 -m unittest discover -s tests -p test_*.py，HarnessTestBase 继承 unittest.TestCase），复用 HarnessTestBase 的 run_cli / run_installed / write_json / snapshot_project。

## 验收方案

- 四层与 ACCEPTANCE_EVIDENCE_LAYERS 的映射（criteria id 与层级以此为准）：合同层 contract.suite = contract_check / L1 / 无 evidence_layer；运行层 runtime.events = behavior_acceptance / local_runtime / L3；安装层 install.surface = behavior_acceptance / package_or_install / L4；降级层 degrade.safety = behavior_acceptance / local_runtime / L3。运行层与降级层同为 L3，因为两者都是在本地真实跑命令，不是测试用例也不是安装流程。
- 合同层 contract.suite（contract_check / L1）：python3 -m unittest discover -s tests -p test_*.py 全绿（含新增 tests/test_usage.py）；assets-check --strict 除预期 Structure WARN 外无 FAIL；self-test status=passed。
- 运行层 runtime.events（behavior_acceptance / local_runtime / L3）：在临时 scratch 项目跑真实命令序列（knowledge query、plan create --dry-run、acceptance create --dry-run、assets-check、structure check），逐条验证 JSONL 逐行落盘且字段与事件字段表一致；dry_run / status / reaccept / user_confirmed 四个 flag 各自被正确记录；hits / failures / warnings 与命令 payload 实际条数一致；git check-ignore .docs-harness/usage/<YYYY-MM>.jsonl 命中；usage report 与 usage report --json 输出 A-F 六组计数且与手工计数逐项相符；非 json 输出含 summary 与 limitations 两键。
- 安装层 install.surface（behavior_acceptance / package_or_install / L4）：project init 到全新 fixture 项目，验证 config schema_version=v13、含 usage_log.enabled=true、installed_module_fingerprints 含两个新模块、scripts/usage_log.py 与 scripts/usage_report.py 落盘；project upgrade --apply 从 v12 config 项目迁移到 v13 且沿用既有 enabled=false；project check 零 finding；project uninstall 删除两个新模块。
- 降级层 degrade.safety（behavior_acceptance / local_runtime / L3）：(a) 无 .docs-harness/config.json 的目录里跑命令，零写入且退出码与埋点前一致；(b) usage_log.enabled=false，零写入；(c) .docs-harness/usage/ 置只读，命令正常完成、退出码不变、append_event 返回 False；(d) 手工塞一行损坏 JSON 与一行 v 不匹配的事件，read_events 跳过两行、usage report 正常输出（该项同时验收 Windows 撕裂行容忍）。
- report v1 指标组（A-F，纯日志聚合）：A 每个 (command, action) 的调用次数、非零退出次数、活跃天数、首次与最近调用时间；B 按资产类型（knowledge/plan/acceptance/adr）的 create 成功次数 vs settle 成功次数，成功定义为 exit_code==0 且 flags.dry_run 不为真；C acceptance record 成功调用中 flags.reaccept 为真的次数、flags.user_confirmed 为真的次数，以及 record 成功总次数；D plan settle 成功调用中 flags.status 为 implemented 与 deprecated 的各自次数；E knowledge query 成功调用中 hits==0 的次数 / 总次数；F 各 check 类命令的调用次数、failures 与 warnings 累计、零失败次数。
- 已删除的草案验收项：知识新鲜度过期 fact 占比、CODEMAP 覆盖率、per-checker 计数——对应指标已按审查意见剥离。
- 不能自验收的层：无。本方案全部层级均可在本地 Python 与临时 fixture 项目内真实运行，不需要用户代跑。

## 是否需要 Acceptance 资产闭环

```json
true
```

## Knowledge 影响

updated

## 约束

- 零第三方依赖：只用 Python 3 标准库（json / time / pathlib / datetime），harness 自身零依赖的既有边界不破。
- 编码质量规范第 1 条先复用：已搜索 scripts/ 全部模块，无既有 JSONL 追加、无既有使用日志、无既有本地事件读写实现；v2_config 的 docs_flag 取值写法、add_target 参数注册、command_structure 的 CLI 投影形状、emit() 的输出契约均被直接复用；cache_plan_selection 的 OSError 静默降级口径被复用为 append_event 的豁免边界。
- 编码质量规范第 9 条业务默认值单一来源：USAGE_LOG_DEFAULT_ENABLED 与 USAGE_REPORT_DEFAULT_DAYS 各自只在一处赋值，harness.py 导入使用，不在 fallback、反序列化或条件分支中硬编码。
- 编码质量规范第 6 条的唯一豁免：usage_log.append_event 的 best-effort 返回 False，范围收窄为 OSError 与 UnicodeEncodeError，理由写入模块 docstring。除此之外全链路错误不吞。
- 编码质量规范第 10 条抽象要证据：不新增文本渲染层，输出沿用既有 emit()；不为尚未出现的 by_checker 粒度预留结构。
- 防御代码准入：is_enabled 不做无证据的 fallback 默认；read_events 跳过不可解析行是有运行证据的（Windows O_APPEND 非原子，接受撕裂行），不是预防性兜底。
- 结构护栏第 5 条搜索面收敛：本任务检索限定 scripts/、tests/、docs/、CHANGELOG.md、package.json，排除 node_modules、__pycache__、.git、.qoder。

## 风险与回滚

- 预期 Structure WARN（预先声明，收尾按 WARN 消费规则转达，不在本任务内重构）：实测 harness.py 4561 行、main() 57 行、build_parser() 145 行、command_self_test() 67 行；structure_check 的阈值逻辑为——文件已超 FILE_RED_LINE(600) 时只有净增 >= OVERSIZE_FILE_GROWTH_ALERT(50) 行才 WARN，函数已超 FUNC_RED_LINE(60) 时只有增长 >= FUNC_GROWTH_ALERT(10) 行才 WARN。因此 harness.py 文件级 WARN 大概率出现（两批合计净增预计超 50 行），属预期；main() 函数级 WARN 可避免且必须避免（57+10=67 即触发），故事件构造必须抽成模块级私有函数把 main() 净增压在 9 行以内；build_parser() 新增子解析器约 8 行低于增长阈值，预期不触发，若实际超出一并转达。
- config schema v13 升版理由必须单一且写清：先例核对显示 v10→v11（2.9.0 commit 977d872，新增 script_hygiene.py）与 v11→v12（2.11.0 commit 047f129，新增 structure_check.py）都随新增受管模块升版，但 2.15.0（commit 0d94fa2）新增 structure_ts_functions.cjs 时 CONFIG_SCHEMA 未变（已 git show 确认）。结论：新增受管模块本身不构成升版理由，本次 v13 的唯一理由是新增顶层 config 键 usage_log，它改变 config 键集合，CURRENT_CONFIG_KEYS 全等断言与 project_findings 键校验都依赖该集合。
- 安装面漏项风险：CONFIG_SCHEMA 的消费点已 grep 全覆盖并分为两类——需手工改的项（见执行范围，含三处测试字面量）与随 MANAGED_MODULE_RELATIVE_FILES 自动覆盖的项（managed_module_fingerprints、portable_install_paths、install_preflight、preflight_owned_files、project_changes、apply_project_install、project_findings 的 asset_module_drift、project uninstall、command_self_test 的 asset_modules_valid 与 project_config_v9、legacy_cleanup_plan、project diff）。漏改任一手工项的表现是对应测试直接红，不会静默。
- 目录误删风险已排除：usage 不在 LEGACY_RUNTIME_NAMES（该元组为 runs / knowledge / knowledge-jobs / background / task-inputs），project upgrade 的 legacy 清理不会误删 .docs-harness/usage/，已核对 legacy_cleanup_plan()。
- 回滚：三批各自可独立 git revert。批 1 回滚即恢复 config v12 与原 MANAGED_MODULE_RELATIVE_FILES，已升级到 v13 的下游项目需重跑 project upgrade --apply 回到 v12 控制器；批 2、批 3 回滚无迁移副作用。日志文件不入库、不影响任何命令行为，遗留的 .docs-harness/usage/ 目录可由用户直接删除。
- 实施期间 plan check 的 C8 反向预警会对本方案条目出现，属预期且暂态：C8 对横幅为有效、且 key_symbols 全部命中 docs/ 之外源码的条目报 WARN（代码可能已交付而 plan 未 settle，是下游实证过的结算泄漏形态）。批 1 落地 usage_log / append_event / USAGE_SCHEMA_VERSION、批 2 落地 build_report 后四个符号全部命中，该 WARN 在批 2 结束到批 3 plan settle 之间出现，settle 后自动消失。C5 符号存活性只对索引镜像为已实施-仅追溯的条目生效，对有效方案不适用，本方案实施期间不会触发 C5。pre-commit 的 assets-check --fast 不跑该检查，只有 --strict 或显式 plan check 会看到。

<!-- docs-harness:plan-governance:start -->
## 资产治理

- 关联验收：`docs/acceptance/usage-observability.json`
- 需要 Acceptance：true
- Knowledge 影响：updated
<!-- docs-harness:plan-governance:end -->
