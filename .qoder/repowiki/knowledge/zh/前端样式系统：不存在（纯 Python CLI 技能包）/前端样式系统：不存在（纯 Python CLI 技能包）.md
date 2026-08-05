---
kind: frontend_style
name: 前端样式系统：不存在（纯 Python CLI 技能包）
category: frontend_style
scope:
    - '**'
---

该仓库为 Docs Harness 控制技能根包，核心实现基于 Python CLI（scripts/harness.py、tests/test_harness.py），package.json 仅作为 npm 元数据包装，不包含任何前端依赖或构建脚本。经全仓搜索未发现 .css、.scss、.less、.stylus、styled-components、Tailwind 配置或任何 UI 组件代码。因此本仓库不涉及前端样式系统，无需定义 CSS 方法论、设计令牌或响应式策略。