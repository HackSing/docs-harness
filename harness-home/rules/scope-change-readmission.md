---
status: active
rule_id: DH-SCOPE-CHANGE-READMISSION
content_fingerprint: sha256:2da44887c83183e0f9c4f01c61ce3b5347fb9db34a1479dd34409e16d069f968
gates: review-audit
keywords: 范围变化,范围变更,scope change,outside scope
plan_fields: 影响范围
evidence_types: review_result
failure_mode: 实际范围、目标或准备动作变化时停止并重新准入
---

# 范围变化重新判断规则

## 适用条件

任务明确讨论范围变化，或执行中发现实际改动超出已冻结范围时生效。

## 必需的方案字段

方案必须列明新增影响范围、触发的新 Gate、授权变化和需要重做的验收。

## 验收条件

必须证明新范围已经进入新任务包版本，旧上下文、方案和证据没有被错误复用。

## 失败处理方式

任何未声明范围、目标或动作变化都立即停止，并从 run 入口重新准入。
