# 收尾记录：EGM 启发两项增强（Plan 零上下文盲审提示词 + evals 行为轨迹离线校验器）

- 日期：2026-11-15
- 冻结方案：`docs/plans/egm-blind-review-and-trace-verifier.json`（状态：`implemented`）
- 验收目标：`docs/acceptance/egm-blind-review-and-trace-verifier.json`（状态：`passed`，4/4 条标准通过）
- 进度清单：`.docs-harness/tasks/egm-blind-review-and-trace-verifier.md`（B1–B5 全部勾选完成）

## 改动路径

- **新增受管核心模块与测试**：
  - `scripts/plan_review.py`
  - `tests/test_plan_review.py`
- **新增源包离线 Evals 运行器与测试**：
  - `evals/trace_adapters.py`
  - `evals/trace_verifier.py`
  - `tests/test_trace_verifier.py`
- **受管接线与分发清单**：
  - `scripts/harness.py`（仅新增 `MANAGED_MODULE_RELATIVE_FILES` 登记、`plan_review_prompt` 包装、`_add_plan_review_args`、`add_plan_parser` action 与 `--lens`/`--context-ref`、`PLAN_EPILOG`、`dispatch_command` 路由）
  - `scripts/cli_support.py`（`_ACTION_FLAGS[("plan", "review-prompt")]`）
  - `package.json`（`"scripts/plan_review.py"`）
  - `tests/harness_test_base.py`（`MANAGED_MODULES` 加入 `"plan_review.py"`）
- **文档、变更日志与治理/证据资产**：
  - `docs/CODEMAP.md`、`docs/contracts.md`、`docs/architecture.md`、`docs/testing.md`、`SKILL.md`、`README.md`、`CHANGELOG.md`（`## Unreleased`）、`TODO.md`
  - `docs/plans/egm-blind-review-and-trace-verifier.json` / `.md`、`docs/INDEX.md`
  - `docs/acceptance/egm-blind-review-and-trace-verifier.json` / `.md`
  - `docs/acceptance/evidence/egm-blind-review-and-trace-verifier/`（`l1-structure-check.json`、`l1-release-sync.json`、`l2-full-unittest.log`、`l4-self-test.json`、`l4-pack-check.txt`、`plan-review-smoke.json`、`trace-verifier-smoke.json`、`trace-verifier-strict-manual-smoke.json`、`smoke-traces/*`）

## 验证命令、退出码与验证层级

- **验证层级**：`focused_test` + `repository_full_test` + `local_runtime` + `package_or_install`（均在后台/无窗命令行完成，无前台窗口弹出）
- **L1/契约与结构/资产检查**：
  - `python scripts/harness.py structure check --target . --json` → 退出码：0（`status=passed`, `checked=51`, `failures=[]`, `warnings=[]`）
  - `python scripts/harness.py release sync --target . --strict --json` → 退出码：0（`status=consistent`, `version_truth=2.35.0`, `changelog_top_version=2.35.0`）
  - `python scripts/harness.py acceptance check --target . --json` → 退出码：0（`status=passed`, `checked=17`, `failures=[]`, `warnings=[]`）
  - `python scripts/harness.py assets-check --target . --strict --json` → 退出码：0（`Plan/Knowledge/Acceptance/ADR/ScriptHygiene/Structure 已检查，违规 0 条、警告 0 条`）
- **L2/聚焦与全量回归测试**：
  - `python -m unittest tests.test_plan_review tests.test_cli_surface -v` → 退出码：0（Ran 23 tests, `OK`, skipped=1 `test_harness_script_runs_under_minimum_python`）
  - `python -m unittest tests.test_trace_verifier tests.test_evals -v` → 退出码：0（Ran 25 tests, `OK`）
  - `python -m unittest discover -s tests -p "test_*.py" -v` → 退出码：0（Ran 516 tests in 329.024s, `OK`, skipped=12）
- **L3/本地真实 CLI 冒烟运行**：
  - `python scripts/harness.py plan review-prompt --target . --plan docs/plans/egm-blind-review-and-trace-verifier.json --lens all --context-ref scripts/cli_support.py --context-ref docs/contracts.md --json` → 退出码：0（`status=ready`, `read_only=true`, `prompts` 含 `comprehension` 与 `implementation_readiness`，`forbid_fork_from_coordinator=true`）
  - `python evals/trace_verifier.py --batch docs/acceptance/evidence/egm-blind-review-and-trace-verifier/smoke-traces --json` → 退出码：0（`passed_traces=1`, `manual_review_traces=1`, `passed_checks=6`, `failed_checks=0`, `manual_review_checks=6`）
  - `python evals/trace_verifier.py --case intent-and-premise-first --trace docs/acceptance/evidence/egm-blind-review-and-trace-verifier/smoke-traces/intent-and-premise-first.jsonl --strict --json` → 退出码：1（按 `--strict` 契约阻断未决 `manual_review`）
- **L4/自检、打包与下游安装验证**：
  - `python scripts/harness.py self-test --target . --json` → 退出码：0（`status=passed`, 11/11 checks true）
  - `npm run pack:check` → 退出码：0（`docs-harness-2.35.0.tgz` 共 112 个文件，包含 `scripts/plan_review.py`、`evals/trace_adapters.py`、`evals/trace_verifier.py`）
  - `test_installed_copy_runs_plan_review_prompt`（含于全量回归 `test_plan_review`）→ 验证 `project init` 安装副本可直接执行 `plan review-prompt`

## 质量自查与非运行态文档结论

- **是否引入重复逻辑**：没有。`scripts/plan_review.py` 直接复用 `harness.py` 的 `safe_target`、`project_input_path`、`ensure_within`、`plan_settle_paths`、`validate_frozen_plan`、`read_json` 与 `_harness_controller` 代理模式（同 `plan_amend.py`）；`evals/trace_verifier.py` 通过统一规则表 `_PATH_FORBID_RULES` / `_HARNESS_FORBID_RULES` / `_TEXT_RULES` 参数化公共判定逻辑，并拆分 `evals/trace_adapters.py` 消除格式解析与判定规则混杂。
- **新增抽象职责**：
  1. `scripts/plan_review.py`：负责方案源提取（冻结/手写/草案）、目标内无符号链接 `--context-ref` 白名单校验、以及 Goldfish 零上下文提示词装配。
  2. `evals/trace_adapters.py`：负责 `docs-harness/behavior-trace/v1` 与 `claude_jsonl` 格式识别与规范化为 `NormalizedTrace`。
  3. `evals/trace_verifier.py`：负责加载 `evals/evals.json` behavior rubric，执行确定性机械核验并对纯语义项降级输出 `manual_review`（含 `--batch` 与 `--strict` 聚合）。
- **非运行态文档核对（零基础读者视角）**：已通读本次改动的 `SKILL.md`、`docs/contracts.md`、`docs/testing.md`、`README.md`、`docs/architecture.md`、`docs/CODEMAP.md`、`CHANGELOG.md` 段落；补齐了 `trace_verifier.py` 默认读取 `evals/evals.json` 及 `--evals` / `--format auto|v1|claude_jsonl` / `--strict` 参数前提，确认未出现引用缺失符号或前置命令未交代的缺口。

## 未覆盖项

- **未覆盖（环境跳过，共 12 项 skipped）**：本机未安装 Python 3.9 解释器，导致最小 Python 3.9 运行时兼容测试（`test_harness_script_runs_under_minimum_python`）跳过（仅在 Python 3.11.15 上跑过，且通过静态 AST/行长扫描确认符合 511 字节物理行与 `from __future__ import annotations` 约束）；Windows 当前会话未开启符号链接权限，1 项安装期父目录符号链接测试（及单测内对应 symlink 断言路径）被环境跳过。
- **未覆盖（在线模型会话）**：`evals/trace_verifier.py` 本次使用构造的 `v1` 与 `claude_jsonl` 样本轨迹验证；未针对真实大模型发起在线 15 条全量多轮对话重采（真实模型在语义项上的稳定通过率需后续实际采样）。
- **未覆盖（用户验收 L5）**：`plan review-prompt` 在跨会话多轮场景中的真实大模型审校效果主观评价留待您在实际工作流中使用后确认。
