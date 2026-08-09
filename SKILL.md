---
name: docs-harness
description: "通过独立控制器完成 Gate、任务包、降级知识上下文、主任务验收和异步文档治理。"
metadata:
  version: 1.7.7
  status: active
---

# Docs Harness

Docs Harness 是独立技能，不读取或调用 `agent-docs-harness`。

## 项目安装

```bash
python3 <docs-harness-skill>/scripts/harness.py project init --target <project> --json
```

- 新项目创建最小知识骨架、执行 `knowledge estimate` 并返回 `knowledge_bootstrap` 后台合同；安装不等待知识生成。
- 已有 `docs/` 的项目安装阶段零文档内容写入；先审查，缺口需要用户同意后才能创建后台 Job。
- 不自动修改 `.gitignore`、提交、推送或发布。
- 项目存在 `.qoder/repowiki` 外部知识库时进入只消费模式：不创建 `docs/` 骨架、不执行 bootstrap/增量同步等任何知识库写动作（`knowledge bootstrap` 返回 `knowledge_external_consume_only` 失败关闭），任务准入按任务文本与 scope 命中知识卡（frontmatter 的 `name`/`scope`）作为上下文；`knowledge_status.source="repowiki"`，交接 mode 为 `external_consume_only`。同时向宿主下发并在受管 `AGENTS.md` 中写入条件式指令：“了解项目架构和模块知识时，优先阅读 `.qoder/repowiki/zh/content/` 下的 Wiki 文档和 `.qoder/repowiki/knowledge/zh/` 下的知识卡片。”
- `runtime_status`、`controller_clone_ready`、整体 `clone_ready`、远端与真实宿主验收分别报告。
- `project upgrade` preserve-and-merge 合法 `document_routes`；非法路由或缺少路由合同的在途治理 Job 返回 `needs_manual_migration`，不覆盖真源配置或旧 Job scope。

## 任务入口

除纯对话、元问题且无需读取项目事实的消息外，每个项目任务的第一条动作：

```bash
python3 scripts/harness.py run --target . --task "<原始用户任务>" --json
```

纯对话或元问题不创建 Harness 任务。`run` 返回 `admission_status=answer_only` 时，宿主可按需读取允许范围内的项目事实并直接回答；不生成证据、不运行 `verify`、不执行写入。普通解释、进度回答、代码阅读、轻量 review 和普通 `git_inspect` 使用该协议；只有用户明确要求可交付审计报告、证据化结论或高风险验收时才声明 `audit_formal`（兼容显式 `audit`），并保留来源证据和最终验收。

只在 `ready_direct|ready_planned|ready_extended` 后进入执行。`context_quality=degraded` 表示知识缺失、构建中、失败或隔离，不改变准入状态；必须从允许范围内的代码、测试、配置和有效文档核实事实，并记录 `fallback_fact_refs`。

同一 target、任务文本、事实与工作区快照重复 `run` 时幂等复用活动任务（返回 `active_task_reused`），不重复建立上下文与授权；任务或初始工作区不同则新建，`--new-task` 强制新建。`answer_only|complete|cancelled|failed|blocked` 状态的任务不复用。

规则、授权、安全、范围、用户指定交付物和必要证据异常继续失败关闭。

首次 `run` 前，宿主必须先根据用户语义提交 `intent_assessment`（`{"intents": [...], "rationale": "..."}`）；兼容字段 `task_intent|candidate_intents` 仅用于迁移期显式声明。Harness 不读取任务正文关键词，也不按 scope 猜测 `task_intent|candidate_intents|mutation_profile`。缺声明时返回 `missing_intent_assessment` 与 `admission_persisted=false`，不生成 task-id、任务包或取消需求。普通写任务还必须提供 `write_scope`，外部写任务必须提供 `external_scope`；缺失时同样非持久化失败，正文中的路径不能替代结构化范围。任务文本仍作为审计快照；Harness Home 规则匹配与交付层需求判断保留各自的受控关键词和否定守卫，但不得反向修改意图。

`intent_assessment.intents` 只能填写受控意图：`query|review_light|audit|audit_formal|git_inspect|git_fetch|git_sync|git_switch|git_commit|modify|external_write`。`read_only|git_metadata_write|workspace_write` 是变更面，`answer_only|ready_direct|ready_planned|ready_extended` 是准入状态，不得当作意图；`external_write` 是唯一与变更面同名的合法意图。跨层误填继续失败关闭，响应会标明识别层级、合法意图和候选项，但控制器不会自动替换。

宿主必须基于任务语义判断风险 Gate；`workspace_write|external_write` 在 `--facts` 中提交 `gate_assessment`（`{"gates": [...], "rationale": "<一句话依据>"}`），只读任务可省略且缺省 Gate 不能授予写权限。写任务缺少声明直接阻断；路径推断只标记文档、代码、测试这类封闭结构，不能代替安全、发布、数据等语义判断。项目确实存在稳定的语义路径边界时，在 `.docs-harness/config.json` 使用 `gate_path_rules` 显式配置 `pattern` 与 `gates`；运行期新路径只依该项目映射触发新 Gate 绊线。

准入响应中的 `completion_manifest` 是收尾真源。宿主提交的 `evidence-declaration/v1` 与完整 v2 JSON 均是 `reported`：控制器可代铸绑定字段，但不会把宿主自述升级为已验证事实。只有控制器自身执行的命令、Git 后检与自动归因入口可产生 `verified` 收据；外部 JSON 不得声称这些 controller producer。安全、发布、恢复、远端交付等高风险证据只接受 `verified` 受控入口，`reported` 不能满足。

`completion_manifest.verification_required=true` 的任务最终验收：

```bash
python3 scripts/harness.py verify --target . --task-id <task-id> --evidence <evidence.json> --json
```

只有 `verify.result=完成` 表示父任务完成。父任务先落盘，再逐项消费冻结的 `background_deliverables`；未声明后台交付物时不得创建 Job，也不得等待 Job 终态才报告父任务结果。

合同稳定时 verify 支持五级处置：可补证据的未归因写入返回 `provide_evidence`，读取基线漂移返回 `refresh_evidence`（只失效引用漂移路径的证据），验证命令失败返回 `retry_verification`，追加上下文走 `incremental_admission`；只有范围或高风险合同变化才 `full_readmission`。证据采用受管副本保存，原始文件事后删除不影响准入。已通过的验证命令带逐项收据复用，不重复执行；仅失败或输入变化的命令重跑，`verification.command_cache_enabled=false` 可整体关闭。

宿主验证必须按实际变更面分层，详细真源见 `docs/testing.md`：行为代码、依赖或公共夹具变化时先跑目标测试，行为稳定后同一行为快照最多一次完整回归；仅版本、README、CHANGELOG 或元数据变化时只做版本一致性、自检、编译和打包检查；下游同步只做 preview/apply/diff/check 与受管文件摘要，不重复上游完整回归。已有完整回归证据在行为快照未变时必须复用，长测试默认安静输出。

write_scope 内的写入由控制器自动归因：代铸 `workspace_attribution` 收据、记录 `auto_attribution` 事件，响应含 `auto_attributed_paths`。该收据只证明“这些路径归当前任务写入”，不证明变更正确；每个写任务仍至少需要一类独立语义验收，当 Gate、规则、意图与显式合同都未提供时自动要求 `change_review`。

v1 在途任务只允许 `task status` 读取；必须显式执行 `task migrate --apply` 后重新准入。存在活动 v2 任务时，`project rollback-check` 必须阻断回滚。

v1.6.9 准入效率加固：scope 值形似 JSON（数组/对象整体作为单值）直接报 `invalid_scope_json` 并给出修复提示；`--facts` 等文件参数在 Windows 上传入 Git Bash `/tmp` 等 POSIX 绝对路径时，缺失文件错误附带改用工作区相对路径的提示；非 blocked/scope_changed 状态下提交 `--facts` 不再静默忽略，响应返回 `facts_ignored` 与生效条件；所有 `next_step_payload` 响应统一携带 `contract_snapshot`（当前 `allowed_scope`/`read_scope`/`write_scope`、`plan_fields`、所需证据类型），每步即可自查合同，无需额外探查。

v1.7.0 低风险轻量准入：低风险文档/规则/测试类小任务可在 `--facts` 显式声明 `fast_track: true`。生效后所需证据收敛为 `code_diff + change_review`（声明验证命令时再加 `test_run`）；差异事实与语义审查仍分层，fast_track 不豁免任何 Gate。

v1.7.1 发版同步与验收提效：`release sync` 单命令核对四处版本真源（VERSION 文件、package.json、SKILL.md frontmatter、`scripts/harness.py` 的 `VERSION` 常量），检查模式输出差异报告（exit 0/2/1），`--apply` 以 `VERSION` 常量为唯一真源原子写入三处受管文件（任一失败整体回滚），`--target-version` 冲突失败关闭（`release_version_conflict`）；CHANGELOG 顶部条目仅提示不自动生成。验收层间按（路径, 清单/内容摘要, 合同版本, target_identity）键复用工作区快照与文件 SHA-256 中间产物（单次 CLI 会话内进程级缓存），verify 响应新增 `layer_reuse` 计数遥测；四层验收判定结论保持独立，fresh clone 与远端网络 I/O 不跳过。

当前验收循环合同：`evidence_checklist` 含 `required/conditional/required_receipts/skeletons/trust_requirements` 五段，高风险项不生成可自填的声明骨架。`verify` 失败载荷返回有序 `recovery_actions`，分别对应 `provide_evidence → refresh_evidence → retry_verification → incremental_admission → full_readmission`，只重做受影响层。`task changes-preview` 只返回工作区分区（`changed_in_write_scope/changed_outside_write_scope/changed_in_read_scope`）与 `attribution_status=unknown_until_evidence`，不宣称 verify 归因或“同源”。任何越出 `write_scope` 的新路径都返回 `full_readmission`/exit 4，`readmission_hint.facts_template` 同时携带范围并集、意图声明和 Gate 声明；控制器不再在 verify 中自动扩围。

## 后台治理

按 `execution_route` 执行：

- `background_direct`：创建一个有界后台子智能体；
- `background_goal`：创建目标型后台子智能体，先建立持续目标和正式方案，再执行工作包；
- `background_goal_phased`：一个目标 Owner 分阶段推进，公共层和知识地图串行合并。

复杂路线的 Plan/Progress 只能由 Harness 控制面写入。宿主先调用 `background prepare`，再建立应用内 Goal/Plan；控制器在进入 `dispatched` 和 `running` 前分别复验绑定、attempt、工作包全集与指纹。后台 Job 不得直接写 `job.json`、`plan.json`、`progress.json` 或 `events.jsonl`。

宿主能力不足时将 Job 置为 `queued_manual`，保留原路线，不静默降级。

中小型复杂 Job（`change_scoped` 估算且分数 <60 的 `background_goal`）可用 v1.7.2 声明制合并快路径减少往返，所有校验闸门与分步执行完全相同：`background dispatch --job-status running --prepare-and-run` 单命令完成 prepare→dispatched→running（已 prepared 且指纹一致时幂等跳过 prepare；phased/oversized/direct/非 change_scoped/分数 ≥60 拒绝并返回 `background_prepare_and_run_not_eligible`）；`background progress --all completed` 一次把全部工作包推进到 completed（任一非法前置态整体拒绝、不部分提交）。

```bash
python3 scripts/harness.py background list --target . --json
python3 scripts/harness.py background status --target . --job-id <job-id> --json
python3 scripts/harness.py background prepare --target . --job-id <job-id> --json
python3 scripts/harness.py background dispatch --target . --job-id <job-id> --job-status dispatched --json
python3 scripts/harness.py background dispatch --target . --job-id <job-id> --job-status running --json
python3 scripts/harness.py background dispatch --target . --job-id <job-id> --job-status running --prepare-and-run --json
python3 scripts/harness.py background progress --target . --job-id <job-id> --work-package-id <wp-id> --work-package-status in_progress --json
python3 scripts/harness.py background progress --target . --job-id <job-id> --work-package-id <wp-id> --work-package-status completed --json
python3 scripts/harness.py background progress --target . --job-id <job-id> --all completed --json
python3 scripts/harness.py background verify --target . --job-id <job-id> --assessment <file> --json
python3 scripts/harness.py background retry --target . --job-id <job-id> --json
```

后台 Job 使用 `docs-harness/background-job/v2`。业务数据面只能写合同声明范围，且不得包含 `.git/**`、`.docs-harness/**` 或 Harness Runtime；控制面只由 CLI 写入。所有 Job 固定 `may_mutate_parent=false`、`may_spawn_child_jobs=false` 和 `suppress_post_completion_dispatch=true`。

`updated|no_change` 验收要求 revision 2 Progress 的所有工作包为 `completed`；`completed_with_finding` 只允许 `completed|blocked`。retry 会归档旧 attempt 工件并要求重新 prepare，不继承完成进度。工件损坏或被篡改时只允许显式 `background prepare --repair` 修复。

任一非终态初始化期间的增量 Job 进入 `waiting_for_bootstrap_merge`；只有 bootstrap 成功且控制器复算知识 ready 才释放等待者，失败、取消、需用户输入或重大发现均失败关闭。所有知识 Job 的 `updated|no_change` 都要求最终知识状态为 ready。

v1.3 `knowledge job-status|dispatch|verify|retry` 是兼容别名；新任务使用 `background`。兼容入口不允许复杂路线跳过 prepare、dispatched、running 或进度验收。

## 质量账本

只有用户明确要求“添加到质量账本”时才执行：

```bash
python3 scripts/harness.py ledger add --target . --task-id <task-id> --review <review.json> --json
```

不得自动记录或在任务结束后主动询问。读取历史时按任务编号或关键词调用 `ledger read`，不得自动注入全部个人账本。

## 按需读取

- 当前 CLI、Schema 与状态机：`docs/contracts.md`
- active 规则：`harness-home/rules/INDEX.md`
