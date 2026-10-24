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
- B1 已提交 `10526ac` 并推送；Qoder hook 原型未提交。

## Qoder UserPromptSubmit hook 原型（A 路径，2026-10-23 追加）

### 改动路径

- `routing/hosts/qoder/route_hook.py`：命令 hook，读 stdin、加载注册表、校验 fake/真实画像、写 Shadow 事件、输出 `additionalContext`；`_route_task` 是真实模型调用替换点。
- `routing/hosts/qoder/fake_profile.json`、`settings.example.json`、`settings.cli.example.json`、`README.md`：fake/CLI backend fixture、Qoder hooks 配置示例与使用说明。
- `routing/hosts/qoder/route_hook.py` 增加 CLI backend：`_route_task` 支持 `fake|cli`，默认用国内原生 `qoderclicn -p -o json --tools "" --max-turns 1 --no-session-persistence`，npm `qodercn` 作 fallback；记录 tokens/Credits/cost/CLI 版本；默认不传 `--model`，使用 CLI `/model` 当前配置，只有 `DOCS_HARNESS_ROUTER_MODEL` 设置时才覆盖；子进程移除 Qoder Desktop 注入的 SDK 环境变量、国际版 token，并设置隔离的 `QODERCN_CONFIG_DIR`。
- 宿主归一化：`must_clarify=true` 时把模型额外给出的动作触发项收敛为 `clarify_required`，避免“澄清 + 动作”混合画像被核心校验器整份拒绝。
- `routing/hosts/qoder/route_cache.py`：同会话路由缓存；首条任务调用 CLI，后续消息复用缓存，新任务标记/`/route-reset`/TTL/注册表指纹变化使其失效。
- `routing/hosts/qoder/user-hook.sh`：用户级 hook 入口，先用 `QODER_PROJECT_DIR` 检查 `routing/registry.json` 或 `.docs-harness/config.json`，不匹配直接退出；匹配才调用 `route_hook.py`。
- 用户级安装：`~/.qoder-cn/settings.json` 的 `hooks.UserPromptSubmit` 已写入 `user-hook.sh` 条目，设置 `DOCS_HARNESS_ROOT`、CLI/config/empty 和 backend；修改前备份为 `settings.json.bak-20261023224819`。demo 的项目级 hook 已移除。
- `tests/test_qoder_hook.py`：20 项独立 stdin 合同测试（基础/门禁 8 + CLI 5 + 缓存 4 + 用户级 3）。
- `docs/routing.md` §10、`docs/CODEMAP.md`、`docs/testing.md`、`TODO.md`：Qoder hook/CLI/缓存审计、边界与测试记录。
- `scripts/routing_shadow_fields.py`、`scripts/routing_metrics.py`：Shadow 模型元数据新增 `credits`，指标新增 `credits_total`/`credits_per_task`。

### 验证

- `python3 -m unittest tests.test_qoder_hook -v`：20 项通过，退出码 0；验证层级：focused_test。
- `npm test`：433 项通过，SKIP 2，退出码 0；验证层级：repository_full_test。
- `python3 scripts/harness.py assets-check --strict --json`：违规 0、警告 0，退出码 0；验证层级：contract_check。
- `python3 scripts/harness.py structure check --target . --json`：warnings 0，退出码 0；验证层级：contract_check。
- `npm run pack:check`：82 个文件，包含 `routing/hosts/qoder/` 下四个文件；验证层级：package_or_install。
- 独立冒烟：sample stdin 输出 `hookEventName=UserPromptSubmit` 与代码契约；Shadow 事件含 `task_hash`/`task_chars`，不含 prompt；验证层级：focused_test。

### 自查

- 重复逻辑：hook 复用 `validate_profile`/`build_shadow_event`/`append_shadow_event`，没有复制校验或日志逻辑。
- 默认关闭：`DOCS_HARNESS_ROUTER_ENABLED` 未设为 `1` 时不读注册表、不注入、不写日志。
- 失败不阻断：无 registry、非法 profile、非法 phase、fake profile 不可读都退出 0，错误写 stderr 与本地脱敏错误日志。
- 未改 AGENTS.md、未改下游安装面；已接国内版真实模型。

### 未覆盖

- 先装了国际版 `@qoder-ai/qodercli`，登录页是国际站；已改为国内版。国际版 npm 包（93M）与旧 config（3M）已清理；国内 npm 包保留为 fallback。
- 国内原生 CLI `qoderclicn` 1.1.78 已通过 `--skip-path` 安装到 `~/.local/bin/qoderclicn`，未改 PATH，并继承 `cn-config` 的 `dfmodel` 登录；npm `qodercn` fallback 仍在 `~/.qoder-cn/docs-harness-router/cn/`。
- 真实路由使用 CLI 当前配置模型 `dfmodel`（不传 `--model`），真实 prompt 路由到 `code`。原生墙钟 3.10s（模型+运行时 1.97s，启动约 1.1s）；npm 墙钟 4.13s（模型+运行时 1.53s，启动约 2.6s）。`dfmodel` 免费、报告 0 tokens / 0 Credits，按用户决定不处理计量。
- Qoder Desktop 端到端已触发：demo 项目 `~/.qoder-cn/docs-harness-router/demo-project` 两次真实 `UserPromptSubmit` 均执行，Shadow 事件 `modules=["code"]`、`model.name="dfmodel"`，延迟 6.09s / 2.87s，无 hook 错误；主任务生成 `hello.py`。两次是不同 session，没有命中会话缓存。
- 同一 session 首条走 CLI，后续消息在 `DOCS_HARNESS_QODER_CLI` 指向不存在路径时仍命中缓存并注入“沿用上次路由”，无错误。
- 项目级 Desktop 已完成真实触发与同会话缓存复验（第三条 `route-cache` / `cache_hit=true` / 0.0s，`hello.py` 更新为 `hello docs`）。
- 用户级 hook 已安装并备份，但尚未在新 Qoder 会话复验；demo 的项目级 hook 已移除。
- 原生 CLI 仍有一次约 1.1s 启动和约 2s 模型耗时；同会话后续消息走缓存，不再付这笔开销。
- 会话缓存的命中率、误复用和 `/route-reset` 体验尚未在多任务、长会话与上下文压缩场景统计。
- 内核/模块契约拆分未做，当前不会降低 AGENTS.md token。
- 用户级 hook 安装与 Claude Code adapter 未做。
- 真实路由质量、20–50 条任务基线和阈值校准未做。
