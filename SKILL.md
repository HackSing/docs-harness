---
name: docs-harness
description: "通过独立控制器完成 Gate、任务包、降级知识上下文、主任务验收和异步文档治理。"
metadata:
  version: 1.7.4
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
- 项目存在 `.qoder/repowiki` 外部知识库时进入只消费模式：不创建 `docs/` 骨架、不执行 bootstrap/增量同步等任何知识库写动作（`knowledge bootstrap` 返回 `knowledge_external_consume_only` 失败关闭），任务准入按任务文本与 scope 命中知识卡（frontmatter 的 `name`/`scope`）作为上下文；`knowledge_status.source="repowiki"`，交接 mode 为 `external_consume_only`。
- `runtime_status`、`controller_clone_ready`、整体 `clone_ready`、远端与真实宿主验收分别报告。
- `project upgrade` preserve-and-merge 合法 `document_routes`；非法路由或缺少路由合同的在途治理 Job 返回 `needs_manual_migration`，不覆盖真源配置或旧 Job scope。

## 任务入口

每个任务的第一条动作：

```bash
python3 scripts/harness.py run --target . --task "<原始用户任务>" --json
```

只在 `ready_direct|ready_planned|ready_extended` 后进入执行。`context_quality=degraded` 表示知识缺失、构建中、失败或隔离，不改变准入状态；必须从允许范围内的代码、测试、配置和有效文档核实事实，并记录 `fallback_fact_refs`。

同一 target、任务文本、事实与工作区快照重复 `run` 时幂等复用活动任务（返回 `active_task_reused`），不重复建立上下文与授权；任务或初始工作区不同则新建，`--new-task` 强制新建。`complete|cancelled|failed|blocked` 状态的任务不复用。

规则、授权、安全、范围、用户指定交付物和必要证据异常继续失败关闭。

`run` 先编译 `task_intent`、`candidate_intents` 和 `deferred_intents`，再取当前任务最高 `mutation_profile` 和风险 Gate。未来任务子句与完成体只进入可审计边界字段，不授权当前写入。只读查询使用 `read_only + write_scope=[]`；Git inspect、fetch、sync 分别使用读取、Git 元数据写入和工作区写入合同。

宿主必须基于任务语义判断风险 Gate，并在 `--facts` 中提交 `gate_assessment`（`{"gates": [...], "rationale": "<一句话依据>"}`）：声明即全部，宽泛关键词不再叠加非安全 Gate，简单任务不会被拖入重流程。`security-sensitive`、`destructive-data`、`release-external` 是控制器代码强制的安全底线，声明不可豁免（漏判会记入 `gate_decision.floor_added` 并强制并入；文本触发用精确词表并带否定守卫，「不要部署」「删除注释」不命中）；不提交 `gate_assessment` 时回退旧的关键词推断。任务中途实际变更命中新路径 Gate 时绊线与重新准入不受声明影响。

准入响应中的 `completion_manifest` 是收尾真源。新任务证据必须使用 `docs-harness/evidence-receipt/v2`，绑定当前 task、target、package fingerprint、可信 producer、时效和读写集合；验证命令只有显式声明白名单 `produces` 才能产生语义证据。验证命令期间新建的已知临时副产物（`__pycache__`、`.pytest_cache`、`.coverage` 等缓存、测试中间产物、日志和系统垃圾）不计入工作区额外写入，只进入 `volatile_write_set` 保持可见；同名已有文件的修改或删除仍失败关闭。项目可在 `.docs-harness/config.json` 的 `verification.volatile_paths` 追加带固定根目录的 glob 白名单，全局或越界模式拒绝。最终验收晚发现仅追加、且不改变路线、授权、范围、方案字段或阻断交付物的普通 Gate 时，控制器原子增量准入并继承同轮已验证收据，宿主只加载新增上下文；高风险或合同变化继续完整重新准入。

最终验收：

```bash
python3 scripts/harness.py verify --target . --task-id <task-id> --evidence <evidence.json> --json
```

只有 `verify.result=完成` 表示父任务完成。父任务先落盘，再逐项消费冻结的 `background_deliverables`；未声明后台交付物时不得创建 Job，也不得等待 Job 终态才报告父任务结果。

合同稳定时 verify 支持五级处置：可补证据的未归因写入返回 `provide_evidence`，读取基线漂移返回 `refresh_evidence`（只失效引用漂移路径的证据），验证命令失败返回 `retry_verification`，追加上下文走 `incremental_admission`；只有范围或高风险合同变化才 `full_readmission`。证据采用受管副本保存，原始文件事后删除不影响准入。已通过的验证命令带逐项收据复用，不重复执行；仅失败或输入变化的命令重跑，`verification.command_cache_enabled=false` 可整体关闭。

write_scope 内的写入由控制器自动归因：代铸 `workspace_attribution` 收据、记录 `auto_attribution` 事件，响应含 `auto_attributed_paths`，`verification.auto_attribute_in_scope=false` 可恢复补证据流程。需要声明证据类型时只提交 `docs-harness/evidence-declaration/v1` 草案（`type`/`write_set`/`read_set`/`concurrent_drift`/`conclusion`），装订字段与 `read_set` 指纹由控制器代铸，完整 v2 收据继续接受。git_sync 遇远端漂移时 `run --task-id` 单命令完成重新准入并复用已冻结方案，pull 已落盘文件经 `git_sync_landed_scope` 自动归因，`origin/HEAD` 更新不再误判 ref 越界。

v1 在途任务只允许 `task status` 读取；必须显式执行 `task migrate --apply` 后重新准入。存在活动 v2 任务时，`project rollback-check` 必须阻断回滚。

v1.6.9 准入效率加固：scope 值形似 JSON（数组/对象整体作为单值）直接报 `invalid_scope_json` 并给出修复提示；`--facts` 等文件参数在 Windows 上传入 Git Bash `/tmp` 等 POSIX 绝对路径时，缺失文件错误附带改用工作区相对路径的提示；非 blocked/scope_changed 状态下提交 `--facts` 不再静默忽略，响应返回 `facts_ignored` 与生效条件；所有 `next_step_payload` 响应统一携带 `contract_snapshot`（当前 `allowed_scope`/`read_scope`/`write_scope`、`plan_fields`、所需证据类型），每步即可自查合同，无需额外探查。

v1.7.0 低风险轻量准入：低风险文档/规则/测试类小任务可在 `--facts` 显式声明 `fast_track: true`（声明制，不做自动推断）；仅在 direct 路线、无 high gate、write_scope 全为文档/规则/测试路径、无 `work_packages` 时生效，否则静默降级普通流程并返回 `fast_track_denied_reason`。生效后响应携带 `evidence_profile: "fast_track"`，所需证据收敛为 `code_diff`（声明验证命令时加 `test_run`）最小集；fast_track 不豁免任何 Gate，运行期命中新风险 Gate 或高风险漂移即单向降级回普通证据集（`fast_track_downgraded`）。fast_track 任务可用 `inline_note`（≤200 字）替代独立 plan 文档，非 fast_track 携带会返回 `inline_note_ignored`。`task status` 新增 `overhead_summary`（`harness_total_ms`/`wall_clock_ms`/`harness_share`），可复算 harness 自身开销占比。

v1.7.1 发版同步与验收提效：`release sync` 单命令核对四处版本真源（VERSION 文件、package.json、SKILL.md frontmatter、`scripts/harness.py` 的 `VERSION` 常量），检查模式输出差异报告（exit 0/2/1），`--apply` 以 `VERSION` 常量为唯一真源原子写入三处受管文件（任一失败整体回滚），`--target-version` 冲突失败关闭（`release_version_conflict`）；CHANGELOG 顶部条目仅提示不自动生成。验收层间按（路径, 清单/内容摘要, 合同版本, target_identity）键复用工作区快照与文件 SHA-256 中间产物（单次 CLI 会话内进程级缓存），verify 响应新增 `layer_reuse` 计数遥测；四层验收判定结论保持独立，fresh clone 与远端网络 I/O 不跳过。

v1.7.3 验收循环提效：准入三处响应（首次 run、二次 run、`task status`）携带 `evidence_checklist`（required/conditional/required_receipts/skeletons，含 write_set 条件性标注）与预生成证据骨架（含 `_instructions` 填写说明），verify 前按清单一次备齐即可消除缺证往返；同三处响应携带 `pending_context_receipts`，执行前自查未加载的上下文阶段与工作包（`work_package:<id>`）。无授权、非 git_sync 的 direct/planned 任务纯越界写入（唯一阻断为 `write_scope_violation`）由 verify 在同一次调用内增量扩展 write_scope 并继续验收（响应含 `scope_extended`/`extended_paths`，单任务上限 3 次；扩围前同轮证据先过与常规 verify 同一标准的 stale_evidence 硬校验，虚报不扩围）；授权任务、git_sync、混合阻断或超限时 exit 4 并携带 `readmission_hint`（精确扩围 `facts_template` + 可执行 `example_argv`），一次重准入即过。`concurrent_drift_overlap` 的 hint 给出收窄 scope（同时剔除 write_scope 与受影响时的 read_scope）与等并发落定重准入两个选项（重叠来自证据 read_set 时只能选后者；只保证失败后一次重准入即过）。verify 前可用恒只读的 `task changes-preview --task-id <id>` 预览 in_scope/outside_scope/read_set_drift（零状态变更），避免 stale_evidence 试探；stale_evidence 错误载荷含 `stale_write_paths`/`actual_changed_paths` 双清单。推荐备证流程：准入读 `evidence_checklist` 知道备什么 → 执行中按清单随手铸 `docs-harness/evidence-declaration/v1` 草案（绑定字段在 verify 时刻代铸，铸证后再改同路径不致 stale，write_set 照实写即可）→ verify 一次提交全齐。宿主未照准入指引执行时仍有兜底：`action_context_missing` 与缺证的 exit 3 失败载荷自身携带 `pending_context_receipts` 与完整 `evidence_checklist`（骨架与清单同批），照失败载荷补齐即过，不依赖指令遵守。

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
