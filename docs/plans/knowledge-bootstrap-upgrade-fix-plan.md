# Docs Harness 知识初始化与后台路由闭环修复方案

状态：源码实现完成（source-only）  
方案版本：1.1  
建议目标版本：Docs Harness v1.6.0  
联合审查：Codex + Claude Code 2.1.220  
问题来源现场：ZBuddy `codex/harness1.5.0`（不执行升级）

## 最终执行范围

用户在实现阶段明确将范围收敛为仅升级 `/Users/aiware/projects/docs-harness` 源码。ZBuddy 与其他真实下游不属于本次交付；临时项目和 fresh clone 只用于验证源码包的可携带性。

## 背景

ZBuddy 升级到 Docs Harness v1.5.0 后，控制器、规则和版本标记已经完成升级，但项目知识库仍处于：

- `knowledge_status=needs_audit`；
- `features=0`；
- 缺少 `docs/knowledge-map.json`。

父任务完成后创建的后台任务是 `knowledge_incremental_sync`，目标只是同步本次业务变化，不是初始化整个项目知识库。该任务没有绑定业务功能、没有创建具体功能文档的权限，因此以 `no_change` 结束符合它收到的合同。

这说明问题不在子智能体执行，而在 Docs Harness 的升级交接、后台路由和验收合同没有形成闭环。源码控制器与 ZBuddy 安装副本的 SHA-256 完全一致，修复真源应当是本仓库 `scripts/harness.py`，不为 ZBuddy 制作一次性补丁。

联合审查还在本次方案准入过程中复现了两个分类问题：

- 用户说“后面另开任务实现”，当前任务仍被提升为 `workspace_write`；
- `docs/reviews/` 因包含字符串 `views/` 被误判为前端页面目录，触发 UI Gate。

## 目标

1. 让 `project init` 与 `project upgrade` 对知识库状态使用同一套交接合同。
2. 让父任务验收只创建任务包明确声明的后台 Job，不再固定创建知识增量 Job。
3. 在知识库尚未初始化时，引导进入“审查 → 用户同意 → bootstrap”，而不是误派增量同步。
4. 让 bootstrap 与增量任务在创建、等待、失败、验收和重试阶段使用同一套知识生命周期判断。
5. 修复时态、否定和路径子串导致的任务意图与 Gate 误判。
6. 过滤知识审查库存中的运行产物、生成目录和不可读二进制资产。
7. 用自动化测试、临时 Git 项目和 fresh clone 复验源码包；真实下游升级另行授权。

## 非目标

- 不升级 ZBuddy 或其他真实下游项目，不提交或推送下游仓库。
- 不自动读取并改写已有项目文档；已有 `docs/` 的项目仍需先审查并取得用户明确同意。
- 不把知识初始化改成父任务同步阻塞步骤；升级完成与知识库完成继续分层报告。
- 不让增量 Job 获得整个 `docs/features/**` 的初始化权限。
- 不自动提交、推送、发布或修改下游业务代码。
- 不以 ZBuddy 专用条件解决通用控制器问题。

## 成功标准

### 产品闭环

- 任意项目执行 `project init` 或 `project upgrade --apply` 后，都能得到明确的 `knowledge_flow`。
- 已有文档但无知识地图时，返回 `audit_existing` 和可执行的 `knowledge audit` 下一步，不自动写知识内容。
- 没有文档的新项目进入 `bootstrap_new`，创建且只创建一个 `knowledge_bootstrap` Job。
- 已 ready 的项目进入 `already_ready`，后续业务变更才允许创建 `knowledge_incremental_sync`。
- 父任务未声明知识增量交付物时，`verify` 不创建知识 Job。
- 任一知识 Job 只有在最终知识状态为 `ready` 时，才允许以 `no_change` 或 `updated` 正常收尾。

### 工程闭环

- 新增测试覆盖正向、负向、幂等、兼容、状态恢复和真实下游升级。
- 源码自测全绿，临时项目全链路通过。
- 临时项目能按返回合同进入 `bootstrap_new|bootstrap_in_progress`，fresh clone 能运行 v1.6.0 自检。
- 源码、ZBuddy 安装副本、Git 交付和 fresh clone 分层报告，不互相替代。

## 首次偏离与根因

### 根因一：后台交付物没有成为派发真源

`classify_document_deliverables()` 会根据 `suppress_post_completion_dispatch` 决定是否把 `feature_knowledge_incremental_sync` 放入 `background_deliverables`，但 `command_verify()` 完成父任务后仍无条件调用 `create_post_completion_knowledge_job()`。

因此：

- 抑制开关只改变了任务包展示，没有改变实际副作用；
- `feature_knowledge_incremental_sync` 没有成为真正的派发合同；
- 只读任务、无变更任务和后台子任务也可能继续产生知识 Job。

首次偏离发生在父任务验收的后台 Job 生成之前，而不是子智能体执行阶段。

### 根因二：知识生命周期判断分散且不一致

当前三个调用点对“是否存在活动 bootstrap”给出不同答案：

| 调用点 | 当前判断 | 风险 |
|---|---|---|
| `knowledge_status()` | 任意非终态 bootstrap | 能识别 `contract_ready` 等状态 |
| `create_background_job()` | 任意非终态 bootstrap | 能做 bootstrap 去重 |
| `create_post_completion_knowledge_job()` | 仅 `dispatched|running` | `contract_ready`、`queued_manual`、`needs_user_input` 等状态下会误放行增量 Job |

同时，后台验收只禁止未 ready 的 bootstrap 使用 `no_change`，没有禁止增量 Job 在 `needs_audit`、`needs_bootstrap`、`partial`、`failed` 或 `quarantined` 状态下结束。

另一个状态机缺口是：bootstrap 失败或取消后，当前 `release_bootstrap_waiters()` 仍可能把等待中的增量 Job 释放为 `contract_ready`。这会让依赖失败后的增量任务继续运行。

### 根因三：升级流程没有知识交接

`project init` 会返回：

```text
audit_existing → 用户确认 → knowledge_bootstrap
```

但 `project upgrade` 只同步控制器、规则、配置和版本标记，没有返回 `knowledge_flow`、`knowledge_next_action`、审查合同或用户同意要求。

此外，升级分支把 `docs_preexisted=True` 写死。对于原本没有 `docs/` 的旧项目，升级既不会创建知识骨架，也不会创建 bootstrap Job。

### 根因四：意图和路径分类依赖无边界子串

当前文本与路径 Gate 使用 `term in lowered`：

- `Claude Code` 中的 `code` 可触发代码编辑 Gate；
- `docs/reviews/` 中的 `views/` 可触发前端 Gate；
- `rapid`、`latest`、`authors` 等名称也可能分别误命中 `api`、`test`、`auth`。

意图推断只检查有限距离内的否定词，没有识别“后续、以后、另开任务”等未来边界。由于 `mutation_profile` 只能升档，误判后无法在当前任务内恢复到只读合同。

### 根因五：知识库存与用户同意没有绑定同一份有效扫描

`knowledge_scan_inventory()` 基于工作区快照返回大量路径，但过滤规则与 `bounded_project_inventory()` 不一致，也没有完整排除 `.playwright-cli`、`zbuddy-output`、缓存、构建输出和 Office/PPT 等不可直接用于知识抽取的资产。

当前 `inventory_fingerprint` 实际来自文档快照，而不是返回给审查者的过滤后项目库存。评估对象与用户同意所绑定的指纹并非同一真源，存在审查漂移风险。

## 目标产品流程

### 安装或升级后的知识交接

```text
project init / project upgrade --apply
  ↓
统一计算 knowledge status
  ├─ ready
  │    → mode=already_ready
  │    → 无初始化动作
  ├─ absent 且安装前没有 docs
  │    → 创建最小骨架
  │    → 创建或复用 knowledge_bootstrap
  │    → mode=bootstrap_new
  ├─ building
  │    → mode=bootstrap_in_progress
  │    → 复用现有非终态 bootstrap，不重复审查或建 Job
  └─ needs_audit / needs_bootstrap / partial / failed / quarantined / invalid
       → mode=audit_existing
       → 零知识内容写入
       → 返回 knowledge audit 下一步
       → assessment=partial 时请求用户同意
       → 同意后创建或复用 knowledge_bootstrap
```

### 父任务完成后的后台路由

```text
run 阶段冻结 background_deliverables
  ↓
verify 先原子完成父任务
  ↓
逐项消费 background_deliverables
  ├─ 未声明 feature_knowledge_incremental_sync
  │    → 不创建知识 Job
  │    → post_completion.status=not_required
  ├─ 声明了增量同步，knowledge=ready
  │    → 创建或复用 knowledge_incremental_sync
  ├─ 声明了增量同步，存在非终态 bootstrap
  │    → 增量 Job 进入 waiting_for_bootstrap_merge
  └─ 声明了增量同步，但知识未 ready 且无 bootstrap
       → 不创建增量 Job
       → 返回 knowledge_handoff.status=action_required
       → 下一步为 knowledge audit
```

`needs_audit` 是需要用户处理的正常交接，不得记录成 `dispatch_failed`。真正的 Runtime、文件系统或合同写入异常才使用 `dispatch_failed`。

### 后台知识状态机

```text
knowledge_bootstrap
  contract_ready → dispatched → running
  running → updated，仅当 knowledge_status=ready
  running → no_change，仅当 knowledge_status=ready
  running → completed_with_finding，视为需要人工处理，不释放增量等待者
  running → needs_user_input / needs_rebase / failed / cancelled

knowledge_incremental_sync
  waiting_for_bootstrap_merge
    ├─ bootstrap updated|no_change 且 knowledge=ready
    │    → 重建当前基线 → contract_ready
    └─ bootstrap failed / cancelled / needs_user_input / completed_with_finding
         → needs_user_input，不得变为可运行

  contract_ready → dispatched → running
  running → updated|no_change，仅当 knowledge_status=ready
```

`waiting_for_bootstrap_merge` 是被动等待状态，不允许直接验收为 `updated` 或 `no_change`。只有依赖成功并重建基线后，才能重新进入 `contract_ready`。

## 执行内容

### 执行范围

- `scripts/harness.py`
- `tests/test_harness.py`
- `VERSION`
- `package.json`
- `SKILL.md`
- `README.md`
- `docs/contracts.md`
- `docs/architecture.md`
- `docs/testing.md`
- `CHANGELOG.md`
- `harness-home/rules/INDEX.md`
- `docs/plans/knowledge-bootstrap-upgrade-fix-plan.md`

### 工作包一：建立统一知识生命周期判定

在 `scripts/harness.py` 新增纯函数或小型领域模块，集中提供：

- `active_knowledge_bootstrap(target)`：返回最后一个非终态 bootstrap；
- `knowledge_handoff(target, operation, docs_preexisted)`：生成统一 `knowledge_flow`；
- `knowledge_ready_for_incremental(target)`：只有 `status=ready` 返回真；
- `knowledge_dependency_outcome(bootstrap_job)`：区分成功释放与失败阻断。
- `evaluate_candidate_knowledge(target, normalized_map)`：不写知识地图，直接依据候选地图和实际功能文档复算是否 ready。

替换以下位置的重复判断：

- `knowledge_status()`；
- `create_background_job()` 的 bootstrap 去重；
- `create_post_completion_knowledge_job()` 的依赖判断；
- `release_bootstrap_waiters()`；
- `command_background()` 的知识验收。

### 工作包二：补齐 project upgrade 知识交接

修改 `command_project()`：

1. `init` 与 `upgrade` 复用同一个 `knowledge_flow` 生成器。
2. `upgrade` 在写入前实测 `docs/` 是否存在，不再硬编码 `docs_preexisted=True`。
3. 预览和 apply 响应都返回：
   - `knowledge_status`；
   - `knowledge_next_action`；
   - `knowledge_flow.mode`；
   - `requires_user_consent_before_update`；
   - `dispatch_status`；
   - `job_id`；
   - `knowledge_next_command_argv`；
   - `assessment_artifact_ref`。
4. 已有文档且未 ready 时不自动创建 bootstrap；返回 `audit_existing`。
5. 没有文档的旧项目升级时，创建骨架并幂等创建 bootstrap。
6. `building` 返回 `bootstrap_in_progress`，复用当前 Job，不重新 audit；`failed|quarantined|invalid` 返回恢复审查合同。
7. `needs_bootstrap` 根据 `docs_preexisting_at_install` 分流：新项目可幂等恢复 bootstrap，已有文档项目仍先 audit 和 consent。
8. 升级文件同步成功、但知识待处理时，使用 `upgraded_knowledge_pending`；它不是失败。若控制器文件尚未提交，仍按现有交付规则返回 `needs_delivery`。

父任务完成和知识初始化完成继续分层：

- `project upgrade` 可完成；
- 产品回执必须明确写“知识初始化待处理”；
- 只有独立知识初始化任务才能以 `knowledge status=ready` 宣称知识库完成。

### 工作包三：让后台交付物成为唯一派发真源

修改 `classify_document_deliverables()`、`build_package()` 与 `command_verify()`：

1. 准入期冻结 `background_deliverables`。
2. `verify` 按交付物逐项调用创建器，不再无条件创建知识 Job。
3. 只读任务、Git inspect、显式抑制任务默认不声明知识增量交付物。
4. 写任务没有业务变化或 `changed_paths=[]` 时返回 `no_write_no_sync`，不创建增量 Job。
5. 没有后台交付物时返回：

```json
{
  "post_completion": {
    "status": "not_required",
    "reason_code": "no_background_deliverables"
  },
  "background_jobs": []
}
```

6. 保留父任务先落盘、后台合同后创建的双通道顺序。

为避免同名语义混淆：

- 父任务 facts 中的 `suppress_post_completion_dispatch` 暂时保留兼容；
- 新任务包增加明确的 `post_completion_dispatch_policy`；
- Job 自身新增 `may_spawn_child_jobs=false`；
- 旧 Job 字段继续只读兼容，不立刻删除。

### 工作包四：修正知识 Job 创建与验收

修改 `create_post_completion_knowledge_job()`：

- 调用统一的 active bootstrap 判定；
- 知识未 ready 且无 bootstrap 时返回结构化 `knowledge_handoff`，不落增量 Job；
- 有任意非终态 bootstrap 时创建等待依赖的增量 Job；
- 复用 `create_background_job()` 的幂等策略，不只依赖固定目录是否存在；
- 父任务重新准入后，如果旧 Job 的 idempotency key 或 package fingerprint 不一致，返回 `needs_rebase`，不得静默复用陈旧 `changed_paths`。

修改 `command_background()`：

- 只有 `running` Job 可以执行 verify；
- 所有 `knowledge_*` Job 的 `updated|no_change` 都要求最终 `knowledge_status=ready`；
- 未 ready 时进入 `needs_user_input`，释放锁并返回明确原因；
- `waiting_for_bootstrap_merge` 不允许直接验收；
- bootstrap 以 `updated|no_change` 结束且控制器复算 ready 时，才释放等待者并重建基线；
- bootstrap 以 `completed_with_finding|failed|cancelled` 结束，或进入 `needs_user_input` 时，等待者进入 `needs_user_input`，记录依赖原因；
- 依赖结果通过穷举 `BACKGROUND_TERMINAL_STATES` 处理，新增终态但未声明策略时失败关闭；
- assessment 中的 `status=ready` 只是输入声明，不能直接作为完成证据；
- `updated` 验收先用 `evaluate_candidate_knowledge()` 对候选地图和已写功能文档做纯读取复算，只有复算 ready 才原子写入 `docs/knowledge-map.json` 并完成 Job；
- 候选复算为 partial 时，知识地图保持原值或不存在，功能文档草稿保留，Job 进入 `needs_user_input`，避免出现“地图已经落盘但 Job 未完成”的中间态。

### 工作包五：修复意图、时态与 Gate 边界

修改 `infer_task_intents()`：

1. 先按标点和连接词拆分任务子句。
2. 识别当前任务锚点：`本次|当前|现在|只|仅`。
3. 识别未来任务锚点：`后续|以后|后面|另行|单独|另开任务|下一任务`。
4. 未来子句中的写动作记录为 `deferred_intents`，不进入当前 `candidate_intents`。
5. “先审查，如有需要再修复”等当前条件式写入继续按最高变更面处理。
6. “已经修改、此前实现、上次修复”等完成体只作为被审查对象，不自动产生当前写意图。
7. 不开放任意 facts 降档；解析仍有歧义时保持失败关闭，避免调用方用 override 隐藏真实写入意图。

修改 `infer_gates()` 与 `infer_gates_from_paths()`：

- 中文词使用受控短语匹配；
- 英文短词使用单词边界和动作对象组合，不再裸子串匹配；
- `Claude Code`、`VS Code` 等工具名不等于代码修改；
- 目录 Gate 按完整路径段匹配，`reviews` 不等于 `views`；
- 只读任务不会仅因路径名称获得 UI、架构、安全或测试写入 Gate；
- `.tsx/.swift` 等真实写入路径继续稳定命中对应 Gate。

任务包增加可审计字段：

```json
{
  "candidate_intents": [],
  "deferred_intents": [],
  "intent_boundary_reason_codes": []
}
```

### 工作包六：统一知识库存过滤与指纹

把 `knowledge_scan_inventory()` 与 `bounded_project_inventory()` 收敛到同一过滤器：

- 路径按完整段排除：`.git`、`.docs-harness`、`node_modules`、`.venv`、`dist`、`build`、`.next`、`.cache`、`coverage`、`target`、`DerivedData`、`Pods`、`.playwright-cli`、`zbuddy-output`；
- 排除 `.DS_Store`、临时文件和凭据相关路径；
- 排除不能直接用于知识抽取的二进制与打包资产，如图片、音视频、压缩包、DMG、Office/PPT；
- 对确有业务意义但默认被排除的路径，支持项目配置显式 include，且需要在 assessment 中留痕；
- 返回 `excluded_summary`，让用户知道过滤了哪些类别，但不泄露敏感文件名。

新增 `knowledge_inventory_fingerprint`，由实际返回给审查者的过滤后库存生成。assessment、consent、decline cache 和 bootstrap 合同都绑定该指纹；不得继续用纯 docs 快照替代项目库存指纹。

### 工作包七：可观测性与停滞提醒

修改 `project_findings()` 和任务入口响应：

- `contract_ready`、`waiting_for_bootstrap_merge` 等非终态 Job 超过 `stale_after` 后给出 yellow/action-required 提醒；
- 知识未初始化且不存在非终态 bootstrap 时，`project check` 返回需要动作的状态和 `knowledge audit` 命令；
- `run` 在 `context_quality=degraded` 时增加独立的 `knowledge_next_command_argv`，不得覆盖准入主链的 `next_command_argv`；
- 不把 yellow 扩大成源码失败；退出码建议使用 3 表示需要用户动作。

### 工作包八：合同、版本与下游升级

建议发布 v1.6.0，而不是 v1.5.1。原因是本次会改变可观察合同：

- `project upgrade` 新增知识交接响应；
- `verify` 的后台副作用和返回状态发生变化；
- 任务 Gate 与意图分类结果会变化；
- Job 合同增加兼容字段。

`waiting_for_bootstrap_merge` 的转换规则属于破坏性行为变化，必须提供显式在途迁移：

- 新版后台 Job 使用 `docs-harness/background-job/v2`，或在 v1 合同中增加等价的受控迁移版本标记；
- reader 继续接受 v1，并在 `project upgrade --apply` 中幂等迁移非终态等待者；
- 依赖已 `updated|no_change` 且知识 ready：重建基线后迁移到 `contract_ready`；
- 依赖仍活动：保留等待态并写入新合同版本；
- 依赖失败、取消、存在重大发现或丢失：迁移到 `needs_user_input`；
- `background status` 保持只读，不在查询时偷偷迁移 Runtime；
- 迁移前后 Job ID、父任务关联和事件历史不变，并写一次有界 migration event。

同步更新：

- `scripts/harness.py` 中的版本常量与受管文本；
- `VERSION`；
- `SKILL.md` frontmatter 和行为说明；
- `package.json`；
- `README.md`；
- `docs/contracts.md`；
- `CHANGELOG.md`；
- 受管 `AGENTS.md` / `CLAUDE.md` 模板；
- 必要时更新 project config schema，提供向后读取和 preserve-and-merge。

## 自动化验收矩阵

| 编号 | 场景 | 预期结果 |
|---|---|---|
| T1 | bootstrap 停在 `contract_ready` 时完成业务写任务 | 增量 Job 进入 `waiting_for_bootstrap_merge`，绑定同一 bootstrap |
| T2 | bootstrap 位于 `queued_manual|needs_rebase|needs_user_input` | 增量 Job 仍不得直接运行 |
| T3 | bootstrap `updated|no_change` 且控制器复算 ready | 等待者重建基线后进入 `contract_ready` |
| T4 | bootstrap `failed|cancelled|completed_with_finding` | 等待者进入 `needs_user_input`，不得释放为可运行 |
| T5 | 只读任务 verify | 父任务完成，`post_completion=not_required`，不创建 Job |
| T6 | 显式抑制的写任务 verify | 不创建知识增量 Job；其他明确声明的治理 Job 不受影响 |
| T7 | `changed_paths=[]` | 返回 `no_write_no_sync`，不创建增量 Job |
| T8 | 知识 ready 的增量 Job `no_change` | 正常完成 |
| T9 | 知识 `needs_audit|needs_bootstrap|partial|failed|quarantined` 的增量 Job `no_change` | 进入 `needs_user_input`，父任务状态不回滚 |
| T10 | `waiting_for_bootstrap_merge` 直接 verify | 拒绝非法状态转换 |
| T11 | ZBuddy 形态：已有 docs、无知识地图、旧控制器升级 | 零业务文档写入，返回 `audit_existing` 和 audit 命令 |
| T12 | 无 docs 的旧项目升级 | 创建骨架与单一 bootstrap Job |
| T13 | 已 ready 项目升级 | `already_ready`，不创建 bootstrap |
| T14 | 连续两次 upgrade | 第二次文件 `changed=[]`，Job 不重复创建 |
| T15 | audit → partial assessment → consent → update → bootstrap verify | 最终 `knowledge status=ready` |
| T16 | consent 或 inventory 指纹漂移 | 拒绝复用旧同意 |
| T17 | inventory 含生成目录、`.playwright-cli`、`zbuddy-output`、Office/PPT | 审查库存排除这些资产并给出分类摘要 |
| T18 | `docs/reviews/x.md` 只读审查 | 不命中 UI Gate，不要求 `ui_acceptance` |
| T19 | `src/views/Home.tsx` 写任务 | 继续命中前端 Gate |
| T20 | 文本含 `rapid|latest|authors|Claude Code` | 不产生无关 Gate |
| T21 | “本次只排查，后面另开任务实现” | 当前任务为 audit/read_only，未来写意图进入 `deferred_intents` |
| T22 | “先排查，必要时直接修复” | 保持 modify/workspace_write，不得错误降档 |
| T23 | 重复 verify 同一父任务 | 不重复创建 Job 或 created 事件 |
| T24 | 旧 schema Job 和兼容别名 | 仍可读取、派发、验收；新字段使用兼容默认值 |
| T25 | 在途 v2 任务升级控制器 | package/receipt 不匹配时要求重新准入和补证，不静默通过 |
| T26 | 非终态 Job 超时 | `project check` 给出 action-required 提醒 |
| T27 | upgrade 时已有 `building` bootstrap | 返回 `bootstrap_in_progress` 并复用 Job，不重新 audit |
| T28 | 旧版 `waiting_for_bootstrap_merge` Job 升级 | 按依赖结果幂等迁移，status 查询本身不写 Runtime |
| T29 | assessment 声明 ready，但候选地图对应文档复算为 partial | 不写知识地图，Job 进入 `needs_user_input`，保留草稿 |
| T30 | 新增未知 bootstrap 终态 | 依赖处理失败关闭，不默认释放等待者 |

## 实施顺序

1. 先写 T1–T16 的失败测试，冻结知识生命周期与派发合同。
2. 实现统一知识状态谓词和等待者结果分流。
3. 让 `background_deliverables` 成为 verify 的唯一派发真源。
4. 补齐 `project upgrade` 交接，跑临时项目全链路。
5. 写 T17–T22，修库存过滤、时态和路径 Gate。
6. 完成兼容、幂等和停滞提醒测试。
7. 同步版本真源、合同、技能说明和 Changelog。
8. 在临时 Git 项目验证源码安装、临时 HEAD 与 fresh clone 分层状态。
9. 不升级 ZBuddy；真实下游的 audit → consent → bootstrap 另行授权。

## 验收结果

本阶段已完成 v1.6.0 源码实现与 source-only 验收；没有升级、提交或推送任何真实下游。

已经取得的实现证据：

- 版本真源、控制器、技能元数据、README、合同与 Changelog 已同步到 `1.6.0`；
- `python3 -m unittest discover -s tests -p 'test_*.py'`：109 项通过；
- `npm run self-test`：v1.6.0 自检通过；
- `npm run pack:check`：生成 28 文件的 v1.6.0 打包清单；
- 临时 Git 项目安装后 `knowledge_flow.mode=bootstrap_new`，重复 upgrade `changed=[]` 且进入 `bootstrap_in_progress`；
- fresh clone 的控制器自检通过，源码、临时安装副本和 fresh clone 控制器 SHA-256 一致；
- ZBuddy 曾产生的本地升级尝试已完整回退，最终工作树干净且仍为 v1.5.0。

本次 source-only 完成结论只覆盖以下层级：

1. 源码和自动化测试；
2. 临时项目完整流程；
3. v1.6.0 打包清单；
4. 临时安装副本与 fresh clone 可复现性。

不覆盖 Docs Harness 源码仓库的 Git 提交/远端交付，也不覆盖任何真实下游安装、知识状态或宿主派发。

## 风险与回滚

- Gate 修复会改变任务包指纹；升级中的 v2 任务可能需要重新准入和补证。
- inventory 规则过严可能漏掉有价值的非标准资料，因此必须支持受控 include 并记录排除摘要。
- 把知识待处理误报为派发失败会污染告警；必须使用独立 `action_required` 语义。
- 只修创建路由、不修宿主接单与停滞提醒，bootstrap 仍可能永久停在 `contract_ready`。
- 只允许对未发布的新版本做整体回滚；下游已生成的新 schema Runtime 时，旧控制器必须失败关闭或只读保留，不能静默解释。
- 在途 waiting Job 未迁移就禁止新控制器执行验收，避免状态机收紧后直接产生不可恢复的硬失败。

## 文档真源

- 本方案是本次修复范围、产品流程、实施顺序和验收口径的唯一方案真源。
- Claude Code 的独立发现与采纳记录位于 [knowledge-bootstrap-upgrade-fix-claude-review-notes.md](knowledge-bootstrap-upgrade-fix-claude-review-notes.md)。
- 当前行为合同仍以 `docs/contracts.md`、`SKILL.md` 和 `scripts/harness.py` 为准；源码实现完成前，本方案不得冒充已生效合同。

## 索引与残留

- 当前仓库没有统一的 `docs/INDEX.md` 方案索引，本任务不新建第二套索引。
- `docs/todo.md` 当前声明无未完成事项；用户本次要求的是保存正式方案，未要求登记 TODO，因此不修改 TODO。
- 现有 v1.4、v1.5 方案保留历史语义，不覆盖、不重命名。
- 实现完成后应将最终行为同步到 `SKILL.md`、`README.md`、`docs/contracts.md` 和 `CHANGELOG.md`，并检查旧字段与旧入口残留。
