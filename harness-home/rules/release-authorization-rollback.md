---
status: active
rule_id: DH-RELEASE-AUTHORIZATION-ROLLBACK
content_fingerprint: sha256:a1bce9d842591546fd72ed5c4ae53f0c24cb436561b26ec48038d9b0beb9db5e
gates: release-external
keywords: 发布,上线,部署,推送,发送,publish,deploy,release,push
plan_fields: 外部目标,发布与回滚
evidence_types: external_state
failure_mode: 外部目标、新鲜授权、产物身份或回滚能力缺失时停止
---

# 发布授权和回滚规则

## 适用条件

任务准备推送、发布、部署、发送、上传或改变第三方外部状态时生效。

## 必需的方案字段

方案必须冻结外部目标、产物身份、授权范围、发布步骤、观测窗口和回滚路径。

## 验收条件

必须以目标系统的实际状态证明结果；本地构建、测试或提交不能替代外部验收。

## 失败处理方式

授权不新鲜、目标不明确、产物无法唯一识别或不可回滚时，停止在外部写入之前。
