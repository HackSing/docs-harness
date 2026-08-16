> 状态：有效（现行决策）
<!-- docs-harness:adr-document/v1 -->

# 项目级文档采用分层治理

- 关键符号：`ADR_SPEC`、`adr_assets`、`project_doc_scaffolds`
- 资产指纹：`sha256:5712accfe67eea401bdc81795781ef36fc358ec88bc9f00da8a411e24c37e9d5`

## 背景

Docs Harness 要成为项目级文档 harness，但 CHANGELOG（只追加日志）、TODO（高频流动清单）、README（项目特异门面）、ADR（定稿决策）的变更频率与不变量差异极大；统一套资产生命周期会对前三者造成指纹与修订语义的空转。

## 决策

分层治理：ADR 作为第四类受管资产（adr create/settle/check，定稿不可改，supersede 闭环，指纹防篡改）；CHANGELOG/TODO 只做缺失脚手架 + project check 存在性与格式检查；CHANGELOG 顶部版本由 release sync --strict 强制与 VERSION 一致；README 仅缺失时生成极简骨架。

## 影响

每类文档治理强度与其变更频率匹配；代价是资产生命周期与脚手架+检查两套机制并存，assets-check（受管资产）与 project check（项目文档）职责分离需文档说清。
