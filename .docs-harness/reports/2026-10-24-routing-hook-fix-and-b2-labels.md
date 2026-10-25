# 2026-10-24 路由 hook 通知过滤、非法画像诊断与 B2 质量标注

## 结果

完成两件事：

1. Qoder hook 现在在路由前跳过 `<task-notification>` 系统消息；画像非法时把 `phase` 与脱敏画像写入 `hook-errors.jsonl`。25 项 hook 测试、59 项路由聚焦测试通过；两条真实通知冒烟均不启动 CLI、不写日志。
2. 对 zbuddy-desktop 截至 `2026-10-25T02:02:15Z` 的 32 条事件做标注：30 条真实消息、2 条系统通知。24 条高置信度标注中，关键漏配 6 条（25%）、过度路由 4 条（16.7%），触发 `critical_miss_rate` 严重告警；另有 1 条画像非法被丢弃。B2 的 0 漏配门槛未达到，canary 暂缓。

## 改动路径

- `routing/hosts/qoder/route_hook.py`：新增 `_is_system_notification`，在加载项目、注册表和缓存前跳过以 `<task-notification>` 开头的系统消息；画像非法时把 `phase` 和 `profile_diagnostic` 结果交给错误落盘；原 576 行，拆出诊断模块后 565 行。
- `routing/hosts/qoder/route_diagnostics.py`：新增。职责是 hook 错误落盘与非法画像脱敏诊断；只保留注册表内 intents/triggers/modules、`must_clarify`、`confidence`、evidence 条数，未知标签折叠为 `<unknown>`，不写任务原文或证据文本；公开接口 `profile_diagnostic`、`report_error`。
- `tests/test_qoder_hook.py`：新增系统通知跳过、非法画像脱敏诊断、未知标签脱敏 3 项测试；25 项总数。
- `docs/routing.md`：补系统消息跳过、`hook-errors` 新字段、通知前缀依赖和缓存跨任务误用的真实例子；更新 zbuddy-desktop 事件量与 B2 标注结果。
- `docs/testing.md`：hook 测试数改为 25 项（Windows 23 通过、SKIP 2），补通知/非法画像覆盖说明。
- `docs/CODEMAP.md`：登记 `route_diagnostics.py`，更新 `route_hook.py` 职责。
- `TODO.md`：更新 hook 测试数、通知/非法画像修复、B2 标注结果和下一步。
- `.docs-harness/inputs/2026-10-24-zbuddy-desktop-needed-modules.json`：本地标注输入，不入库；报告中的表格由它和 shadow 日志生成。
- 未改 `CHANGELOG.md`：本分支的路由实现尚未进入发布版本，仓库按 release 统一更新；此前的路由提交（`5219393` 等）也未改 CHANGELOG。
- 宿主侧未改 `~/.qoder-cn/settings.json`：用户级 hook 每次按 prompt 调用本仓 `route_hook.py`，代码改动下一次 prompt 即生效，不需要重装。

## 验证

- `PYTHONUTF8=1 py -3 -m unittest tests.test_qoder_hook -v`：25 项，OK（skipped=2），退出码 0；验证层级：focused_test。跳过项仍是 Windows 下 fake CLI 无法转发多行路由提示。
- `PYTHONUTF8=1 py -3 -m unittest tests.test_routing_contract tests.test_routing_shadow tests.test_routing_metrics tests.test_routing_offline -v`：59 项，OK（skipped=1），退出码 0；验证层级：focused_test。
- 真实通知冒烟：从 zbuddy-desktop 会话记录取 `2026-10-24T08:18:37Z`（426 字）和 `2026-10-24T14:55:17Z`（418 字）两条 `<task-notification>` 正文，在临时项目里用缺失的 CLI 路径运行 `route_hook.py`；两次均返回 0，stdout/stderr 为空，没有创建 `.docs-harness/routing`；验证层级：local_runtime。
- 标注指标：对 30 条真实事件中 24 条高置信度记录调用 `summarize_shadow`，得到 `critical_miss_count=6`、`critical_miss_rate=0.25`、`over_routing_count=4`、`over_routing_rate=0.1667`、`clarify_count=7`、`cache_hit_count=12`、`latency_p50_ms=4520.5`、`latency_p95_ms=9309.9`；阈值 `critical_miss_rate_max=0.0` 触发 1 条 critical 告警；验证层级：contract_check（分析脚本基于注册表阈值）。
- 18 次真实新路由累计 122.2s，中位 5.21s，最长 24.55s；12 次真实缓存命中为 0s；验证层级：contract_check（从 shadow 事件聚合）。
- `PYTHONUTF8=1 py -3 scripts/harness.py assets-check --json`：status=passed，违规 0 条、警告 1 条，退出码 0；验证层级：contract_check。警告是 `tests/test_qoder_hook.py` 636 行超过 600 行结构阈值。
- `PYTHONUTF8=1 py -3 scripts/harness.py report check --path .docs-harness/reports/2026-10-24-routing-hook-fix-and-b2-labels.md`：退出码 0，五项字段齐全；验证层级：contract_check。

## 标注方法与结果

快照：`zbuddy-desktop/.docs-harness/routing/shadow-2026-10.jsonl` 截至 `2026-10-25T02:02:15Z` 共 32 条事件；排除 `2026-10-24T08:18:37Z` 和 `2026-10-24T14:55:17Z` 两条系统通知后是 30 条真实消息。

标注规则：

- 只读问答、无交付物的确认 → `[]`。
- 代码或配置编辑、测试、构建、本地启动 → `code`。
- 缺陷定位与修复 → `bugfix + code`。
- 方案、设计、配置表决策 → `plan`。
- 打包、安装、发布验证 → `release`。
- 无法从动作明确判断的 6 条留在 `medium_confidence`，不写 `needed_modules`，不进入官方指标，避免用未标注数据伪造比率。
- `2026-10-24T07:50:37Z` 的画像非法任务没有 shadow 事件，按 `needed_modules=["code","plan"]` 单独计为 1 条漏配，不混入 `summarize_shadow`。

| 时间 (Z) | 任务（截断；附件路径已脱敏） | 路由 | needed_modules | 判定 | 置信 |
|---|---|---|---|---|---|
| 10-24 06:48 | 请只读查看 zbuddy-desktop 的 README 或 package.json… | [] | [] | OK | 高 |
| 10-24 06:57 | 拉取代码到本地 | [] | 未标注（候选 ['code']） | 未标注 | 中 |
| 10-24 07:08 | 现在拉起zbuddy的本地联调 | ['code'] | ['code'] | OK | 高 |
| 10-24 07:10 | 报错了  附件引用： - 文件：[附件] | ['code'] | ['bugfix', 'code'] | MISS bugfix | 高 |
| 10-24 07:15 | 重启本地联调 | ['code'] | ['code'] | OK | 高 |
| 10-24 07:50 | 当前本地联调的这个版本号对应不上实际的版本号，检查原因输出方案 | 无事件 | ['code', 'plan'] | MISS | 高 |
| 10-24 07:56 | 按照推荐方案做 | [] | ['code'] | MISS code | 高 |
| 10-24 08:17 | 启动本地联调应用验证页脚显示 | ['code'] | ['code'] | OK | 高 |
| 10-24 08:20 | 鼠标是不是蓝牙模式下能看到电量，2.4g模式下看不到电量 | [] | [] | OK | 高 |
| 10-24 09:33 | 为什么本地联调把AI剪辑放出来了，给客户打送样包和签名包不会放出来把  附件引用： - … | [] | [] | OK | 高 |
| 10-24 09:38 | 只要送样包和签名包不会出现即可，本地联调是另外一个路线，这个路线是能选择放开所有的功能，… | [] | 未标注（候选 []） | 未标注 | 中 |
| 10-24 09:40 | 那把2和3做了，那旧文件还要吗 | [] | ['code'] | MISS code | 高 |
| 10-24 09:54 | 现在本地联通开了入口，也使用不了  附件引用： - 文件：[附件] | ['bugfix', 'code'] | ['bugfix', 'code'] | OK | 高 |
| 10-24 10:24 | 后端已经上了，我们可以检测一下 | ['bugfix', 'code'] | ['bugfix', 'code'] | OK | 高 |
| 10-24 11:56 | 好的，刚确认服务端没有实现，现在这个任务暂时收尾 | [] | 未标注（候选 []） | 未标注 | 中 |
| 10-24 11:57 | 不过这个提示文案并不准确，需要优化  附件引用： - 文件：[附件] | [] | ['code'] | MISS code | 高 |
| 10-24 13:35 | 现在有三个配置吧 1、送样包的配置 2、签名包的配置 3、本地联调包的配置 | [] | 未标注（候选 []） | 未标注 | 中 |
| 10-24 14:04 | 现在这里有点乱，其实送样和正式只是控制包的功能开关，签名和测试包、本地联调只是这个包的三… | [] | 未标注（候选 []） | 未标注 | 中 |
| 10-24 14:10 | AI剪辑和账号、会员、设备额度控制、大模型推理控制是一样的，都是因为没实现好，所以没到送… | [] | 未标注（候选 []） | 未标注 | 中 |
| 10-24 14:18 | AI剪辑和其他功能都是一个层级的，没必要单独价格字段来控制吧，可以放到config/re… | ['plan'] | ['plan'] | OK | 高 |
| 10-24 14:21 | videoGeneration，meetingNotes，都是已经实现的功能，不用放在配… | ['plan'] | [] | +OVER plan | 高 |
| 10-24 14:31 | pptSlidesPanel 目前是开的还是关的 | ['plan'] | [] | +OVER plan | 高 |
| 10-24 14:35 | 这个已实现的功能依然保持关闭 我是这样想的： ai剪辑、账号、会员/积分、设备额度、推理… | ['plan'] | ['plan'] | OK | 高 |
| 10-24 14:40 | 推理行为也关，目前推理关闭将来也是不做前端的，只是由后端下发给前端，是的，共用，那么现在… | ['plan'] | ['plan'] | OK | 高 |
| 10-24 14:44 | 肯定是后者啊，功能都是一个一个实现来的，第二个问题按照你的建议来，另外目前推理行为默认都… | ['plan'] | ['plan'] | OK | 高 |
| 10-24 14:45 | 好，对的 | ['plan'] | ['code'] | MISS code +OVER plan | 高 |
| 10-24 14:54 | 现在重启本地联调 | ['plan'] | ['code'] | MISS code +OVER plan | 高 |
| 10-25 00:55 | 打个zbuddy的测试包 | ['release'] | ['release'] | OK | 高 |
| 10-25 01:16 | 现在语音输入时，系统记录了哪些数据 | [] | [] | OK | 高 |
| 10-25 02:00 | 安装会影响本机环境，这个没明白啥意思 | ['release'] | ['release'] | OK | 高 |
| 10-25 02:02 | 现在我看到zbuddy和Smartclaw都启动了，是没安装运行的吗 | ['release'] | ['release'] | OK | 高 |

指标：

| 口径 | 关键漏配 | 过度路由 | 完全正确 | 说明 |
|---|---|---|---|---|
| 高置信度（24 条） | 6（25.0%） | 4（16.7%） | 16（66.7%） | 官方 `summarize_shadow` 口径，触发 critical 告警 |
| 加入 07:50 丢弃任务 | 7（28.0%，分母 25） | 4（16.0%，分母 25） | 16（64.0%） | 丢弃任务按 code+plan 计漏配，不混入事件指标 |
| 宽松：6 条中等置信度按 `[]` | 6（20.0%，分母 30） | 4（13.3%） | 22（73.3%） | 中等条目不改变结论 |
| 严格：06:57=code、11:56=docs、13:35=plan、14:10=plan | 10（33.3%，分母 30） | 4（13.3%） | 18（60.0%） | 敏感度上界 |

模块级：

| 模块 | 需要条数 | 路由命中 | 召回 | 路由总次数 | 精确 |
|---|---|---|---|---|---|
| code | 11 | 6 | 54.5% | 6 | 100% |
| bugfix | 3 | 2 | 66.7% | 2 | 100% |
| plan | 4 | 4 | 100% | 8 | 50% |
| release | 3 | 3 | 100% | 3 | 100% |
| 只读（needed=[]） | 6 条高置信 + 5 条中等 | 4 条高置信空路由全对；2 条高置信 plan 过度 | — | — | — |

主要漏配/过度路由：

- 短跟进判澄清，导致 code 漏配：`07:56 按照推荐方案做`、`09:40 那把2和3做了`、`11:57 提示文案需要优化`。三条随后都产生了代码编辑（21、21、5 处 Edit/Write）。
- 缓存跨任务复用：`07:10 报错了` 复用 07:08 的 code 路由，缺 bugfix；`14:45 好，对的` 和 `14:54 现在重启本地联调` 复用 plan 路由，但实际是 code 实现/重启。
- plan 过度路由：`14:21`、`14:31` 是只读配置问题，plan 契约不需要；`14:45`、`14:54` 是 code 任务，plan 也不对。plan 路由精确率因此只有 50%。
- 技术性丢弃：`07:50 版本号对不上，检查原因输出方案` 是真实可执行任务，`trigger_conflict` 被整份丢弃；修复后会在 `hook-errors.jsonl` 留下 phase 与脱敏画像。

## 判断

- 路由器“选中的模块”精度不错：code 6/6、release 3/3、只读 4/4 都合理；主要问题是召回和缓存任务切换。用户看到的“真实任务表现不错”主要来自 shadow 不注入，任务仍由完整 AGENTS.md 执行，不能当作路由有效的证据。
- B2 的 `critical_miss_rate_max=0.0` 是硬门槛；当前 25%（敏感度 20–33%，加丢弃任务 28%）远高于 0，`summarize_shadow` 已经报 critical。按现有方案，canary 暂缓。
- 两条路径需要用户决定：
  1. 先提召回：处理“短跟进判澄清”和“缓存跨任务复用”，再采一批新任务重标；漏配降到可接受阈值后再 canary。
  2. 接受澄清作为安全回退，修订方案的 B2 阈值：说明 shadow/canary 下澄清只意味着不注入、主 agent 仍有完整规则，把 `critical_miss_rate_max` 从 0 调到有依据的值；这需要 `plan amend` 并写清理由，不能静默改。
- 如果只想验证注入链路，可以先做受限 canary：只对非澄清、带 code/release 模块的轮次注入，其余保持 shadow；但这不满足 B2 的质量门槛，c7 仍是 pending。

## 自查

- 复用：通知跳过复用现有 `main` 入口；脱敏诊断复用 `routing_contract` 的注册表标签；错误落盘复用 `route_cache.routing_dir`；指标复用 `summarize_shadow`。没有复制路由或指标逻辑。
- 新增抽象：`_is_system_notification` 只负责识别宿主系统消息；`route_diagnostics.profile_diagnostic` 只负责把非法画像转成脱敏字段；`report_error` 只负责 stderr 与 hook-errors 落盘。三者职责单一，没有为未出现的复用场景预留层。
- 无新增第三方依赖；未把任务原文、证据文本、路径或未知标签写进 hook-errors。
- 根因与影响面：通知是宿主把 `<task-notification>` 正文当 prompt 传入；非法画像在 `_run_full_route` 校验失败后只记错误码，无法定位；两处都在 hook 边界修复。已用两条真实通知和 trigger_conflict 测试覆盖。
- 结构 WARN：`tests/test_qoder_hook.py` 636 行超过 600 行阈值。它仍是一个 `QoderHookTest` 测试类，新增用例复用同一 `setUp`/fake CLI/缓存辅助；拆分会复制约 180 行 setup 或引入基类，增加跳转，故保留并在报告说明。`route_hook.py` 的 61 行诊断逻辑已拆到 `route_diagnostics.py`，hook 回到 565 行。

## 未覆盖

- 单机 Windows、单用户、单日快照；一段 plan 讨论占 8/30 条，样本结构偏斜；`02:02:15Z` 之后的日志未纳入。
- 24 条高置信度为人工判读，不是日志真值；6 条中等置信度（20%）未进入官方指标；`completed`/`rework` 未独立标注，返工率仍不可用。
- 2 条历史系统通知仍留在 shadow 日志里，修复只影响后续事件；07:50 的历史错误记录没有脱敏画像，无法回填。
- `dfmodel` 仍报 0 tokens / 0 Credits，token/成本阈值不可校准；release 打包任务的最终结果未回填。
- 未跑仓库全量 `npm test`（改动只在 hook 模块，未触发全量条件）；未在 macOS 复跑；未提交代码。
