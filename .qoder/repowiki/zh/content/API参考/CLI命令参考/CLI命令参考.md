# CLI命令参考

<cite>
**本文引用的文件**   
- [scripts/harness.py](file://scripts/harness.py)
- [package.json](file://package.json)
- [SKILL.md](file://SKILL.md)
- [docs/contracts.md](file://docs/contracts.md)
</cite>

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细命令参考](#详细命令参考)
6. [依赖关系分析](#依赖关系分析)
7. [性能与可观测性](#性能与可观测性)
8. [故障排除指南](#故障排除指南)
9. [结论](#结论)
10. [附录：JSON输出与结构化响应](#附录json输出与结构化响应)

## 简介
本文件为 Docs Harness v1.6.5 的完整 CLI 命令参考，覆盖 run、verify、background、project、ledger、context、progress、task、knowledge、self-test 等全部命令。文档包含每个命令的语法、必需与可选参数、环境变量与配置项、错误码与退出码、常见工作流示例、命令间依赖与执行顺序指导，以及 JSON 输出格式说明与调试建议。所有规范以仓库内源码与契约文档为依据。

## 项目结构
- 入口脚本：scripts/harness.py（Python 实现）
- 包元数据：package.json（版本、脚本、打包清单）
- 技能说明：SKILL.md（安装、任务入口、后台治理、质量账本等高层流程）
- 契约与状态机：docs/contracts.md（任务包、证据、上下文、授权、验证命令、迁移与回滚、退出码等）

```mermaid
graph TB
A["CLI 入口<br/>scripts/harness.py"] --> B["子命令解析器<br/>build_parser()"]
B --> C["run / context / progress / verify / task / ledger / knowledge / background / project / self-test"]
C --> D["运行时状态目录<br/>.docs-harness/runs/<task-id>"]
C --> E["项目配置<br/>.docs-harness/config.json"]
C --> F["Git 集成<br/>git_* 工具函数"]
C --> G["规则与知识<br/>harness-home/rules/*<br/>docs/knowledge-map.json"]
```

图表来源 
- [scripts/harness.py:10160-10279](file://scripts/harness.py#L10160-L10279)
- [package.json:1-23](file://package.json#L1-L23)

章节来源
- [scripts/harness.py:10160-10279](file://scripts/harness.py#L10160-L10279)
- [package.json:1-23](file://package.json#L1-L23)

## 核心组件
- 命令行解析与分发：build_parser() 定义所有子命令与参数；main(argv) 路由到具体 command_* 函数并统一输出 emit()。
- 任务生命周期：command_run() 负责幂等复用、任务包构建、范围绑定、Gate 编译、计划冻结、授权与上下文加载。
- 验收与证据：command_verify() 支持五级处置（provide_evidence/refresh_evidence/retry_verification/incremental_admission/full_readmission），逐项验证命令缓存与收据复用。
- 后台治理：command_background() 管理 estimate/list/status/prepare/dispatch/progress/verify/retry/prune，严格状态机与工件校验。
- 项目生命周期：command_project() 提供 init/upgrade/uninstall/check/diff/rollback-check。
- 质量账本：command_ledger() 支持 add/read，按任务或关键词检索。
- 上下文与进度：command_context() 按阶段加载上下文并写回执；command_progress() 推进 extended 工作包状态。
- 任务管理：command_task() 支持 status/migrate/cancel/archive/list/prune。
- 知识库：command_knowledge() 兼容 background 别名，支持 status/estimate/audit/bootstrap/update/verify/job-status/dispatch/retry。
- 自检：command_self_test() 运行内置合同自检。

章节来源
- [scripts/harness.py:10160-10279](file://scripts/harness.py#L10160-L10279)
- [scripts/harness.py:4540-4739](file://scripts/harness.py#L4540-L4739)
- [scripts/harness.py:6273-6472](file://scripts/harness.py#L6273-L6472)
- [scripts/harness.py:8629-8828](file://scripts/harness.py#L8629-L8828)
- [scripts/harness.py:9850-10153](file://scripts/harness.py#L9850-L10153)
- [scripts/harness.py:6983-7200](file://scripts/harness.py#L6983-L7200)
- [scripts/harness.py:4130-4539](file://scripts/harness.py#L4130-L4539)
- [scripts/harness.py:5506-6272](file://scripts/harness.py#L5506-L6272)
- [scripts/harness.py:3718-4129](file://scripts/harness.py#L3718-L4129)
- [scripts/harness.py:8987-9849](file://scripts/harness.py#L8987-L9849)

## 架构总览
下图展示 CLI 主流程与关键子系统交互：

```mermaid
sequenceDiagram
participant U as "用户/宿主"
participant CLI as "harness.py<br/>build_parser()/main()"
participant RUN as "command_run()"
participant CTX as "command_context()"
participant PRG as "command_progress()"
participant VER as "command_verify()"
participant BG as "command_background()"
participant PROJ as "command_project()"
participant LED as "command_ledger()"
participant TSK as "command_task()"
participant KNO as "command_knowledge()"
participant FS as "文件系统/.docs-harness"
participant GIT as "Git 工具"
U->>CLI : 调用子命令 + 参数
CLI->>RUN : run
RUN->>FS : 读取/写入任务状态与包
RUN->>GIT : git_preflight/postcheck
RUN-->>U : 准入/下一步(next_action, next_command_argv)
U->>CTX : context --stage plan|action|acceptance
CTX-->>U : 上下文回执
U->>PRG : progress begin/submit/block
PRG-->>U : 工作包状态更新
U->>VER : verify --evidence ...
VER->>FS : 证据索引/受管副本
VER->>GIT : 后检查
VER-->>U : 五级处置结果+事件记录
U->>BG : background prepare/dispatch/...
BG->>FS : 工件校验/状态机转换
BG-->>U : Job 状态/下一步
U->>PROJ : project init/upgrade/...
PROJ-->>U : 项目安装/升级/检查
U->>LED : ledger add/read
LED-->>U : 质量账本条目
U->>TSK : task status/migrate/...
TSK-->>U : 任务管理结果
U->>KNO : knowledge status/estimate/...
KNO-->>U : 知识库/后台兼容操作
```

图表来源 
- [scripts/harness.py:10322-10359](file://scripts/harness.py#L10322-L10359)
- [scripts/harness.py:4540-4739](file://scripts/harness.py#L4540-L4739)
- [scripts/harness.py:6273-6472](file://scripts/harness.py#L6273-L6472)
- [scripts/harness.py:8629-8828](file://scripts/harness.py#L8629-L8828)

## 详细命令参考

### 通用选项
- --target <路径>：目标项目根目录，默认当前目录。
- --json：以 JSON 形式输出结构化响应。

章节来源
- [scripts/harness.py:10155-10158](file://scripts/harness.py#L10155-L10158)

### run 命令
用途：任务路由、任务包编译与执行准入。

语法
- python3 scripts/harness.py run --target <项目> [--task "<原始任务>"] [--task-id <id>] [--new-task] [--facts <事实文件>] [--plan <方案文件>] [--authorization <授权文件>] [--scope <路径>...] [--feature <功能ID>...] [--action <动作>...] [--success <成功标准>...] --json

必需参数
- 首次创建任务：--task（原始任务文本）
- 继续已有任务：--task-id

可选参数
- --new-task：跳过活动任务幂等复用，强制新建
- --facts：结构化任务事实 JSON 文件路径（不接受内联内容）
- --plan：正式方案 Markdown 或 JSON 文件路径（不接受内联内容）
- --authorization：结构化授权 JSON 文件路径（不接受内联内容）
- --scope/--feature/--action/--success：限制范围、功能、动作与成功标准

行为要点
- 幂等复用：同一 target、归一化任务文本、事实指纹与工作区快照命中活动任务时返回 active_task_reused，不重复建立上下文与授权。
- Gate 与范围：先编译意图与候选范围，再根据最高 mutation_profile 与风险 Gate 决定准入状态。
- 计划冻结：若需提交/补全计划，返回 complete_plan 或 complete_plan_delta，仅列出缺失字段，避免整份重交。
- Git 预检/后检查：对 git_fetch/git_sync 进行 preflight 与 postcheck，漂移将触发重新准入。

返回值与下一步
- 可能返回 next_action 与 next_command_argv，如 load_plan_context、load_action_context、obtain_authorization、provide_evidence、retry_verification、rerun_harness_for_readmission 等。

示例
- 首次准入：python3 scripts/harness.py run --target . --task "修复登录超时问题" --facts facts.json --json
- 继续任务：python3 scripts/harness.py run --target . --task-id dh-YYYYMMDDTHHMMSS-xxxxxxxxxx --json
- 提交计划：python3 scripts/harness.py run --target . --task-id <id> --plan plan.json --json

章节来源
- [scripts/harness.py:10165-10192](file://scripts/harness.py#L10165-L10192)
- [scripts/harness.py:4540-4739](file://scripts/harness.py#L4540-L4739)
- [SKILL.md:25-41](file://SKILL.md#L25-L41)
- [docs/contracts.md:48-76](file://docs/contracts.md#L48-L76)

### context 命令
用途：按阶段加载精确上下文并写回执。

语法
- python3 scripts/harness.py context --target <项目> --task-id <id> [--stage plan|action|acceptance] [--work-package <wp-id>] --json

参数
- --task-id：必填
- --stage：plan/action/acceptance，默认 action
- --work-package：扩展路线下指定工作包

行为要点
- 按 stage 与 compiler_contract、content_set_fingerprint 进行内容寻址复用；跨 task/target/stage/contract 或内容变化必须重载。
- 回执用于后续 verify 阶段校验上下文有效性。

示例
- python3 scripts/harness.py context --target . --task-id <id> --stage plan --json

章节来源
- [scripts/harness.py:10194-10198](file://scripts/harness.py#L10194-L10198)
- [docs/contracts.md:222-234](file://docs/contracts.md#L222-L234)

### progress 命令
用途：推进 extended 工作包状态。

语法
- python3 scripts/harness.py progress <status|begin|submit|block> --target <项目> --task-id <id> [--work-package <wp-id>] [--evidence <证据文件>] [--reason <原因>] [--scope-changed] [--handoff] --json

参数
- action：status/begin/submit/block
- --work-package：必填（除 status 外）
- --evidence：submit 时必须提供
- --reason：受限原因码
- --scope-changed/--handoff：标记变更与交接

行为要点
- 合法状态转换：pending→in_progress|blocked，in_progress→completed|blocked；相同状态幂等，倒退/跳过/未知 ID 失败关闭。
- submit 时生成证据收据并归档。

示例
- python3 scripts/harness.py progress begin --target . --task-id <id> --work-package wp-1 --json
- python3 scripts/harness.py progress submit --target . --task-id <id> --work-package wp-1 --evidence evidence.json --json

章节来源
- [scripts/harness.py:10200-10212](file://scripts/harness.py#L10200-L10212)
- [docs/contracts.md:336-338](file://docs/contracts.md#L336-L338)

### verify 命令
用途：同源验收、补证或重新准入。

语法
- python3 scripts/harness.py verify --target <项目> --task-id <id> [--evidence <证据文件>...] --json

参数
- --task-id：必填
- --evidence：结构化证据 JSON 文件路径，可重复（不接受内联内容）

行为要点
- 五级处置：provide_evidence、refresh_evidence、retry_verification、incremental_admission、full_readmission。
- 验证命令逐项缓存：输入不变且上次通过则复用收据；失败或输入变化才重跑。可通过 verification.command_cache_enabled=false 整体关闭。
- 自动归因：write_scope 内未归因写入默认由控制器代铸 workspace_attribution 收据；可通过 verification.auto_attribute_in_scope=false 恢复补证据流程。
- 每次 verify 均记录结构化事件，统计命令执行次数、缓存命中、上下文加载计数与 readmission_count。

示例
- python3 scripts/harness.py verify --target . --task-id <id> --evidence evidence.json --json

章节来源
- [scripts/harness.py:10214-10222](file://scripts/harness.py#L10214-L10222)
- [scripts/harness.py:6273-6472](file://scripts/harness.py#L6273-L6472)
- [SKILL.md:43-57](file://SKILL.md#L43-L57)
- [docs/contracts.md:199-221](file://docs/contracts.md#L199-L221)

### task 命令
用途：查询、取消、归档、清理任务或显式迁移 v1 在途任务。

语法
- python3 scripts/harness.py task <status|migrate|cancel|archive|list|prune> --target <项目> [--task-id <id>] [--apply] [--reason-code <码>] [--older-than <天数>] [--dry-run] [--include-archived] --json

参数
- action：status/migrate/cancel/archive/list/prune
- --task-id：按需提供
- --apply：显式应用迁移/取消/归档/清理；缺省仅预览
- --reason-code：受控原因码
- --older-than/--dry-run/--include-archived：清理与列表控制

行为要点
- v1 在途任务只允许 status；migrate --apply 在 staging/backup/journal 中切换并支持回滚。
- list 支持 include-archived 查看已归档 v1 对象。

示例
- python3 scripts/harness.py task status --target . --task-id <id> --json
- python3 scripts/harness.py task migrate --target . --task-id <id> --apply --json

章节来源
- [scripts/harness.py:10224-10232](file://scripts/harness.py#L10224-L10232)
- [docs/contracts.md:236-246](file://docs/contracts.md#L236-L246)

### ledger 命令
用途：人工触发的个人本地质量账本。

语法
- python3 scripts/harness.py ledger <add|read> --target <项目> [--task-id <id>] [--review <复盘文件>] [--query <检索>] [--limit <条数>] --json

参数
- action：add/read
- --task-id：记录或精确读取的任务编号
- --review：脱敏质量复盘 JSON 文件路径（不接受内联内容）
- --query：按摘要、范围、Gate、价值、经验或风险检索
- --limit：读取条数，范围 1-20，默认 5

行为要点
- 不得自动记录或在任务结束后主动询问；读取历史时按任务编号或关键词调用 read。

示例
- python3 scripts/harness.py ledger add --target . --task-id <id> --review review.json --json
- python3 scripts/harness.py ledger read --target . --query "安全边界" --limit 10 --json

章节来源
- [scripts/harness.py:10234-10244](file://scripts/harness.py#L10234-L10244)
- [SKILL.md:91-99](file://SKILL.md#L91-L99)

### knowledge 命令
用途：功能知识库审查、评估与兼容后台入口。

语法
- python3 scripts/harness.py knowledge <status|estimate|audit|bootstrap|update|verify|job-status|dispatch|retry> --target <项目> [--assessment <报告>] [--consent <同意回执>] [--job-id <id>] [--job-status <状态>] [--result updated|no_change] --json

参数
- action：status/estimate/audit/bootstrap/update/verify/job-status/dispatch/retry
- --assessment/--consent：结构化文件路径（不接受内联内容）
- --job-id/--job-status：后台 Job 相关
- --result：updated/no_change，默认 updated

行为要点
- 作为 background 的弃用别名，共享相同安全不变量；仅 background_direct 保留旧别名的 contract_ready 直达 running 兼容。

示例
- python3 scripts/harness.py knowledge estimate --target . --candidate candidate.json --json
- python3 scripts/harness.py knowledge dispatch --target . --job-id <id> --job-status dispatched --json

章节来源
- [scripts/harness.py:10246-10253](file://scripts/harness.py#L10246-L10253)
- [docs/contracts.md:332-338](file://docs/contracts.md#L332-L338)

### background 命令
用途：统一后台文档治理 Job 控制器。

语法
- python3 scripts/harness.py background <estimate|list|status|prepare|progress|dispatch|verify|retry|prune> --target <项目> [--candidate <候选文件>] [--job-id <id>] [--job-status <状态>] [--work-package-id <wp-id>] [--work-package-status in_progress|completed|blocked] [--reason-code <码>] [--repair] [--assessment <报告>] [--result updated|no_change|completed_with_finding] [--older-than <天数>] [--apply] [--dry-run] --json

参数
- action：estimate/list/status/prepare/progress/dispatch/verify/retry/prune
- --candidate：后台候选项 JSON 文件路径（不接受内联内容）
- --job-id：统一后台 Job ID
- --job-status：宿主报告的 Job 状态
- --work-package-id/--work-package-status：工作包目标状态
- --reason-code：有界、受控的原因码
- --repair：显式归档并修复无效 Goal 工件
- --assessment：知识或重大发现验收报告文件
- --result：updated/no_change/completed_with_finding
- --older-than/--apply/--dry-run：prune 控制

行为要点
- 状态机严格：contract_ready→dispatched→running，复杂路线必须先 prepare；禁止直接写 job/plan/progress/events。
- verify 对 updated/no_change 要求全部工作包 completed；completed_with_finding 只允许 completed/blocked。
- retry 会归档旧 attempt 工件并要求重新 prepare，不继承完成进度。

示例
- python3 scripts/harness.py background prepare --target . --job-id <id> --json
- python3 scripts/harness.py background dispatch --target . --job-id <id> --job-status dispatched --json
- python3 scripts/harness.py background progress --target . --job-id <id> --work-package-id wp-1 --work-package-status completed --json
- python3 scripts/harness.py background verify --target . --job-id <id> --assessment assessment.json --json
- python3 scripts/harness.py background retry --target . --job-id <id> --json

章节来源
- [scripts/harness.py:10255-10269](file://scripts/harness.py#L10255-L10269)
- [scripts/harness.py:8629-8828](file://scripts/harness.py#L8629-L8828)
- [SKILL.md:59-88](file://SKILL.md#L59-L88)
- [docs/contracts.md:332-338](file://docs/contracts.md#L332-L338)

### project 命令
用途：项目安装生命周期。

语法
- python3 scripts/harness.py project <init|upgrade|uninstall|check|diff|rollback-check> --target <项目> [--apply] [--purge-runtime] --json

参数
- action：init/upgrade/uninstall/check/diff/rollback-check
- --apply：显式应用变更
- --purge-runtime：清理运行时

行为要点
- init：新项目创建最小知识骨架、执行 knowledge estimate 并返回 knowledge_bootstrap 后台合同；不等待知识生成。
- upgrade：preserve-and-merge 合法 document_routes；非法路由或缺少路由合同的在途治理 Job 返回 needs_manual_migration。
- rollback-check：存在活动 v2 任务时阻断回滚。

示例
- python3 scripts/harness.py project init --target . --json
- python3 scripts/harness.py project upgrade --target . --apply --json

章节来源
- [scripts/harness.py:10271-10276](file://scripts/harness.py#L10271-L10276)
- [SKILL.md:13-24](file://SKILL.md#L13-L24)

### self-test 命令
用途：运行内置合同自检。

语法
- python3 scripts/harness.py self-test --target <项目> --json

行为要点
- 返回 version/status/checks/rules/rule_errors/empty_rules_legal 等自检结果。

示例
- python3 scripts/harness.py self-test --target . --json

章节来源
- [scripts/harness.py:10277-10278](file://scripts/harness.py#L10277-L10278)
- [scripts/harness.py:10150-10153](file://scripts/harness.py#L10150-L10153)

## 依赖关系分析
- 命令依赖
  - run → context（plan/action/acceptance）→ verify（证据与命令缓存）→ progress（extended 工作包）
  - background → prepare → dispatch → progress → verify → retry（必要时）
  - project init → knowledge estimate → background prepare（knowledge_bootstrap）
- 外部依赖
  - Git：git_root/git_command/git_preflight_contract/git_postcheck
  - 文件系统：.docs-harness/runs、quality-ledger、knowledge/background
  - 配置：.docs-harness/config.json（verification.* 开关、document_routes 等）

```mermaid
flowchart TD
Start(["开始"]) --> Run["run"]
Run --> Context["context (plan/action/acceptance)"]
Context --> Verify["verify"]
Verify --> Progress{"是否 extended?"}
Progress --> |是| Prog["progress (begin/submit/block)"]
Progress --> |否| End(["结束"])
Prog --> End
Run --> BG["background (estimate/list/status/prepare/...)"]
BG --> End
```

图表来源 
- [scripts/harness.py:10160-10279](file://scripts/harness.py#L10160-L10279)
- [scripts/harness.py:4540-4739](file://scripts/harness.py#L4540-L4739)
- [scripts/harness.py:6273-6472](file://scripts/harness.py#L6273-L6472)
- [scripts/harness.py:8629-8828](file://scripts/harness.py#L8629-L8828)

章节来源
- [scripts/harness.py:10160-10279](file://scripts/harness.py#L10160-L10279)

## 性能与可观测性
- 验证命令缓存：按 argv、produces 与输入指纹（读取集与工作区相关写入）绑定；输入不变且上次通过则复用收据，减少昂贵命令重跑。可通过 verification.command_cache_enabled=false 整体关闭。
- 上下文内容寻址：按 stage、compiler_contract、content_set_fingerprint 复用正文，避免重复加载。
- 事件记录：每次 verify 入口最终写入 events.jsonl，包含 duration_ms、command_executed_count、command_cache_hit_count、context_load_count、readmission_count 等指标。
- 工作区快照：非 Git 工作区限制文件数量上限，避免截断基线导致误判。

章节来源
- [scripts/harness.py:1188-1213](file://scripts/harness.py#L1188-L1213)
- [scripts/harness.py:1031-1071](file://scripts/harness.py#L1031-L1071)
- [scripts/harness.py:1112-1135](file://scripts/harness.py#L1112-L1135)
- [docs/contracts.md:199-221](file://docs/contracts.md#L199-L221)

## 故障排除指南
- 常见错误码与退出码
  - 退出码 0：命令成功；只有 verify.result=完成 表示父任务完成
  - 退出码 1：项目检查、自检或完整性读取失败
  - 退出码 2：输入、合同、绑定或状态无效
  - 退出码 3：需要方案、授权、证据（含 provide_evidence/refresh_evidence）、迁移、用户输入或 Git 交付
  - 退出码 4：范围、漂移、Gate、远端、授权或规则变化，必须重新准入
- 典型问题定位
  - 活动任务幂等复用：若期望新建任务，使用 --new-task
  - 计划不完整：按 missing_plan_fields 补充字段，优先使用 complete_plan_delta
  - 证据不足：按 reason_code 提示补充对应类型证据；必要时刷新过期证据
  - Git 漂移：postcheck 失败将触发 full_readmission；git_sync 场景需单命令重新准入并复用冻结方案
  - 后台 Job 状态非法：检查 transition 合法性与工件完整性，必要时 prepare --repair
- 调试建议
  - 始终使用 --json 获取结构化响应
  - 关注 next_action 与 next_command_argv，按指引执行下一步
  - 查看 events.jsonl 与 evidence-index.json 了解最近轮次与证据状态
  - 检查 .docs-harness/config.json 的 verification.* 开关是否符合预期

章节来源
- [docs/contracts.md:359-370](file://docs/contracts.md#L359-L370)
- [scripts/harness.py:10322-10359](file://scripts/harness.py#L10322-L10359)
- [scripts/harness.py:6273-6472](file://scripts/harness.py#L6273-L6472)
- [scripts/harness.py:8629-8828](file://scripts/harness.py#L8629-L8828)

## 结论
Docs Harness CLI 围绕“意图优先、证据可复用、失败关闭”的原则设计，通过严格的准入、范围绑定、Gate 编译、上下文与授权回执、逐命令验证与收据复用，确保任务执行的可审计性与稳定性。掌握 run/context/verify/progress/background/project/ledger/task/knowledge/self-test 的命令规格与依赖关系，即可高效编排从任务准入到验收的全流程。

## 附录：JSON输出与结构化响应
- 输出格式
  - 使用 --json 输出标准化 JSON；非 JSON 模式逐行打印 key: value
  - 错误统一为 {"status":"error","code":<错误码>,"message":<消息>}
- 关键字段
  - task_id、admission_status、verification_status、control_status、next_action、next_command_argv、reason_code
  - completion_manifest、contract_delta、plan_contract、plan_delta_contract
  - evidence_index、auto_attributed_paths、workspace_attribution
  - background job 字段：job_id、status、execution_route、attempt、created_at、updated_at、completed_at
- 事件与指标
  - events.jsonl 记录 verification_attempt、readmission、auto_attribution 等事件
  - 指标包括 duration_ms、command_executed_count、command_cache_hit_count、context_load_count、readmission_count

章节来源
- [scripts/harness.py:10282-10288](file://scripts/harness.py#L10282-L10288)
- [scripts/harness.py:1031-1071](file://scripts/harness.py#L1031-L1071)
- [docs/contracts.md:199-221](file://docs/contracts.md#L199-L221)
- [docs/contracts.md:359-370](file://docs/contracts.md#L359-L370)