# 意图路由基线

这是意图路由的评测数据集与评分器，不是生产路由实现。目标是先量出“纯代码规则判断意图”会在哪些输入上错配，再拿同一份 gold 比较小模型、强模型或混合方案。

## 标签

- **意图**：`answer_only`、`code_task`、`bug_fix`、`plan_decision`、`asset_lifecycle`、`release`、`docs_change`。
- **模块**：`code`、`bugfix`、`docs`、`plan`、`assets`、`release`。内核不参与评分。
- **触发项**：`read_only`、`code_edit`、`code_verify`、`bug_report`、`plan_required`、`asset_operation`、`release`、`docs_edit`、`direct_override`、`clarify_required`。

意图到模块的映射写在 `cases.json` 的 `intent_modules`。`must_clarify: true` 的用例不装配任何模块，先澄清交付物或范围。

## 用例

`cases.json` 目前有 20 条，覆盖只读问答、代码改动、bugfix、Plan、资产、发布、文档、多意图和歧义输入。每条包含：

- `setup`：给独立模型会话使用的项目初始状态；
- `prompt`：用户输入原文；
- `expected_intents` / `expected_triggers`：gold 标签；
- `forbidden_modules`：明确不该装配的模块，用于识别过度路由；
- `must_clarify`：是否应先澄清；
- `difficulty`：`explicit`、`trap`、`ambiguous`、`multi_intent`。

`trap` 用例专门放关键词会误判的输入，例如“发版前跑测试”里的“发版”、“先不要改代码”里的“改”、路径 `docs/plans/` 里的 `plan`。

## 运行规则基线

```bash
python3 evals/intent_routing/score.py
python3 evals/intent_routing/score.py --json
python3 evals/intent_routing/score.py --write-predictions .docs-harness/evals/rules.json
```

`score.py` 内置的 `rules-v1` 是刻意简单的关键词预测器，只用来做对照基线，不代表生产规则引擎的上限。它按关键字命中收集意图，再按 `intent_modules` 装配模块。

## 评分模型或 jev

把预测写成如下 JSON，再跑 `--predictions`：

```json
{
  "schema_version": "docs-harness/intent-routing-predictions/v1",
  "predictor": "jev",
  "model": "模型标识",
  "predictions": [
    {
      "id": "code-rename-slugify",
      "intents": ["code_task"],
      "modules": ["code"],
      "triggers": ["code_edit"],
      "must_clarify": false,
      "confidence": 0.86,
      "evidence": ["用户明确要求修改 slugify 并同步测试"]
    }
  ]
}
```

```bash
python3 evals/intent_routing/score.py --predictions <预测文件>
```

模型应只输出意图画像，不输出模块集合；模块应由宿主按 `intent_modules` 映射。这里允许预测里带 `modules`，是为了同时评估“模型直接选模块”的方案。缺失某个用例的预测会按空预测计分，并计入关键漏配。

## 指标

- `intent_exact_rate`：意图集合完全匹配的用例占比；
- `module_exact_rate`：模块集合完全匹配的用例占比；
- `module_recall` / `module_precision`：必需模块的召回与精确率；
- `critical_miss_rate`：漏掉必需模块（或没有预测）的用例占比；
- `misroute_rate`：关键漏配或命中 `forbidden_modules` 的用例占比；
- `clarify_accuracy`：该澄清时澄清、不该澄清时不澄清的用例占比；
- `trigger_recall` / `trigger_precision`：触发项覆盖情况，用于定位时序和误触发。

## 首轮基线（2026-10-23）

`rules-v1` 在 20 条用例上的结果：

| 指标 | 值 |
|---|---|
| 意图完全匹配 | 45.0% |
| 模块完全匹配 | 45.0% |
| 模块召回 | 100.0% |
| 模块精确 | 57.6% |
| 关键漏配率 | 0.0% |
| 错配率 | 55.0% |
| 澄清判断正确率 | 100.0% |
| 触发项召回 | 81.8% |
| 触发项精确 | 58.1% |

这组数字说明规则基线的主要问题不是漏掉必需模块，而是关键词过度命中：只读问答里出现“测试/版本/慢/问题”，或方案里出现“改代码”，都会多装模块。它正好对应要解决的无关指令稀释。模型或 jev 的对照尚未运行；按 `docs/testing.md` 的独立会话方法跑完后，把结果追加到该文件的运行记录。

## Jev 1.14.0 对照（2026-10-23）

`jev_predict.py` 直接调用 `POST https://api.typesafe.ai/v1/systemone`，不依赖 SDK。Key 只从 `TYPESAFE_API_KEY` 环境变量读取；本地放在 `.docs-harness/inputs/jev.env`（已被 gitignore），不要写进仓库。

请求包含：

- 1 个 `primary_intent` Choice（7 个意图 + `unclear`）；
- 7 个意图 Noul（每个意图一个 yes/no 概率，用于多意图）；
- `clarify_required`、`direct_override`、`code_verify` 三个 Noul。

模型只输出意图画像；模块和触发项由 `jev_predict.py` 按 `intent_modules` 和固定阈值映射。阈值：primary confidence 0.5、次要意图 0.8、clarify 0.7、辅助 Noul 0.7。

运行：

```bash
set -a; . .docs-harness/inputs/jev.env; set +a
python3 evals/intent_routing/jev_predict.py
python3 evals/intent_routing/score.py --predictions .docs-harness/evals/jev-predictions.json
```

| 指标 | rules-v1 | Jev v1 | Jev v2 |
|---|---|---|---|
| 意图完全匹配 | 45.0% | 90.0% | 90.0% |
| 模块完全匹配 | 45.0% | 85.0% | 95.0% |
| 模块召回 | 100.0% | 84.2% | 89.5% |
| 模块精确 | 57.6% | 88.9% | 100.0% |
| 关键漏配率 | 0.0% | 10.0% | 5.0% |
| 错配率 | 55.0% | 15.0% | 5.0% |
| 澄清判断正确率 | 100.0% | 95.0% | 100.0% |

模型 `jev-1.14.0`（请求 `jev-latest`）；v2 使用 31,489 输入 token、5,428 输出 token，按文档价格 $42/Btok 输入约 $0.0013，输出免费。连续两次运行标签、指标和 token 用量完全一致。

v2 的唯一关键漏配是 `release-after-bugfix`：primary 为 release，`bug_fix` 的 Noul 为 0.76，低于次要意图阈值 0.8，因此漏掉 code+bugfix。下一步应在未参与措辞调整的 held-out 用例上校准多意图阈值，或加一个专门的“是否同时要求修复” Noul；不要直接在同一组 20 条上继续调阈值。

v2 是在看过 v1 错误后修订问题措辞的，所以它不是无偏泛化估计；v1 是首轮零样本对照，v2 是同集迭代结果。v2 同时把 `docs-customer-guide` 的 setup 补成具名的“报表导出功能”，避免目标未命名导致 gold 本身有歧义。两者都只覆盖 20 条诊断用例，不能当作生产发生率。

## Held-out 50 条（2026-10-23）

`held_out_cases.json` 是 50 条未参与 v2 调词的新用例，分布为 29 explicit、9 trap、6 ambiguous、6 multi-intent；ID 与诊断集 20 条不相交，taxonomy 由测试锁定。

| 指标 | rules-v1 | Jev 1.14.0 |
|---|---|---|
| 意图完全匹配 | 50.0% | 68.0% |
| 模块完全匹配 | 54.0% | 76.0% |
| 模块召回 / 精确 | 83.3% / 62.5% | 72.9% / 85.4% |
| 关键漏配率 | 14.0% | 14.0% |
| 错配率 | 46.0% | 24.0% |
| 澄清判断正确率 | 78.0% | 88.0% |
| 触发项召回 / 精确 | 63.8% / 53.6% | 82.8% / 73.9% |

Jev 的失败模式：

- **6 条误澄清**：`heldout-bug-race`、`heldout-bug-timezone-test`、`heldout-bug-token-refresh`、`heldout-docs-migration-guide`、`heldout-multi-code-assets`、`heldout-multi-bugfix-docs`。primary 置信度有 0.81–0.99，但 clarify Noul 在 0.70–0.78，现有 `clarify >= 0.7` 直接清空模块，造成 6 条关键漏配。
- **5 条过度包含**：`heldout-code-add-test`、`heldout-code-upgrade-dep`、`heldout-asset-knowledge-create`、`heldout-asset-adr-create`、`heldout-release-downstream`。
- **3 条多意图漏配**：`heldout-multi-code-assets`、`heldout-multi-bugfix-docs`、`heldout-multi-plan-code`。
- **5 条意图标签不完全匹配但模块集正确**：其中 4 条是 `bug_fix` 同时标了 `code_task`，1 条是 `heldout-ambiguous-plan` 的 tentative intent 为空。

结论：诊断集上的 5% 没有泛化。Jev 单独不足以生产；最大单点收益是把“clarify 只看 Noul”改成“clarify Noul + primary/意图置信度联合门”，其次是主力模型在中间带复核。held-out-1 已经消费，不能在这 50 条上继续调阈值；下一步用 held-out-2 验证 clarify 联合门和复核器。

## 强力模型直路由对照（2026-10-23）

方法：把 50 条 held-out 用例去掉 `expected_*`、`difficulty`、`forbidden_modules`、`notes`，只保留 `id/setup/prompt`；连同 taxonomy、module mapping、policy 和 output schema 作为附件，交给宿主当前强力模型。两个独立会话各跑一次；模型只读取附件、写出 JSON，没有读取仓库里的 gold 文件。会话 ID：`3f09b870-18c0-525b-ac56-ef5421f5ccea`、`13db605f-3b6c-502b-a3fc-0d7f2eefa0bf`。

| 指标 | rules-v1 | Jev 1.14.0 | 强力模型 |
|---|---|---|---|
| 意图完全匹配 | 50.0% | 68.0% | 100.0% |
| 模块完全匹配 | 54.0% | 76.0% | 100.0% |
| 关键漏配率 | 14.0% | 14.0% | 0.0% |
| 错配率 | 46.0% | 24.0% | 0.0% |
| 澄清判断正确率 | 78.0% | 88.0% | 100.0% |

两次独立会话的 50 条标签完全一致，评分全部 100%。这组数据支持“强力模型直接负责路由”，但要注意：

- 这是**带 taxonomy 和 policy 的引导式路由**，不是无提示裸分类；生产也会给同样的契约，所以这是合理的模拟，但它降低了任务难度。
- 用例和 gold 由同一个 agent 编写，强力模型也来自同一模型家族，存在作者偏差/自偏好；两次独立会话只能证明稳定性，不能消除这种偏差。
- 会话仍在当前工作区，理论上有 AGENTS.md 影响；工具记录只显示读取附件和写出结果，未读 gold，但不能完全排除工作区提示的隐性影响。
- 50 条是诊断集，不是生产随机样本；100% 不能当作生产准确率。
- 没有计量 token 成本和单任务延迟；批量 50 条在 1–2 分钟内完成，单任务延迟需实测。
- 下一步：把强力模型做成**执行前的独立结构化路由调用**，保留宿主侧的 module mapping、依赖闭包、冲突消解和收尾覆盖率核对；用真实会话测成本、延迟和漏配，再决定是否完全移除 Jev。

## 第二组 held-out 50 条（强力模型，2026-10-23）

`held_out_cases_2.json` 是 50 条全新用例，分布为 27 explicit、10 trap、6 ambiguous、7 multi-intent；ID 与诊断集、第一组都不相交。按要求只测强力模型，没有跑 rules/Jev 对照。

两个独立会话各跑一次，标签完全一致：意图、模块、关键漏配、错配、澄清全部 100%；触发项召回 98.31%、精确 100%。唯一未命中的是 `h2-code-upgrade-node` 的 `code_verify`：提示只要求升级 Node、更新 CI 和 lockfile，没有明确要求跑测试，gold 里的 `code_verify` 可能偏严；模块集 `code` 正确，不影响路由或返工。

会话 ID：`ed3e0fdc-6fb3-5716-aa52-e7604a87674f`、`b7645e13-f828-510d-a5dc-6e7b79ac27ce`。工具记录只有读取附件和写出结果，没有读取 gold。

边界：依然是带 taxonomy/policy 的引导式路由、同模型家族/作者偏差、50 条诊断集、没有成本和延迟计量。第二组结果支持继续推进，但仍不是生产准确率。第二组已经消费，不再根据结果调题。

## 边界

- 20 条用例是首轮基线，不是统计显著样本；结论只用于方向判断。
- `rules-v1` 是人为简化的对照组，不能据此推断所有规则实现的上限。
- 数据集只覆盖工具调用前的意图路由，不覆盖执行中的重路由、模块冲突和最终任务成功率。
- 背景证据见 `docs/history/plans/intent-routing-authority-governance-plan.md`：真实生产里关键词和分支名曾把写任务编译成只读任务。
