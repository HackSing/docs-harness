# 2026-10-23 格式阶梯与收尾规则

## 改动路径

- `scripts/agent_prompt.md`：收窄阶梯第 1/2/7 行的触发条件；补「命中多行取更具体的一行」、有改动任务收尾优先于一句话、只读多结论兜底行；收尾四块补附件位置与记录路径末行；解释类请求补「图后最多 3 条、不写步骤清单」。
- `AGENTS.md`：同步受管入口区块。
- `tests/test_agent_prompt_format.py`：表驱动合同测试，覆盖 9 个阶梯分支、交叉优先级、出图独立性与收尾四块顺序。
- `evals/evals.json`：新增 `format-ladder-readonly-multi-form`、`format-ladder-changed-closing`、`format-ladder-diagram-trigger` 三条 behavior 用例。
- `scripts/report_check.py`：命令字段接受 `python3`、`python3.12` 等版本化解释器；原正则的 `python\b` 不匹配 `python3`。
- `tests/test_report_check.py`：新增版本化 Python 命令的通过用例。
- `docs/testing.md`：behavior 用例说明补「格式阶梯选型」；运行方法补首次 init 的提交、工作区边界与越界产物清理；追加运行记录。
- `TODO.md`：出图文字密度问题已通过收紧规则解决，移到已完成。

## 验证

- `python3 -m unittest tests.test_agent_prompt_format tests.test_report_check tests.test_cli_surface tests.test_evals`：32 项通过，退出码 0；验证层级：focused_test。
- `npm test`：327 项通过（skipped=2），退出码 0；验证层级：repository_full_test。
- `python3 scripts/harness.py self-test --target . --json`：status=passed，退出码 0；验证层级：focused_test。
- `python3 scripts/harness.py assets-check --target . --strict --json`：违规 0 条、警告 0 条，退出码 0；验证层级：focused_test。
- `python3 scripts/harness.py report check --target . --path .docs-harness/reports/2026-10-23-agent-output-ladder.md`：status=passed，退出码 0；验证层级：focused_test。
- Behavior 真实会话（local_runtime，宿主当前模型，最终计数每用例 1 轮）：
  - `format-ladder-changed-closing` 5/5：四块顺序、diff 紧跟结果、记录路径末行、证据进记录、下一步编号附推荐。
  - `format-ladder-readonly-multi-form` 5/5（二轮）：首问纯文字、三步编号无图、对比表格、末问两个编号选项各附推荐、无四块无记录。首轮旧问法得 4/5，不计入。
  - `format-ladder-diagram-trigger` 4/4（三轮）：结论后给图，图后仅 3 条补充，无步骤清单，覆盖 Plan/Acceptance/Knowledge 与结算顺序。前两轮均为 3/4，不计入。
  - 会话 id：changed-closing `6108e07b-11cc-5369-a74f-45a822b776cb`；readonly 首轮 `eb5f7f06-d26e-58bc-a700-77679dc6acf2`、二轮 `5972a99b-9824-5b95-ac00-9edb44802d12`；diagram 首轮 `a4551b5d-52c9-563b-a344-559a972f638a`、二轮 `248b8ef7-cd2c-52ec-a23a-c81a40ac10aa`、三轮 `3c0a9d27-61cb-5edf-ad8f-6ff827a3c1d0`。

## 根因

- 阶梯混用了「内容形态」与「任务场合」两个维度：第 2 行「任务收尾」覆盖只读检查和有改动收尾，第 1 行没有限定只读，第 7 行把任何代码改动都当成必须展示 diff，收尾节没有定义附件位置。修复按场合收窄触发条件，补优先级规则、只读兜底行和附件位置。
- `report_check` 的 `_COMMAND` 用 `python\b`，`python3` 的 `3` 是词字符，边界不成立，导致合法的 `python3 -m unittest` 被判为缺少验证命令。改为匹配版本号后缀。
- behavior 运行文档没有写明首次 `init --apply` 会返回 `needs_delivery` 并以非零码退出，也没有要求提交后再启动会话；实测会话还会在源仓 `.docs-harness/views/` 生成越界视图。文档补提交步骤、工作区边界和清理检查。
- 出图规则只说「文字只补图里放不下的」，解释类请求缺少可判定的密度上限；第一轮补「不逐节点复述」仍失败，第二轮改为「最多 3 条、不写步骤清单」后通过。

## 自查

- 是否引入重复逻辑：没有。测试直接解析 `scripts/agent_prompt.md` 的阶梯表，没有在测试里复制一份选型实现；behavior 用例只描述场景与 rubric，不复制规则文本。
- 新增抽象职责：`section()` 提取受管入口章节，`ladder_rows()` 解析阶梯表；`FormatLadderTest` 守规则合同，behavior 用例守模型实际选型。
- 未顺手加固：只修了测试暴露出的报告校验与文档缺口，没有改无关规则，没有新增回退逻辑。

## 未覆盖

- behavior 每个用例最终计数 1 轮，未做稳定性采样；模型为宿主当前会话模型，未记录型号。diagram 用例为收敛规则复跑 3 轮，前两轮失败记录保留在上文。
- `report_check` 的修复有单测和本报告端到端检查；没有在真实下游报告上再做一轮抽样。
- behavior 会话仍在源仓生成了越界视图，说明「只在该目录工作」的边界约束不能完全阻止模型越界；已清理产物并在 `docs/testing.md` 增加检查步骤，工具层没有独立工作区隔离。
- 未发版、未 bump 版本、未更新 CHANGELOG；下游项目未升级，没有 3–7 天真实调用指标。
- behavior fixture 是临时目录，验证后清理；可用 `evals/evals.json` 的场景重建。

## 追加：归档形式阶梯文档（2026-10-23）

- 新增 `docs/output-format-ladder.md`：当前阶梯的可读快照，真源仍是 `scripts/agent_prompt.md`；文档头写明用途与同步要求。
- 登记到 `docs/INDEX.md`、`docs/README.md`，并加入 `package.json` 的 `files`，避免 npm 包内的 `docs/README.md` 出现死链。
- `tests/test_agent_prompt_format.py` 新增 `test_archive_snapshot_matches_prompt_sections`：归档中的 `## 呈现形式`、`## 收尾` 两节是逐字快照，测试比对两节全文；任一提示词改动都会失败并要求同步本文件。
- 验证：`python3 -m unittest tests.test_agent_prompt_format tests.test_cli_surface tests.test_evals`：28 项通过，退出码 0；验证层级：focused_test。
- 验证：`npm test`：328 项通过（skipped=2），退出码 0；验证层级：repository_full_test。
- 验证：`python3 scripts/harness.py assets-check --target . --strict --json`：违规 0 条、警告 0 条，退出码 0；验证层级：focused_test。
- 未覆盖：归档文档不是第二份规则真源，后续修改提示词仍需同步；没有放进 `docs/history/`，因为该目录只保存已被替代的 1.x 内容。
- 并发工作树说明：验证期间另一个任务写入了 `evals/intent_routing/`、`tests/test_intent_routing_eval.py` 与 `docs/CODEMAP.md`；这些不属于本任务，未修改、未纳入。曾出现一条 `evals/intent_routing/score.py::score_cases` 的 Structure WARN，随后该项检查恢复 0/0。
