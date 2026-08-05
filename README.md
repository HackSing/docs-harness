# Docs Harness

> 为没有原生 Hook 的 AI 编程宿主提供可安装、可追踪、可验收，并且“主交付优先、文档异步治理”的任务控制闭环。

Docs Harness v1.6.4 把重复协作成本降下来：同一任务重复 `run` 幂等复用活动任务；合同与方案一次冻结，新增 Gate 只补差异字段；证据采用受管副本，已通过的验证命令带逐项收据复用，只重跑失败或输入变化的命令。合同稳定时 `verify` 按五级处置返回（补证据/重读/重试/增量准入/完整重新准入），不再把可补救问题一律升级为重新准入。v1.6.3 让 `verify` 的本地验证命令对验证期间新建的已知临时副产物（缓存、测试中间产物、日志和系统垃圾，如 `__pycache__`、`.pytest_cache`、`.coverage`）不再误判为额外写入；同名已有文件被修改或删除仍失败关闭。项目可通过 `.docs-harness/config.json` 的 `verification.volatile_paths` 追加带固定根目录的 glob 白名单，全局或越界模式拒绝。v1.6.2 为后台文档治理增加失败关闭的真源路由合同：显式配置优先，未配置时只接受根目录或 `docs/` 下的唯一可信候选；缺失、多候选、非法配置或运行时漂移都不会获得写权限。研发任务仍拆成两条状态独立的通道：

- 主任务通道完成用户价值、用户明确要求的交付物和必要验收；
- 后台治理通道处理知识初始化、知识增量、ADR、Changelog、TODO 和非阻塞证据整理。

主任务 `verify` 通过后先原子写入 `control_status=complete`，再创建后台 Job。后台排队、失败、重试或发现新问题，都不能回滚父任务的历史完成事实。

## 产品边界

Docs Harness 负责 Gate、任务包、上下文、授权、证据、后台 Job 和 Git 交付检查。它不负责：

- 绕过宿主直接创建真实 Agent；
- 自动提交、推送、发布或修改 `.gitignore`；
- 把本地健康、当前 HEAD、远端、fresh clone、发布产物和真实 UI 混成一个完成结论；
- 在知识缺失时编造项目事实；
- 自动写入个人质量账本。

控制规则、授权、安全、范围和必要验收继续失败关闭。知识缺失、构建中、失败或隔离只返回 `context_quality=degraded`，业务任务仍保留 `ready_direct|ready_planned|ready_extended` 准入状态。

## 核心流程

```text
原始任务
  ↓
run：意图/变更面 → 风险 Gate → task-package/v2 + completion_manifest
  ↓
context / plan / authorization / progress
  ↓
实现与必要验收
  ↓
verify：原子写入父任务 complete
  ↓
立即返回最小交付回执
  └─ 后台候选项 → workload estimate → 统一 Background Job
                              ├─ background_direct
                              ├─ background_goal
                              └─ background_goal_phased
```

文档是否阻塞由产品角色决定，不由扩展名决定。用户明确要求的文档、协议/迁移/恢复说明、安全审批材料和必要验收证据进入 `blocking_deliverables`；事后 ADR、Changelog、TODO、知识同步和完整证据排版进入 `background_deliverables`。

## 安装

从包含 `harness-home/rules/` 的来源目录执行：

```bash
python3 /path/to/docs-harness/scripts/harness.py project init \
  --target /path/to/project \
  --json
```

安装会 preserve-and-merge `AGENTS.md` / `CLAUDE.md`，复制控制脚本和固定规则快照，并写入 `docs-harness/project-config/v4`。

- 新项目：创建最小知识骨架，执行有界工作量评估，创建 `knowledge_bootstrap` Job，立即返回安装完成和 `knowledge_status=building`；
- 已有 `docs/`：安装阶段零文档内容写入，只返回审查、工作量和同意边界；
- Git 项目：控制器未进入当前 HEAD 时返回 `needs_delivery`；知识未完成或未进入 HEAD 时整体 `clone_ready=false`。

安装完成不等于远端或 fresh clone 已验收。

### 升级版本标记

`project diff|upgrade` 会同步 `AGENTS.md` 和 `docs/INDEX.md` 中 Docs Harness 明确拥有的受管版本区块。预览会返回 `from_version`、`to_version` 和人工迁移项；仅对完全匹配白名单的旧索引模板自动迁移。

归属不明的旧版本正文保持不变，apply 返回 `needs_manual_migration`。升级同时返回 `knowledge_flow.mode`：ready 项目为 `already_ready`，活动初始化为 `bootstrap_in_progress`，无 docs 的旧项目为 `bootstrap_new`，已有 docs 且知识未 ready 为 `audit_existing`。Git 当前 HEAD、远端与 fresh clone 仍需分层验收。

## 工作量评估与宿主路线

```bash
python3 scripts/harness.py knowledge estimate --target . --json
python3 scripts/harness.py background estimate --target . --candidate <candidate.json> --json
```

评估器有界扫描文件数量、功能候选、架构域、技术栈、知识缺口和依赖，输出原始分数、评分路线、硬升级原因和最终路线：

| 分数 | 工作量 | 路线 |
|---:|---|---|
| 0–24 | simple | `background_direct` |
| 25–59 | complex | `background_goal` |
| 60–100 | oversized | `background_goal_phased` |

bootstrap、全项目审查和全量 preserve-and-merge 使用 `project_wide`；知识增量与交付治理使用 `change_scoped`，按实际变化路径、功能和交付物估算。只有 project-wide 才会因扫描超限、全仓多域或大量既有文档硬升级；响应保留 `project_scale_context`、`change_scope_fingerprint`、`raw_score` 和原 `source_fingerprint`。

宿主能力不足时：

- 完全不支持后台：Job 进入 `queued_manual`；
- 只支持普通后台：复杂路线仍保持 `background_goal|background_goal_phased`，不静默降级；
- 支持目标但不支持并行：由单一目标 Owner 串行执行；
- 支持完整能力：按原路线执行。

## 日常任务

每个任务的第一条动作：

```bash
python3 scripts/harness.py run \
  --target . \
  --task "<原始用户任务>" \
  --json
```

`run` 返回唯一任务包、准入状态、`context_quality`、阻塞/后台交付物、带指纹的 `completion_manifest` 和下一条可执行命令。`planned` 与 `extended` 使用同一个 `task-id` 完成方案和工作包，不创建重复任务。同一 target、任务文本、事实与工作区快照重复 `run` 时幂等复用活动任务（返回 `active_task_reused`）；任务或初始工作区不同则新建，`--new-task` 强制新建，`complete|cancelled|failed|blocked` 状态不复用。

任务包使用 `docs-harness/task-package/v2`：

- `task_intent`：`query|audit|git_inspect|git_fetch|git_sync|modify|external_write`；
- `candidate_intents|deferred_intents|intent_boundary_reason_codes`：区分当前动作、未来动作和完成体上下文；
- `mutation_profile`：`read_only|git_metadata_write|workspace_write|external_write`；
- `read_scope|write_scope|git_scope|external_scope` 分别承载读取、工作区写入、Git 元数据和外部目标；
- 混合意图按最高变更面和最高风险 Gate 编译，显式 facts 只能升级；
- 只读任务默认 `ready_direct + read_only + write_scope=[]`，自然语言范围返回 `invalid_scope_description`。

最终验收：

```bash
python3 scripts/harness.py verify \
  --target . \
  --task-id <task-id> \
  --evidence <evidence.json> \
  --json
```

`result=完成` 的回执包含：

- `delivered_value`；
- `acceptance_layers`：只列出证据已验证的交付层；
- `delivery_layers`：每层交付的 `expectation`（`not_applicable|not_requested|required`）、`status` 与 `evidence_refs`；
- `minimum_evidence`；
- 受控 `known_limit_codes` 和人类说明：只从“明确要求且尚未验证”的层派生，只读任务不再显示不适用的远端未验证提示；
- `parent_completed_at`；
- 后台 Job ID 与各自 `created_at`；没有声明后台交付物时返回 `post_completion.status=not_required`。

这能证明控制器先固化父任务再创建后台合同。宿主不能提供 `user_response_emitted_at` 时，只能声称“后台状态不阻塞响应生成”，不能声称“界面零等待”。

### Git 与工作区验收

`git_fetch|git_sync` 冻结脱敏远端身份、目标 OID、HEAD、索引、工作区和受控 refs。`git_sync` 根据预检目标自动生成变化范围，不要求操作者手写文件清单；远端漂移、非 fast-forward、ref 越界、重叠脏改动、LFS/Submodule 不可验证均失败关闭。

验收分别输出 `task_write_set`、`read_set`、`concurrent_drift` 和 `unattributed_drift`。无关且不重叠的漂移只告警；读取事实、写入范围或安全/数据/发布边界重叠时重新准入。仅追加且不改变路线、授权、范围、方案字段或阻断交付物的普通 Gate 由控制器原子增量准入；同轮收据随来源指纹留下继承记录并继续复用，宿主只加载新增上下文。产品、架构、安全、数据破坏、外部发布、前端设计、extended 路线及其他合同变化仍完整重新准入。

合同稳定时 verify 按五级处置：未归因写入全部在写入范围内返回 `provide_evidence`（退出 3，补证据后继续，不增 package revision）；读取基线漂移返回 `refresh_evidence`，只失效引用漂移路径的证据后重读；验证命令失败返回 `retry_verification`；追加 Gate 走 `incremental_admission`；只有范围、高风险合同或规则变化才 `full_readmission`（退出 4）。

### v2 证据与上下文复用

新任务只接受 `docs-harness/evidence-receipt/v2`。收据首次提交必须绑定当前任务、目标、任务包指纹、可信生产者、命令摘要、时效、结果摘要及读写集合；过期、跨任务、跨目标和不可信生产者均拒绝。若同一次 `verify` 只触发兼容的增量 Gate 准入，控制器可把已经校验的收据原子继承到新包并记录原始/来源 package fingerprint，不要求宿主伪造或重写收据。验证命令必须使用白名单 `produces` 声明证据类型，退出 0 不会自动获得任意语义证据。

证据文件在验收时复制进受管 artifact store，准入只依赖受管副本；原始文件事后删除或修改不影响已采纳证据。验证命令按 argv、`produces` 与输入指纹带逐项收据：输入不变且上次通过的命令直接复用（`cache_hit=true`），只重跑失败或输入变化的命令；`verification.command_cache_enabled=false` 可整体关闭。

上下文收据按同一 task、target、stage、compiler contract 和 `content_set_fingerprint` 复用；命中缓存时不重复返回规则和项目事实正文。授权仍绑定当前 package fingerprint，不跨修订复用。

### v1 在途任务迁移

```bash
python3 scripts/harness.py task status --target . --task-id <task-id> --json
python3 scripts/harness.py task migrate --target . --task-id <task-id> --json
python3 scripts/harness.py task migrate --target . --task-id <task-id> --apply --json
python3 scripts/harness.py project rollback-check --target . --json
```

v1 任务默认只读兼容，不静默改写。显式迁移使用 staging、全对象备份、manifest 和 journal；中断自动回滚，迁移后必须按 v2 重新准入。存在活动 v2 任务时不允许项目回滚；v2 对象在回滚后只读保留，旧控制器遇到 v2 必须失败关闭。

### 任务终结处置

废弃的 v2 任务、v1 历史对象和超期终态对象有受支持的终结入口，不需要手工删除 Runtime 目录：

```bash
python3 scripts/harness.py task cancel --target . --task-id <task-id> --reason-code operator_abandoned --json
python3 scripts/harness.py task cancel --target . --task-id <task-id> --reason-code operator_abandoned --apply --json
python3 scripts/harness.py task archive --target . --task-id <task-id> --reason-code superseded --apply --json
python3 scripts/harness.py task list --target . --json
python3 scripts/harness.py task prune --target . --older-than 30 --dry-run --json
python3 scripts/harness.py task prune --target . --older-than 30 --apply --json
```

- `cancel` 只把编译状态置为 `cancelled` 并追加不可变取消事件，不改写任务包、freeze 和既有证据；相同原因幂等，不同原因冲突失败；
- `archive` 只写独立处置索引，v1 源对象保持只读；`task list` 默认隐藏已归档对象，源指纹漂移失败关闭；
- `prune` 缺省 dry-run 并冻结候选清单，`--apply` 只删除清单中指纹未变化、已过保留期且无未终结子 Job 或严重发现的对象。

## 统一后台 Job

```bash
python3 scripts/harness.py background list --target . --json
python3 scripts/harness.py background status --target . --job-id <job-id> --json
python3 scripts/harness.py background prepare --target . --job-id <job-id> --json
python3 scripts/harness.py background dispatch --target . --job-id <job-id> --job-status dispatched --json
python3 scripts/harness.py background dispatch --target . --job-id <job-id> --job-status running --json
python3 scripts/harness.py background progress --target . --job-id <job-id> --work-package-id <wp-id> --work-package-status in_progress --json
python3 scripts/harness.py background progress --target . --job-id <job-id> --work-package-id <wp-id> --work-package-status completed --json
python3 scripts/harness.py background verify --target . --job-id <job-id> --assessment <file> --json
python3 scripts/harness.py background retry --target . --job-id <job-id> --json
python3 scripts/harness.py background prune --target . --older-than 30 --json
```

Job 类型为 `knowledge_bootstrap`、`knowledge_incremental_sync`、`delivery_governance` 和 `critical_followup`。所有 Job：

- 使用 `docs-harness/background-job/v2`，upgrade 幂等迁移活动 v1 Job；
- 固定 `may_mutate_parent=false`、`may_spawn_child_jobs=false`、`suppress_post_completion_dispatch=true`；
- 业务数据面声明允许读、允许写和禁止写范围，且不得覆盖 `.git/**`、`.docs-harness/**` 或 Harness Runtime；
- `job.json`、`plan.json`、`progress.json`、`events.jsonl`、锁和索引只由 Harness CLI 写；
- 在运行前校验基线与锁；
- 复杂路线先 prepare revision 2 工件，在 `dispatched` 和 `running` 前分别校验绑定、attempt、工作包全集和指纹；
- `updated|no_change` 要求全部工作包 completed，重大发现只允许 completed 或 blocked；
- 最多尝试 3 次；
- retry 归档旧 attempt 工件且不继承进度，普通 prepare 不覆盖无效工件，修复必须显式 `--repair`；
- 用脱敏、去重的 append-only 事件记录状态变化；
- 终态摘要按 Job、attempt、status 进入本地索引后，才可能成为 prune 候选。

`completed_with_finding` 会幂等创建独立 `critical_followup`，并显示 `delivery_confidence=questioned`，不会改写父任务。

初始化 Job 处于任一非终态时，增量 Job 进入 `waiting_for_bootstrap_merge`。只有 bootstrap 以 `updated|no_change` 结束且控制器复算知识 ready，等待者才重建基线进入 `contract_ready`；失败、取消、需用户输入或重大发现会把等待者置为 `needs_user_input`。

v1.3 的 `knowledge job-status|dispatch|verify|retry` 仍可使用，响应包含 `deprecated_alias=true` 和对应 `background` 替代命令；兼容入口不能绕过复杂路线的 prepare、dispatched、running 或进度门禁。

## 知识审查与同意

```bash
python3 scripts/harness.py knowledge status --target . --json
python3 scripts/harness.py knowledge audit --target . --json
python3 scripts/harness.py knowledge audit --target . --assessment <assessment.json> --json
python3 scripts/harness.py knowledge update --target . --assessment <assessment.json> --consent <consent.json> --json
```

已有文档项目的同意/拒绝回执绑定审查指纹、过滤后项目库存指纹和受控范围。库存排除生成目录、运行产物、敏感路径和 Office/PPT 等二进制资产，并返回分类摘要；项目可通过受控 `knowledge.inventory_include` 显式纳入特殊路径。指纹未变的拒绝不会重复询问；审查变化或范围扩大时必须重新取得同意。

知识地图损坏时状态为 `quarantined`，控制器不加载不可信内容。Agent 必须从允许范围内的代码、测试、配置和有效文档现场核实，并在任务完成时记录 `fallback_fact_refs`。

## Runtime 与交付面

| 工作区 | 任务 Runtime | 后台 Runtime | 质量账本 |
|---|---|---|---|
| Git | `<git-dir>/docs-harness/runs/` | `<git-dir>/docs-harness/background/` | `<git-dir>/docs-harness/quality-ledger/` |
| 非 Git | `<project>/.docs-harness/runs/` | `<project>/.docs-harness/background/` | `<project>/.docs-harness/quality-ledger/` |

Runtime、队列、锁、计划、进度和本地回执不进入 Git。真实知识、ADR、Changelog 和 TODO 按项目规则进入 Git 交付面。`background prune` 缺省只 dry-run；只有显式 `--apply` 才删除已终结、已索引且不含严重发现的 Job。`task prune` 同样缺省 dry-run 并冻结候选清单，`--apply` 只删除清单中指纹未变化的终态任务对象。

## 质量账本

质量账本只在用户明确要求时写入：

```bash
python3 scripts/harness.py ledger add --target . --task-id <task-id> --review <review.json> --json
python3 scripts/harness.py ledger read --target . --query "<关键词>" --limit 5 --json
```

它保持本地、脱敏、不可变，不因 v1.4 统一后台引擎而自动记录。

## 开发与验收

```bash
npm test
npm run self-test
npm run pack:check
```

这些命令只证明当前来源包的对应检查。发布还必须分别取得临时项目、真实 Git/fresh clone、直接后台路线、目标型后台路线、部分支持宿主和完全不支持宿主的证据。

当前版本：`1.6.4`。详细 Schema 与状态机见 [docs/contracts.md](docs/contracts.md)，版本历史见 [CHANGELOG.md](CHANGELOG.md)。
