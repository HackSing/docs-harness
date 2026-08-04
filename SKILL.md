---
name: docs-harness
description: "通过独立控制器完成 Gate、任务包、降级知识上下文、主任务验收和异步文档治理。"
metadata:
  version: 1.6.4
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

准入响应中的 `completion_manifest` 是收尾真源。新任务证据必须使用 `docs-harness/evidence-receipt/v2`，绑定当前 task、target、package fingerprint、可信 producer、时效和读写集合；验证命令只有显式声明白名单 `produces` 才能产生语义证据。验证命令期间新建的已知临时副产物（`__pycache__`、`.pytest_cache`、`.coverage` 等缓存、测试中间产物、日志和系统垃圾）不计入工作区额外写入，只进入 `volatile_write_set` 保持可见；同名已有文件的修改或删除仍失败关闭。项目可在 `.docs-harness/config.json` 的 `verification.volatile_paths` 追加带固定根目录的 glob 白名单，全局或越界模式拒绝。最终验收晚发现仅追加、且不改变路线、授权、范围、方案字段或阻断交付物的普通 Gate 时，控制器原子增量准入并继承同轮已验证收据，宿主只加载新增上下文；高风险或合同变化继续完整重新准入。

最终验收：

```bash
python3 scripts/harness.py verify --target . --task-id <task-id> --evidence <evidence.json> --json
```

只有 `verify.result=完成` 表示父任务完成。父任务先落盘，再逐项消费冻结的 `background_deliverables`；未声明后台交付物时不得创建 Job，也不得等待 Job 终态才报告父任务结果。

合同稳定时 verify 支持五级处置：可补证据的未归因写入返回 `provide_evidence`，读取基线漂移返回 `refresh_evidence`（只失效引用漂移路径的证据），验证命令失败返回 `retry_verification`，追加上下文走 `incremental_admission`；只有范围或高风险合同变化才 `full_readmission`。证据采用受管副本保存，原始文件事后删除不影响准入。已通过的验证命令带逐项收据复用，不重复执行；仅失败或输入变化的命令重跑，`verification.command_cache_enabled=false` 可整体关闭。

v1 在途任务只允许 `task status` 读取；必须显式执行 `task migrate --apply` 后重新准入。存在活动 v2 任务时，`project rollback-check` 必须阻断回滚。

## 后台治理

按 `execution_route` 执行：

- `background_direct`：创建一个有界后台子智能体；
- `background_goal`：创建目标型后台子智能体，先建立持续目标和正式方案，再执行工作包；
- `background_goal_phased`：一个目标 Owner 分阶段推进，公共层和知识地图串行合并。

复杂路线的 Plan/Progress 只能由 Harness 控制面写入。宿主先调用 `background prepare`，再建立应用内 Goal/Plan；控制器在进入 `dispatched` 和 `running` 前分别复验绑定、attempt、工作包全集与指纹。后台 Job 不得直接写 `job.json`、`plan.json`、`progress.json` 或 `events.jsonl`。

宿主能力不足时将 Job 置为 `queued_manual`，保留原路线，不静默降级。

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
