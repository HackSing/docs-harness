---
status: active
rule_id: DH-EXTERNAL-INPUT-SECURITY
content_fingerprint: sha256:46ff9a9cf122ee40def4327ee050ac2d8b479ff44baae40e3bcf99c2f0e943be
gates: security-sensitive
keywords: 安全,鉴权,权限,密钥,隐私,security,auth,token
plan_fields: 安全边界,负向路径
evidence_types: security_acceptance
failure_mode: 外部输入、权限、秘密或负向路径未被证明安全时停止
---

# 外部输入安全规则

## 适用条件

任务触及外部输入、鉴权、授权、秘密、隐私数据、文件解析或供应链边界时生效。

## 必需的方案字段

方案必须说明信任边界、最小权限、秘密处理、数据留存和负向路径。

## 验收条件

必须提供安全验收证据，覆盖未授权、畸形输入、敏感信息泄露和失败关闭行为。

## 失败处理方式

无法证明边界、数据去向或失败关闭时，不得继续实现或降低保护。
