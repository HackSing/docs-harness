---
status: active
rule_id: DH-TESTING-RELEASE
content_fingerprint: sha256:9c3f74b749f41a8d29a4bae9c52eac1a6a52f52bfe533a1cce1c66ab9390731b
gates: testing-acceptance
keywords: 测试,验收,回归,test,verify,acceptance
plan_fields: 验收结果
evidence_types: test_result
failure_mode: 测试层级、实际命令、产物身份或失败项未闭合时停止
---

# 测试放行规则

## 适用条件

任务要求测试、回归、验收、构建放行或对完成状态作出判断时生效。

## 必需的方案字段

方案必须区分静态检查、源码测试、运行时验证、产物验证和真实产品验收。

## 验收条件

记录实际执行命令、退出码、覆盖范围和失败项；目标涉及产物或真实流程时不得只用源码测试代替。

## 失败处理方式

测试未运行、证据过期、目标层级不匹配或存在未解释失败时，不得宣称完成。
