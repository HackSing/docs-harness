# Docs Harness v1.7.1 合同

## 1. 产品边界

Docs Harness 负责任务意图、风险 Gate、范围、上下文、授权、证据、验收、后台治理和 Git 交付检查。它不自动提交、推送、发布、安装下游项目或修改 `.gitignore`，也不把源码、本地 Runtime、当前 HEAD、远端、fresh clone、发布产物和真实 UI 合并为一个完成结论。

项目配置继续使用 `docs-harness/project-config/v4`，版本值为 `1.7.1`。Harness Home 缺失、没有合法 active 规则、规则指纹漂移、来源版本不一致或配置无效均失败关闭。

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
| `git_commit` | `git_metadata_write` | `direct` |
| `modify` | `workspace_write` | 按 Gate 决定 |
| `external_write` | `external_write` | 至少 `planned` |

`git_commit` 覆盖本地提交层（写 `.git` 对象/索引/分支引用，不改工作区、不触远端）：默认动作 `read` + `git_commit`，不附带 `git_fetch` 授权，也不触发远端交付层；触发词为「git commit」「commit」「本地提交」「提交改动」「提交代码」「提交当前」「提交工作区」「提交暂存」，裸「提交」刻意不收（避免「提交证据/提交方案」误判）。任务文本关键词不参与 Gate 分类；规则 keywords 匹配与交付层需求判定仍各自使用否定守卫，因此「不推送」「无需部署」「不要发布」不会误匹配 `DH-RELEASE-AUTHORIZATION-ROLLBACK` 规则，也不会把 `remote_delivery` 层标为 `required`。

宿主使用 `intent_assessment` 提交权威意图声明（`{"intents": [...], "rationale": "..."}`）；兼容字段 `task_intent|candidate_intents` 同样视为显式声明。一旦声明，任务文本启发式不得增补或覆盖；未声明时的启发式结果只是诊断候选，不能授予写权限。写任务缺少意图声明失败关闭，响应携带可填的声明模板。

宿主必须在 facts 中提交 `gate_assessment`（`{"gates": [...], "rationale": "..."}`，rationale 为 500 字符内非空字符串）对 Gate 做权威语义判断。写任务缺少该声明失败关闭。初始路径只能推断 `document-edit|code-edit|testing-acceptance` 这类封闭结构 Gate，不根据 `security|auth|api|migration|database|frontend` 等开放路径名称猜语义。项目级稳定映射使用 `.docs-harness/config.json` 的 `gate_path_rules: [{"pattern": "...", "gates": [...]}]` 显式声明，运行期绊线仅依该映射触发语义 Gate。

路径范围只接受项目内相对路径、glob 或受控 Git 资源。完整句子、否定说明和自然语言边界返回 `invalid_scope_description`。形似 JSON 的值（数组或对象整体作为单个 scope 字符串）返回 `invalid_scope_json` 并附修复提示；`--scope` 是可重复单值参数，facts 中 scope 字段必须是字符串数组。自然语言约束应放入任务约束，不得伪装成路径。

所有经 `next_step_payload` 的逐步响应统一携带 `contract_snapshot`：当前 `allowed_scope`/`read_scope`/`write_scope` 实际值、`plan_fields` 与完成清单所需证据类型（`required_evidence_types`）。快照只含合同字段，不含任务正文与原始环境信息。`--facts` 仅在 blocked 或 scope_changed 的重准入时生效；其他状态下提交 facts 不再静默忽略，响应返回 `facts_ignored=true` 与 `facts_effective_condition` 说明。Windows 上文件参数（`--facts`/`--plan`/`--evidence`/`--authorization` 等）传入 Git Bash `/tmp` 等 POSIX 绝对路径导致文件缺失时，错误附带改用工作区相对路径的 `suggested_fix`。

`run` 按 active task key 幂等复用：同一 target、归一化任务文本、事实指纹与当前工作区快照命中活动任务时返回 `active_task_reused` 和原 task_id，不重复建立上下文与授权。任务文本、事实或初始工作区不同则新建；`--new-task` 强制新建；`complete|cancelled|failed|blocked` 状态的任务不复用，blocked 保证重新校验规则。

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

`verify` 只按当前清单固定项及预声明条件验收，不得在收尾阶段静默增加隐藏要求。产品、架构、安全、数据破坏、外部发布、前端设计、extended 路线，以及任何改变执行路线、授权、范围、方案字段、工作包或阻断交付物的新 Gate，必须完整重新准入。仅追加且保持上述合同不变的普通 Gate 由控制器原子生成下一 package revision：保留首次冻结基线，把同轮已校验收据以 `origin_package_fingerprint|adopted_from_package_fingerprint|adoption_reason` 留痕后继承，并在需要时只要求加载新 action context；宿主不重新执行完整 `run`，也不重新生成相同证据。补证使用增量收据；父任务最终正文只生成一次。

低风险任务可显式声明 `fast_track: true`；生效时 `required_evidence_types` 收敛为 `code_diff + change_review`，声明验证命令时再加 `test_run`。`code_diff` 证明差异事实，`change_review` 证明变更与意图一致，两者不得互相替代。

合同与方案一次冻结：package revision 变化时控制器生成 `contract_delta`（新增证据类型、收据、条件项与阻断项）并归档到 `package-history`；新增 Gate 只缺方案字段时返回 `complete_plan_delta` 和 `plan_delta_contract`，宿主只补充缺失字段，不重做完整方案。上下文正文按 task、stage、compiler contract 与内容指纹跨阶段复用，不随 revision 重复加载。

准入三处响应携带 `evidence_checklist` 五段：`required`、`conditional`、`required_receipts`、`skeletons`、`trust_requirements`。高风险证据列入 `trust_requirements` 且不生成可自填骨架，明确要求受控入口。缺证失败载荷同样携带完整清单、`pending_context_receipts` 和有序 `recovery_actions`，宿主可直接执行最小修复动作。

完成回执保留兼容字段，同时携带结构化 `delivery_layers`。每一层包含 `expectation`（`not_applicable|not_requested|required`）、`status`（`not_verified|verified`）与 `evidence_refs`；最小层级为：

```text
source
local_verification
git_head
remote_delivery
fresh_clone
release_artifact
ui
external_state
```

`query|audit|git_inspect` 默认将 `remote_delivery` 与 `fresh_clone` 标记为 `not_applicable`；本地 `modify` 未声明 Git 或外部交付时标记为 `not_requested`；`git_sync|external_write` 或成功标准明确要求远端、发布、安装或 fresh clone 时标记为 `required`。`acceptance_layers` 只列出证据已验证的层，不再由完成函数固定生成；`known_limit_codes` 只从 `expectation=required` 且未验证的层派生，`remote_delivery_not_verified` 不再是无条件默认值。`not_applicable|not_requested` 不产生“未验证”告警，但必须在 `delivery_layers` 中可见。远端、fresh clone、发布产物与 UI 证据分别绑定独立证据类型（`remote_delivery`、`fresh_clone_verification`、`release_acceptance`、`ui_acceptance`），不得由一个 Git 后检统一推导。

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
- `controlled_refs_namespace` 自动包含 `.git:refs/remotes/<remote>/HEAD`（由 `git_scope` 的远端引用推导），`origin/HEAD` 的创建或更新不再判为 ref 越界；
- 远端漂移重新准入时，用 `git diff --name-status 旧HEAD 新HEAD`（旧 HEAD 为 unborn 时对空树 diff）算出 pull 已落盘文件，记入任务包 `git_sync_landed_scope`（跨多次漂移累积）并并入 `write_scope`；归因时与 `git_sync_scope` 同等待遇自动认领，diff 之外的杂散写入依旧阻断；
- 远端漂移重新准入时，若旧方案受管副本指纹仍有效且新旧方案合同除范围字段外逐字段相等，新 compiled 直接继承已冻结的 `plan_ref`/`plan_fingerprint`/`plan_artifact`，单条 `run --task-id` 即回到 `ready_planned`；合同变化照旧重交方案；
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

合同稳定（无规则错误且 active 规则指纹等于冻结规则）时，verify 按五级处置返回：

| 处置 | 条件 | 退出码 |
|---|---|---|
| `provide_evidence` | 未归因写入全部在 `write_scope` 内，可补证据归因（默认由控制器代铸 `workspace_attribution` 收据自动认领，见第 6 节 `auto_attribute_in_scope`；开关关闭时才走此处置） | `3`，不增 package revision |
| `refresh_evidence` | 读取基线漂移，只失效引用漂移路径的证据后重读 | `3`，不增 package revision |
| `retry_verification` | 验证命令失败，输入不变 | `3` |
| `incremental_admission` | 仅追加普通 Gate 且合同不变 | `3` |
| `full_readmission` | 范围、高风险合同或规则变化 | `4` |

重读漂移路径后其指纹与当前快照一致即视为已解释，不再阻断。

范围是语义合同，不存在 verify 内自动扩围例外。任何 `write_scope_violation` 都返回 exit 4 `full_readmission`；控制器不修改 package revision、不重绑旧证据、不产生 `scope_extended` 或 `scope_extension_readmission`。

`write_scope_violation` 的 `readmission_hint.facts_template` 包含新旧 `write_scope` 并集、`intent_assessment` 与 `gate_assessment`，宿主必须重新确认扩围后的意图和风险。`task changes-preview` 仅返回 `changed_in_write_scope|changed_outside_write_scope|changed_in_read_scope` 分区与 `attribution_status=unknown_until_evidence`，不代表 verify 归因结论。

## 6. evidence-receipt/v2

新任务接受 `docs-harness/evidence-declaration/v1` 或 `docs-harness/evidence-receipt/v2`；两者由宿主/外部提交时均是 `reported`。v2 必填绑定字段：

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

过期、跨任务、跨目标、跨 package fingerprint、非零退出或摘要无效均拒绝。生产者名称只是识别字段，不是信任来源：宿主提交的 v2 JSON 一律是 `reported`，且不得冒充 `docs-harness/git_postcheck|verification_command|auto_attribution` controller producer。只有这些受控内部入口可产生 `verified`。

验证命令使用：

```json
{
  "argv": ["python3", "-m", "unittest"],
  "produces": ["test_result"]
}
```

`produces` 只能使用证据白名单。命令退出 0、输出摘要和工作区无额外交付写入同时满足后，控制器生成并持久化 v2 收据；原始 stdout/stderr 不进入 Runtime。只容忍验证期间新建的已知临时副产物：`__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`、`.tox`、`.nox`、`.hypothesis`、`.cache`、`.nyc_output`、`htmlcov` 等缓存目录，`.pyc|.pyo|.tmp|.temp|.swp|.bak|.log` 后缀，`.coverage`（含并行分片）、`.DS_Store`、`Thumbs.db`、`.eslintcache` 和编辑器临时文件；同名已有文件被修改或删除仍阻断。项目可在 `.docs-harness/config.json` 的 `verification.volatile_paths` 追加带固定根目录的 glob 白名单，`*|**`、越界、绝对路径和控制面路径失败关闭。被容忍的新建写入进入 `volatile_write_set` 保持可见，其余写入仍使命令失败并只列出阻断路径。

宿主提交的证据文件在验收时复制进受管 artifact store（任务 Runtime 内），准入只依赖受管副本；原始文件事后删除或修改不影响已采纳证据，收据保留 `artifact_ref` 指回副本。

证据可以简化为 `docs-harness/evidence-declaration/v1` 声明草案，宿主只提供声明正文：

```json
{
  "schema_version": "docs-harness/evidence-declaration/v1",
  "type": "test_result",
  "write_set": ["src/core.py"],
  "read_set": ["docs/architecture.md"],
  "concurrent_drift": [],
  "conclusion": "验收通过"
}
```

`type`、`write_set`、`changed_paths`、`read_set`、`concurrent_drift`、`conclusion` 由宿主声明；绑定字段与指纹由控制器在 verify 时刻代铸，producer 记 `("docs-harness", "host_declaration")`。代铸只解决时效与绑定，信任等级仍为 `reported`；宿主声明的 `concurrent_drift` 只记为 `reported_concurrent_drift`，不能证明并发归因，也禁止同路径被自动认领。与任务读写范围重叠时返回 `concurrent_drift_unverified + provide_evidence`，要求受控并发归因收据。

合同稳定且唯一阻断是 `write_scope` 内未归因写入时，控制器默认代铸 `workspace_attribution` 收据。它只消解写入所有权，不满足语义验收；每个写任务至少需要一类非 attribution 证据，没有其他合同要求时默认为 `change_review`。

验证命令使用 `docs-harness/verification-command-receipt/v1` 逐项收据：命令按 argv、声明 `produces` 与输入指纹（读取集与工作区相关写入）绑定。输入不变且上次通过的命令直接复用收据（`cache_hit=true`），不重复执行；输入变化、上次失败或 volatile 副产物改变输入时重跑。只重跑失败或输入变化的命令，其余沿用通过收据。项目可在 `.docs-harness/config.json` 设置 `verification.command_cache_enabled=false` 整体关闭复用；关闭时不读不写收据缓存，验证事件记录 `command_cache_enabled=false`。

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

## 8.1 任务终结处置

v2 任务取消：

```bash
harness task cancel --task-id <id> --reason-code <reason-code>
harness task cancel --task-id <id> --reason-code <reason-code> --apply
```

缺省为预览，只有显式 `--apply` 才写入。受控原因码为 `host_task_closed|superseded|duplicate|invalid_admission|operator_abandoned`。取消前要求对象为有效 v2 任务、任务包与编译状态及 freeze 指纹一致、当前状态不是 `complete|cancelled|failed`、不存在活动状态锁。取消只把 `compiled-task.json.control_status` 置为 `cancelled`、清空 `next_action` 并记录 `cancelled_at` 与受控原因码，同时向 `events.jsonl` 追加不可变 `task_cancelled` 事件；任务包、freeze、既有证据与上下文收据不被改写。相同任务相同原因重复取消返回同一幂等结果，不同原因返回 `task_cancel_conflict`，不得覆盖首次处置事实。取消不可改回活动状态；需要继续原目标时创建新任务并引用原任务。

v1 对象保持只读，通过 `task archive` 写入独立的 `docs-harness/task-disposition-index/v1` 处置索引：

```text
task_id
source_schema
source_object_fingerprint
disposition=archived
reason_code
recorded_at
```

归档只影响任务列表和治理候选，不修改 v1 任务目录。`task list` 默认隐藏已归档对象，显式 `--include-archived` 才展示；源对象指纹漂移时归档失效并失败关闭（`archive_source_drift`）。归档不替代 v1→v2 显式迁移合同。

终态清理：

```bash
harness task prune --target . --older-than 30 --dry-run
harness task prune --target . --older-than 30 --apply
```

dry-run 把候选清单（含状态指纹）冻结到 `task-prune-candidates.json`；`--apply` 只删除冻结清单中指纹未变化且仍满足条件的对象，没有冻结清单时失败关闭。候选必须处于 `complete|cancelled|failed` 终态或已归档 v1、超过保留期、处置事件可追溯，且不存在锁、未终结子 Job、`completed_with_finding` 或 `critical_followup` 严重发现。物理 prune 一旦执行不承诺恢复。

变更预览（只读合同）：

```bash
harness task changes-preview --target . --task-id <id>
```

恒只读、无 `--apply`：以冻结基线对当前工作区做纯函数 diff，返回 `action`、`changed_paths`、`changed_in_write_scope`、`changed_outside_write_scope`、`changed_in_read_scope` 与 `attribution_status=unknown_until_evidence`；它只是工作区分区，不代表 verify 时的证据归因。命令不写 compiled、freeze、事件与任何状态文件，执行前后任务 state 目录逐字节一致。

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

admission、planning、context、verification、business_action 各阶段事件均以 `time.monotonic()` 记录真实 `duration_ms`。`task status` 响应携带 `overhead_summary`：`harness_total_ms`（全部事件 `duration_ms` 求和）、`wall_clock_ms`（首末事件时间差）、`harness_share`（两者比值，`wall_clock_ms` 为 0 时 `null`），作为「harness 自身开销占任务总时长比例」的复算口径；不含任务正文与路径以外信息。

verify 响应携带有界遥测字段 `layer_reuse`：`snapshot_hits`/`snapshot_misses`（工作区快照复用计数）与 `file_hash_hits`/`file_hash_misses`（文件 SHA-256 复用计数），只含计数，不含路径以外信息。

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

合并快路径（v1.7.2，声明制，不跳过任何上述闸门）：

- `background dispatch --job-status running --prepare-and-run` 把 `prepare → dispatched → running` 合并为单命令，必须显式给出 `--job-status running`（缺失或其他值失败关闭），仅支持 `contract_ready` 起点。资格限制：仅 `execution_route == "background_goal"` 且 `workload_estimate_ref` 估算为 `change_scoped`、`raw_score < 60`；phased/oversized、direct、估算缺失、非 `change_scoped` 或分数 ≥60 统一以 exit 3 `background_prepare_and_run_not_eligible` 拒绝，携带精确 `eligibility_reason_code` 并记录 `transition_rejected` 事件，不执行任何步骤。合并执行复用与分步完全相同的闸门实现：已 prepared 且指纹一致时按 `already_prepared` 幂等跳过 prepare；任一闸门失败停在该步，prepare 闸门抛出与分步 prepare 相同错误码，dispatch 闸门返回与分步 dispatch 相同的 `next_action`/`next_command_argv`/`reason_code`，并附加 `prepare_and_run: true` 与 `completed_steps`。成功响应携带 `prepare_status` 与 `dispatch_sequence`。
- `background progress --all completed` 把冻结 Plan 全部工作包一次推进到 completed：`pending → in_progress → completed` 逐包连续推进，事件逐包记录，与逐包分步执行逐条一致；已 completed 的包幂等跳过。先整体预检，任一工作包处于非法前置态（blocked 或未知状态）即整体拒绝、不写任何进度（exit 3 `background_progress_all_blocked` + `blocking_work_packages` 阻断清单 + `partial_commit: false`）。`--all` 与 `--work-package-id`/`--work-package-status` 混用失败关闭。

`background verify` 对 `updated|no_change` 要求全部工作包 completed；`completed_with_finding` 只允许 completed 或 blocked，并返回 blocked ID。revision 2 工件漂移失败关闭；升级前已在 running 且有绑定指纹的旧工件仅当前 attempt 可走一次 legacy verify，retry 后必须重新 prepare。

retry 只归档当前 attempt 工件、推进 attempt、清空准备引用并刷新基线，不生成新工件。后台事件仅保存有界状态、attempt、工作包 ID、原因码和指纹，不保存 Plan 正文、异常正文、任务正文、环境变量、宿主会话或调用者绝对临时路径；连续相同拒绝幂等去重。终态摘要以 `(job_id, attempt, status)` 为键。

`project init|upgrade` 共享 `knowledge_flow`：`already_ready` 不创建初始化动作；`bootstrap_new` 幂等创建单一 bootstrap；`bootstrap_in_progress` 复用活动 Job；`audit_existing` 保持零知识内容写入并返回 audit/consent 下一步；`external_consume_only`（项目存在 `.qoder/repowiki` 外部知识库）不创建任何知识动作。任一非终态 bootstrap 都会阻塞增量 Job。只有 bootstrap `updated|no_change` 且控制器复算知识 ready 才释放等待者；其他结果进入 `needs_user_input`。所有知识 Job 的 `updated|no_change` 都要求最终 ready，候选地图在落盘前按实际功能文档纯读取复算。

外部只消费知识源：项目存在 `.qoder/repowiki/knowledge/<locale>/`（含知识卡 `.md`）时，`knowledge_status` 直接返回 `ready` 且带 `source="repowiki"`，不再检查 `docs/` 与 `knowledge-map.json`；准入上下文按任务文本与 scope 命中知识卡 frontmatter 的 `name`/`scope` 选卡（`knowledge_context.source="repowiki"`），命中即 `context_quality=complete`，未命中沿用 `unresolved` 降级语义；知识卡枚举上限 1000（可用环境变量 `DOCS_HARNESS_REPOWIKI_CARD_LIMIT` 覆盖为正整数），超限按排序截断，`knowledge_status` 与 `knowledge_context` 始终回传 `total_cards` 与 `truncated` 暴露截断事实，不得静默丢弃。只要 `.qoder/repowiki` 目录存在，任务包与运行时响应就通过 `context_instructions` 下发“了解项目架构和模块知识时，优先阅读 `.qoder/repowiki/zh/content/` 下的 Wiki 文档和 `.qoder/repowiki/knowledge/zh/` 下的知识卡片”，并在项目安装或升级时写入受管 `AGENTS.md`；该提示不依赖当前任务是否命中具体知识卡。该模式下不创建 `docs/` 骨架、不自动声明 `feature_knowledge_incremental_sync`/`adr_changelog_todo_review` 交付物、增量 Job 创建短路返回 `knowledge_external_consume_only`，`knowledge bootstrap` 以同码失败关闭（退出码 3）；知识交付不参与 `clone_ready` 判定（`knowledge_delivery_status="external_repowiki"`）。

知识审查与工作量估算共享过滤器。`.git`、`.docs-harness`、依赖/构建/缓存目录、`.playwright-cli`、`zbuddy-output`、敏感路径及图片、音视频、压缩包、DMG、Office/PPT 等资产默认排除；响应返回 `excluded_summary`。assessment、consent 与 decline cache 绑定实际返回库存生成的 `knowledge_inventory_fingerprint`。

工作量估算的 `estimate_basis` 缺省为 `project_wide`，供 bootstrap、全项目审查和全量 preserve-and-merge 使用。知识增量和交付治理传入有界 `change_scoped` 候选项，按实际 `changed_paths`、selected features、deliverables 与允许写入范围路由；整仓扫描截断在此模式只降低 confidence，不单独强制 phased。响应保留 `project_scale_context` 和 `change_scope_fingerprint`。`change_scoped` 模式下 `source_fingerprint` 只绑定 `change_scope_fingerprint` 与范围内文件指纹（`changed_paths` 或写入范围覆盖的文件），范围外无关文件变化不改变 Job 幂等键；`project_wide` 模式仍按全量库存指纹。

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
| `3` | 需要方案、授权、证据（含 `provide_evidence`/`refresh_evidence`）、迁移、用户输入或 Git 交付 |
| `4` | 范围、漂移、Gate、远端、授权或规则变化，必须重新准入 |

所有文件型参数只接受文件路径。文件大小、UTF-8、JSON 类型和文件系统错误必须转成结构化错误，不回显敏感输入。

## 13. 发版同步与验收层中间产物复用

`release sync` 是发版版本真源的单命令入口，`sync` 为默认（唯一）action：

- 检查模式（默认）：扫描四处版本真源——`VERSION` 文件、`package.json` 的 `version`、SKILL.md frontmatter `metadata.version`、`scripts/harness.py` 的 `VERSION` 常量（与 `validate_project_source` 共用读取逻辑）——以 `VERSION` 常量（`controller`）为基准输出 JSON 差异报告（`sources`/`diffs`），退出码 0 一致（`consistent`）、2 不一致（`inconsistent`）、1 读取失败（`unreadable`，含缺失真源清单）。CHANGELOG.md 顶部条目版本号一并报告（`changelog_top_version`），不一致只给 `changelog_hint` 提示，不自动生成文案、不影响退出码。
- `--apply`：以 `VERSION` 常量为唯一真源原子写入 `VERSION` 文件、`package.json`、SKILL.md frontmatter 三处 Docs Harness 受管文件。原子性：全部目标先写临时文件并逐一校验（JSON 可解析且版本生效、frontmatter 可解析且版本生效、字节回读一致），再统一 `os.replace`；任一失败整体回滚到原始字节，无部分写入。已一致时返回 `already_consistent` 且零写入。
- `--target-version X.Y.Z`：与 `VERSION` 常量不一致时失败关闭（exit 2，`release_version_conflict`，附 `actual_vs_expected`）；一致时作为显式确认。非语义版本格式报 `invalid_target_version`。
- 失败关闭边界：`VERSION` 常量不可读取报 `release_source_unreadable`（exit 1）；version 字段缺失、出现多次或 frontmatter 不完整等归属不明内容报 `release_managed_file_unrecognized`；写入或替换失败报 `release_write_failed`（exit 1）并保证无部分写入。只写受管文件，不触碰业务文档，不自动提交或推送 git。

验收层中间产物复用：源码、安装副本、Git HEAD/远端、fresh clone 四层验收判定结论保持各自独立（第 11 节合同不变），只复用层间确定性中间产物。`workspace_snapshot()` 按（路径， 清单摘要， 合同版本， target_identity）键做进程级缓存，清单摘要为全部受跟踪文件（相对路径， 大小， mtime_ns）的 SHA-256；安装副本 SHA-256 比对按（路径， 大小， mtime_ns）键缓存。缓存仅在单次 CLI 会话内有效；清单摘要漂移、合同版本或目标变化即失效重算。fresh clone 与远端验证的网络 I/O 不跳过。复用命中/未命中通过 verify 响应的 `layer_reuse` 字段观测（第 9 节）。
