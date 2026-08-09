# Docs Harness 知识初始化修复方案 Claude Code 审查记录

审查日期：2026-08-04  
审查工具：Claude Code 2.1.220  
审查方式：安全模式，只开放 Read、Grep、Glob；禁止编辑、Shell 和子智能体  
审查对象：Docs Harness v1.5.0 源码、测试、合同，以及 ZBuddy 现场副本  
审查结论：根因成立，建议补齐状态机、可观测性和分类器边界后进入实现

## 审查范围

Claude Code 独立读取并核对：

- `scripts/harness.py`；
- `tests/test_harness.py`；
- `SKILL.md`；
- `docs/contracts.md`；
- ZBuddy 对应控制器、配置和知识状态。

本次审查没有修改任何文件。第一次只读调用因权限模式进入无输出等待，已终止；第二次使用 `dontAsk` 和只读工具完成审查。

## Claude Code 确认的结论

### 1. 后台增量交付物没有实际控制派发

`classify_document_deliverables()` 会移除后台交付物，但 `command_verify()` 仍固定调用知识 Job 创建器。因此抑制开关在产品上不可用。

### 2. bootstrap 活动状态判断不一致

`knowledge_status()` 和 bootstrap 去重逻辑把所有非终态 Job 视为活动，但增量 Job 创建器只识别 `dispatched|running`。这会让 `contract_ready`、`queued_manual` 或 `needs_user_input` 状态的 bootstrap 失去依赖保护。

### 3. project upgrade 缺少知识交接

`project init` 有 `knowledge_flow`，`project upgrade` 没有。升级分支还把 `docs_preexisted=True` 写死，导致没有 docs 的旧项目也不能进入新项目 bootstrap 流程。

### 4. 增量 no_change 的验收过宽

只有 bootstrap 在知识未 ready 时禁止 `no_change`。增量 Job 可以在全局知识缺失时正常完成，形成静默空转。

### 5. 子串 Gate 存在系统性假阳性

Claude Code 复核了 `docs/reviews/` 命中 `views/` 的路径问题，并指出 `ui`、`api`、`test`、`auth` 等英文短词还可能误伤普通单词。

### 6. 现有测试只覆盖了恰好正确的 happy path

现有 bootstrap 串行测试会先把 bootstrap 推到 `running`，没有覆盖 `contract_ready` 等状态；升级测试会先正常 init，因此没有覆盖“旧项目已有 docs、无知识地图”的 ZBuddy 形态。

## Claude Code 补充的重要遗漏

### 非终态 Job 可能永久停滞

当前停滞提醒没有完整覆盖 `contract_ready` 等状态。即使路由修复正确，如果宿主没有真正接单，bootstrap 仍可能无限期停留，而项目只显示一条黄色 `knowledge_pending`。

### 下游受管入口也要同步

修复不能只改 Python 控制器。写入下游 `AGENTS.md` / `CLAUDE.md` 的受管说明必须覆盖 upgrade 知识交接，否则智能体仍只会在 init 响应中寻找 audit 流程。

### 在途任务兼容风险

Gate、candidate intents 和 background deliverables 都参与 task package fingerprint。升级控制器后，在途 v2 任务可能需要重新准入，旧授权和证据不能静默复用。

## 采纳意见

最终方案采纳了以下建议：

- 新增统一 active bootstrap 判定，替换分散谓词；
- 让 `background_deliverables` 成为 verify 的派发真源；
- `project init` 与 `project upgrade` 复用同一 knowledge flow；
- 只读和显式抑制任务不产生知识增量 Job；
- 所有知识 Job 的正常收尾都要求最终状态 ready；
- 路径 Gate 改为完整路径段匹配；
- inventory 复用统一过滤策略；
- 增加 Job 超时与每次任务入口的知识下一步提醒；
- 建议以 v1.6.0 发布，并明确在途任务重新准入边界。

## 修正或未直接采纳的意见

### 1. 不把 knowledge_not_bootstrapped 记为 dispatch_failed

Claude Code 建议从创建器抛出 `knowledge_not_bootstrapped`，复用现有 `dispatch_failed` 分支。最终方案没有采纳这一产品语义。

原因：`needs_audit` 是预期的用户交接，不是 Runtime 故障。最终方案要求返回独立的 `knowledge_handoff.status=action_required`，只有真正的 Job 创建异常才使用 `dispatch_failed`。

### 2. partial 不允许增量 Job 正常收尾

Claude Code 的最小流程一处把 `partial` 与 `ready` 并列为可创建或完成增量 Job。最终方案收紧为只有 `ready` 才允许。

原因：本次用户已经明确要求初始化完成以 `knowledge status=ready` 为口径；`partial` 仍代表功能知识存在缺口。

### 3. 不开放通用 intent override 降档

Claude Code 建议提供可留痕的 `intent_override.drop_intents`。最终方案暂不采纳。

原因：允许 facts 主动丢弃推断出的高风险意图，会削弱“只能升档”的安全上界。最终方案优先修复子句、时态、否定和未来任务边界；仍有歧义时继续失败关闭。

### 4. ZBuddy Runtime 位置需要修正

Claude Code 根据项目根目录 `.docs-harness/` 判断没有后台 Job，但 ZBuddy 是 Git 项目，真实 Runtime 位于 `.git/docs-harness/`。原增量 Job 和本次诊断 Job 均存在。

该事实不影响其源码根因判断，但说明后续现场验收必须通过控制器或 Git Runtime 路径读取，不能只检查项目根目录 `.docs-harness/`。

## Codex 补充的状态机缺口

Claude Code 提醒了 active bootstrap 谓词，但没有完整处理两个依赖结果：

1. `waiting_for_bootstrap_merge` 当前可以直接转换为 `updated|no_change`；最终方案要求禁止这种转换。
2. bootstrap 失败或取消后，当前等待者可能被释放为 `contract_ready`；最终方案要求等待者进入 `needs_user_input`，不能继续运行。

## 最终方案复核

Claude Code 对落盘后的两份文件进行了第二轮只读复核，结论为“无 P0，存在 4 个 P1”。最终方案已全部吸收：

1. 明确 bootstrap `no_change + ready` 属于成功释放；`completed_with_finding` 阻断等待者并转人工处理。
2. 为旧版 `waiting_for_bootstrap_merge` Job 增加显式、幂等、非查询时迁移，避免状态机收紧后硬失败。
3. 为 upgrade 增加 `bootstrap_in_progress`，显式处理 `building`，并补充 `invalid` 兼容分支。
4. assessment 的 ready 不直接等于完成；先纯读取复算候选知识，ready 后才原子写地图，partial 时不污染地图。

相应测试已增加 T27–T30。复核提出的 inventory include 数量和单文件大小上限，也纳入实现约束：include 必须继续受现有 4096 项和 2 MiB 单文件上限保护，不能成为绕过库存边界的通道。

## 最终联合结论

这不是一个单点条件判断错误，而是四个合同之间没有共同真源：

```text
项目升级合同
  → 知识生命周期合同
  → 父任务后台派发合同
  → 后台 Job 验收合同
```

最小可交付修复必须同时闭合这四层，并增加意图/Gate 和 inventory 两项已复现的入口问题。只修 `project upgrade` 返回提示，或只把增量 Job 改名为 bootstrap，都不能保证知识库真正建立并达到 ready。
