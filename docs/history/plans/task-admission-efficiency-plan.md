# Docs Harness 任务准入与证据效率优化方案

状态：v1.5.0 已实现并完成源码、临时项目、真实 Git/fresh clone 与宿主合同验收  
方案版本：1.1  
目标版本：Docs Harness v1.5.0（不纳入 v1.4.1）  
适用范围：任务意图识别、Gate 路由、读写范围、工作区漂移、上下文收据、语义证据、宿主收尾和效率度量

## 1. 执行摘要

当前 Docs Harness 已能通过 `direct|planned|extended`、范围冻结和语义证据保持任务失败关闭，但简单只读查询和 Git 操作仍可能进入编辑型 Gate、方案链和写入型证据链。并发外部进程产生的工作区变化还会被统一解释为当前任务范围变化，导致重复准入和重复加载相同上下文。

本方案的目标不是放松控制，而是把控制施加到正确对象：先识别任务意图和变更面，再匹配风险 Gate；分别管理读取范围、工作区写入、Git 元数据写入和外部写入；保留首次冻结基线，同时区分任务写入、并发漂移和读取事实漂移；将命令、文件读取、审查和 Git 检查归一为可复用的类型化收据。

目标闭环为：

```text
原始任务
  ↓
意图与变更面分类
  ↓
风险 Gate + 读写范围 + 证据合同
  ↓
direct / planned / extended
  ↓
业务执行
  ↓
同源验收：任务写入 + 读取事实 + 并发漂移 + 类型化证据
  ↓
一次性完成回执
```

## 2. 当前问题

### 2.1 任务意图与关键词 Gate 混用

当前 Gate 主要通过任务文本中的关键词和路径后缀推断。任务只要提到“代码”或“文档”，即使真实意图是定位、解释或审计，也可能进入 `code-edit` 或 `document-edit`。这会连带引入方案字段、项目事实、上下文加载和写入型语义证据。

### 2.2 direct 路线缺少只读合同

当前 `direct` 已存在，但初始范围为空时仍会升级为 `planned`，默认动作也包含 `write`。系统没有一等的 `read_scope`、空 `write_scope` 和只读完成证据，因此“无需修改任何内容”不能稳定转换为低开销准入。

### 2.3 执行范围同时承载路径与自然语言

`allowed_scope` 的产品语义是项目内相对路径或 glob，但现有校验可能接受“仅只读查询，不产生工作树变更”一类自然语言。该值无法覆盖任何真实文件，后续变化会被错误识别为越界。

### 2.4 工作区变化缺少来源归因

首次冻结基线应保持不可变，但当前验收把基线后的全部变化统一视为当前任务变化。共享工作区中的桌面应用、其他智能体或用户操作会因此触发当前任务重新准入，即使变化与任务的读取和写入范围无关。

### 2.5 证据与宿主收据无法复用

通过的验证命令、文件读取、Git 检查和独立审查属于不同宿主工具输出，不能稳定映射为 Harness 的 `test_result|document_review|external_state` 等语义证据。任务包修订后，即使规则和项目事实内容指纹未变化，也可能重复加载相同上下文。

### 2.6 缺少真实效率度量

现有 Runtime 能记录任务包版本和部分事件，但不能回答各阶段耗时、重复上下文次数、宿主补证次数和重新准入原因占比。流程复盘只能依赖人工估算。

## 3. 产品目标

1. 只读查询、只读审计和 Git 检查稳定进入低开销直接路线。
2. Git 元数据写入与工作区写入使用不同合同，不把 `fetch`、`show` 和 `pull` 混为代码编辑。
3. 任务范围只接受结构化路径或受控资源，不接受自然语言描述。
4. 保留首次冻结基线，不通过重建基线吞掉任务期间发生的变化。
5. 对变化进行有限归因；与任务无关的并发漂移不自动阻断，影响读取事实、写入范围或高风险边界时继续失败关闭。
6. 同一内容指纹在同一任务内只要求加载一次。
7. 宿主在执行前获得完整的收尾证据清单，不在任务结束后逐轮追加隐藏要求。
8. 用结构化指标证明效率改善，不再用人工百分比代替运行数据。

## 4. 非目标

- 不允许任务事实删除脚本已识别的安全、数据、发布或不可逆 Gate。
- 不把 `git pull` 视为只读操作；它可能修改 HEAD、索引和工作区。
- 不自动修改 `.gitignore`、取消跟踪文件或隐藏已跟踪运行态。
- 不自动提交、推送、发布、安装或执行外部写入。
- 不承诺无 Hook 宿主能够物理阻止所有越权写入；只能检测、记录并按证据能力给出真实边界。
- 不改变 `runtime_status`、当前 HEAD、远端、fresh clone、发布产物和真实 UI 分层验收原则。

## 5. 目标任务模型

### 5.1 任务意图

新增受控 `task_intent`：

| 意图 | 含义 | 默认路线 | 默认变更面 |
|---|---|---|---|
| `query` | 定位、解释、比较已有事实 | `direct` | `read_only` |
| `audit` | 只读审查并形成判断 | `direct`；高风险审计可升级 | `read_only` |
| `git_inspect` | status、log、show、diff、ls-remote | `direct` | `read_only` |
| `git_fetch` | 获取对象和远端引用，不修改工作区 | `direct` | `git_metadata_write` |
| `git_sync` | fast-forward 或其他受控同步 | `planned` | `workspace_write` |
| `modify` | 修改项目文件 | 按 Gate 决定 | `workspace_write` |
| `external_write` | 推送、发布、发送、部署 | 至少 `planned` | `external_write` |

意图识别先判断用户动词、否定约束和目标对象，再执行风险 Gate。出现“文档”不等于修改文档，出现“代码”不等于修改代码。

#### 5.1.1 混合意图与安全上界

任务允许混合意图，例如“先审计、如需要再修复”“获取远端后同步”。`task_intent` 保留一个用于路由展示的主意图，同时新增 `candidate_intents` 数组记录全部被识别到的候选意图及其各自变更面：

```json
{
  "task_intent": "audit",
  "candidate_intents": [
    { "intent": "audit", "mutation_profile": "read_only" },
    { "intent": "modify", "mutation_profile": "workspace_write" }
  ]
}
```

Gate 编译取 `candidate_intents` 中的最高变更面和最高风险 Gate 结果，不按主意图单独降级。常见混合模式：

- `audit+fix`（先审后改）：按 `modify` 的变更面和 Gate 编译；
- `if-needed-fix`（不确定是否需要改）：按可能触发的最高变更面编译，不等到运行时才升级；
- `fetch+sync`（先取后同步）：按 `git_sync` 的变更面和 Gate 编译，`git_fetch` 不单独降低要求。

显式 facts 只能把已编译结果升级为更高变更面或更严格 Gate，不能用来把混合意图中已识别的高风险分支降级或隐藏。

### 5.2 变更面

新增受控 `mutation_profile`：

```text
read_only
git_metadata_write
workspace_write
external_write
```

四类变更面逐级升级，不能通过显式 facts 降级。风险 Gate 与变更面正交：只读安全审计仍可命中 `security-sensitive`，但不会因此获得写权限。

### 5.3 读写范围分离

任务包升级为 `docs-harness/task-package/v2`，核心字段为：

```json
{
  "task_intent": "query",
  "mutation_profile": "read_only",
  "read_scope": ["docs/**", ".git:history"],
  "write_scope": [],
  "git_scope": [],
  "external_scope": [],
  "allowed_actions": ["read"],
  "semantic_evidence_requirements": ["source_trace"]
}
```

约束如下：

- `read_only` 必须满足 `write_scope=[]` 且不得包含写动作；
- 文件范围只接受项目内相对路径、glob 或受控资源标识；
- `.git:history`、`.git:refs/remotes/<remote>` 使用受控资源标识，不伪装成工作区路径；
- 含空格的完整句子、句末标点或“仅限、不会、不产生”等描述性文本返回 `invalid_scope_description`；
- 自然语言边界进入 `constraints`，不进入路径范围。

### 5.4 路线决策

路线按以下顺序确定：

1. 编译 `task_intent` 和 `mutation_profile`；
2. 编译风险 Gate，Gate 只能保持或升级控制要求；
3. 编译读写范围、授权和证据；
4. 根据工作包、风险和不可逆性选择 `direct|planned|extended`。

只读任务不因“没有写入范围”升级到 `planned`。只有范围本身无法确定、用户要求正式方案、存在高风险决策或需要多工作包时才升级。

## 6. Git 操作模型

### 6.1 git_state_snapshot

`git_inspect` 之外的 Git 操作（`git_fetch`、`git_sync`）必须绑定独立的 `git_state_snapshot`，作为预检和后检之间的可验证锚点，不依赖 `git_sync_scope` 单独承载：

```json
{
  "repo_identity": "...",
  "remote": { "name": "origin", "url_fingerprint": "...", "refspec": "..." },
  "preflight_target_oid": "...",
  "head": "...",
  "index_tree": "...",
  "worktree_fingerprint": "...",
  "controlled_refs_namespace": ["refs/heads/*", "refs/remotes/origin/*"],
  "lfs_available": true,
  "submodule_available": true
}
```

约束：

- `remote.url_fingerprint` 在计算前必须去除用户名、token、密码、查询参数等凭证材料；Runtime 不保存带凭证的 URL 原文；
- `git_fetch` 执行后，只允许 `controlled_refs_namespace` 内声明的 refs/objects 发生变化；`head`、`index_tree` 和工作区指纹必须与预检快照一致，出现其他变化即失败关闭；
- `git_sync` 必须绑定预检阶段记录的 `preflight_target_oid`；执行前检测到远端当前目标值不等于 `preflight_target_oid` 时，必须重新准入并生成新快照，不得沿用旧快照继续写入；
- Git LFS、Submodule、remote helper 的可用性或其凭证交互副作用无法验证时，操作失败关闭，或要求显式人工路径完成；
- 对应路线不等于免授权：`git_fetch`、`git_sync` 无论编译到哪条路线，仍必须满足 `git_state_snapshot` 的全部预检和后检约束。

### 6.2 git_inspect

适用于 `git status/log/show/diff/branch --contains/ls-remote`。任务不修改工作区，不要求逐文件写入范围，证据类型为 `git_inspection_result`。读取本地工作区内容时仍记录相应 `read_set`。

### 6.3 git_fetch

适用于仅更新对象库和远端跟踪引用的 fetch。任务声明 remote、refspec 和预期引用命名空间，冻结执行前远端目标值写入 `git_state_snapshot`，执行后验证引用变化和工作区未变化。它不是纯只读，但不应按源码编辑处理。

### 6.4 git_sync

适用于会更新 HEAD、索引或工作区的同步。Harness 在写入前执行 fetch 和 diff 预检，自动生成新增、修改、删除、重命名、LFS 和 Submodule 清单，并将清单指纹冻结为 `git_sync_scope`，同时将预检目标值写入 `git_state_snapshot.preflight_target_oid`。

默认只允许可验证的 fast-forward。以下情况失败关闭或要求额外授权：

- 脏工作区与预期变化重叠；
- 不可 fast-forward；
- 远端目标在预检后漂移；
- 删除数量超过阈值；
- 命中安全、发布、安装、数据库或其他高风险路径；
- LFS 或 Submodule 状态无法确认。

执行后必须逐项校验：

- `HEAD` 是否等于冻结的目标远端提交；
- 本地分支与目标远端分支是否不存在未解释的领先或落后；
- 工作区和索引状态是否符合预检后的预期；
- Git LFS 对象、指针和拉取状态是否完整；
- Submodule 提交与工作树状态是否符合冻结清单。

任一后检项缺失、失败或与预检清单不一致时，不得报告 Git 同步完成。通过后也只报告 Git 同步层验收，不扩大为构建、运行、发布或 UI 验收。

## 7. 工作区漂移与变更归因

### 7.1 保留不可变基线

`freeze.json.workspace_snapshot` 继续保存任务首次创建时的不可变基线。重新准入只更新任务包和合同指纹，不刷新首次基线。

### 7.2 新增四类集合

验收阶段分别计算：

- `task_write_set`：由宿主写工具收据、Git 预检合同和任务证据支持的任务写入；
- `read_set`：本任务实际读取并用于结论的文件或受控资源及其指纹；
- `concurrent_drift`：基线后发生、但没有任务写入收据且不在预期写入集合内的变化；
- `unattributed_drift`：宿主能力不足，无法确定来源的变化。

### 7.3 阻断规则

- `task_write_set` 超出 `write_scope`：阻断并重新准入；
- `read_set` 在形成结论后漂移：阻断，要求重读或重新准入；
- `concurrent_drift` 与读写范围重叠：阻断；
- 并发变化命中安全、数据、发布或不可逆边界：阻断或要求人工确认；
- 与任务无关且不重叠的并发变化：记录警告，不自动把它归因于当前任务；
- `unattributed_drift` 不得冒充 `concurrent_drift` 或计入 `task_write_set`；来源无法证明时，其 `attribution_quality` 必须标记为 `unknown`；
- `unattributed_drift` 与 `read_scope`、`write_scope` 或 `git_scope` 存在重叠，或命中安全、数据、发布、不可逆边界：失败关闭；
- 仅当能够证明 `unattributed_drift` 的路径与全部范围不重叠、且不命中上述边界时，才允许记录警告后继续，但结论中不得声称已完成来源归因；
- 无 Hook 宿主只能得到 `attribution_quality=reported|partial|unknown`，不能声称已证明写入来源。

### 7.4 运行态路径

高频运行态优先迁移到 `.git/docs-harness/`、系统应用支持目录或其他明确 Runtime。只有同时满足“未跟踪、可再生、非任务输入、非安全边界”的路径，才允许作为项目级 runtime exclusion。已跟踪文件不能仅靠 `.gitignore` 或 exclusion 从验收面隐藏。

## 8. 类型化证据与收据复用

### 8.1 统一证据适配器

新增 `docs-harness/evidence-receipt/v2`，允许以下来源归一化：

| 来源 | 可产生的证据类型 |
|---|---|
| 文件读取或定位 | `source_trace`、`document_trace` |
| 验证命令 | 声明的 `test_result`、`contract_acceptance` 等 |
| Git 预检与后检 | `git_inspection_result`、`git_fetch_result`、`git_sync_result` |
| 独立审查 | `review_result`、`document_review`、`security_acceptance` |
| 外部状态检查 | `external_state` |

每份 evidence-receipt/v2 必须绑定以下字段，缺失任一字段视为不可信证据：

```json
{
  "task_id": "...",
  "target_identity": "...",
  "package_fingerprint": "...",
  "content_set_fingerprint": null,
  "producer": { "adapter": "...", "capability": "..." },
  "command_argv_digest": "...",
  "cwd": "...",
  "started_at": "...",
  "ended_at": "...",
  "ttl": "...",
  "exit_code": 0,
  "output_or_artifact_digest": "...",
  "read_set": [],
  "write_set": []
}
```

约束如下：

- `package_fingerprint` 为必填字段，阻断型语义证据始终绑定当前任务的 `package_fingerprint`；`content_set_fingerprint` 为可选字段，只支持同一任务、同一目标的来源或上下文复用，不能替代当前任务包绑定，也不能单独作为阻断型证据的绑定依据；
- 验证命令必须在任务事实中声明 `produces`，`produces` 使用白名单枚举，只能映射到已定义证据类型，不接受任意字符串；命令退出、输出摘要、工作区指纹和证据类型同时满足合同后，才能补足对应语义证据；不能因为任意命令退出 0 就自动获得高等级证据；
- `attribution_quality=reported` 的证据不能单独满足安全、发布、不可逆判断等高风险阻断类证据，必须搭配可验证的宿主收据或独立审查；
- 已过期（超出 `ttl`）、绑定了不同 `task_id`、绑定了不同 `target_identity`，或来自不可信 `producer` 的证据一律不得复用；
- 证据只保存指纹、摘要和结构化元数据，不记录命令原始输出、任务正文、环境变量或凭证。

### 8.2 只读任务证据

`query|git_inspect` 默认不要求编辑型 review。最小证据为：

- 使用过的来源引用；
- 读取时和完成时的内容指纹；
- 结论与来源之间的有界映射；
- 未覆盖层级和不确定性。

只有命中安全、法律、财务、不可逆判断或用户明确要求独立审查时，才增加对应审查证据。

### 8.3 上下文收据复用

上下文收据新增 `content_set_fingerprint`，复用范围限定在同一 `task_id`、同一 target（仓库/项目标识）、同一 stage、同一 compiler contract 版本和同一 `content_set_fingerprint` 五者同时成立时才生效；跨 task、跨 target、跨 stage 或 compiler contract 变化后一律重新加载，不做跨范围复用。任务包修订后，如果阶段所需规则、项目事实和内容指纹集合完全相同，控制器自动复用旧收据；新增或变化的内容只增量加载。授权和用户确认永不按 `content_set_fingerprint` 复用，必须绑定当前任务包指纹重新获取。

## 9. 宿主完成合同

`run` 在准入时返回带指纹的 `completion_manifest`，作为前置条件合同：除固定必需项外，`conditional_reviews` 和 `conditional_evidence` 各自声明触发条件和 `reason_code`。

```json
{
  "manifest_fingerprint": "sha256:...",
  "required_evidence_types": ["source_trace"],
  "required_receipts": ["read_set"],
  "conditional_reviews": [
    {
      "review_type": "security_acceptance",
      "trigger": "write_scope_overlaps_security_path",
      "reason_code": "security_sensitive_path_touched"
    }
  ],
  "conditional_evidence": [
    {
      "evidence_type": "test_result",
      "trigger": "mutation_profile>=workspace_write",
      "reason_code": "workspace_write_requires_verification"
    }
  ],
  "verification_commands": [],
  "completion_blockers": []
}
```

执行阶段只能激活合同中已预声明的 `conditional_reviews|conditional_evidence` 条件；一旦出现新的风险 Gate、范围扩大或未在合同内声明的条件，必须先重新准入生成新的 `manifest_fingerprint`，不得在现有合同下临时追加。`verify` 只解析并比对当前 `completion_manifest` 的固定项和已激活的条件项，不得在收尾末端新增隐藏要求。

宿主不得在业务完成后新增未在合同中声明的固定 review 或 security review。真实范围、风险 Gate 或用户要求发生变化时，必须通过重新准入显式更新合同。

收尾使用增量协议：草稿只生成一次，后续 `complete_step` 只提交新增收据和缺口状态，最终回复只输出一次正文及一份证据摘要，不重复渲染完整答案。

## 10. 效率遥测

每个任务事件新增有界字段：

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

不得记录原始工具输出、用户正文、环境变量、凭证或完整日志。复盘只使用聚合计数和受控原因码。

首批原因码至少包括：

```text
intent_ambiguous
scope_required
scope_description_invalid
read_set_drift
write_scope_violation
concurrent_drift_overlap
git_remote_drift
context_content_changed
missing_typed_evidence
host_receipt_missing
```

## 11. 兼容与迁移

### 11.1 v1 → v2 对象矩阵

迁移覆盖的对象不止 `allowed_scope`，还包括任务准入涉及的其他持久化对象：

| 对象 | v1 形态 | v2 形态 | 迁移方式 | 回滚约束 |
|---|---|---|---|---|
| task-package | `allowed_scope`（路径/自然语言混用） | `read_scope\|write_scope\|git_scope\|external_scope` + `task_intent\|candidate_intents\|mutation_profile` | 路径型 `allowed_scope` 按任务变更面迁移到对应 scope；自然语言范围拒绝自动迁移，要求显式重建 | 回滚窗口内 v1 读取路径必须保留 |
| compiled-task | 单一 Gate 编译结果 | 意图优先编译结果，取混合意图最高变更面与最高风险 Gate | 新任务直接按 v2 规则重新编译，不回填改写既有 v1 编译结果 | 回滚后不得以 v1 控制器直接复用 v2 编译结果 |
| freeze | 仅 `workspace_snapshot` 单一基线 | 保留首次 `workspace_snapshot`，按适用任务增加固定 `git_state_snapshot`/Schema 元数据；`read_set\|task_write_set\|concurrent_drift\|unattributed_drift` 由 verify 计算并记录到 compiled/events/evidence，不回写首次基线 | 新增元数据字段随冻结生成，不重建历史基线；四类动态集合不进入不可变 freeze | 回滚后 freeze 新增元数据字段只读保留，不参与 v1 判定 |
| evidence-index | 未类型化或弱类型证据 | evidence-receipt/v2（绑定字段见 8.1） | 新证据一律写 v2；历史证据保持 v1 只读，不追加缺失字段 | 回滚后 v2 证据不得被当作满足 v1 弱类型要求的等价物 |
| context receipts | 无 `content_set_fingerprint` | 绑定 `content_set_fingerprint` 及 task/target/stage/compiler contract（见 8.3） | 新收据写 v2；旧收据不参与新的指纹复用判断 | 回滚不清除已生成的 v2 收据，仅停止新复用 |
| authorization receipts | 绑定任务包 | 绑定 package fingerprint，不得跨 fingerprint 复用 | 新授权一律绑定当前 package fingerprint | 回滚不得放宽跨 fingerprint 复用限制 |

### 11.2 迁移规则

1. 保留现有六种准入状态和三种执行路线，降低宿主迁移成本；
2. 新任务一律写入 v2 结构；处于执行中的 v1 任务不静默改写为 v2，只提供兼容读取或要求显式迁移后继续；
3. 跨文件迁移（task-package、freeze、evidence-index 等联动更新）执行完整迁移事务：先在 staging 生成全部受影响对象及其 manifest/fingerprint，校验通过后原子切换到新状态；不支持原子目录切换的平台使用迁移 journal 加全对象备份完成恢复；`package-history` 只作为补充历史记录，不是 evidence、context、authorization 等对象的唯一恢复源；迁移在任意步骤中断时按 journal 和备份回退，不产生半迁移状态；
4. 授权凭证绑定当前任务包的 fingerprint，不得跨 package fingerprint 复用，包括迁移前后产生的不同 fingerprint；
5. 旧版本控制器遇到 v2 任务包、收据或合同时必须失败关闭，不得按 v1 语义误解析后继续执行；
6. 项目整体降级或回滚，受当前是否存在活动 v2 任务约束（见 12.2）；
7. 项目配置升级版本由实现阶段确定；安装快照、规则、脚本和入口必须作为同一候选升级；
8. 下游项目只有完成安装升级、本地运行、当前 HEAD、远端和 fresh clone 分层验收后，才能声称新机制已交付。

## 12. 实施顺序

阶段之间存在硬依赖：后一阶段不得绕过前一阶段直接实现，只能在前一阶段出口门槛通过后开始。允许使用 RC 或 feature flag 对单个阶段分段验证，但 v1.5.0 的整体完成声明必须等全部阶段的阻断验收项通过后才能给出；任何阶段单独通过时，只报告该阶段对应层级的完成情况，不得推广为整体完成声明。

### 阶段一：意图、变更面和范围合同

- 入口门槛：方案评审通过，task-package/v2 Schema 定稿；
- 依赖：无前置阶段；
- 出口门槛：`query|audit|git_inspect|git_fetch|git_sync` 回归矩阵全部通过，自然语言范围回归全部失败关闭，混合意图（`audit+fix`、`if-needed-fix`、`fetch+sync`）按最高变更面编译的回归通过；
- 内容：
  - 新增 `task_intent`、`candidate_intents`、`mutation_profile` 和 task-package/v2；
  - 将 Gate 推断调整为“意图优先、风险 Gate 后置”；
  - 拆分读写、Git 和外部范围；
  - 对自然语言范围失败关闭；
  - 为 `query|audit|git_inspect|git_fetch|git_sync` 建立回归矩阵。

### 阶段二：漂移归因和 Git 操作

- 入口门槛：阶段一出口门槛通过；
- 依赖：`mutation_profile`、`read_scope|write_scope|git_scope` 已可用；
- 出口门槛：`unattributed_drift` 不得被误判为 `concurrent_drift` 或 `task_write_set` 的回归通过，`git_state_snapshot` 预检/后检回归通过，Git 远端漂移重新准入回归通过；
- 内容：
  - 增加 `read_set|task_write_set|concurrent_drift|unattributed_drift`；
  - 实现 `git_state_snapshot` 与 Git inspect、fetch、sync 的预检和后检合同；
  - 保持首次冻结基线不可变；
  - 增加并发外部写入、脏工作区、远端漂移和 LFS/Submodule 回归。

### 阶段三：证据适配和宿主收尾

- 入口门槛：阶段二出口门槛通过；
- 依赖：`task_write_set`、`git_state_snapshot` 已可用于绑定证据；
- 出口门槛：evidence-receipt/v2 全部绑定字段回归通过，过期/跨任务/跨目标/不可信生产者拒绝复用回归通过，`completion_manifest` 条件激活与重新准入回归通过；
- 内容：
  - 实现 evidence-receipt/v2 和命令 `produces` 白名单；
  - 按内容集合指纹复用上下文收据，限定同一 task/target/stage/compiler contract；
  - 输出带指纹的前置 `completion_manifest`；
  - 将收尾改为增量提交和一次性最终回复。

### 阶段四：遥测与下游交付

- 入口门槛：阶段三出口门槛通过；
- 依赖：全部阻断证据类型和收尾合同已实现；
- 出口门槛：v1→v2 迁移中断恢复、v1 在途任务兼容读取、旧控制器遇 v2 失败关闭三类回归全部通过，源码自检、临时项目、真实 Git/fresh clone 和真实宿主验收全部通过；
- 内容：
  - 写入脱敏效率事件；
  - 建立基线任务集并比较 v1.4 与候选版本；
  - 完成源码自检、临时项目、真实 Git/fresh clone 和真实宿主验收；
  - 再按授权升级下游项目，不从源码通过推导安装完成。

### 12.1 迁移与兼容回归

以下回归项在对应阶段出口门槛内验证，任一失败均不得声明整体完成：

- 迁移中断恢复：跨文件迁移在任意步骤中断后，可通过 staging 校验产物或迁移 journal 加全对象备份恢复，不产生半迁移状态；`package-history` 仅作补充历史，不作为唯一恢复源；
- v1 在途任务：迁移开始前已存在的 v1 任务包在迁移期间可继续走兼容读取路径，不被静默改写；
- 旧控制器读 v2：旧版本控制器遇到 v2 任务包或收据时失败关闭，不按 v1 语义误解析；
- 条件清单：`completion_manifest` 的 `conditional_reviews|conditional_evidence` 只能在预声明触发条件下激活，未声明条件出现时必须重新准入；
- 新鲜度与信任：过期、跨任务、跨目标或生产者不可信的 evidence-receipt/v2 一律拒绝复用；
- Git refs 远端漂移：`git_fetch|git_sync` 预检后远端目标漂移时必须重新准入，不得沿用旧 `git_state_snapshot` 继续写入。

### 12.2 回滚标准

- 项目降级或回滚只允许在没有活动 v2 任务的窗口执行；存在活动 v2 任务时，回滚必须先等待任务完成或显式取消并释放授权；
- 回滚后，v2 产生的 task-package、compiled-task、freeze、evidence-index、context receipts 和 authorization receipts 在存储层只读保留；旧 v1 控制器遇到它们继续失败关闭，只有 v2 兼容读取器或显式导出流程可以查看，不得被 v1 控制器直接复用为新授权；
- 任一阶段的出口门槛未通过时，不得对下游项目声明该阶段对应能力已交付；下游升级只在授权范围内逐项进行，不从源码状态推导安装完成。

## 13. 验收标准

### 13.1 只读查询

1. “文档在哪”“解释这段代码”“审计某分支是否可删除”不因对象名命中编辑 Gate。
2. 默认 `ready_direct + read_only + write_scope=[]`。
3. 不创建正式方案，不要求编辑型 document review。
4. Harness 控制调用不超过 `run + verify` 两次；业务读取调用单独计数。
5. 相同内容集合在同一任务内只加载一次。

### 13.2 Git 操作

1. `git_inspect` 不要求逐文件写入范围。
2. `git_fetch` 只冻结远端、refspec 和 Git 引用范围，并验证工作区未变化。
3. `git_sync` 自动生成工作区变化范围，操作者不手写逐文件清单。
4. 预检后远端漂移、不可 fast-forward、危险删除或重叠脏改动继续失败关闭。
5. 执行后逐项验证 `HEAD`、目标远端指针、分支分歧、工作区与索引、Git LFS 和 Submodule 状态；缺少任一项时不得报告完成。
6. 完成结论只覆盖对应 Git 层级。

### 13.3 并发漂移

1. 无关外部写入不会被记为当前任务写入。
2. 外部写入影响 `read_set`、`write_scope` 或高风险边界时必须阻断。
3. 已跟踪运行态不能通过 `.gitignore` 或 exclusion 隐藏。
4. 无 Hook 宿主明确报告归因质量，不能伪造强保证。

### 13.4 证据与收尾

1. 合法验证命令可按声明映射到对应语义证据。
2. 收尾前一次性返回完整证据需求，不出现固定的末端补证惊喜。
3. 同一回复正文不因多轮收据补充而重复输出。
4. 所有效率结论都能由 Runtime 的结构化指标复算。

## 14. 风险与控制

| 风险 | 控制 |
|---|---|
| 只读路线被用于规避安全 Gate | 意图与风险 Gate 正交，显式 facts 只能升级 |
| 并发变化被错误放行 | 读取、写入或高风险边界重叠时失败关闭 |
| 宿主伪造任务写入归因 | 记录 `attribution_quality`，缺少 Hook 时不声称已证明 |
| 命令退出 0 被冒充语义通过 | 命令必须声明 `produces` 并满足类型合同 |
| Git 预检结果过期 | 冻结远端目标和变更清单指纹，漂移即重新准入 |
| 为降耗隐藏已跟踪运行态 | 禁止 tracked path exclusion，优先迁移运行态 |
| 遥测泄漏敏感信息 | 只保存计数、耗时和受控原因码 |

## 15. 下一步

先完成阶段一的 Schema、状态转换和回归用例设计，重点证明三件事：只读查询不会误入编辑 Gate、自然语言不能进入路径范围、风险 Gate 不能被新意图模型降级。方案评审通过后再开始实现，不在评审阶段修改控制器。
