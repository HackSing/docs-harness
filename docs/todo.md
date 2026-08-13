# Docs Harness 2.1.0 待办

本文件只记录 2.1.0 当前尚未完成的交付层。1.x 已完成事项保留在 Git 历史、CHANGELOG 和 `docs/history/`，不再作为当前 TODO。

## 发布前

- 在正式 npm 包 fresh install 环境验证安装、CLI 和自检；
- 在一个真实 pre-2.0 下游项目执行 upgrade preview，人工确认所有权清单后再决定是否 apply；
- 正式发布前复核 npm 包只包含当前 2.1.0 对外文档，历史方案、旧规则和旧状态机测试不进入包。

## 下游

- 在 ZBuddy 执行单向 upgrade preview，确认受管区块、控制器、模板、v6 配置、旧工件清理和保留清单符合预期；
- 选择一个简单任务验证零 Harness 调用；
- 选择一个架构任务验证按需知识与 full/architecture 方案；
- 选择一个真实运行态任务验证 L3/L5 验收交接；
- 用户确认后再进行提交、推送、npm 发布和下游正式安装。
