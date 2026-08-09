# Docs Harness 意图路由权威治理产品方案

## 1. 背景

Docs Harness 已在合同中规定：宿主通过 `intent_assessment` 提交权威意图声明，任务文本启发式只作为诊断候选，不能授予写权限。但真实 ZBuddy 任务证明，生产行为仍由 `INTENT_PATTERNS` 的字符串匹配结果决定：

- “切换到其他分支”被编译为 `query / read_only`；
- `git switch codex/ai-ppt-review-flow` 因分支名含 `review` 被编译为 `review_light` 或旧控制器中的 `audit`；
- “输出一份详细的产品方案文档到本地”被编译为 `query / read_only`；
- 宿主事后发现合同错误，只能取消旧任务、补范围后重新准入，实际产生三次准入和一个遗留 `ready_direct` 任务。

根因不是词表不完整，而是权威边界不完整：控制器一方面声明宿主语义是权威来源，另一方面又允许启发式在“看起来只读”时生成正式合同。该不对称使漏判写意图比误判写意图更危险，也让兼容逻辑成为生产决策器。

同时，ZBuddy main 与 AI PPT worktree 的控制器都标记为 `1.7.6`，但内容指纹和行为不同，说明行为变更没有形成可跨 worktree 验证的控制器身份。

## 2. 产品目标

1. 模型语义声明是正式任务意图的唯一来源。
2. 控制器不再根据任务文本关键词决定 `task_intent`、`candidate_intents` 或 `mutation_profile`。
3. 缺少结构化意图时失败关闭，但不创建需要随后取消的伪任务。
4. 信息完整的任务保持一次准入；信息不完整时最多一次结构化补全，不形成取消/重建循环。
5. 本地 Git 操作、工作区写入和外部写入继续由控制器做确定性范围、状态和后检验证。
6. 控制器行为身份可跨分支和 worktree 验证，同版本不得存在多个未区分的行为实现。

## 3. 非目标

- 不把意图判断重新交给另一套关键词、正则或本地分类模型。
- 不让自然语言直接授予写权限、Git 权限或外部写权限。
- 不移除否定守卫、交付层需求匹配、Harness Home 规则选择等非意图路由逻辑；这些逻辑必须继续限定在各自合同内。
- 不自动猜测任意文件路径、删除 worktree、强制切换分支或绕过现有范围合同。
- 不修改 ZBuddy 产品代码。

## 4. 核心产品原则

### 4.1 单一权威来源

正式意图来源只允许：

1. `intent_assessment`；
2. 迁移期兼容的显式 `task_intent|candidate_intents`，并在响应中标记 `legacy_explicit`；
3. 已冻结任务包在合法重准入时继承的原声明。

任务正文仅保存为审计快照和用于知识检索，不参与意图、变更面或授权编译。

### 4.2 缺声明不是只读

没有结构化意图声明时，结果必须是 `missing_intent_assessment`，不能回退为 `query`。控制器返回声明 Schema、允许值、示例和宿主修复动作，但不生成正式 task-package、freeze、evidence-index 或活动任务状态。

### 4.3 语义与事实验证分层

模型负责声明“用户要做什么”；控制器负责验证“是否允许以及是否真的做到”：

| 层级 | 权威来源 | 控制器职责 |
|---|---|---|
| 意图 | 宿主模型 `intent_assessment` | Schema、枚举、完整性和不可降级校验 |
| 风险 Gate | 宿主模型 `gate_assessment` + 项目显式规则 | 校验声明、路径绊线和授权要求 |
| 范围 | 结构化 scope / Git 资源 / 外部目标 | 规范化、越界检查和冻结 |
| 执行结果 | Git、工作区、命令和外部状态 | 确定性预检、后检与证据绑定 |

### 4.4 兼容不能改变语义

旧宿主没有提交新字段时只能得到结构化迁移错误；兼容层不得替旧宿主猜意图。兼容目标是“错误可操作”，不是“旧调用继续静默运行”。

### 4.5 历史任务包迁移

历史 v1 任务包不具备宿主权威意图声明，迁移时不得回读任务正文猜测意图。迁移仅允许使用已经冻结的结构化范围做保守映射：

- 存在非空 `allowed_scope`：迁移为 `modify / workspace_write`；
- 不存在写范围：迁移为 `query / read_only`；
- 迁移结果标记 `legacy_scope_conservative`，不能伪装成宿主判断；
- 若操作者需要更精确的意图，必须通过新准入提交结构化声明，不能修改历史审计事实。

保守迁移宁可抬高风险等级，也不允许任务文本把历史写任务降级成只读。

## 5. 产品流程

### 5.1 首次准入

```text
用户请求
  → 宿主模型生成 intent_assessment；写任务同时生成 gate_assessment + 结构化范围
  → Harness 校验声明与范围
  → 信息完整：一次创建正式任务
  → 信息不足：返回非持久化缺项响应
```

完整写任务示例：

```json
{
  "intent_assessment": {
    "intents": ["modify"],
    "rationale": "用户明确要求将产品方案写入本地 Markdown 文档"
  },
  "gate_assessment": {
    "gates": ["document-edit"],
    "rationale": "只新增产品方案并同步受管文档索引，不修改产品代码"
  },
  "write_scope": [
    "docs/plans/ai-ppt-agent-progress-feedback-product-plan.md",
    "docs/INDEX.md"
  ]
}
```

### 5.2 缺声明响应

`run` 在创建任务状态前检查声明。缺失时返回：

```json
{
  "code": "missing_intent_assessment",
  "admission_persisted": false,
  "missing_items": ["intent_assessment"],
  "assessment_schema": {
    "intents": ["<task_intent>"],
    "rationale": "<宿主基于用户语义给出的判断>"
  },
  "suggested_fix": "宿主完成语义判断后，以 --facts 提交结构化声明并重新执行首次准入"
}
```

该响应不是任务，不产生 task-id，不需要 `task cancel`。

### 5.3 缺范围响应

意图明确为写入但缺少目标范围时返回 `missing_write_scope`，同样不持久化正式任务。控制器只返回结构化字段要求；只有项目配置存在明确文档路由时才提供候选路径，不自动授权整个目录。

### 5.4 已有任务重准入

已冻结任务发生范围或 Gate 变化时继续使用原 task-id 和 package revision，不把同一目标拆成多个活动任务。任何新增范围必须重新提交 `intent_assessment` 与 `gate_assessment`，并记录合同差异。

## 6. 意图路由调整

### 6.1 删除生产关键词裁决

从生产准入路径移除：

- `INTENT_PATTERNS`；
- `mutation_intent_explicitly_requested()`；
- `classify_task_intents()` 中对任务正文的 `find()`、否定、未来体和完成体关键词扫描；
- `has_declared_scope ? modify : query` 默认意图；
- `heuristic_advisory` 正式任务模式。

保留 `parse_intent_assessment()` 与显式兼容字段解析。`classify_task_intents()` 若继续保留，应只处理结构化声明，不读取 `task`；更清晰的方案是重命名为 `resolve_declared_intents()`。

### 6.2 不删除的关键词逻辑

以下逻辑不属于意图路由，本方案不一并删除：

- 交付层是否明确要求推送、发布、安装或 fresh clone 的受控匹配；
- Harness Home 规则的关键词选择及否定守卫；
- 文档交付物解析；
- 敏感信息检测；
- Git 命令结果和路径结构识别。

这些逻辑必须有独立调用边界和测试，不能反向修改 `task_intent` 或 `mutation_profile`。

### 6.3 Git 意图扩展

新增 `git_switch` 作为结构化意图，不依赖“切换”“checkout”等文本触发：

- 变更面：`workspace_write`；
- 允许动作：`read + git_switch`；
- 目标范围：单一 `.git:refs/heads/<branch>`；
- 预检：当前分支、HEAD、目标 OID、工作区、索引、所有 worktree 分支占用；
- 初期仅支持干净工作区和已有本地分支；
- 目标分支被其他 worktree 占用时返回现有 worktree 路径，不自动移动或删除；
- 后检生成控制器可信的 `git_switch_result`。

## 7. 宿主适配合同

受管 `AGENTS.md`、`SKILL.md` 和调用示例必须要求宿主在第一次 `run` 前完成：

1. 判断当前意图及全部混合意图；
2. 提交 `intent_assessment`；
3. `workspace_write|external_write` 必须提交 `gate_assessment`；只读任务可省略，且缺省 Gate 不能授予写权限；
4. 提交对应 `read_scope|write_scope|git_scope|external_scope`；
5. 无法确定时先向用户澄清，不调用 Harness 创建伪任务。

宿主不得调用 Harness 的旧文本分类函数替自己生成语义声明。测试适配器也不得使用被测分类器生成期望值。

任务正文不得参与 Gate 授权或变更面裁决。既有 `infer_gates(task, ...)` 如暂时保留，只能用于无授权能力的证据建议；路径绊线和项目显式规则仍可确定性地增加 Gate，但不能降低宿主已声明的风险等级。

## 8. 测试策略

### 8.1 核心不变量

1. 无 `intent_assessment` 且无兼容显式字段：所有任务文本统一返回 `missing_intent_assessment`，不持久化任务。
2. 相同结构化声明配不同任务正文：意图、变更面和路线相同。
3. 相同任务正文配不同结构化声明：按声明编译，并保留审计 rationale。
4. 任务正文中的 `review|audit|fix|release` 出现在分支名或路径中，不影响意图。
5. 显式声明不得用低变更面覆盖混合意图中的高变更面。

### 8.2 真实缺陷回放

| 输入 | 结构化声明 | 预期 |
|---|---|---|
| 切换到其他分支 | 缺失 | `missing_intent_assessment`，无 task-id |
| 切换到其他分支 | `git_switch` + 单一目标分支 | 进入 Git 预检 |
| `git switch codex/ai-ppt-review-flow` | `git_switch` | 不出现 review/audit |
| 输出产品方案到本地 | 缺失 | `missing_intent_assessment`，无 task-id |
| 输出产品方案到本地 | `modify` + 完整文档 scope | 一次准入 |
| 如何切换分支 | `query` | `answer_only` |

### 8.3 防自证测试

- 删除测试辅助器中调用生产分类器自动注入 `intent_assessment` 的逻辑；
- 夹具显式声明预期意图；
- 增加真实宿主调用固定装置，验证首次命令实际包含双声明；
- 增加“声明缺失但文本像只读”和“声明缺失但文本像写入”对称测试；
- 增加任务目录前后快照，证明缺声明不产生 Runtime 状态。

## 9. 控制器身份与跨 worktree 交付

行为代码变化必须形成新的控制器身份：

```text
controller_build_id = semantic_version + script_fingerprint + contract_schema
```

发布与下游升级分别验收：

1. 上游源码指纹；
2. npm/package 候选指纹；
3. ZBuddy main 安装指纹；
4. 每个活动 worktree 的控制器指纹；
5. 真实宿主首次调用是否提交意图声明，写任务是否同时提交 Gate 声明；
6. fresh clone 是否得到同一行为身份。

同一语义版本出现不同脚本指纹时必须报告 `controller_build_conflict`，不能以“配置中的 installed fingerprint 与本地脚本一致”视为已升级。

## 10. 实施范围

预计修改：

- `scripts/harness.py`：移除关键词正式路由、前置声明校验、增加 `git_switch` 合同；
- `tests/test_harness.py`：删除自证注入并补回放矩阵；
- `docs/contracts.md`、`README.md`、`SKILL.md`：同步单一权威来源和宿主首次调用合同；
- 受管宿主指引生成块：要求首次准入提交双声明；
- 版本与发布元数据：行为变化必须升级身份；
- `evals/`：增加两条 ZBuddy 真实误判样本和同版本多实现检查。

不在本轮自动修改 ZBuddy 业务文件、工作分支、worktree 或 Runtime 任务状态。下游升级需要独立授权和分层验收。

## 11. 实施顺序

1. 冻结本方案和真实失败样本。
2. Kimi CLI 只读审查本方案与现有实现，重点裁决是否应彻底删除生产关键词路由；审查已完成并批准移除。
3. 先补缺声明不持久化测试，再修改控制器。
4. 删除关键词意图路由和测试自证逻辑。
5. 更新宿主合同与文档。
6. 实现并验证 `git_switch` 专属合同。
7. 运行定向回归、完整回归、自检与包检查。
8. 用 ZBuddy main 和 AI PPT worktree 做只读版本/指纹审计；获得授权后再升级下游。

## 12. 验收标准

- 三条真实误判指令不再被关键词编译成正式只读任务；
- 缺声明响应不产生 task-id、任务目录或 cancel 需求；
- 完整声明的普通任务保持一次准入；
- 生产源码不存在任务文本到 `task_intent` 的关键词映射；
- 测试不调用生产分类器生成自己的意图期望；
- `git_switch` 的目标分支、worktree 占用和后检全部由控制器确定性验证；
- 同版本不同控制器指纹被明确识别；
- 行为快照通过一次完整回归，后续仅元数据变化不重复全量测试；
- 未经授权不修改或升级 ZBuddy 下游。

## 13. 决策门

若 Kimi CLI 确认以下任一项，即直接移除关键词正式路由：

1. 启发式 `query/read_only` 可以在缺声明时进入正式任务；
2. 关键词结果被测试适配器回填为“宿主权威声明”；
3. 路径或 Git 引用中的词可以改变意图；
4. 继续扩充词表无法证明完整性或安全性。

当前本地证据已命中全部四项，因此本方案的推荐决策是：**移除生产关键词意图路由，不再扩充词表。**

Kimi CLI 审查结论：`APPROVE_REMOVE_KEYWORD_ROUTING=true`。审查要求将缺声明校验前移到任务状态创建之前、删除测试自证、补齐 v1 保守迁移和 `git_switch` 合同；这些要求已纳入本方案。
