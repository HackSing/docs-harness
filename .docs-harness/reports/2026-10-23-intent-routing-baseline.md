# 2026-10-23 意图路由基线

## 改动路径

- `evals/intent_routing/cases.json`：新增 20 条带 gold 意图、触发项与禁止模块的用例，覆盖只读、代码、bugfix、Plan、资产、发布、文档、多意图和歧义输入。
- `evals/intent_routing/score.py`：新增数据集校验、`rules-v1` 关键词基线、外部 predictions 评分与指标输出；`_score_case` 负责单用例评分，`_aggregate` 负责汇总，`format_summary` 只负责呈现。
- `evals/intent_routing/README.md`：记录标签、schema、运行方式、首轮结果与边界。
- `tests/test_intent_routing_eval.py`：11 项合同测试，覆盖数据集 schema、意图→模块映射、澄清规则、规则可复现、指标计算、缺失预测和 CLI。
- `docs/testing.md`：新增第 12 节「意图路由基线」，记录运行方法与首轮结果。
- `docs/CODEMAP.md`：登记评分器模块与公开接口。
- `TODO.md`：登记下一步模型/jev 对照事项。
- `.docs-harness/tasks/intent-routing-baseline.md`：本任务进度清单（本地，不入库）。
- `.docs-harness/evals/rules.json`、`.docs-harness/evals/rules-score.json`：规则基线预测与完整评分（本地证据，不入库）。

## 验证

- `python3 -m json.tool evals/intent_routing/cases.json`：JSON 合法，退出码 0；验证层级：focused_test。
- `python3 -m unittest tests.test_intent_routing_eval tests.test_evals`：16 项通过，退出码 0；验证层级：focused_test。
- `python3 scripts/harness.py structure check --target . --json`：status=passed，检查 30 个文件，违规 0、警告 0，退出码 0；验证层级：focused_test。
- `python3 scripts/harness.py assets-check --fast --json`：违规 0 条、警告 0 条，退出码 0；验证层级：focused_test。
- `python3 evals/intent_routing/score.py --write-predictions .docs-harness/evals/rules.json --json > .docs-harness/evals/rules-score.json`：退出码 0；20 条用例。首轮指标：意图完全匹配 45.0%，模块完全匹配 45.0%，模块召回 100.0%，模块精确 57.6%，关键漏配率 0.0%，错配率 55.0%，澄清判断正确率 100.0%，触发项召回 81.8%，触发项精确 58.1%。
- `python3 scripts/harness.py report check --target . --path .docs-harness/reports/2026-10-23-intent-routing-baseline.md`：status=passed，退出码 0；验证层级：focused_test。

## 结果说明

- `rules-v1` 的主要失败是过度命中，不是漏掉必需模块。只读问答里出现「测试/版本/慢/问题」、方案里出现「改代码」、发布里出现「文档」、路径里出现 `plan`，都会多装模块。
- 关键漏配率为 0，说明这版规则偏召回、不偏精确；55% 的错配全部来自不必要的模块。这正好量化了无关指令稀释：规则能识别「提到了什么」，但不能稳定区分「提到」与「要求做什么」。
- 20 条中 9 条 `trap` 用例的错配率为 100%，规则基线在专门设计的歧义输入上没有一条通过；`explicit` 组为 77.8%，`multi_intent` 组为 100%。这些分组数字来自同一次运行，样本很小，只用于方向判断。

## 复用与边界

- 复用了 `evals/evals.json` 的登记表约定、`tests/test_evals.py` 的机械校验思路和 `docs/testing.md` 的独立会话方法。
- 没有直接扩展 `evals/evals.json`：其 v3 schema 只允许 `cli` / `behavior`，`behavior` 要求 `scenario` + `rubric` 与 `expected` 键逐一对应；强行加入意图/模块标签会破坏现有校验。独立数据集保持现有登记表不变。
- 没有修改 `AGENTS.md`、`scripts/agent_prompt.md`、`scripts/harness.py` 或生产路由；工作区里已有的格式阶梯改动（`AGENTS.md`、`scripts/agent_prompt.md`、`evals/evals.json`、`docs/output-format-ladder.md` 等）本次未触碰。

## 自查

- 是否引入重复逻辑：没有。评分器只有一套指标汇总，测试用合成用例验证同一个 `score_cases`；规则预测器是独立对照组，没有复用或复制生产控制器。`score_cases` 超 60 行结构阈值后已拆出 `_score_case`，拆分后职责单一、结构检查无警告。
- 新增抽象职责：`score.py` 承担数据校验、规则预测、评分与 CLI；`cases.json` 是唯一 gold 数据源；`tests/test_intent_routing_eval.py` 守 schema、映射和指标；`README.md` 只负责使用说明。
- 未顺手加固：没有给评分器加生产兜底，没有改现有 `evals.json` 的用例，没有改用户正在编辑的格式阶梯文件。

## 未覆盖

- 模型 / jev 的独立会话基线尚未运行；本轮只有 `rules-v1` 对照，不能证明模型方案更好。
- 20 条用例只用于方向判断，未做统计显著性和多轮稳定性采样。
- 未覆盖执行中的重路由、模块冲突、最终任务成功率和真实宿主会话日志。
- `rules-v1` 是刻意简化的关键词基线，不代表所有规则实现的上限；它偏召回，关键漏配为 0，但过度路由明显。
- 没有发版、没有更新 CHANGELOG、没有升级下游；本次是评测基线，不改变用户可见行为。

## 追加：Jev 1.14.0 对照（2026-10-23）

- 新增 `evals/intent_routing/jev_predict.py`：直接调用 `POST https://api.typesafe.ai/v1/systemone`，不引入 SDK 或新依赖；key 仅从 `TYPESAFE_API_KEY` 读取，本地文件 `.docs-harness/inputs/jev.env` 已被 gitignore。
- 新增 `tests/test_jev_predict.py`：7 项离线契约测试，覆盖请求形状、多意图阈值、澄清、answer_only 归一、低置信度和缺 key 错误。
- 请求形状：1 个 primary Choice + 7 个意图 Noul + `clarify_required` / `direct_override` / `code_verify` 三个 Noul；模型只输出意图画像，模块和触发项由代码映射。
- v1（secondary Choice）：意图 90.0%、模块 85.0%、错配 15.0%、关键漏配 10.0%、澄清 95.0%。
- v2（7 个意图 Noul + 尖锐化 criteria + 修正 `docs-customer-guide` fixture）：意图 90.0%、模块 95.0%、错配 5.0%、关键漏配 5.0%、澄清 100.0%、触发项召回/精确 95.5%/91.3%。
- 稳定性：连续两次运行标签、指标和 token 用量完全一致（31,489 输入 / 5,428 输出，约 $0.0013）。
- 唯一关键漏配：`release-after-bugfix`，`bug_fix` Noul 0.76 < 0.8 次要意图阈值，漏掉 code+bugfix。
- 统计边界：v2 在 v1 错误上修订措辞，属于同集迭代，不是无偏泛化估计；下一步用 held-out 用例校准多意图阈值，不继续在同一组 20 条上调参。
- 验证：`python3 -m unittest tests.test_jev_predict tests.test_intent_routing_eval -v`：18 项通过，退出码 0；验证层级：focused_test。
- 验证：`python3 scripts/harness.py structure check --target . --json`：status=passed，检查 33 个文件，违规 0、警告 0，退出码 0；验证层级：focused_test。
- 验证：`python3 evals/intent_routing/jev_predict.py`：20 条请求全部成功，退出码 0；模型 `jev-1.14.0`；验证层级：local_runtime。
- 未覆盖：held-out 用例、真实宿主会话、执行中重路由、模块冲突和最终任务成功率；v2 的 5% 错配不代表生产发生率。

## 追加：50 条 held-out 验证（2026-10-23）

- 新增 `evals/intent_routing/held_out_cases.json`：50 条新用例，29 explicit / 9 trap / 6 ambiguous / 6 multi-intent；ID 与诊断集不相交，taxonomy 与主数据集一致。
- 扩展 `tests/test_intent_routing_eval.py`：held-out 数量/ID 不相交/taxonomy/forbidden 集合/难度分布与 rules CLI 契约。
- rules-v1：错配 46.0%、关键漏配 14.0%、模块完全匹配 54.0%、模块召回/精确 83.3%/62.5%、澄清 78.0%。
- Jev 1.14.0：错配 24.0%、关键漏配 14.0%、模块完全匹配 76.0%、模块召回/精确 72.9%/85.4%、澄清 88.0%；用量 78,316 输入 / 13,569 输出。
- 失败模式：6 条误澄清（primary 置信度 0.81–0.99，clarify Noul 0.70–0.78），5 条过度包含，3 条多意图漏配；另有 5 条意图标签不完全匹配但模块集正确。
- 结论：诊断集上的 5% 没有泛化；Jev 单独不足以生产。最大单点收益是 clarify 联合门，其次是主力模型中间带复核；held-out-1 已消费，下一步用 held-out-2 验证，不在本组上调阈值。
- 验证：`python3 -m unittest tests.test_intent_routing_eval tests.test_jev_predict -v`：23 项通过，退出码 0；验证层级：focused_test。
- 验证：`python3 evals/intent_routing/score.py --cases evals/intent_routing/held_out_cases.json --predictor rules --json`：50 条，退出码 0；验证层级：focused_test。
- 验证：`python3 evals/intent_routing/jev_predict.py --cases evals/intent_routing/held_out_cases.json --output .docs-harness/evals/jev-held-out-predictions.json`：50 条请求成功，退出码 0；验证层级：local_runtime。
- 未覆盖：held-out-2、真实宿主会话、执行中重路由、模块冲突和最终任务成功率。

## 追加：强力模型直路由对照（2026-10-23）

- 方法：50 条 held-out 去掉 gold、difficulty、forbidden、notes，仅保留 `id/setup/prompt`；附 taxonomy、module mapping、policy、output schema；两个独立会话各跑一次；模型只读附件、写 JSON，未读取 gold。会话 ID：`3f09b870-18c0-525b-ac56-ef5421f5ccea`、`13db605f-3b6c-502b-a3fc-0d7f2eefa0bf`。
- 结果：两次均 50/50；意图、模块、触发项完全匹配 100.0%，关键漏配 0.0%，错配 0.0%，澄清判断 100.0%。
- 对比：rules-v1 错配 46.0%、关键漏配 14.0%；Jev 1.14.0 错配 24.0%、关键漏配 14.0%。
- 边界：引导式路由、同一模型家族/作者偏差、50 条诊断集、没有成本和延迟计量；100% 不代表生产准确率。
- 验证：`python3 evals/intent_routing/score.py --cases evals/intent_routing/held_out_cases.json --predictions .docs-harness/evals/strong-held-out-predictions.json --json`：50 条，退出码 0；验证层级：focused_test。第二次预测同样 50/50。
- 未覆盖：真实宿主会话、成本/延迟、生产分布、执行中重路由、模块冲突和任务成功率。

## 追加：第二组 held-out 50 条（强力模型，2026-10-23）

- 新增 `evals/intent_routing/held_out_cases_2.json`：50 条新用例，27 explicit / 10 trap / 6 ambiguous / 7 multi-intent；ID 与诊断集和第一组不相交，测试锁定。
- 方法：去掉 gold、difficulty、forbidden、notes，仅保留 `id/setup/prompt`；两个独立会话各跑一次；模型只读附件、写 JSON，未读 gold。会话 ID：`ed3e0fdc-6fb3-5716-aa52-e7604a87674f`、`b7645e13-f828-510d-a5dc-6e7b79ac27ce`。
- 结果：两次均 50/50；意图、模块、关键漏配、错配、澄清判断 100.0%；触发项召回 98.31%、精确 100.0%。唯一未命中 `h2-code-upgrade-node` 的 `code_verify`，疑似 gold 偏严。
- 按要求本组没有跑 rules/Jev 对照。
- 边界：引导式路由、同模型家族/作者偏差、50 条诊断集、没有成本和延迟计量；第二组已消费，不再调题。
- 验证：`python3 -m unittest tests.test_intent_routing_eval tests.test_jev_predict -v`：23 项通过，退出码 0；验证层级：focused_test。
- 验证：`python3 evals/intent_routing/score.py --cases evals/intent_routing/held_out_cases_2.json --predictions .docs-harness/evals/strong-held-out-2-predictions-run1.json --json`：50 条，退出码 0；验证层级：focused_test。run2 同样 50/50。
- 未覆盖：真实宿主会话、成本/延迟、生产分布、执行中重路由、模块冲突和任务成功率。
