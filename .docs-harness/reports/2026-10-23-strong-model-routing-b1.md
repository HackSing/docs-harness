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
- 用户级安装：`~/.qoder-cn/settings.json` 的 `hooks.UserPromptSubmit` 已写入 `user-hook.sh` 条目，设置 `DOCS_HARNESS_ROOT`、CLI/config/empty 和 backend；修改前备份为 `settings.json.bak-20261023224819`，去掉 `statusMessage` 时再备份为 `settings.json.bak-20261023225341`。demo 的项目级 hook 已移除。
- 项目门禁收紧：`user-hook.sh` 只检查 `routing/registry.json`；旧版 docs-harness（只有 `.docs-harness/config.json`）和未安装项目静默退出，不启动 Python/CLI、不写日志、不改上下文。
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
- 用户级 hook 已安装并备份；本仓当前会话已真实触发（见下方 B2 记录）；demo 的项目级 hook 已移除。用户级门禁只认 `routing/registry.json`，旧项目不受影响。
- 原生 CLI 仍有一次约 1.1s 启动和约 2s 模型耗时；同会话后续消息走缓存，不再付这笔开销。
- 会话缓存的命中率、误复用和 `/route-reset` 体验尚未在多任务、长会话与上下文压缩场景统计。
- 内核/模块契约拆分未做，当前不会降低 AGENTS.md token。
- Claude Code adapter 未做。
- 真实路由质量、20–50 条任务基线和阈值校准未做。

## B2 shadow 仅记录模式与首批真实事件（2026-10-23 追加）

### 改动路径

- `routing/hosts/qoder/route_hook.py`：新增 `DOCS_HARNESS_ROUTER_PHASE=shadow|canary|enforced`（默认 `shadow`）。`shadow` 只写 Shadow 事件，不输出 `additionalContext`；`canary`/`enforced` 才注入。shadow 的 `actual_modules` 记为注册表全部模块，因为当前仍加载完整常驻规则、没有切换模块；canary/enforced 记为实际注入模块。
- `tests/test_qoder_hook.py`：新增 shadow 不注入、canary 注入、shadow 缓存命中不注入的合同测试；缓存/CLI/用户级用例改为显式 `canary` 才断言注入。22 项通过。
- `docs/routing.md`、`docs/testing.md`、`routing/hosts/qoder/README.md`、`TODO.md`：阶段语义、缓存阶段行为、测试计数与下一步同步。
- `~/.qoder-cn/settings.json`：用户级 hook 的 `env` 显式加入 `DOCS_HARNESS_ROUTER_PHASE=shadow`；修改前备份为 `settings.json.bak-20261023230312`。JSON 读回 validated，phase=shadow、enabled=1、backend=cli。

### 验证

- `python3 -m unittest tests.test_qoder_hook -v`：22 项通过，退出码 0；验证层级：focused_test。
- `npm test`：435 项通过，SKIP 2，退出码 0；验证层级：repository_full_test。
- `python3 scripts/harness.py assets-check --strict --json`：违规 0、警告 0，退出码 0；验证层级：contract_check。

### 首批真实事件

本仓 `.docs-harness/routing/shadow-2026-10.jsonl` 已记录 3 条用户级 hook 真实事件：

1. `05:52:41Z`：`answer_only`/`read_only`，无模块，`dfmodel`，6164.2ms。
2. `05:57:15Z`：澄清画像，`confidence=0.62`，无模块，`dfmodel`，3564.4ms。
3. `05:59:42Z`：`code_task` + 澄清，`confidence=0.42`，无模块，`actual_modules` 为全部 6 个模块（新 shadow 语义），`dfmodel`，3214.9ms。

观察：第一条内容型问题被稳定识别为 `answer_only`；两条流程/元指令被判为澄清或低置信。后两条不注入，符合 shadow 不改变执行。元指令是否应新增意图标签，需继续采样，不能凭 2 条改 taxonomy。三条都未命中缓存，因为答案型和澄清画像不写缓存；新任务仍要付 3–6 秒 CLI 开销。

### 未覆盖

- 真实任务量仍只有 3 条，远低于 20–50 条基线；关键漏配、过度路由、返工、p95 和阈值校准没有数据。
- `needed_modules`、返工和完成状态尚无采集通道，指标会全部落在 `quality_unverified`。
- 用户级 hook 在其他 opt-in 项目、多任务/长会话/上下文压缩下的行为未统计。

## 下游 zbuddy 路由试点（2026-10-23 追加）

### 方案与改动

- `docs/plans/zbuddy-routing-pilot.json/.md`：独立 brief 方案，冻结后执行并结算为 implemented；主方案不改“不向下游安装路由器”的边界，试点作为独立计划管理。
- `docs/plans/strong-model-routing-rollout.json/.md`：两次 `plan amend` 同步 B0/B1 完成、B2 开始和下游试点；最终指纹 `sha256:fb0f338649c48a9efe180a40abee3a96145f310bf8ee08d33e5a0ccf90c8867f`（amend_count=2）。
- `zbuddy-mobile/routing/registry.json`、`routing/README.md`：opt-in 快照，注册表 `1.0.0`。
- `zbuddy-desktop/routing/registry.json`、`routing/README.md`：同一快照。
- 未改两个下游的 `AGENTS.md`、`scripts/`、`.docs-harness/config.json` 或 docs-harness 受管文件；未安装路由脚本。

### 验证

- `load_registry`：两个下游快照均通过，`version=1.0.0`、`fingerprint=sha256:c3b984d65a55111bdee379dbb666a52dea3d234fdd94b856ec179825835b912a`，与本仓一致；验证层级：contract_check。
- fake backend 门禁冒烟：在两个项目运行 `user-hook.sh`，均退出 0、stdout/stderr 为空；Shadow 事件 `phase=shadow`、`modules=["code"]`、`actual_modules` 为全部 6 个模块、`model.name=fake-router`；合成日志随后删除；验证层级：local_runtime。
- 回滚冒烟：临时把 `routing/registry.json` 改名后运行 `user-hook.sh`，两个项目均退出 0、stdout/stderr 为空、不创建 `.docs-harness/routing`；恢复后文件大小 9056 字节；验证层级：local_runtime。
- `python3 scripts/harness.py assets-check --fast --json`（zbuddy-mobile）：违规 0、警告 0，退出码 0；验证层级：contract_check。
- `python3 scripts/harness.py assets-check --fast --json`（zbuddy-desktop）：违规 0、警告 0，退出码 0；验证层级：contract_check。
- 两个下游已按用户明确确认提交并推送：zbuddy-mobile `67e9eb9`、zbuddy-desktop `1c359540`。该提交动作覆盖试点方案中“不提交下游仓库”的执行约束，方案本身保持 settled 记录；提交只含 `routing/registry.json` 与 `routing/README.md`，未改下游受管文件。

### 未覆盖

- 下游 Desktop 新会话的真实 `UserPromptSubmit` 触发、真实代码任务和 shadow 数据量均未产生。
- 两个下游依赖本机用户级 hook 与 `DOCS_HARNESS_ROOT`，不是可移植安装；换机后注册表快照不会被自动使用。
- 注册表漂移只能手工重新复制；没有下游版本检测或跨项目日志聚合。
