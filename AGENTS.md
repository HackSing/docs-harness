# AGENTS.md

<!-- docs-harness:managed-entry:start -->
## Docs Harness 2.0.0：默认直跑，能力按需

Docs Harness 当前版本：2.0.0

- 普通问答、只读检查、代码修改、构建和测试默认由 Codex 直接完成；Harness 不作为任务入口，也不创建任务控制状态。
- 用户明确说“不使用 Harness”时必须直接执行，不得暗中恢复旧流程。
- 只有缺少的项目事实会改变目标、范围、方案或验收时才运行只读 knowledge query。
- 简单任务不生成方案；复杂、跨模块、高风险或用户明确要求时才运行 plan select，按 Level 与实际修改面 Profile 生成方案。
- 验收以真实功能为中心：能运行聚焦测试、接口、页面、应用、构建或安装流程时运行最小充分流程；不能独立判断时准备最低成本环境，再交给用户做最短确认。
- 高风险动作使用 Codex 原生授权与沙箱，不建立第二套 Harness Gate 或授权协议。
- 需要项目架构或模块事实时，优先按需阅读 .qoder/repowiki/zh/content/ 和 .qoder/repowiki/knowledge/zh/；不得全量注入。
- pre-2.0 项目只通过 project upgrade 单向迁移；迁移后不保留旧运行能力。
- 不自动更新知识库、ADR、Changelog、TODO 或质量账本。ADR 由主 Codex 编写，复杂决策可选只读子智能体复审。
<!-- docs-harness:managed-entry:end -->
