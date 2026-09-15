> 状态：已实施-仅追溯（代码已是真源，2026-09-15 核对）
<!-- docs-harness:plan-document/v1 -->

# 命令摩擦治理：usage 错误码观测、plan WARN 部分交付第三态、手写方案结算路径

- 冻结合同：`sha256:4a0cea8475cb900e80f079bd3abaf51845812dea160b0d2d049e6680c64b0ecf`
- 关键符号：`PLAN_PARTIAL_DELIVERY_RECHECK_DAYS`、`partial_delivery_checked_recently`、`last_warnings`、`error_codes`

## 背景

2026-09-15 复核 zbuddy-desktop usage 日志：事件只记 result=error 不记错误码，一次完整任务里 11 次首次失败无法归因（该任务不在 CCD 会话内，原始报错已不可找回）；usage report 的 checks.warnings 跨调用加总，47 次检查累计 518 条实为 12 条 plan WARN 反复计数；当前 18 条 WARN 中 12 条为「横幅有效但关键符号全部命中」，TODO 审计记录其中多数是部分交付、按规定应保持有效，而 WARN 只给 settle/deprecated 两个出口，每次 pre-commit 原样重复；另有 21 个手写方案无伴随 JSON，plan settle 以 invalid_plan_ref 拒绝，审计只能手工构造 JSON 补登。

## 目标

让首次失败可按错误码归因、检查告警按最近一次计数；给部分交付仍有效的方案一个有时效的核对出口；让手写方案不经伪造冻结 JSON 即可结算。

## 非目标

不新增 plan register 命令，不为手写方案生成冻结 JSON 或治理合同；不升 usage 事件 schema 版本（仅新增可选键）；不记自由文本；不改 assets-check --fast 行为；不重构 harness.py 存量体量债。

## 成功标准

- HarnessError 路径的 cmd.invoke 事件带 error_code（取 payload.code 枚举），成功路径不写该键
- usage report 的 commands 每项带 errors 与 error_codes 分布；checks 每项只报 last_failures/last_warnings，不再跨调用加总
- 横幅为「有效-部分交付（YYYY-MM-DD 核对）」且核对日期在 30 天内时，plan check 不报符号全命中 WARN；过期或日期非法时照常报，WARN 文案给出三个出口
- plan settle 接受无伴随 JSON、无 Harness 文档标记的手写方案：implemented 改横幅，deprecated 改横幅并移入 archive/ 与改写链接；受管区块外的 INDEX 条目不改写并在 warnings 中提示；手写方案传 --governance-input 被拒绝
- 合同、--help、受管入口、SKILL/README 与代码同步；受影响模块测试通过

## 执行范围

- scripts/harness.py
- scripts/usage_report.py
- tests/test_usage.py
- tests/test_plan_lifecycle.py
- tests/test_cli_surface.py
- docs/contracts.md
- SKILL.md
- README.md
- docs/knowledge/usage-observability.json
- CHANGELOG.md
- TODO.md
- AGENTS.md
- CLAUDE.md

## 执行内容

三批串行（均修改 scripts/harness.py，按工作流规则第 5 条同一文件保持串行）。B1 ← 无：usage_invoke_event 增 error_code；usage_report 增 errors/error_codes、checks 改 last_failures/last_warnings；合同 §9.1/§9.4 与 test_usage 同步。B2 ← B1：command_plan_check 的 C8 增部分交付豁免与时效，WARN 文案增第三出口；合同与受管入口判定纪律同步；test_plan_lifecycle 增用例。B3 ← B2：plan_settle_paths 识别手写方案，replace_plan_status_banner 与 settle_deprecated_plan 支持无 JSON 路径，plan settle 分支与 --help 同步；合同 §3.3、SKILL、README 同步；test_plan_lifecycle 增用例。收尾：Knowledge update → Acceptance → Plan settle、CHANGELOG/TODO、assets-check。

## 模块划分与接口骨架

scripts/harness.py（修改）：usage_invoke_event 事件增可选键 error_code；新增常量 PLAN_PARTIAL_DELIVERY_BANNER、PLAN_PARTIAL_DELIVERY_RECHECK_DAYS 与 partial_delivery_checked_recently(banner: str, today: date) -> bool；plan_settle_paths(target, raw) -> tuple[Path | None, Path, bool]（手写方案 JSON 位为 None）；replace_plan_status_banner(text, status, *, managed=True)；settle_deprecated_plan 的 plan_json 参数接受 None。scripts/usage_report.py（修改）：build_report 签名不变，输出 commands[*] 增 errors/error_codes，checks[*] 由 failures/warnings 累计改为 last_failures/last_warnings。复用：plan_check_banner、plan_index_doc_tokens、update_plan_index_text、settled_plan_identity、rewrite_archived_plan_links、atomic_write_text。不新增受管模块。

## 验收方案

c1 契约同步（L1 contract_check）：合同 §3.3/§9、plan settle 与 plan check 的 --help、受管入口判定纪律、SKILL/README 与代码行为一致。c2 聚焦测试（L2 focused_test）：test_usage、test_plan_lifecycle、test_cli_surface、test_release_version_sync 通过。c3 本地运行（L3 local_runtime）：新引擎对 zbuddy-desktop 本地克隆运行——复制真实 usage 日志跑 usage report 看到 errors 与 last_warnings；标注一个部分交付方案后 plan check 对应 WARN 消失；settle 一个手写方案 implemented 与一个 deprecated，核对横幅、归档、链接与 warnings。

## 是否需要 Acceptance 资产闭环

```json
true
```

## Knowledge 影响

updated

## 约束

harness.py 行数上限测试为 4850（改前 4759），超出须在测试注释登记上调理由；受管模块不得反向 import harness；usage 只记枚举与计数；不改下游仓库，下游运行验证只在本地克隆上做。

## 风险与回滚

部分交付标注可能被用来静默 WARN，以 30 天时效与未来日期不豁免兜底；手写横幅整行改写可能丢失状态后的附注，实现保留首个「｜」之后的附注；回滚为还原上述文件，已结算的下游手写方案横幅需手工改回。

<!-- docs-harness:plan-governance:start -->
## 资产治理

- 关联验收：`docs/acceptance/command-friction-observability-and-plan-exits.json`
- 需要 Acceptance：true
- Knowledge 影响：updated
<!-- docs-harness:plan-governance:end -->
