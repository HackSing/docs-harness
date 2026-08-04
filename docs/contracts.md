# Docs Harness v1.6.2 合同

## 1. 产品边界

Docs Harness 负责任务意图、风险 Gate、范围、上下文、授权、证据、验收、后台治理和 Git 交付检查。它不自动提交、推送、发布、安装下游项目或修改 `.gitignore`，也不把源码、本地 Runtime、当前 HEAD、远端、fresh clone、发布产物和真实 UI 合并为一个完成结论。

项目配置继续使用 `docs-harness/project-config/v4`，版本值为 `1.6.2`。Harness Home 缺失、没有合法 active 规则、规则指纹漂移、来源版本不一致或配置无效均失败关闭。

## 2. task-package/v2

新任务使用 `docs-harness/task-package/v2`：

```json
{
  "task_intent": "query",
  "candidate_intents": [
    {"intent": "query", "mutation_profile": "read_only"}
  ],
  "deferred_intents": [],
  "intent_boundary_reason_codes": [],
  "mutation_profile": "read_only",
  "read_scope": ["docs/**", ".git:history"],
  "write_scope": [],
  "git_scope": [],
  "external_scope": [],
  "allowed_actions": ["read"]
}
```

受控意图：

| 意图 | 默认变更面 | 默认路线 |
|---|---|---|
| `query` | `read_only` | `direct` |
| `audit` | `read_only` | `direct`，高风险可升级 |
| `git_inspect` | `read_only` | `direct` |
| `git_fetch` | `git_metadata_write` | `direct` |
| `git_sync` | `workspace_write` | `planned` |
| `modify` | `workspace_write` | 按 Gate 决定 |
| `external_write` | `external_write` | 至少 `planned` |

混合意图保留全部 `candidate_intents`，未来子句进入 `deferred_intents`，完成体只作为审查上下文；Gate 编译取当前任务最高变更面和风险结果。显式 facts 只能升级，不能把 `audit+fix`、`if-needed-fix` 或 `fetch+sync` 降级。英文短词按单词边界、路径按完整段匹配，`Claude Code`、`reviews`、`rapid`、`latest`、`authors` 不得产生无关 Gate。

路径范围只接受项目内相对路径、glob 或受控 Git 资源。完整句子、否定说明和自然语言边界返回 `invalid_scope_description`。自然语言约束应放入任务约束，不得伪装成路径。

## 3. 准入、路线与完成清单

准入状态保持：

```text
blocked
needs_plan
needs_authorization
ready_direct
ready_planned
ready_extended
```

只读任务允许空 `write_scope`，不会因此升级为 `planned`。`run` 返回带指纹的 `docs-harness/completion-manifest/v1`：

```json
{
  "manifest_fingerprint": "sha256:...",
  "required_evidence_types": ["source_trace"],
  "required_receipts": ["read_set"],
  "conditional_reviews": [],
  "conditional_evidence": [],
  "verification_commands": [],
  "completion_blockers": [],
  "completion_protocol": "incremental_receipts_single_final"
}
```

`verify` 只按当前清单固定项及预声明条件验收。新风险 Gate、范围扩大或清单外条件必须重新准入，不得在收尾阶段临时增加隐藏要求。补证使用增量收据；父任务最终正文只生成一次。

## 4. Git 状态合同

`git_fetch|git_sync` 绑定 `git_state_snapshot`：

```json
{
  "repo_identity": "sha256:...",
  "remote": {
    "name": "origin",
    "url_fingerprint": "sha256:...",
    "refspec": "refs/heads/main"
  },
  "preflight_target_oid": "...",
  "head": "...",
  "index_tree": "sha256:...",
  "worktree_fingerprint": "sha256:...",
  "controlled_refs_namespace": [
    ".git:refs/remotes/origin/main",
    ".git:refs/heads/main"
  ],
  "lfs_available": true,
  "submodule_available": true,
  "git_sync_scope": []
}
```

远端 URL 在计算指纹前移除用户名、密码、token、查询参数和 fragment，Runtime 不保存原文。

- `git_inspect` 只读，不要求逐文件写入范围；
- `git_fetch` 只允许声明的远端 refs/objects 变化，HEAD、索引和工作区必须不变；
- `git_sync` 绑定单一预检 OID，自动生成新增、修改、删除和重命名范围；
- 远端漂移、ref 越界、非 fast-forward、分支分歧、重叠脏改动、危险删除、LFS/Submodule 不可验证均失败关闭；
- 通过只证明对应 Git 层，不扩大为构建、运行、远端交付或 UI 完成。

## 5. 工作区漂移归因

`freeze.json.workspace_snapshot` 是首次任务基线，重新准入不刷新。验收输出：

- `task_write_set`：有可信或报告型任务写入收据支持的变化；
- `read_set`：用于结论的路径/受控资源和读取指纹；
- `concurrent_drift`：可信生产者证明来自并发进程的变化；
- `unattributed_drift`：来源不能证明的变化。

阻断规则：

- 任务写入超出 `write_scope`；
- 读取事实在结论形成后漂移；
- concurrent/unattributed 变化与读写范围重叠；
- concurrent/unattributed 变化命中安全、数据、发布或不可逆边界；
- 新增风险 Gate 或规则指纹变化。

能够证明与全部范围不重叠且不命中高风险边界的漂移只记录警告，不归因给当前任务。无 Hook 宿主不得把 `reported|partial|unknown` 扩大为已证明来源。

## 6. evidence-receipt/v2

新任务只接受 `docs-harness/evidence-receipt/v2`。必填绑定字段：

```json
{
  "task_id": "dh-...",
  "target_identity": "sha256:...",
  "package_fingerprint": "sha256:...",
  "content_set_fingerprint": null,
  "producer": {"adapter": "codex-host", "capability": "review_receipt"},
  "command_argv_digest": "sha256:...",
  "cwd": "/bounded/project/path",
  "started_at": "...",
  "ended_at": "...",
  "ttl": 3600,
  "exit_code": 0,
  "output_or_artifact_digest": "sha256:...",
  "read_set": [],
  "write_set": []
}
```

过期、跨任务、跨目标、跨 package fingerprint、不可信生产者、非零退出或摘要无效均拒绝。安全、发布、恢复等高风险证据必须来自可信 v2 生产者；报告型旧证据不能满足。

验证命令使用：

```json
{
  "argv": ["python3", "-m", "unittest"],
  "produces": ["test_result"]
}
```

`produces` 只能使用证据白名单。命令退出 0、输出摘要和工作区无额外写入同时满足后，控制器生成并持久化 v2 收据；原始 stdout/stderr 不进入 Runtime。

## 7. 上下文与授权收据

上下文使用 `docs-harness/context-receipt/v2`，复用必须同时满足：

```text
同一 task_id
同一 target_identity
同一 stage
同一 compiler_contract
同一 content_set_fingerprint
```

缓存命中时不重复返回规则和项目事实正文。跨 task、target、stage、compiler contract 或内容集合变化必须重载。授权使用 `docs-harness/authorization-receipt/v2`，始终绑定当前 package fingerprint，不按内容集合跨修订复用。

## 8. v1→v2 迁移与回滚

v1 在途任务只允许：

```bash
harness task status --task-id <id>
harness task migrate --task-id <id>
harness task migrate --task-id <id> --apply
```

迁移不静默执行。apply 在 `migration-v1-v2/` 创建 staging、全对象 backup、manifest 和 journal，再切换 task-package、compiled-task、freeze、evidence-index、context receipts 和 authorization receipts。任一步中断都按全对象备份回滚；首次 workspace 基线保持不变。旧 evidence 只读保存在 `legacy_evidence`，不满足 v2 任务。

迁移后任务进入 `needs_readmission`。存在活动 v2 任务时 `project rollback-check` 返回 `active_v2_tasks`；没有活动任务时只表示回滚窗口可用。回滚后的 v2 对象只读保留，旧控制器遇到 v2 对象必须失败关闭。

## 9. 脱敏效率事件

任务事件使用 `docs-harness/event/v2`，只保存有界字段：

```text
phase
started_at
duration_ms
reason_code
package_revision
context_cache_hit
context_load_count
readmission_count
evidence_round_count
host_receipt_count
business_action_count
```

不得保存用户任务正文、原始工具输出、环境变量、凭证或完整日志。效率结论必须由这些字段和受控原因码复算。

## 10. 双通道与后台治理

主任务完成状态与后台治理状态保持独立。`verify` 先原子写入父任务 `complete`，再逐项消费任务包冻结的 `background_deliverables`。未声明交付物返回 `not_required`，`changed_paths=[]` 返回 `no_write_no_sync`。后台合同使用 `docs-harness/background-job/v2`；v1 只读兼容，并在 `project upgrade --apply` 中幂等迁移。后台队列、失败、重试或重大问题不能回滚父任务。

### 文档真源路由

`background_governance.document_routes` 可显式声明 `architecture`、`changelog`、`todo`、`adr_root` 与 `reviews_root`。值必须是项目内 POSIX 相对路径；文件类必须已存在且为常规文件，根目录类必须已存在且为目录，路径链不得包含符号链接。未知键、错误类型、越界、glob、反斜杠、绝对路径或不存在目标统一返回 `invalid_document_route_config`，不得回退自动探测。

未显式配置的类别只扫描项目根和 `docs/` 的直接条目：三个文件类匹配同名 Markdown，ADR 与 Review 只匹配 `docs/adr`、`docs/reviews`。唯一可信候选才能解析成功；缺失、多候选或不安全候选创建零写权限 `needs_user_input` 治理 Job，并由 post-completion 返回 `action_required`。

已解析治理 Job 保存 `docs-harness/document-routes/v1` 合同、稳定 `route_base_key` 与 `route_contract_fingerprint`。估算、读写 scope、路径锁和文档类别锁都从同一合同派生。prepare、dispatch 与 verify 前重新解析；合同或目标漂移时进入 `needs_rebase` 或 `needs_user_input`。缺少路由合同的旧治理 Job 只能读取或显式迁移：宿主停止执行后先报告 `cancelled`，再通过 retry 重建新 attempt，禁止沿用或合并旧 scope。

后台路线：

- `background_direct`：有界后台执行；
- `background_goal`：持久目标与正式方案；
- `background_goal_phased`：单一目标 Owner 分阶段执行。

能力不足时进入 `queued_manual`，不得静默降级。Job 固定 `may_mutate_parent=false`、`may_spawn_child_jobs=false`、`suppress_post_completion_dispatch=true`。

后台写入分成两个平面：业务数据面只允许后台 Job 写入 `allowed_write_scope`；`job.json`、`plan.json`、`progress.json`、`events.jsonl`、锁和索引属于 Harness 控制面，只允许 CLI 写入受管 Runtime。业务范围覆盖 `.git/**`、`.docs-harness/**` 或实际 Runtime 时返回 `invalid_background_scope`，控制面豁免不会扩大业务授权。

复杂路线的标准序列为：

```text
contract_ready → background prepare → 宿主 Goal/Plan → dispatched → running
               → background progress（一次或多次）→ background verify → 终态
```

`background prepare` 只在 `contract_ready` 或 v1.6.0 在途 `dispatched` 使用。它从冻结的 `goal_contract`、`work_packages`、`job_id`、`idempotency_key` 和 attempt 确定性生成 revision 2 Plan/Progress，不写时间戳；重复调用只有在内容、绑定和指纹完全一致时返回 `already_prepared`。部分、无效、冲突或篡改工件不会被普通 prepare 覆盖，必须显式 `--repair` 先归档再生成。

`contract_ready → dispatched` 与 `dispatched → running` 都校验 Schema、revision、Job 绑定、attempt、工作包全集、进度全集和已记录指纹。缺失工件返回 `prepare_background_goal` 下一步。`knowledge job-status|dispatch|verify|retry` 继续作为弃用别名，但与 `background` 共享相同安全不变量；仅 `background_direct` 保留旧别名的 contract_ready 直达 running 兼容。

`background progress` 只允许 running 的复杂 Job，工作包 ID 必须来自冻结 Plan。合法转换是 `pending → in_progress|blocked` 和 `in_progress → completed|blocked`；相同状态幂等，倒退、跳过执行、未知 ID 或自由文本原因失败关闭。完成与剩余列表由控制器派生。

`background verify` 对 `updated|no_change` 要求全部工作包 completed；`completed_with_finding` 只允许 completed 或 blocked，并返回 blocked ID。revision 2 工件漂移失败关闭；升级前已在 running 且有绑定指纹的旧工件仅当前 attempt 可走一次 legacy verify，retry 后必须重新 prepare。

retry 只归档当前 attempt 工件、推进 attempt、清空准备引用并刷新基线，不生成新工件。后台事件仅保存有界状态、attempt、工作包 ID、原因码和指纹，不保存 Plan 正文、异常正文、任务正文、环境变量、宿主会话或调用者绝对临时路径；连续相同拒绝幂等去重。终态摘要以 `(job_id, attempt, status)` 为键。

`project init|upgrade` 共享 `knowledge_flow`：`already_ready` 不创建初始化动作；`bootstrap_new` 幂等创建单一 bootstrap；`bootstrap_in_progress` 复用活动 Job；`audit_existing` 保持零知识内容写入并返回 audit/consent 下一步。任一非终态 bootstrap 都会阻塞增量 Job。只有 bootstrap `updated|no_change` 且控制器复算知识 ready 才释放等待者；其他结果进入 `needs_user_input`。所有知识 Job 的 `updated|no_change` 都要求最终 ready，候选地图在落盘前按实际功能文档纯读取复算。

知识审查与工作量估算共享过滤器。`.git`、`.docs-harness`、依赖/构建/缓存目录、`.playwright-cli`、`zbuddy-output`、敏感路径及图片、音视频、压缩包、DMG、Office/PPT 等资产默认排除；响应返回 `excluded_summary`。assessment、consent 与 decline cache 绑定实际返回库存生成的 `knowledge_inventory_fingerprint`。

工作量估算的 `estimate_basis` 缺省为 `project_wide`，供 bootstrap、全项目审查和全量 preserve-and-merge 使用。知识增量和交付治理传入有界 `change_scoped` 候选项，按实际 `changed_paths`、selected features、deliverables 与允许写入范围路由；整仓扫描截断在此模式只降低 confidence，不单独强制 phased。响应保留 `project_scale_context` 和 `change_scope_fingerprint`，原 `source_fingerprint` 与 Job 幂等键语义不变。

知识缺失、构建中、失败或隔离只降低 `context_quality`，不自动阻断业务准入；控制规则、授权、安全、范围和必要证据继续失败关闭。

## 11. Runtime、隐私与交付层

| 项目 | 任务 Runtime | 后台 Runtime | 质量账本 |
|---|---|---|---|
| Git | `<git-dir>/docs-harness/runs/` | `<git-dir>/docs-harness/background/` | `<git-dir>/docs-harness/quality-ledger/` |
| 非 Git | `.docs-harness/runs/` | `.docs-harness/background/` | `.docs-harness/quality-ledger/` |

Runtime、锁、迁移 journal、收据和本地质量账本不进入 Git。真实知识、ADR、Changelog 和 TODO 按项目规则进入交付面。已跟踪运行态不能通过 `.gitignore` 或 exclusion 从验收面隐藏。

## 12. 退出码

| 退出码 | 产品含义 |
|---|---|
| `0` | 命令成功；只有 `verify.result=完成` 表示父任务完成 |
| `1` | 项目检查、自检或完整性读取失败 |
| `2` | 输入、合同、绑定或状态无效 |
| `3` | 需要方案、授权、证据、迁移、用户输入或 Git 交付 |
| `4` | 范围、漂移、Gate、远端、授权或规则变化，必须重新准入 |

所有文件型参数只接受文件路径。文件大小、UTF-8、JSON 类型和文件系统错误必须转成结构化错误，不回显敏感输入。
