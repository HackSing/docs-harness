# 2026-10-14 Harness Plan 区分与 full 模板字段

## 改动路径

- `plan-templates/levels/full.json`：新增 `process_flowchart`、`ux_journey`
- `AGENTS.md`、`scripts/harness.py`（`_managed_content`）、`SKILL.md`：Harness Plan vs IDE Plan；full 必填说明
- `VERSION`、`package.json`、`SKILL.md` metadata、`evals/evals.json`、全部 `plan-templates/**` version → 2.30.0
- `CHANGELOG.md` 2.30.0 条目
- `tests/test_plan_lifecycle.py`：`test_full_level_requires_flowchart_and_ux_journey_fields`

## 下游同步（本机）

- 已 upgrade + commit + push：`zbuddy-desktop`、`ai_study`、`zbuddy-mobile`（并修正 mobile `.gitignore` 允许 `config.json` 入库）
- 已 upgrade + commit，push 需 rebase：`dispatch`、`suiyi`、`opc-skills`（远端领先）
- 本机未克隆：`onceright`、`awesome-llm-made-videos`、`avatanel`、`content-system`
- 升级醒目：`project upgrade` 人类可读输出末尾「重要提示」+ payload `notices`（2.30.0 一次性）

## 验证

- `python -m unittest tests.test_plan_lifecycle.PlanLifecycleTest.test_full_level_requires_flowchart_and_ux_journey_fields` — ok
- `python -m unittest tests.test_project_upgrade.UsageEnabledNoticeTest` — ok（含 2.30.0 notice）
- `python -m unittest tests.test_plan_lifecycle.PlanLifecycleTest.test_bugfix_profile_requires_structured_verification_contract` — ok
- `python -m unittest tests.test_release_version_sync` — ok（evals 版本同步后）
- `python -m unittest tests.test_eval_cli_cases.EvalCliCasesTest.test_brief_frontend_ignores_profile_fields` — ok

## 验收层

- 模块级 plan lifecycle + release version sync；未跑全仓 unittest

## 自查

- 重复逻辑：无；字段定义仅在 full.json 一处。
- 新抽象：无代码抽象，仅模板与提示词。
