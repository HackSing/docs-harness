# 2026-10-22 遵循率优化方案冻结

## 改动

- 新增冻结方案 `docs/plans/harness-adherence-optimization.json` 与同名 Markdown，登记 `docs/INDEX.md`。
- 新增验收资产 `docs/acceptance/harness-adherence-optimization.json` 与同名 Markdown，`plan_ref` 指向上述方案，6 条 pending 标准。
- 方案按 B0–B5 分阶段：测量基线、检查器降噪、验收闭环诊断、输出契约、plan check 性能/计划状态、集成发布。
- 方案冻结的指标：WARN>0 运行占比 mobile <20%、desktop <30%；可行动 WARN ≤5/次；mobile acceptance settle/record 失败下降 ≥50%；收尾报告五项齐全 ≥80%；代码提交双行 ≥95%（若钩子获批）；desktop 增量 plan check <30s；usage report 增加 WARN 率/真实失败率/报告完整率；behavior evals 有基线对比。

## 验证

- `plan create --dry-run`：dry_run_valid；正式创建退出 0。
- `acceptance create --dry-run`：dry_run_valid；正式创建退出 0，6 条标准。
- `plan check`：passed，0 失败 0 警告。
- `acceptance check`：passed，0 失败 0 警告。
- `assets-check --strict`：passed，0 失败 0 警告。

## 验收层

- 资产契约层：Plan/Acceptance 创建与索引、检查器通过。
- 未执行 B0–B5 功能实现与下游升级。

## 未覆盖

- B0–B5 尚未实施；behavior evals 基线尚未运行。
- zbuddy-mobile/desktop 尚未升级到 2.31.0，指标尚未前后对比。
- B3 的 commit-msg 强制检查需要用户确认，方案中已标为门控项。
