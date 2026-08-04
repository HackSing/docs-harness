---
status: active
rule_id: DH-DOCUMENTATION-CHANGES
content_fingerprint: sha256:601b3a6680072eb973f3b78a3bf9e261423cd97bc45edee27e05c19a0caac9d6
gates: document-edit
keywords: 文档,说明,readme,markdown
plan_fields: 文档真源,索引与残留
evidence_types: document_review
failure_mode: 文档真源、事实来源或旧引用未闭合时停止并补齐
---

# 文档修改规则

## 适用条件

新增、修改、迁移、重命名或删除项目文档及运行时入口时生效。

## 必需的方案字段

方案必须说明唯一真源、需要同步的索引，以及旧入口和死引用的清理范围。

## 验收条件

事实必须有当前证据，索引和链接有效，旧入口不再参与路由，并完成独立文档审查。

## 失败处理方式

事实无法确认、索引断链或新旧体系同时生效时，停止并补齐迁移清单。
