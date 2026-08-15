> 状态：有效（现行事实）
<!-- docs-harness:knowledge-document/v1 -->

# Docs Harness 三资产治理执行机制

- 修订：1
- 关键符号：`run_assets_check`、`acceptance_refs`、`knowledge_impact`、`prepare_settlement`
- 资产指纹：`sha256:b7f51a73056eb7fd883ea5aa7e04a074d5088ad8961e7c8931724db720ea61cc`

## 摘要

2.7.0 对已有 Plan、Knowledge、Acceptance 资产建立统一检查、反向关系和分层提交防线。

## 事实

### `assets.check.execution`

assets-check 聚合三类资产与跨资产关系；pre-commit 使用 fast，GitHub CI 使用 strict。

证据：`scripts/asset_checks.py`、`scripts/githooks/pre-commit`、`.github/workflows/assets-check.yml`

### `plan.governance.v3`

Full Plan 使用 acceptance_required 和单字段 knowledge_impact，Acceptance 反向登记由 Harness 自动维护，结算顺序为 Knowledge、Acceptance、Plan。

证据：`scripts/plan_governance.py`、`plan-templates/levels/full.json`、`docs/contracts.md`
