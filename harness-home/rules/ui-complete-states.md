---
status: active
rule_id: DH-UI-COMPLETE-STATES
content_fingerprint: sha256:bf7e6b22d9797e8f49d93cb5af669aa82a9277c8fbdd384cc4af1a031a3ec11d
gates: frontend-design
keywords: ui,界面,页面,组件,视觉,交互,frontend,swiftui
plan_fields: 设计状态,真实页面验收
evidence_types: ui_acceptance
failure_mode: 页面完整状态、真实数据或可操作性未验收时停止
---

# UI 完整状态规则

## 适用条件

任务改变页面、组件、视觉、交互、响应式布局或可访问性时生效。

## 必需的方案字段

方案必须覆盖加载、空、成功、失败、禁用、窄窗口和关键交互状态，并说明真实入口。

## 验收条件

必须从真实页面入口验收可见结果和关键操作；截图、DOM 或单测只证明各自层级。

## 失败处理方式

缺少完整状态、使用演示数据冒充真实链路或页面不可操作时，不得宣称完成。
