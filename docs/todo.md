# TODO

> **TODO 写入原则**：新增 TODO 前，必须先在 `docs/plans/` 中建立独立的方案文档，并在 TODO 条目中使用相对链接引用该文档。TODO 只记录状态、问题说明、影响、目标、安全边界、验收摘要和下一步，不复制方案正文；同一问题已有条目时更新原条目，不新增重复入口。缺少方案文档或有效引用时，不得登记 TODO。

## Runtime 生命周期与交付回执语义治理

- 状态：已完成源码实施、ZBuddy 安装与 Runtime 治理；物理清理经用户授权提前执行完毕。
- 方案：[Runtime 生命周期与交付回执语义治理方案](plans/runtime-lifecycle-and-delivery-receipt-plan.md)
- 背景：历史任务与后台 Job 缺少完整终结入口，通用完成回执又无条件显示远端未验证，导致 Runtime 待办与交付边界失真。
- 结果：新增 `task cancel|archive|list|prune` 受控终结合同与 `delivery_layers` 回执分层；ZBuddy 21 条废弃任务与 13 条废弃 Job 全部终态化并按期物理清理，严重发现单独结论后关闭，`rollback-check` 恢复通过。
- 版本说明：按方案约定本批次不绑定新版本号；版本标记、Changelog 与发布由后续发布阶段决定。
