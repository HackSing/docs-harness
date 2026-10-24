# 2026-10-23 强力模型意图路由 B1：契约、Shadow 与覆盖率

## 改动路径

- `routing/registry.json`：路由单点真源，含 7 意图、6 模块、10 触发项、意图映射、模块契约、风险级别、clarify/direct_override 规则、预算阈值、版本与内容指纹。
- `scripts/routing_registry.py`：注册表加载、规范化指纹与数据合同校验。
- `scripts/routing_contract.py`：profile schema、标签/冲突/澄清/低置信校验、模块依赖闭包解析、直接执行短语识别。
- `scripts/routing_shadow_fields.py`：Shadow 事件字段白名单、结构校验、时间/哈希/任务标识规范化。
- `scripts/routing_shadow.py`：Shadow 事件构造、本地 JSONL 写入/读取、损坏/缺失日志显式失败。
- `scripts/routing_metrics.py`：关键漏配、过度路由、澄清、返工、完成率、p50/p95、token/cost、分组与阈值告警；执行前覆盖率核对。
- `tests/test_routing_contract.py`、`tests/test_routing_shadow.py`、`tests/test_routing_metrics.py`、`tests/test_routing_offline.py`、`tests/test_routing_surface.py`：61 项合同/行为测试。
- `docs/routing.md`：B0 宿主能力审计、B1 使用方式、B2 运行手册、隐私与回滚。
- `docs/architecture.md`、`docs/CODEMAP.md`、`docs/INDEX.md`、`docs/README.md`、`README.md`、`docs/testing.md`、`TODO.md`：架构、索引、测试与待办同步。
- `docs/adr/strong-model-intent-routing.json/.md`：路由决策 ADR。
- `docs/acceptance/strong-model-routing-rollout.json/.md`、`docs/acceptance/evidence/strong-model-routing-rollout/b1.json`：验收目标与 B1 证据。
- `docs/knowledge/strong-model-routing-b1.json/.md`：B1 现行事实。
- `package.json`：源码包加入 `routing/` 与五个路由脚本；未加入 `MANAGED_MODULE_RELATIVE_FILES`，未改变下游安装面。
- `docs/plans/strong-model-routing-rollout.json/.md`：冻结合同未修改；进度记录在 `.docs-harness/tasks/strong-model-routing-rollout.md`。

## 验证

- `python3 -m unittest tests.test_routing_contract tests.test_routing_shadow tests.test_routing_metrics tests.test_routing_offline tests.test_routing_surface -v`：61 项通过，退出码 0；验证层级：focused_test。
- `npm test`：412 项通过，SKIP 2，退出码 0；验证层级：repository_full_test。
- `python3 scripts/harness.py assets-check --strict --json`：违规 0、警告 0，退出码 0；验证层级：contract_check。
- `python3 scripts/harness.py plan check --target . --json`：活文档 20、违规 0、警告 0，退出码 0；验证层级：contract_check。
- `python3 scripts/harness.py acceptance check --target . --json`：checked 15、违规 0、警告 0，退出码 0；验证层级：contract_check。
- `python3 scripts/harness.py knowledge check --target . --json`：checked 4、违规 0、警告 0，退出码 0；验证层级：contract_check。
- `python3 scripts/harness.py adr check --target . --json`：checked 6、违规 0、警告 0，退出码 0；验证层级：contract_check。
- `python3 scripts/harness.py release sync --strict --target . --json`：status=consistent，版本 2.33.0，退出码 0；验证层级：contract_check。
- `npm run self-test`：status=passed，退出码 0；验证层级：contract_check。
- `npm run pack:check`：退出码 0，78 个文件，包含 `routing/registry.json`、五个路由脚本与 `docs/routing.md`；验证层级：package_or_install。
- 临时 git 仓库 `project init --apply`：退出码 3（首次 init 的预期 `needs_delivery`），安装目录没有任何 routing 文件；验证层级：local_runtime。
- 离线：20 条诊断集 + 两组各 50 条 held-out 的 gold 画像全部通过注册表校验并解析出期望模块；`registry-gold` 预测经 `score_cases` 的 case_pass、critical_miss、misroute 为 100%/0%/0%；四份本地强模型预测各 50/50；验证层级：focused_test。
- `acceptance record` 在资产仍有 pending 标准时返回退出码 3，但六条 B1 记录均已 persisted_to=asset；这是聚合状态，不是写入失败。随后 `acceptance check` 通过。

## 自查

- 重复逻辑：没有复制评分逻辑，离线测试直接复用 `evals/intent_routing/score.py` 的 `score_cases`；Shadow 字段校验只有 `routing_shadow_fields` 一份，构造、读取和指标都调用 `validate_shadow_event`；注册表映射在评测数据集中保留一份作为合同对照，生产真源只有 `routing/registry.json`。
- 新增抽象职责：`routing_registry` 管数据真源与指纹；`routing_contract` 管画像语义；`routing_shadow_fields` 管事件 schema 与脱敏；`routing_shadow` 管事件构造与本地日志；`routing_metrics` 管聚合与覆盖率。拆分原因：注册表校验与画像校验变化方向不同，事件字段校验与文件 IO 变化方向不同；拆分后 strict 结构检查 0 警告。
- WARN：最终 `assets-check --strict` 为 0 警告。中途 `routing_shadow.py` 621 行触发 strict 失败，已按职责拆出 `routing_shadow_fields.py`，未用删空行规避。
- 未顺手加固：没有修改既有 CLI、Plan 模板、下游安装清单或无关模块；`docs/plans/strong-model-routing-rollout.json` 保持冻结。
- 版本与 CHANGELOG：本批默认关闭、不改变 CLI 契约、执行行为和下游安装面，未提升版本、未写 CHANGELOG；发版时再按 release 流程处理。

## 未覆盖

- B2 Shadow、B3 Canary、B4 高风险类、B5 强制执行均未开始。
- 宿主侧独立低上下文调用、model/version、token/latency、feature flag、shadow sink 与回滚开关未确认；B0 审计表见 `docs/routing.md`。
- 20–50 条真实任务基线、真实返工数据和延迟/成本/澄清/返工阈值未取得；预算与阈值仍为 `pending_shadow`。
- 路由未安装到下游项目；下游仍使用 2.33.0 提示词规则。
- 离线强模型证据是引导式、同模型家族的 curated 集，不代表生产准确率。
- 本次未提交、未推送。
