> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# EGM 启发两项增强：Plan 零上下文盲审提示词与 evals 行为轨迹离线校验器

- 修订：2
- 关键符号：`run_plan_review_prompt`、`build_review_prompts`、`verify_trace_case`、`adapt_trace_payload`
- 资产指纹：`sha256:f8711231af7b880115331da8b6f9cdd4f338caeb2c5252168d92e4b7938b3dcf`
- 关联方案：`docs/plans/egm-blind-review-and-trace-verifier.json`

## 验收目标

交付只读 CLI 子命令 `plan review-prompt`（scripts/plan_review.py）与离线 behavior 轨迹校验器（evals/trace_adapters.py + evals/trace_verifier.py），满足契约一致性、单测与全量回归、真实 CLI 冒烟及打包安装可运行性。

## 验收标准

### `c1` CLI 契约、打包清单（package.json/MANAGED_MODULES/CODEMAP）、py39 行长<=511B 与结构/资产检查全通过

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/egm-blind-review-and-trace-verifier/l1-structure-check.json`、`docs/acceptance/evidence/egm-blind-review-and-trace-verifier/l1-release-sync.json`

### `c2` 新增测试 tests/test_plan_review.py 与 tests/test_trace_verifier.py 及仓库全量单测套件全部通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/egm-blind-review-and-trace-verifier/l2-full-unittest.log`

### `c3` 真实 CLI 本地运行冒烟通过：plan review-prompt 对冻结 Plan 生成零上下文提示词，evals/trace_verifier.py 对样本轨迹完成离线判定并归档证据日志

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/egm-blind-review-and-trace-verifier/plan-review-smoke.json`、`docs/acceptance/evidence/egm-blind-review-and-trace-verifier/trace-verifier-smoke.json`、`docs/acceptance/evidence/egm-blind-review-and-trace-verifier/trace-verifier-strict-manual-smoke.json`

### `c4` 打包、自检与下游安装验证通过：self-test、npm run pack:check 与 test_project_install 验证安装副本可运行 plan review-prompt

- 状态：passed
- 类型：behavior_acceptance
- 层级：L4
- 证据：`docs/acceptance/evidence/egm-blind-review-and-trace-verifier/l4-self-test.json`、`docs/acceptance/evidence/egm-blind-review-and-trace-verifier/l4-pack-check.txt`、`docs/acceptance/evidence/egm-blind-review-and-trace-verifier/l2-full-unittest.log`
