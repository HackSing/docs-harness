# 2026-10-25 路由召回 shadow 实验：缓存任务切换与澄清提示

## 结果

在保持 `phase=shadow`、不注入上下文的前提下，加了两项召回实验：

1. **plan 缓存任务切换绕过**：缓存是 `plan_decision`，新消息含执行动作（重启/启动/打包/检测/优化等）、只读问题（吗/呢/是什么/还是等）或报错信号时，不沿用缓存，重新路由。
2. **router system prompt 提示**：明确执行动作时不要轻易 `must_clarify=true`，除非目标、交付物或范围确实不清。

9 条历史漏配/过度路由 prompt 的单次真实 CLI 回放显示：07:56、11:57、14:21、14:31、14:54 得到预期画像；07:10 单独重路由会退化为 `answer_only`，所以 code 缓存遇到报错消息不绕过；09:40、14:45 仍缺会话上下文；07:50 从非法画像变成合法的 `answer_only`，不再丢弃，但仍是漏配。按回放估计，高置信度关键漏配从 7/25 降到 4/25（16%），过度路由从 4/25 降到 1/25（4%），仍未达到 B2 的 0 漏配门槛；需要下一批真实 shadow 数据复验。

## 改动路径

- `routing/hosts/qoder/route_signals.py`：新增。职责是缓存命中的确定性任务切换检查；公开接口 `cache_bypass_reason`。plan 缓存遇到执行/只读问题/报错信号返回 `plan_task_switch`；code 缓存遇到报错消息不绕过。
- `routing/hosts/qoder/route_hook.py`：`_handle_cache` 在读取缓存后调用 `cache_bypass_reason`；`_router_system_prompt` 增加“明确执行动作不要轻易判澄清”的提示；文件 572 行。
- `tests/test_routing_signals.py`：新增 8 项缓存信号测试，覆盖 plan 任务切换、只读问题、报错、设计延续不误触发、code 缓存不绕过。
- `tests/test_qoder_hook.py`：新增 plan 缓存执行绕过、code 缓存报错复用、plan 设计延续 3 项集成测试；28 项总数。
- `docs/routing.md`：记录缓存绕过规则、router 提示、shadow 实验边界和回放估计。
- `docs/testing.md`：命令改为 `tests.test_qoder_hook tests.test_routing_signals`，36 项；补召回实验说明。
- `docs/CODEMAP.md`：登记 `route_signals.py`。
- `TODO.md`：更新测试数、召回实验结果和下一步。
- `.docs-harness/inputs/2026-10-25-recall-replay.json`：本地回放输入与结果，不入库。
- 未改 `routing/registry.json`：指纹不变，没有改阈值；未启用 canary，未改宿主 `settings.json`（`DOCS_HARNESS_ROUTER_PHASE` 仍为 `shadow`）。
- 未改 `CHANGELOG.md`：路由实现尚未进入发布版本，仓库按 release 统一更新。

## 验证

- `PYTHONUTF8=1 py -3 -m unittest tests.test_qoder_hook tests.test_routing_signals -v`：36 项，OK（skipped=2），退出码 0；验证层级：focused_test。Windows 跳过 2 项 fake CLI 多行参数测试。
- `PYTHONUTF8=1 py -3 -m unittest tests.test_routing_contract tests.test_routing_shadow tests.test_routing_metrics tests.test_routing_offline -v`：59 项，OK（skipped=1），退出码 0；验证层级：focused_test。
- 单次回放：9 条历史 prompt 通过真实 `qoderclicn`/`dfmodel` 调用路由，未写 shadow 日志、未注入；9 条画像全部通过 `validate_profile`。验证层级：local_runtime。
- shadow 边界：用户级 hook 的 `DOCS_HARNESS_ROUTER_PHASE` 仍为 `shadow`；`_should_inject("shadow")` 返回 False；回放直接调用 `_route_task_cli`，没有经过 `_emit`。验证层级：local_runtime。
- `PYTHONUTF8=1 py -3 scripts/harness.py assets-check --json`：status=passed，违规 0 条、警告 1 条，退出码 0；验证层级：contract_check。警告是 `tests/test_qoder_hook.py` 689 行超过 600 行结构阈值。
- `PYTHONUTF8=1 py -3 scripts/harness.py report check --path .docs-harness/reports/2026-10-25-routing-recall-shadow-experiment.md`：退出码 0，五项字段齐全；验证层级：contract_check。

## 回放结果

原始路由取 2026-10-24 的 shadow 事件；回放是新 router prompt 下的单次真实调用，不是生产数据。

| 历史 prompt（标签） | 原始路由 | 回放画像 | 判断 |
|---|---|---|---|
| 07:10 报错截图 | code 缓存 | answer_only / clarify | 单独重路由更差；保留 code 缓存，bugfix 缺口仍在 |
| 07:56 按推荐方案做 | clarify | code_task / code_edit | 命中预期，修复 code 漏配 |
| 09:40 做 2 和 3 | clarify | clarify | 仍缺上下文，未修复 |
| 11:57 文案优化 | clarify | code_task / code_edit | 命中预期，修复 code 漏配 |
| 14:21 配置项问题 | plan 缓存 | answer_only / read_only | 修复 plan 过度路由 |
| 14:31 面板开关问题 | plan 缓存 | answer_only / read_only | 修复 plan 过度路由 |
| 14:54 重启联调 | plan 缓存 | code_task / code_verify | 修复 plan 缓存误用 |
| 07:50 版本号排查 | 画像非法丢弃 | answer_only / read_only（合法） | 不再丢弃，但仍漏 code+plan |
| 14:45 确认语 | plan 缓存 | clarify | 重路由不会更好；保留缓存，仍漏 code |

回放估计（不是实测）：

| 口径 | 实验前 | 回放估计 |
|---|---|---|
| 关键漏配 | 7/25（28%） | 4/25（16%） |
| 过度路由 | 4/24（16.7%） | 1/25（4%） |
| 完全正确 | 16/24（66.7%） | 21/25（84%） |

剩余 4 条漏配：07:10（bugfix 需要截图上下文）、09:40（“2 和 3”需要会话上下文）、14:45（确认语需要会话上下文）、07:50（模型判成 answer_only）。这些不是缓存规则能解决的，下一步要么接受非零漏配，要么给路由器增加会话/截图上下文；这需要单独决策。

## 自查

- 复用：缓存、注册表、Shadow 和指标继续使用现有 `route_cache`、`routing_contract`、`routing_shadow`、`routing_metrics`；没有复制路由逻辑。
- 新增抽象：`cache_bypass_reason` 只负责“缓存是否应让路”，不解析任务、不生成画像；router 提示只影响模型输入，不在宿主层强制改画像。
- 无新增依赖；未改注册表、阈值、指纹或 phase；未注入 `additionalContext`。
- 根因与影响面：plan 缓存跨任务复用和短跟进判澄清是两类不同根因；前者用确定性缓存策略，后者用模型提示。回放显示 code 缓存的报错绕过会更差，已撤回该分支，只保留 plan 缓存绕过。
- 结构 WARN：`tests/test_qoder_hook.py` 689 行超过 600 行阈值。它仍是一个 `QoderHookTest` 测试类，新增用例复用同一 `setUp`/fake CLI/缓存辅助；拆分会复制大量 setup 或引入基类，故保留并说明。`route_hook.py` 572 行、`route_signals.py` 87 行，均在阈值内。

## 未覆盖

- 回放是 9 条历史 prompt 的单次真实调用，不是生产数据；模型有波动，不能当作准确率。
- 下一批真实 shadow 数据尚未产生，回放估计（16%/4%）需要实测复验；B2 的 0 漏配门槛仍未达到。
- 09:40、14:45、07:10 需要会话或截图上下文，本轮没有实现；07:50 的 answer_only 是模型分类问题，可能随 prompt 变化。
- 未跑仓库全量 `npm test`（改动只在 hook 模块）；未在 macOS 复跑；未提交代码。
- 结构 WARN 仍在；`dfmodel` 仍报 0 tokens / 0 Credits；release 任务结果未回填。
