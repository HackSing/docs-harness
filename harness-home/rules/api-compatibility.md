---
status: active
rule_id: DH-API-COMPATIBILITY
content_fingerprint: sha256:791078154f2dc45a3cb37d85b80adc9d430a092c22e2da0651f975429a9fd55f
gates: architecture-contract
keywords: api,接口,schema,协议,数据库,迁移
plan_fields: 兼容策略,迁移与回滚
evidence_types: contract_acceptance
failure_mode: 公共契约、消费者影响或回滚路径不清楚时停止并重新准入
---

# API 兼容规则

## 适用条件

修改 API、Schema、协议、持久化结构、跨模块公共契约或迁移路径时生效。

## 必需的方案字段

方案必须说明兼容策略、受影响消费者、迁移顺序和可执行回滚路径。

## 验收条件

必须提供契约验收证据，覆盖新旧消费者、失败路径和必要的迁移验证。

## 失败处理方式

发现未声明消费者、实际范围扩大或回滚不可执行时，停止实现并重新准入。
