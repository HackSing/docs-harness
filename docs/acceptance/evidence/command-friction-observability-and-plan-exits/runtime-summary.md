# c3 本地运行验收摘要

运行时间：2026-09-15T20:23:34；目标：zbuddy-desktop 本地浅克隆（HEAD 快照 + 复制的真实 usage 日志）；引擎：docs-harness 源包 scripts/harness.py。

- 错误码探针：plan settle 缺参数返回 missing_plan_input，事件 error_code=missing_plan_input
- usage report：plan settle errors=9 error_codes={'missing_plan_input': 1} exit_codes={'2': 9, '0': 4}
- usage report：acceptance record errors=3 exit_codes={'3': 4, '2': 3, '0': 1}（退 3 为记录已存入，不计 errors）
- usage report：assets-check calls=50 last_warnings=6，同一日志按旧口径跨调用加总为 548
- plan check：符号全命中 WARN 标注前 12 条，把 docs/plans/agent-presentation-projection-separation-development-plan.md 标为部分交付后 11 条，该方案不再出现；failures 前后 0/0
- 手写方案 implemented：cross-plan-architecture-review.md 横幅由「- 状态：有效（架构审查稿，terminal-settlement 统一方案的评审输入；2026-08-12 归一化）」改为「> 状态：已实施-仅追溯（代码已是真源，2026-09-15 核对）」，changed=['docs/plans/cross-plan-architecture-review.md']，warnings=1 条
- 手写方案 deprecated：agent-grep-discoverability-plan.md 移入 archive/，横幅「> 状态：已废弃（2026-09-15 核对，无替代方案）」，改写文件 2 个，warnings=1 条
- 结算后 plan check：status=passed，failures 0 条（结算前 0 条）
