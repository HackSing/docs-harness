# Docs Harness 意图路由权威治理 Kimi 审查记录

## 审查对象

- 产品方案：`docs/plans/intent-routing-authority-governance-plan.md`
- 现有实现：`scripts/harness.py`、`tests/test_harness.py`、`docs/contracts.md`、`README.md`、`SKILL.md`
- 审查工具：Kimi CLI 0.34.0
- 模型：K3-256k，high
- 会话：`session_c88319d4-d599-496c-a558-13c6d359f718`

## 正式结论

```text
APPROVE_REMOVE_KEYWORD_ROUTING=true
```

Kimi 认定根因判断成立，四个决策门全部命中，应完整移除生产意图关键词路由，而不是继续补词表。

## 关键发现

1. `INTENT_PATTERNS` 的结果仍进入正式任务合同；缺声明时只有被判成写任务才会阻塞，被判成 `query / read_only` 的任务会继续成为正式任务。
2. 当前控制器会持久化这类误判任务，导致宿主只能取消后重建，形成伪任务和重复准入。
3. 测试辅助器调用生产 `classify_task_intents()` 生成宿主声明，属于被测逻辑给自己制造正确答案。
4. Git 分支名和路径中的 `review` 等词会污染意图，有限关键词词典无法证明语义完整性。

## 必须完成

### P0

- 删除 `INTENT_PATTERNS`、`mutation_intent_explicitly_requested()` 以及正文扫描和 scope 默认意图。
- 在 `create_task_state()` 之前执行缺声明校验；失败响应不得持久化。
- 删除测试辅助器对生产分类器的自证调用。

### P1

- 明确 v1 迁移不得使用 `infer_task_intents()` 猜测正文，采用显式声明或保守结构化迁移。
- 明确只读任务与写任务的 `gate_assessment` 要求，避免合同歧义。
- 补齐 `git_switch` 的枚举、变更面、动作、范围和操作合同。

### P2

- 继续收紧 `infer_gates(task, ...)` 的职责，禁止任务正文参与授权。
- 同步控制器指纹、回放样本和宿主文档。

## 建议实施顺序

1. 先增加失败测试和任务目录不变断言。
2. 将缺声明预检前移到任务状态创建之前。
3. 将分类器收缩为只解析结构化声明的 resolver。
4. 修正 v1 历史迁移。
5. 删除测试自证。
6. 补齐 `git_switch`、文档、指纹和回放矩阵。

## 验收矩阵

- 缺声明的分支切换、文档输出、纯查询均返回同一结构化错误，且不创建状态。
- 分支名含 `review` 的显式 `git_switch` 不得产生 review/audit 意图。
- 相同声明配不同正文，合同结果一致；相同正文配不同声明，以声明为准。
- 混合意图不能被低风险意图降级。
- 完整写任务只进行一次准入。
- 缺声明前后任务目录快照一致。
- v1 迁移不读取任务正文判断意图。
- 测试不调用生产 resolver 生成自己的期望声明。

## 实施后复审

- 复审会话：`session_86d77d9b-928d-404f-9e95-ce04b0e8a0d0`
- 复审结论：`IMPLEMENTATION_ACCEPTED=true`

Kimi 基于最终磁盘状态确认：生产正文关键词意图路由无残留；缺意图在复用与落盘前失败；action、scope 与单独抬高 mutation profile 均不能绕过声明；v1 迁移不读正文；`git_switch` 预检和后检方向为 fail-closed；测试辅助器不再调用生产意图 resolver 自证。

复审发现的混合 Git/工作区写意图组合不完整、`git_commit` action 变更面漏检、正文路径自动补 scope、测试 Gate 自证、`git_switch` LFS/Submodule 检查和缺范围文档同步问题，已在复审过程中收口。多个可执行 Git 操作或 Git 操作与普通写入的混合合同现在显式返回 `unsupported_mixed_git_intents`，避免静默丢动作或证据。
