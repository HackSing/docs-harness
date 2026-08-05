# Docs Harness Runtime 生命周期与交付回执语义治理方案

## 1. 方案状态

- 当前状态：方案已建立，待实施审查；尚未修改控制器、测试或任何项目 Runtime。
- 目标版本：不预先绑定版本号，由实施与发布阶段确定。
- 方案范围：Docs Harness 源码中的任务生命周期、后台 Job 收口、完成回执分层语义及对应测试和合同文档。
- 下游范围：ZBuddy 仅作为后续安装与治理验收目标，本方案阶段不改写其 Runtime。
- 唯一方案真源：本文档。

## 2. 背景

截至 2026-08-05 的只读现场核对显示，ZBuddy Runtime 存在两类未闭环状态：

- 21 条更早的非终态任务记录，其中 13 条为 v2 活动任务、8 条为 v1 只读兼容任务；没有对应的运行中执行进程。
- 13 条非终态后台 Job，其中 4 条 `delivery_governance` Job 会阻塞 `project rollback-check`。

当前任务状态模型已经把 `cancelled` 视为终态，但 `task` CLI 只提供 `status` 与 `migrate`，缺少受支持的取消、归档和终态清理入口。直接删除 Runtime 目录或手工改写 `compiled-task.json` 会绕过事件、指纹、幂等与回滚合同。

同时，通用完成回执无条件返回 `remote_delivery_not_verified`，并固定声明 `acceptance_layers=["source","local_verification"]`。这会把以下状态混为一谈：

- 当前任务不涉及远端交付；
- 用户没有要求远端交付；
- 远端交付被要求但尚未验证；
- 远端与 fresh clone 已经验证。

两个问题的共同根因是：Runtime 缺少明确的“终结处置真值”，完成回执缺少明确的“交付适用性与验证真值”。

## 3. 目标

1. 用受支持、可审计、幂等的命令终结废弃 v2 任务，不伪造完成证据。
2. 只读保留 v1 对象，通过独立归档处置让其不再显示为待处理任务。
3. 复用现有后台 Job 状态机，安全终结已确认废弃的非终态 Job，并单独保护严重发现。
4. 只有“任务明确要求且尚未验证”的交付层才产生 `known_limit_codes`。
5. `acceptance_layers` 只反映真实证据已经覆盖的层，不再由完成函数固定生成。
6. 先完成源码合同与测试，再安装到 ZBuddy；治理前后都有可复查清单和回滚检查。
7. 默认保留审计对象，物理清理必须经过保留期和 `dry-run` 候选确认。

## 4. 非目标

- 不把历史任务伪装为 `complete`，不补造业务证据。
- 不手工编辑或批量删除 `.git/docs-harness/runs/**`。
- 不因治理任务自动提交、推送、发布或升级 ZBuddy。
- 不把 `rollback_allowed=true` 扩大解释为源码、安装、运行或业务验收完成。
- 不把所有后台 Job 一律取消；`critical_followup`、`completed_with_finding` 及仍有宿主进程的 Job 必须单独审查。
- 不在方案阶段决定实现版本号、发布分支或远端交付范围。

## 5. 最小产品合同

### 5.1 v2 任务取消

新增命令：

```bash
python3 scripts/harness.py task cancel \
  --target . \
  --task-id <task-id> \
  --reason-code <reason-code> \
  --json

python3 scripts/harness.py task cancel \
  --target . \
  --task-id <task-id> \
  --reason-code <reason-code> \
  --apply \
  --json
```

缺省为预览；只有显式 `--apply` 才写入。最小受控原因码包括：

```text
host_task_closed
superseded
duplicate
invalid_admission
operator_abandoned
```

应用前必须满足：

- 对象为有效 v2 任务，任务包、编译状态与 freeze 指纹一致；
- 当前状态不是 `complete|cancelled|failed`；
- 不存在活动状态锁；若宿主报告过执行中状态，必须先证明宿主与子进程静止；
- 取消动作不修改任务包、freeze、既有证据与上下文收据。

应用后只允许：

- 将 `compiled-task.json.control_status` 置为 `cancelled`；
- 将 `next_action` 清空并记录 `cancelled_at`、受控原因码；
- 向 `events.jsonl` 追加不可变取消事件；
- 返回原状态、新状态、任务指纹、事件引用和幂等结果。

相同任务使用相同原因重复执行必须返回同一结果；不同原因重复取消必须返回冲突，不得覆盖首次处置事实。

### 5.2 v1 只读归档

v1 对象继续保持只读，不为了“消除待办”而迁移到 v2。新增独立的本地归档处置索引，至少保存：

```text
task_id
source_schema
source_object_fingerprint
disposition=archived
reason_code
recorded_at
```

归档只影响任务列表和治理候选，不修改 v1 任务目录。默认列表隐藏已归档对象，显式 `--include-archived` 才展示。源对象指纹变化时归档失效并失败关闭。

### 5.3 终态清理

新增任务清理入口，与现有后台 `prune` 保持一致：

```bash
python3 scripts/harness.py task prune --target . --older-than 30 --dry-run --json
python3 scripts/harness.py task prune --target . --older-than 30 --apply --json
```

候选必须同时满足：

- 已处于 `complete|cancelled|failed`，或为已归档且源指纹未变化的 v1 对象；
- 已超过保留期；
- 已进入受控索引，摘要与处置事件可追溯；
- 不存在锁、活动宿主、未处理严重发现、授权等待或未终结子 Job；
- 缺省只生成候选，`--apply` 仅删除本次候选清单中指纹未变化的对象。

首轮 ZBuddy 治理不执行物理删除，只终结并归档。

### 5.4 后台 Job 收口

后台 Job 继续使用现有取消状态转换，不新增第二套状态机。治理清单分为：

- 可直接取消：确认废弃且处于 `contract_ready|queued_manual|waiting_*` 的普通知识或治理 Job；
- 需静止证明：`dispatched|running`；
- 需人工结论：`critical_followup`、严重发现或依赖链未闭合的 Job；
- 不处理：已经处于终态的 Job。

取消后必须重新执行 `background list` 和 `project rollback-check`。任务取消与后台 Job 取消是两个独立验收面，不能用其中一个替代另一个。

## 6. 交付回执分层语义

### 6.1 分层状态

完成回执保留兼容字段，同时新增结构化 `delivery_layers`。每一层至少包含：

```json
{
  "remote_delivery": {
    "expectation": "not_applicable | not_requested | required",
    "status": "not_verified | verified",
    "evidence_refs": []
  }
}
```

最小层级包括：

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

### 6.2 生成规则

- `query|audit|git_inspect` 默认将远端交付和 fresh clone 标记为 `not_applicable`。
- 本地 `modify` 任务未声明 Git 或外部交付时标记为 `not_requested`。
- `git_sync|external_write` 或成功标准明确要求远端、发布、安装、fresh clone 时标记为 `required`。
- `acceptance_layers` 从通过且仍新鲜的证据推导，只列出 `verified` 层。
- `known_limit_codes` 只从 `expectation=required && status=not_verified` 的层生成。
- `not_applicable` 与 `not_requested` 不生成“未验证”告警，但必须在 `delivery_layers` 中可见。
- 远端、fresh clone、发布产物和 UI 证据必须分别绑定，不得由一个 Git 后检统一推导。

### 6.3 兼容策略

- 保留 `acceptance_layers`、`known_limit_codes` 和 `known_limit_details` 字段，避免宿主立即断裂。
- 移除 `remote_delivery_not_verified` 的无条件默认值，改为由 `delivery_layers` 派生。
- 旧宿主可以继续读取字符串数组；新宿主以结构化层级为准。
- 回执合同发生变化时更新合同文档与测试，不静默改变同一 schema 的含义；是否升级 schema 在实施审查时决定。

## 7. 实施顺序

### 阶段 A：源码合同与测试

1. 先补失败测试，覆盖 v2 取消预览、应用、幂等、冲突、锁和终态保护。
2. 覆盖 v1 只读归档及源指纹漂移失败关闭。
3. 覆盖任务 prune 的候选冻结、保留期、严重发现和二次指纹检查。
4. 覆盖只读、本地修改、要求远端、已验证远端四类回执矩阵。
5. 实现最小控制器变化，并更新 `docs/contracts.md` 与 `README.md`。

### 阶段 B：源码验收

至少通过：

- 定向合同测试；
- 全量测试；
- 内置 self-test；
- Python 编译检查；
- 包内容检查；
- 独立代码与合同审查。

这一阶段只证明源码候选可用，不证明已提交、已推送、已安装或已治理 ZBuddy。

### 阶段 C：ZBuddy 安装前预览

1. 核对 Docs Harness 源、安装快照、ZBuddy HEAD 与工作区状态。
2. 生成 13 条 v2 任务取消预览、8 条 v1 归档预览和非终态后台 Job 分类清单。
3. 单独确认 `critical_followup` 与严重发现，不纳入默认批次。
4. 只有预览清单、原因码和作用范围被确认后才应用。

### 阶段 D：ZBuddy 治理验收

目标结果：

- v2 活动任务数为 0；
- v1 历史任务全部只读归档且对象指纹未变化；
- 废弃后台 Job 进入合法终态，严重发现有明确保留或处置结论；
- 活动文档路由 Job 数为 0；
- `project rollback-check` 不再因活动 v2 任务或文档路由 Job 阻塞；
- ZBuddy 业务工作区、HEAD 和受跟踪文件没有被 Runtime 治理修改；
- 新回执对只读治理任务不再显示不适用的远端未验证提示。

### 阶段 E：延迟清理

保留至少 30 天后执行 `task prune --dry-run` 与 `background prune --dry-run`。只有候选、索引、严重发现保护和对象指纹全部通过复核，才另行授权 `--apply`。

## 8. 验收标准

### 8.1 功能验收

- 取消、归档、清理命令均缺省只读预览，写入需要显式 `--apply`。
- v2 取消不改写任务包、freeze 和既有证据。
- v1 归档不改写 v1 对象。
- 运行中、锁定、严重发现和依赖未闭合对象失败关闭。
- 回执能稳定区分 `not_applicable`、`not_requested`、`required/not_verified` 和 `required/verified`。

### 8.2 回归验收

- 已完成任务不会重新进入活动集合。
- `blocked` 任务的既有重新准入语义不被取消命令破坏。
- v1→v2 显式迁移合同不被归档路径替代。
- 现有后台状态机、Job prune 与回滚保护测试保持通过。
- 旧宿主读取兼容字段时不会报 schema 错误。

### 8.3 交付分层验收

实施完成后分别报告：

```text
方案完成
源码实现完成
本地测试完成
Git HEAD 已提交
远端已接收
fresh clone 已验证
ZBuddy 已安装
ZBuddy Runtime 已治理
保留期后物理清理完成
```

任何上一层通过都不能代替下一层。

## 9. 风险与失败关闭

- 误取消仍有价值的任务：应用前输出原任务摘要、状态、原因码和指纹，禁止无原因批量取消。
- v1 对象被兼容写入破坏：只写独立归档处置索引，源对象保持只读。
- 清理后证据不可追溯：首轮不删除；后续 prune 要求终态索引、保留期和二次指纹检查。
- 严重发现被批量吞掉：`critical_followup` 与严重发现永不进入默认取消或 prune 候选。
- 回执隐藏真实缺口：只有 `not_applicable|not_requested` 不告警；`required/not_verified` 必须继续失败关闭或明确提示。
- 回执宣称超过证据：每个 `verified` 层必须绑定新鲜、可信的 evidence ref。

## 10. 回滚策略

- 源码实施回滚：恢复控制器、测试与合同文档；不自动触碰已经生成的 Runtime 处置事件。
- 任务取消不可改回活动状态；需要继续原目标时创建新任务并引用原任务，不改写历史。
- v1 归档可以通过显式反归档恢复列表可见性，但不能修改源对象。
- 物理 prune 一旦执行不承诺恢复，因此必须晚于保留期并另行授权。
- ZBuddy 安装回滚必须先通过 `project rollback-check`，并继续保留新版本 Runtime 对象的只读安全边界。

## 11. 文档真源、索引与残留

- 本方案是该需求的唯一方案真源。
- `docs/todo.md` 只保存相对链接、风险、目标、验收摘要和下一步，不复制本文。
- 实施时同步更新 `docs/contracts.md` 与 `README.md`；若 schema 或兼容边界变化，再按项目规则更新 ADR 与 Changelog。
- 旧的计划文档只作为历史事实，不新增第二份并行实施方案。
- ZBuddy Runtime 清单属于运行态证据，不进入 Git 方案正文的持续状态源；实施前必须重新盘点。

## 12. 下一步

对本文进行一次只读实施审查，冻结命令、状态迁移、回执矩阵和兼容边界；审查通过后，按阶段 A 先写失败测试，不直接从 ZBuddy Runtime 清理开始。
