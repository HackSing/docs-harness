# Changelog

## 2.4.1 - 2026-08-14

- docs-check C5（关键符号存活性）改为剪枝遍历 + 源码白名单：新增 `docs_check_walk_files` 不进入隐藏/符号链接/剪枝目录，取代 `rglob("*")` 全量枚举与逐条目双 stat，ZBuddy 仓实测 32.3s→4.6s；新增 `DOCS_CHECK_SOURCE_SUFFIXES` 扩展名白名单与 `DOCS_CHECK_ARTIFACT_DIRS` 产物目录黑名单，构建产物里的旧符号不再算「代码仍是真源」证据；C3 死链扫描复用剪枝遍历，结果集等价。
- C6（横幅时效）实测后保持不动：单次 `git log` 子进程约 25ms，代价可忽略，不满足优化触发条件。

## 2.4.0 - 2026-08-13

- pre-commit 钩子机制回灌为默认安装能力：新增 `scripts/githooks/pre-commit` 与 `scripts/githooks/setup.sh` 模板并进入 `project init|upgrade` 安装面，与方案模板共用同一套指纹归属预检（用户修改拒绝覆盖）、预览 diff、复制与卸载（按指纹只删未改过的钩子）路径；钩子随包分发但不自动执行 `git config core.hooksPath`，init/upgrade 输出附 `githook_activation_hint`，由用户显式执行一次 `scripts/githooks/setup.sh` 激活。
- 项目配置 Schema 升级 `project-config/v7`：仅新增 `installed_githook_fingerprints` 字段；v6 并入已知旧 Schema 集合，`project upgrade` 将 v6 配置平滑重写为 v7，迁移记录保留来源版本。
- `project check` 新增 `githook_drift` 红级检查；受管 AGENTS.md/CLAUDE.md 区块的「文档可发现性规范」补充 pre-commit 强制说明。

## 2.3.0 - 2026-08-13

- docs-check 与「文档可发现性规范」上游化：新增 docs/plans 状态横幅、INDEX.md 符号索引闭环、归档死链、关键符号存活与时效的常驻检查命令 docs-check（含 --strict CI 模式）；受管 AGENTS.md 区块随安装注入同一套规范，plan create 输出附 docs_hygiene_hint 落盘指引；文档体系未建立的项目 docs-check 自动 skipped。
- CLAUDE.md 受管区块改为与 AGENTS.md 共享同一内容源（_managed_content 单点生成），不再是单行指针；两份文档由同一生成器产出，消除双文档措辞漂移。
- 修复受管区块再生成时标记前累积反斜杠的缺陷：受管块改为拼接生成，不再在 f-string 内联标记。

## 2.2.0 - 2026-08-13

- 受管 `AGENTS.md` 区块新增通用工程规范：工作流规则、编码质量规范、防御代码准入、提示词与代码流程同步、测试与验收范围（聚焦优先，按风险扩展）与收尾要求；project init/upgrade 的目标项目自动获得同一套执行纪律。
- 工作流规则改为"每条规则自带触发条件"：验收先行与根因优先在标准明确、修复局部可逆时直接执行，仅当验收有歧义、根因跨模块或修复不可逆时才请求用户确认；分批交付随首批报告批次划分，不再默认前置确认。绝对化措辞收敛为带边界的硬规则，工具 handler/状态机/workflow 改动的消费链证据保留为不可豁免项。
- 新增"防御代码准入"：修复落在状态或数据的所有者层，优先恢复不变量；新增 fallback、retry、兼容分支、catch-and-continue 或重复校验必须有接口契约或可复现证据；无证据的潜在风险只进收尾报告不进代码；禁止以"更保险""顺手加固"为理由扩大修改面。
- 受管区块措辞从 Codex 泛化为 agent（多 agent 宿主共用同一份受管 `AGENTS.md`），高风险动作表述改为"使用原生授权与沙箱"。

## 2.1.0 - 2026-08-10

- Bugfix Profile 新增结构化 `affected_modules`、`verification_scope`、`full_regression_trigger` 与 `failure_attribution`。仓库级全量测试只接受跨模块、公共契约、共享基础设施、依赖/共享夹具或发布门禁原因码；受影响模块模式不得伪造全量触发依据，四项合同进入执行投影。
- Acceptance 输入与记录升级为 v3，新增不可互相替代的 `focused_test`、`repository_full_test`、`local_runtime`、`package_or_install`、`real_device` 证据层，并固定映射到 L2–L5；真实设备行为证据与用户主观确认继续分离。
- 失败验收必须提交 `failure_attributions[]`，逐项记录 `change_related|unrelated|pre_existing|environment|flaky`、摘要、阻断性和项目内证据引用；缺失、重复、未知类别或证据不存在均拒绝记录。

## 2.0.0 - 2026-08-09

- 默认产品合同改为 Codex 直接执行：普通问答、只读检查、代码修改、构建和测试不再要求 `run`、Gate、通用 Plan、旧 Verify 或 Readmission；受管 `AGENTS.md`/`CLAUDE.md` 与 SKILL 明确尊重用户“不使用 Harness”的选择。
- 2.0.0 采用单向迁移，不兼容运行 1.x 文档系统：`run|context|progress|verify|task|background|authorization`、`--legacy-opt-in` 和知识维护 Job 入口从当前 CLI 与控制器移除。
- 新增显式只读 `knowledge query`：按具体问题、可选 scope、条数和字符预算返回短事实与引用；不自动注入、不写知识库，并明确未与运行态比对的冲突边界。
- 新增版本化 `plan-templates/` 与 `plan select|create`：支持 `none|brief|full` 和 `general|frontend_ui|backend_service|bugfix|architecture|migration_release` 双维选择；用户显式选择优先，复杂度与实际修改面采用结构化输入，不从任务关键词猜模板；冻结方案只向执行阶段返回紧凑投影。
- 架构 Profile 新增 `adr_decision`。ADR 由主 Codex 编写，复杂、高风险、跨模块或不可逆决策可选使用只读子智能体复审；已接受决策通过新 ADR supersede，不原地重写历史。
- 新增 `acceptance record`：分离 Contract Check、Behavior Acceptance 和 User Acceptance，使用 L1-L5 真实验收层；Contract Check 不能产生 `behavior_verified`，失败只返回原因和下一步，独立 CLI 只记录 `user_pending`，不能自行宣称用户已接受。
- 删除任务级 Gate 后不再新增 Harness preflight、授权文件、Host Adapter 或 usage metrics；高风险动作完全使用 Codex 原生授权与沙箱，避免重新建立第二套控制系统。
- 项目安装不再创建知识正文或自动派发知识/后台治理 Job；知识不参与控制器 clone-ready 判定。升级会预览并删除指纹归属明确的旧规则、已识别知识地图、受管版本区块和旧 Runtime，保留项目文档、质量账本以及已修改或归属不明文件，并写入纯 `project-config/v6` 迁移记录。
- 当前合同、架构、测试、TODO 和文档地图只保留 2.0.0 产品事实；1.x 方案与审查迁入 `docs/history/`，默认知识查询排除该目录，npm 包改为当前文档白名单。
- 源包和 npm 包删除 1.x 规则快照与旧状态机测试；`docs/history/` 仅留在源码仓库作历史证据，不进入安装包，也不会被默认知识查询召回。

## 1.8.2 - 2026-08-09

- 修复 repowiki 知识卡注入"过宽、重复、低相关、被静默截断却标记完整交付"的问题：`**`/`*`/空 scope 的全局卡不再参与 scope 自动匹配（fnmatch 的 `*` 可跨 `/`，旧逻辑下任意任务都会召回全部全局卡），改为进入候选池经相关性评分（name 命中权重 2、category 权重 1，CJK 长 token 4 字符滑窗部分匹配，阈值 2，top 3）后限量选中；单次任务选中总数受 `DOCS_HARNESS_REPOWIKI_SELECT_LIMIT`（默认 8）硬上限约束。`knowledge_context.selection` 记录 text/scope/relevance 三类选中、候选池规模与被过滤数量，选卡依据全程可审计。
- context 交付新增估算 token 预算：`DOCS_HARNESS_CONTEXT_TOKEN_BUDGET`（默认 6000，约 3 字符 1 token 保守估算）内按序内联全文，放不下的条目只输出 `ref + fingerprint` 进 `omitted_refs`，并提示宿主按需 Read 原文；单个条目超出整个预算时截断正文并打 `content_truncated` 标记，杜绝空交付。省略项不计入已交付指纹，后续 stage 会在各自预算内自动重试，可分阶段交付完毕。
- 交付标记诚实化：context 响应新增 `delivery`（预算/估算用量/交付数/省略数/是否截断），收据新增 `omitted_refs`、`estimated_tokens`、`budget_tokens`、`truncated` 字段；存在省略或截断时，本次响应内 `knowledge_context.coverage` 降为 `partial`、`context_quality` 降为 `degraded`，不再无条件宣称完整交付。
- 新增 `test_v182_*` 合同测试：全局卡跳过 scope 自动匹配、CJK 相关性选中、候选池 top-K 限量、选中上限生效、预算省略与单项截断、预算内交付保持 complete、收据缓存命中路径不变。

## 1.7.7 - 2026-08-08

- 修复宿主连续把 `workspace_write`、`answer`、`answer_only` 等跨层概念误填为任务意图后只能盲试的问题：受管入口现在从控制器意图映射生成完整分组，明确区分 `task_intent`、`mutation_profile` 与准入状态；`invalid_task_intent` 保持失败关闭、不接受别名、不自动猜测，同时返回识别层级、合法意图、候选项和 `admission_persisted=false`。新增真实模拟回归，证明错误准入零状态残留，改用 `review_light` 后只创建一个 `read_only + answer_only` 任务。

- 新增 `answer_only` 只读快路由：纯 `query`、`review_light` 与普通 `git_inspect` 无显式 Gate/证据/验证命令时不生成 evidence checklist、不要求 read_set、不运行 verify，响应直接返回 `next_action=respond`；纯对话和无需项目事实的元问题由受管宿主入口直接回答，不创建 Harness 任务。`审查/评审/review` 归入轻量评审，`审计/audit` 归入 `audit_formal`，兼容显式旧 `audit`。
- 收敛意图与规则误升级：只读讨论中提到“修改、升级、git fetch/pull、发布”等动作不再升级变更面，只有明确祈使或“并/然后/随后”等执行连接词才保留动作意图；仅声明 `read_scope` 时缺省保持 query。Harness Home 关键词仅对工作区/外部写入选规则，只读与 Git 元数据任务必须靠显式 Gate，不再因讨论安全、API、测试、UI 或发布被追加证据。
- `git_commit` 补齐专属控制器后检：准入冻结 HEAD、分支引用、工作区内容和候选变化路径；verify 验证 HEAD 单步前进、仅当前分支 ref 变化、提交路径来自准入前变化、索引与 HEAD 一致且工作区内容未被提交动作改写，并由 `git_commit_result` 受控收据闭环，不再要求任意宿主补证。
- `.qoder/repowiki` 外部知识源补齐显式阅读指令：只要目标目录存在，任务包、首次/二次准入、context 与 task status 响应均通过 `context_instructions` 提示宿主在了解项目架构和模块知识时优先阅读 `.qoder/repowiki/zh/content/` Wiki 与 `.qoder/repowiki/knowledge/zh/` 知识卡；project init/upgrade 同步把条件式指令写入受管 `AGENTS.md`。既有只消费、按任务选卡和不写 repowiki 的边界不变。
- 写任务准入改为双声明失败关闭：宿主必须提交 `intent_assessment` 与 `gate_assessment`，显式意图不再被文本关键词升级；初始路径只判断文档/代码/测试结构 Gate，安全、发布等项目语义边界改由 `gate_path_rules` 显式映射。
- 证据信任与 JSON 内的 producer 名称解耦：宿主 `evidence-declaration/v1` 与外部 v2 收据统一为 `reported`，不得冒充 controller producer；高风险证据和并发归因只接受受控内部入口。`evidence_checklist` 新增 `trust_requirements`，高风险项不再生成可自填骨架。
- 自动 `workspace_attribution` 只证明写入归属，不再单独完成写任务；没有其他语义验收要求时，完成清单至少要求 `change_review`。fast track 最小集改为 `code_diff + change_review`。
- 取消 verify 内 write_scope 自动扩围和旧证据重绑；任何新路径都返回 exit 4 重新准入，`readmission_hint` 同时携带范围并集、意图声明和 Gate 声明。失败响应新增有序 `recovery_actions`，验证命令失败明确返回 `retry_verification`。
- `task changes-preview` 改为纯工作区分区预览：返回 `changed_in_write_scope|changed_outside_write_scope|changed_in_read_scope` 与 `attribution_status=unknown_until_evidence`，不再宣称与 verify 归因同源。

## 1.7.6 - 2026-08-08

- 新增按实际变更面选择验证强度的测试策略：同一行为快照最多一次完整回归，行为代码、依赖和公共夹具未变时复用已有全量证据；版本、说明和元数据变更只做轻量发布检查；下游同步只验 preview/apply/diff/check 与受管文件摘要。策略写入 `docs/testing.md` 真源、`SKILL.md` 操作规则和下游 `AGENTS.md` 受管模板，长测试默认安静输出，避免重复回归和无效上下文消耗。
- 新增 `git_commit` 受控意图（本地提交层）：触发词「git commit」「commit」「本地提交」「提交改动」「提交代码」「提交当前」「提交工作区」「提交暂存」（裸「提交」刻意不收，避免「提交证据/提交方案」误判），变更面 `git_metadata_write`（写 `.git` 对象/索引/分支引用，不改工作区、不触远端），默认动作 `read` + `git_commit`，不附带 `git_fetch` 授权；未来子句（「后续再提交」）进 `deferred_intents`，完成体（「已经提交」）只作上下文。修复「先提交当前的用户改动」被回退为 `query` 只读合同、宿主无法据合同执行本地提交的准入误判。
- 移除任务文本关键词 Gate 路由：`infer_gates` 只校验和规范化显式 Gate；提交 `gate_assessment` 时信任宿主模型的语义判断，未提交时只合并既有 `facts.gates` 与 scope 路径推断。删除安全底线词表、floor 推断函数、`gate_decision.floor_added` 和 `GATE_DEFS.terms` 死配置，避免「权限是被谁阻断的」等纯查询被裸词误判为高风险任务；任务中途的实际变更路径绊线继续生效。
- 非 Gate 文本判断保持独立：`load_active_rules` 的规则关键词与交付层需求判定继续使用否定守卫，「不推送」「无需部署」「不要发布」不会误匹配发布规则或派生 `remote_delivery_not_verified`；这两条链路不再参与 Gate 分类。
- 新增或改写 `test_v175_*` 与 `gate_assessment` 合同测试，并把需要指定 Gate 的历史用例统一改为通过 `--facts` 提交正式 `gate_assessment`，不新增第二套 `run --gate` CLI；全量 453 项合同测试通过。

## 1.7.4 - 2026-08-08

- `validate_scope` 增加多路径拼接检测：条目含 `;` `,` `|` `\t` 或连续空格时拒绝并返回 `invalid_scope_concatenated`（附 `suggested_fix`），防止用分隔符拼接的多路径字符串静默进入 `allowed_scope` 导致准入死循环。覆盖 `--scope` CLI 和方案 `执行范围` 两条注入路径。
- `plan_scope_mismatch` 报错 payload 新增 `scope_diff`（`only_in_task` / `only_in_plan` 两个有序列表），将范围不一致的诊断成本从手动比对降为直接读 diff。
- 新增 `test_v173_scope_rejects_semicolon_concatenated` 和 `test_v173_scope_rejects_comma_concatenated` 两个合同测试。

## 1.7.3 - 2026-08-07

- 验收循环五原因码全治理（ZBuddy 08-06/08-07 质量账本驱动：verify 平均 2.0 轮、一次通过率仅约 28%，非完成原因 `missing_evidence_types` 18、`write_scope_violation` 17、`stale_evidence` 5、`missing_receipts` 4、`concurrent_drift_overlap` 4）：
- write_scope 严格超集增量扩展：合同稳定、唯一阻断为 `write_scope_violation`、无新 Gate、`direct|planned` 路线、无授权要求、非 `git_sync` 时，verify 在同一次调用内以 `write_scope = 原范围 ∪ 越界路径` 重编译任务包（除 scope 外 `STABLE_FIELDS_MINUS_SCOPE` 稳定字段逐字段一致、blockers 为空、`matched_gates` 不新增、planned 额外要求 `plan_fields` 不变，候选 scope 覆盖并集硬断言兜底），`package_revision + 1` 保留 `created_at` 写 `recompiled_at`，既有索引收据与本轮证据按新指纹重绑（`adoption_reason="scope_superset_extension"` 全审计字段，按 source_fingerprint 替换不双写），写 `scope_extension_readmission` 事件后继续同轮证据评估，响应携带 `scope_extended`/`extended_paths`。单任务上限 3 次（事件扫描计数跨包持久），超限 exit 4 `scope_extension_limit_exceeded`；任一前置不满足失败关闭回退全量重准入（授权任务扩围必改授权合同指纹，一律走重准入，无授权绕过）。
- 证据清单前置：准入三处响应（首次 run、二次 run ready、`task status`）携带 `evidence_checklist` 四段（`required`/`conditional`/`required_receipts` 含 `write_set` 条件性标注/`skeletons`，三处均受 `completion_manifest_valid` 守卫）；证据骨架准入时经 `ensure_evidence_skeletons` 统一预生成（含 `_instructions` 填写说明），verify 缺证路径与准入共用同一批骨架。同三处响应携带 `pending_context_receipts` 待加载上下文阶段与工作包（`work_package:<id>`）状态位，消灭 `action_context_missing`。失败即前置：`action_context_missing` 与缺证（exit 3）失败载荷自身携带 `pending_context_receipts` 与完整 `evidence_checklist`（骨架与清单同批），宿主未照准入指引执行时照失败载荷补齐即过，不依赖指令遵守。
- 越界重准入提示：verify 因 `write_scope_violation` 走全量重准入时响应携带 `readmission_hint`（`facts_template` 只含 `write_scope` 并集 + 可执行 `example_argv`），宿主一次重准入即过。
- `task changes-preview`：新增恒只读 action（无 `--apply`），以冻结基线对当前工作区纯函数 diff，返回 `changed_paths`/`in_scope`/`outside_scope`/`read_set_drift`，与 verify 时刻归因同源，执行前后任务 state 目录逐字节一致；`stale_evidence` 硬错误载荷新增 `stale_write_paths` 与 `actual_changed_paths` 双清单，把基线漂移压到零试探。
- `concurrent_drift_overlap` 双选项 `readmission_hint`：收窄 scope 剔除重叠路径（同时给出剔除后的 `write_scope` 与受影响时的 `read_scope`；重叠来自证据 read_set 时只能选后项），或等并发落定后不带 scope 变更全量重准入；该码只保证失败后一次重准入即过，不承诺首轮必过（唯一无确定性承诺的码，如实声明）。
- 外部审查（kimi CLI，报告 `docs/history/reviews/v1.7.3-verify-loop-fix-kimi-code-review.md`）发现修复：扩围前对同轮 supplied 证据先执行与常规 verify 同一标准的 `write_set ⊆ 实际变化路径` 硬校验（虚报失败关闭抛 `stale_evidence`、不扩围），扩展函数对 supplied 来源收据补齐受管 artifact 审计字段；`pending_context_receipts` 覆盖工作包（`work_package:<id>`）；concurrent 选项 1 补 `read_scope` 剔除；行尾宽容指纹修复 1MiB chunk 边界 CRLF 归一化；`task changes-preview` 对 legacy v1 任务与缺 `workspace_snapshot` 基线结构化失败关闭；`first_run_payload` 补 `completion_manifest_valid` 守卫，三处清单置位防护一致。
- 验收层环境宽容修复：验证命令缺失（`FileNotFoundError`）不再崩溃，失败关闭为 failed 收据 + `verification_command_unavailable` 原因码；`core.autocrlf` 等行尾转换不再触发安装副本 script_drift 红线（行尾宽容指纹）；`release sync --apply` 目标非普通文件时以 `release_write_failed` 整体拒绝，无部分写入。
- 全量测试 455 项无豁免全绿（含 V4 修复的 `test_cross_platform_task_detection`、`test_authorization_template_command` 等历史失败）；新增 30 个 `test_v173_*` 合同测试（T1–T23 + V1 回放复现 + V2 失败关闭矩阵，T19–T23 为外部审查发现修复的回归守护）；V3 影子验收脚本 `docs/history/plans/v1.7.3-v3-shadow-acceptance.py` 安装副本全链路 25 项断言通过；最小宿主流程验证脚本 `docs/history/plans/v1.7.3-minimal-host-flow-verify.py` 15 项断言通过（实证：前置清单 + declaration 实时铸证一次过 verify，声明绑定 verify 时代铸、铸后再改同路径不致 stale，write_set 虚报被 stale_evidence 精确拦下，扩展轮同一标准）。预期效果：平均 verify 轮次 2.0 → ~1.2，一次通过率 28% → ~70%，实际以 ZBuddy 升级后账本复核。

## 1.7.2 - 2026-08-07

- 后台治理合并快路径（声明制，不跳过任何既有校验闸门）：`background dispatch --job-status running --prepare-and-run` 单命令内顺序执行 prepare → contract_ready→dispatched 校验 → dispatched→running 校验（工件校验、绑定、attempt、工作包全集、指纹、路由合同复验原样保留），任一闸门失败停在该步并返回与分步执行相同的出口（prepare 闸门相同错误码；dispatch 闸门相同 `next_action`/`reason_code`，附加 `prepare_and_run` 与 `completed_steps`）；已 prepared 且指纹一致时复用 `already_prepared` 幂等语义跳过 prepare。资格限制：仅 `execution_route == "background_goal"` 且估算为 `change_scoped`、`raw_score < 60` 的 Job 可用，phased/oversized/direct/非 change_scoped/分数 ≥60 统一以 exit 3 `background_prepare_and_run_not_eligible` + 精确 `eligibility_reason_code`（`route_phased_oversized`/`route_not_complex_goal`/`workload_estimate_unavailable`/`estimate_not_change_scoped`/`score_not_below_60`）拒绝并记录 `transition_rejected` 事件。
- `background progress --all completed`：一次把冻结 Plan 全部工作包从合法前置态推进到 completed（`pending → in_progress → completed` 逐包连续推进、事件逐包记录，复用逐包状态机校验）；任一工作包处于非法前置态（如 blocked）即整体拒绝、不部分提交（exit 3 `background_progress_all_blocked` + 阻断清单 + `partial_commit: false`）。`--all` 与单包参数混用失败关闭。
- 实现上把 dispatch 执行体抽取为 `dispatch_background_job_status`，分步路径与合并路径共享同一份闸门代码；控制面不变量不变（Job 仍不能直写 `job.json`/`plan.json`/`progress.json`/`events.jsonl`），`knowledge` 兼容别名共享同路径同门禁，`background_direct` 行为不变。

## 1.7.1 - 2026-08-07

- 新增 `release sync [--apply] [--target-version X.Y.Z]` 单命令发版同步：检查模式（默认）扫描四处版本真源（`VERSION` 文件、`package.json` version、SKILL.md frontmatter `metadata.version`、`scripts/harness.py` 的 `VERSION` 常量，复用 `validate_project_source` 读取逻辑）并输出 JSON 差异报告（exit 0 一致 / 2 不一致 / 1 读取失败），CHANGELOG 顶部条目版本号仅作差异提示不自动生成；`--apply` 以 `VERSION` 常量为唯一真源原子写入三处受管文件（全部目标先写临时文件并校验，再统一替换，任一失败整体回滚、无部分写入），`--target-version` 与常量不一致时失败关闭（exit 2，`release_version_conflict`），一致时作为显式确认；归属不明内容（version 字段缺失/多重/frontmatter 不完整）失败关闭。
- 验收层中间产物复用：`workspace_snapshot()` 与安装副本 SHA-256 比对按（路径， 清单/内容摘要， 合同版本， target_identity）键做单次 CLI 会话内进程级缓存，跨验收层复用确定性中间产物（快照指纹、文件 SHA-256）；清单摘要漂移、合同版本或目标变化即失效重算。四层验收判定结论保持独立，fresh clone 与远端网络 I/O 不跳过。verify 响应新增有界遥测字段 `layer_reuse`（`snapshot_hits`/`snapshot_misses`/`file_hash_hits`/`file_hash_misses` 计数，不含路径以外信息）。
- self-test 的 `script_version` 检查从只查 VERSION 文件扩展为四源比对，`command_parser` 清单同步纳入 `release`。

## 1.7.0 - 2026-08-07

- 低风险任务轻量准入通道（fast_track，声明制）：facts 显式声明 `fast_track: true`（非布尔失败关闭），且路线为 direct、未命中 high gate 与安全底线 Gate、`write_scope` 全部落在文档/规则/测试路径（复用 `infer_gates_from_paths` 分类）、无 `work_packages` 时生效；任一条件不满足静默降级普通流程并在响应标注 `fast_track_denied_reason`（受控原因码 `route_not_direct`/`high_gate_present`/`scope_not_doc_like`/`has_work_packages`）。fast_track 不豁免任何 Gate 判定。
- fast_track 证据裁剪显式化：`completion_manifest` 新增 `evidence_profile`，fast_track 任务 `required_evidence_types` 收敛为最小集（`code_diff` + 声明验证命令时的 `test_run`），语义规则累加不叠加；准入与 verify 响应显式携带 `evidence_profile: "fast_track"`，禁止静默裁剪；verify 按 profile 校验，缺证据骨架按 profile 生成。证据白名单新增 `code_diff`、`test_run`。
- 运行期单向降级：verify 归因命中 `new_risk_gate` 或 `high_risk_drift` 时任务包 `fast_track` 写回 `false`、`completion_manifest` 重建为标准证据集、记录 `fast_track_downgraded` 事件与原因，响应标注 `fast_track_downgraded`；降级单向，重准入只继承任务包记录的生效值。
- `inline_note` 内联通道：fast_track 任务可在 facts 携带 ≤200 字 `inline_note` 替代独立 plan 文档，落入任务包不写 `docs/plans/`；非 fast_track 提交返回 `inline_note_ignored` 提示；超长或非字符串失败关闭。
- 耗时度量：admission（created/readmission/scope_bound_readmission）、planning（plan_frozen/plan_amendment_required）、business_action（begin/block/submit）事件补齐 `time.monotonic()` 真实 `duration_ms`（此前仅 context/verification 有真实计时）；`task status` 响应新增 `overhead_summary`（`harness_total_ms` 各阶段耗时求和、`wall_clock_ms` 首末事件墙钟、`harness_share` 占比，墙钟为 0 时 `null`），为「harness 开销 ≤ 任务总时长 1/10」提供复算口径。

## 1.6.9 - 2026-08-06

- 准入效率加固（ZBuddy 质量账本 `dh-20260806T173420-72df04e033` 复盘驱动，目标 harness 自身耗时 ≤ 任务总时长 1/4）：
- scope 输入防呆：`--scope` 或 facts scope 字段中形似 JSON 的值（数组/对象整体作为单个字符串）直接报 `invalid_scope_json`，附 `actual_vs_expected` 与 `suggested_fix`，不再静默污染 `allowed_scope` 引发 write_scope_violation / plan_scope_mismatch 死循环。
- 每步响应自描述：`next_step_payload` 统一携带 `contract_snapshot`（当前 `allowed_scope`/`read_scope`/`write_scope` 实际值、`plan_fields`、完成清单 `required_evidence_types`），重准入修 scope 可同时核对三字段、verify 前可一次性备齐证据，消除补证据与缺字段的额外轮次。
- `--facts` 静默忽略显性化：非 blocked/scope_changed 状态下提交 facts 时响应返回 `facts_ignored=true` 与 `facts_effective_condition` 生效条件说明。
- Windows 路径提示：`--facts` 等文件参数传入 Git Bash `/tmp` 等 POSIX 绝对路径导致文件缺失时，错误附带改用工作区相对路径的 `suggested_fix`。
- 托管操作指引同步增补：scope 单值禁 JSON、文件参数工作区相对路径、重准入三字段核对、verify 前按 manifest 备证据、planned 改方案先 `context --stage plan`。

## 1.6.8 - 2026-08-06

- 错误提示 actionable 化：`HarnessError` 新增 `suggested_fix`、`missing_items`、`actual_vs_expected` 结构化字段并随 JSON 错误输出序列化。`authorization_mismatch` 逐项列出缺失的授权动作与未覆盖的 write/git/external scope（含每项 `scope_type`、`required`、`authorized`、`hint`，git scope 给出 `.git:refs/remotes/<remote>/<branch>` 格式示例）；`stale_evidence` 列出 `declared_but_not_changed` 与 `changed_but_not_declared` 具体路径并提示 write_set 只写 git 可跟踪源码路径；证据 JSON 解析失败与非对象证据给出 `actual_vs_expected` 对比（如 "JSON list" vs "single JSON object per --evidence parameter"）。宿主可直接消费字段渲染修复指引，不再靠报错文本试错。
- 新增 `harness authorization template --task-id <id> [--output <file>]`：从任务包提取 `authorization_requirements`、allowed/git/external scope 生成可编辑授权文件模板（含 `_template_hints` 说明每个字段来源与填法），生成后可直接作为 `--authorization` 输入消费，消除手写授权 schema 的试错循环。
- 跨平台任务感知：按 write/read scope 文件后缀检测平台专属脚本（`.ps1/.bat/.cmd` → windows，`.sh/.bash/.zsh` → unix），任务包新增 `platform_scope`（`detected_platforms`、`current_platform`、`cross_platform`、`verification_layers`）；`first_run_payload` 对跨平台任务输出 `cross_platform_notice`，提示当前平台无法直接验证的目标平台及建议的分层验证策略，避免 macOS 上 PowerShell 脚本任务验证无法闭环时才发现。
- 新增 `harness task adopt --task-id <id> --outcome <summary> [--external-evidence <file>...] [--bypass-reason <reason>]`：将绕过 harness 在外部完成的非终态任务补录进账本，外部证据摄取为受管副本，任务状态转为 `complete` 且 `verification_status=adopted_external`，写入 `task_adopted` 审计事件并提示补写质量账本；终态任务与缺 `--outcome` 失败关闭。绕过不再留下永久悬置的 in-flight 任务。

## 1.6.7 - 2026-08-05

- repowiki 外部只消费知识源上限从 200 张提高到 1000 张，并可用环境变量 `DOCS_HARNESS_REPOWIKI_CARD_LIMIT` 覆盖为任意正整数；非法取值回退默认 1000。超限仍按排序截断，但不再静默：`knowledge_status` 与 `knowledge_context` 在 repowiki 模式下始终回传 `total_cards`（磁盘卡片总数）与 `truncated`（是否截断），准入降级可归因为候选集不完整而非知识缺失；未截断时 `truncated=false`、`total_cards` 等于 `features`，既有消费者只增字段不改语义。

## 1.6.6 - 2026-08-05

- 支持 `.qoder/repowiki` 外部只消费知识源：项目存在 `.qoder/repowiki/knowledge/<locale>/` 知识卡时，`knowledge_status` 返回 `ready` 并带 `source="repowiki"`，知识交接 mode 为 `external_consume_only`；不创建 `docs/` 骨架与 `knowledge-map.json`，不再自动声明 `feature_knowledge_incremental_sync`/`adr_changelog_todo_review` 交付物，增量 Job 创建短路、`knowledge bootstrap` 以 `knowledge_external_consume_only` 失败关闭。任务准入按任务文本与 scope 命中知识卡 frontmatter 的 `name`/`scope` 选卡作为上下文（`knowledge_context.source="repowiki"`，纯标准库定向解析 frontmatter，上限 200 张）；命中即 `context_quality=complete`，未命中沿用 `unresolved` 降级语义。知识交付不参与 `clone_ready` 判定（`.qoder` 常被 gitignore）。

## 1.6.5 - 2026-08-05

- Gate 分类改由宿主语义判断：facts 新增 `gate_assessment`（`gates` + 500 字符内非空 `rationale`）权威声明，声明即全部，非安全 Gate 不再做任务关键词与 scope 路径推断，简单任务不再被宽泛关键词拖入重流程；`security-sensitive`、`destructive-data`、`release-external` 安全底线 Gate 仍由控制器确定性强制并入（文本触发使用底线专用精确词表并带否定守卫，「不要部署」「删除注释」不命中）并记入 `gate_decision.floor_added`；准入响应与 task-package 新增 `gate_decision` 审计字段（`mode`/`declared_gates`/`rationale`/`floor_added`）；未声明时回退关键词推断，行为与旧版一致；任务中途基于实际变更路径的 Gate 绊线与增量/完整重新准入不受影响。

- write_scope 内未归因写入默认由控制器自动归因：合同稳定且唯一阻断是 `unattributed_drift_overlap` 时，控制器代铸 `workspace_attribution` 收据（producer `("docs-harness", "auto_attribution")`）索引留痕、记录 `auto_attribution` 事件并继续本次 verify，响应新增 `auto_attributed_paths`；项目配置 `verification.auto_attribute_in_scope=false` 恢复 `provide_evidence` 补证据行为。范围之外的写入、其他阻断与高风险 Gate 处理不变。
- 新增 `docs-harness/evidence-declaration/v1` 证据声明草案：宿主只声明 `type`/`write_set`/`changed_paths`/`read_set`/`concurrent_drift`/`conclusion`，`task_id`、`target_identity`、`package_fingerprint`、`cwd`、起止时间、`ttl`、digest 与 `read_set` 指纹全部由控制器代铸（producer `("docs-harness", "host_declaration")`），代铸后按完整 v2 收据同等校验索引；完整 `evidence-receipt/v2` 继续接受，缺 `type`、未知 `type`、越界路径失败关闭。
- git_sync 远端漂移重新准入继承已落盘同步范围：用 `git diff --name-status 旧HEAD 新HEAD`（unborn 时对空树）算出 pull 已落盘文件记入 `git_sync_landed_scope`（跨多次漂移累积）并并入 `write_scope`，归因时与 `git_sync_scope` 同等自动认领；diff 之外的杂散写入依旧阻断。
- git 漂移重新准入在旧方案指纹有效且方案合同除范围字段外逐字段相等时直接继承已冻结方案，`run --task-id` 单命令回到 `ready_planned`，省掉 context 与 run --plan 两轮。
- `controlled_refs_namespace` 自动包含 `.git:refs/remotes/<remote>/HEAD`，`origin/HEAD` 的创建或更新不再误判为 `git_ref_scope_violation`。
- 安装交付判定改用 git 自身比较（`git diff --quiet HEAD`）：`core.autocrlf=true` 等行尾转换配置下仅行尾差异不再让 `project check` 永远停在 `pending_commit`。

## 1.6.4 - 2026-08-04

- 关闭“增量 Gate + 授权收据 + delta context”下一轮 verify 再次失效的循环：授权合同指纹未变时通过 `authorization-adoption/v1` 记录受控继承，证据同轮复用；每次 verify（含失败）都写入有界 `verification_attempt` 事件，`readmission_count` 纳入增量 Gate 重新准入；`changed_paths=[]` 不再创建知识增量与治理 Job。
- 正式计划只冻结一次：范围绑定后在同一事务中重新校验并采用原计划；只缺新增字段时通过 `contract_delta`/`complete_plan_delta` 补丁完成，补丁不得修改已冻结字段或 scope；测试 Gate 单独新增不要求计划补写；上下文正文按内容寻址跨 stage 复用，stage 确认收据单独生成。
- 受管 artifact store（`artifacts/plans|authorizations|evidence|verification`）：计划、授权、证据摄取为受管副本，调用者临时文件删除后继续有效；证据新鲜度与授权有效性优先校验受管副本指纹。
- 验证命令改为逐项执行与复用：每条命令独立计算输入指纹（排除 volatile 项的完整工作区快照）、命令前后快照与写入分类；通过的命令写入 `verification-command-receipt/v1` 收据（绑定 task、target、argv digest、cwd、输入指纹、合同摘要与 TTL），补证或重试时命中收据不重跑，只重跑失败或输入失效的命令；阻断写入只翻转当事命令，新建 volatile 副产物保持可见；项目配置 `verification.command_cache_enabled=false` 可整体关闭缓存并回退为逐命令执行。
- verify 结果由“补证或完整重新准入”二分法改为五级分类：`provide_evidence`、`refresh_evidence`、`retry_verification`、`incremental_admission`、`full_readmission`；允许范围内缺 write-set 归因降级为补归因收据（不增加 package revision），read-set 漂移只失效引用该路径的证据；越界写入、高风险 Gate、规则或授权合同变化、远端漂移仍完整重新准入。
- 首次 `run` 计算活动任务幂等键（target、任务、facts 与初始工作区快照）：相同键的非终态任务默认复用并返回当前状态，终态与 blocked 任务不复用；`--new-task` 强制创建独立任务。
- change-scoped 工作量估算保留 project-wide 规模上下文，但去重与 `source_fingerprint` 只绑定变化路径、选中功能、交付物与解析后写入范围的文件指纹，无关项目文件变化不再改变后台 Job 幂等键。
- `npm test` 脚本去掉 Windows cmd 不剥离的单引号模式参数，修复 Windows 上 `npm test` 发现 0 个测试的问题。

## 1.6.3 - 2026-08-04

- 路径 Gate 推导识别 `*.test.*`、`*.spec.*` 与中文“测试文件”范围描述，减少直到最终 `verify` 才发现 `testing-acceptance` 的情况。
- `verify` 晚发现仅追加、且不改变执行路线、授权、范围、方案字段或阻断交付物的 Gate 时，由控制器原子执行增量准入；同轮已验证收据写入来源指纹和继承记录后复用，只加载新增上下文，不再要求完整 `run` 和重新生成相同证据。产品、架构、安全、数据破坏、外部发布、前端设计、extended 路线及任何合同变化仍完整重新准入。
- `verify` 的本地验证命令工作区写入检查区分交付写入与验证期间新建的已知临时副产物：`__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`、`.tox`、`.nox`、`.hypothesis`、`.cache`、`.nyc_output`、`htmlcov` 等缓存目录，`.pyc|.pyo|.tmp|.temp|.swp|.bak|.log` 后缀，`.coverage`（含并行分片）、`.DS_Store`、`Thumbs.db`、`.eslintcache` 与编辑器临时文件不再把通过的命令翻转为 `verification_command_workspace_write`；同名已有文件被修改或删除仍失败关闭。
- 验证命令结果新增 `volatile_write_set` 字段，被容忍的临时写入保持可见；交付路径的真实写入仍然失败关闭并只列出阻断路径。
- 项目配置新增 `verification.volatile_paths` glob 白名单，允许项目声明额外可容忍的验证副产物；模式必须位于工作区内并带固定根目录，`*|**` 等全局模式失败关闭；`project upgrade` preserve-and-merge 该配置。
- npm 打包显式排除 Python bytecode、`__pycache__` 与本地 tgz，验证缓存不会进入发布包。

## 1.6.2 - 2026-08-04

- 新增 `docs-harness/document-routes/v1`：统一解析 Architecture、Changelog、TODO、ADR 与 Review 真源，显式合法配置优先，自动探测仅接受受控范围内的唯一可信候选。
- `delivery_governance` Job 的估算、读写范围、锁和运行时复验统一绑定路由合同；缺失、多候选、非法配置形成零写权限 `needs_user_input` Job，父任务完成事实保持不变。
- 治理 Job 使用稳定 `route_base_key` 去重；路由变化通过独立指纹检测，prepare、dispatch、verify 在目标漂移时失败关闭。
- 缺少路由合同的旧治理 Job 只读可见，仅允许宿主停止后显式取消并 route repair；迁移不合并旧 scope，也不消耗原有执行重试预算。
- `project check`、`project upgrade` 与 `rollback-check` 增加路由配置、在途 Job 和混合版本边界；安装升级 preserve-and-merge 合法 `document_routes`，不创建 canonical 文档。

## 1.6.1 - 2026-08-04

- 新增 `background prepare|progress`：复杂路线的 revision 2 Plan/Progress 由 Harness CLI 确定性生成、原子维护，宿主不再直接写 Runtime 控制文件。
- `contract_ready → dispatched` 与 `dispatched → running` 均校验工件绑定、attempt、工作包全集和文件指纹；`knowledge dispatch` 兼容别名不再拥有复杂路线旁路。
- `background verify` 把最终工作包进度纳入成功证据；retry/rebase 归档旧 attempt 工件、清空引用，显式 `prepare --repair` 才能修复部分、无效、冲突或被篡改的工件。
- 后台事件统一为脱敏有界字段，重复拒绝幂等去重；终态摘要按 `(job_id, attempt, status)` 记录，prune 只接受当前最新 attempt 的终态摘要。
- 后台业务写入范围明确排除 `.git/**`、`.docs-harness/**` 和实际 Runtime；Git 与非 Git 控制面路径仅由 Harness 解析和写入。
- 工作量评估新增 `project_wide|change_scoped` 基础。bootstrap 保持项目级估算，知识增量与交付治理按实际变化面估算，同时保留原 `source_fingerprint` 与 Job 幂等键语义。

## 1.6.0 - 2026-08-04

- `project init|upgrade` 统一返回知识交接合同：`already_ready|bootstrap_new|bootstrap_in_progress|audit_existing`；已有文档保持零知识内容写入，无文档旧项目升级会幂等创建单一 bootstrap。
- `background_deliverables` 成为 `verify` 的唯一后台派发真源；未声明时返回 `not_required`，无实际写入时返回 `no_write_no_sync`，知识未 ready 且无 bootstrap 时返回 `action_required`。
- 后台合同升级为 `docs-harness/background-job/v2`，新增 `may_spawn_child_jobs=false`、完整 bootstrap 依赖结果分流和 upgrade 时的在途 v1 幂等迁移；`background status` 保持只读。
- 所有知识 Job 只有在控制器复算 `knowledge_status=ready` 后才能以 `updated|no_change` 完成；候选地图先纯读取复算，partial 时不落盘知识地图。
- 任务包新增 `deferred_intents` 与 `intent_boundary_reason_codes`；未来动作和完成体不再提升当前任务变更面，英文短词、工具名与路径 Gate 改为单词/路径段边界匹配。
- 知识审查与工作量评估共享库存过滤器，排除运行产物、生成目录、敏感路径、不可读二进制与打包资产；同意、拒绝和 assessment 绑定过滤后库存指纹，并返回分类排除摘要。
- `project check` 对超时非终态后台 Job 返回 action-required yellow 提醒；源码回归新增 bootstrap、upgrade、派发、分类、库存与候选复算场景。

## 1.5.0 - 2026-08-04

- 任务准入升级到 `task-package/v2`：先编译 `query|audit|git_inspect|git_fetch|git_sync|modify|external_write`，再按混合意图最高变更面和风险 Gate 决定路线。
- 拆分 `read_scope|write_scope|git_scope|external_scope`；只读任务默认 `ready_direct + read_only + write_scope=[]`，自然语言范围失败关闭。
- `git_fetch|git_sync` 新增脱敏 `git_state_snapshot`、自动同步范围、远端 OID/refs/HEAD/索引/工作区预后检及 LFS/Submodule、脏范围和远端漂移阻断。
- 验收区分 `task_write_set|read_set|concurrent_drift|unattributed_drift`；无关漂移只告警，重叠或高风险漂移重新准入。
- 新任务只接受绑定 task、target、package、producer、时效和读写集合的 `evidence-receipt/v2`；验证命令使用白名单 `produces` 并生成脱敏 v2 收据。
- 上下文升级到 `context-receipt/v2`，按 task/target/stage/compiler/content set 复用；`run` 前置返回带指纹的 `completion_manifest`。
- 任务事件升级到有界、脱敏 `event/v2`；新增 `task status|migrate` 事务迁移与 `project rollback-check`，迁移中断按全对象备份恢复，旧控制器遇 v2 失败关闭。

## 1.4.1 - 2026-08-04

- `project init|diff|upgrade|check` 使用来源包版本真源，确定性维护 `AGENTS.md` 和 `docs/INDEX.md` 的 Docs Harness 受管版本区块。
- upgrade preview 显式返回 `from_version`、`to_version`、`manual_migrations` 和 `apply_completion_possible`，重复 apply 保持幂等。
- 旧知识索引仅自动迁移完全匹配白名单的版本行；归属不明的引用保持不变并返回 `needs_manual_migration`。
- 来源包的 `VERSION`、控制器常量、技能元数据和 `package.json` 版本不一致时使用 `source_version_inconsistent` 失败关闭。

## 1.4.0 - 2026-08-03

- 将父任务交付与非阻塞文档治理拆为独立状态通道；`verify` 先原子写入父任务 `complete`，再返回最小交付回执和一个或多个后台 Job。
- 新增文档交付分类，显式输出 `blocking_deliverables` 与 `background_deliverables`，用户指定文档、控制要求和必要验收不能被降级到后台。
- 新增有界工作量评估 `docs-harness/workload-estimate/v1`，按 simple、complex、oversized 路由到 `background_direct`、`background_goal`、`background_goal_phased`，硬升级保留原始分数与原因。
- 项目配置升级到 `docs-harness/project-config/v4`；新项目安装创建异步 `knowledge_bootstrap` 合同并立即返回，已有文档继续保持零内容写入和指纹绑定的同意边界。
- 知识缺失、构建中、失败或隔离改为 `context_quality=degraded`，不再单独阻断业务准入；控制规则、授权、安全、范围和必要证据继续失败关闭。
- 统一知识初始化、知识增量、交付治理和严重跟进为 `docs-harness/background-job/v1`，增加父任务不可变约束、目标合同、宿主能力合同、最大重试、完整状态机、范围/符号链接检查和终态摘要索引。
- 复杂后台路线进入 `running` 前强制校验绑定当前 Job 的正式方案与持久化进度，防止仅声明目标路线却绕过目标治理。
- 初始化运行期间的知识增量进入 `waiting_for_bootstrap_merge`；初始化完成或失败后废弃旧基线并基于当前工作区重新调度，禁止重放旧文本补丁。
- 后台重大发现进入 `completed_with_finding`，幂等创建绑定父任务与父 Job 的 `critical_followup`，不回滚父任务。
- 新增 `background estimate/list/status/dispatch/verify/retry/prune`；v1.3 `knowledge job-status/dispatch/verify/retry` 保留为带弃用提示的兼容别名。
- Runtime 迁移到 `background/estimates|jobs|locks|index.jsonl`；`prune` 缺省 dry-run，只有显式 `--apply` 才删除已终结、已索引且不含严重发现的 Job。

## 1.3.0 - 2026-08-03

- 新增按功能组织的 L2 项目知识库：`docs/features/<feature-id>/` 分别维护产品、研发、测试、设计事实，`docs/shared/` 维护跨功能架构、安全、设计系统和测试策略。
- 安装时审查知识库状态：项目没有 `docs/` 时创建骨架并返回 `needs_bootstrap`；已有 `docs/` 时不改写文档并返回 `needs_audit`，文档不完整时必须先获得用户同意。
- 新增 `knowledge status/audit/update/verify/job-status/dispatch/retry` 命令，以及知识地图、审查结论、用户授权和后台 Job 的版本化合同。
- Gate 根据任务功能与类别动态加载知识；无法解析既有功能或缺少必需类别时失败关闭，明确的新功能任务使用受控豁免模式。
- 主任务验收完成后先落盘 `control_status=complete`，再创建并返回幂等后台调度合同；合同创建异常降级为 `dispatch_failed`，支持子智能体的宿主负责异步派发，后台结果不阻塞、回滚或改写主任务完成状态。
- 后台知识 Job 增加父任务稳定去重、防递归、功能级/公共层/目录级互斥锁、知识库基线、脏文档与越界写入保护、失败降级与显式重试。
- Git 交付检查新增知识库清单与 `knowledge_delivery_status`；整体 `clone_ready=true` 同时要求控制器和完整知识库进入当前 HEAD。

## 1.2.0 - 2026-08-03

- 新增人工触发的个人本地质量账本：`ledger add` 保存一次性任务快照，`ledger read` 供后续智能体按任务编号或关键词读取。
- Git 项目把记录写入 `<git-dir>/docs-harness/quality-ledger/records/`；非 Git 项目写入 `.docs-harness/quality-ledger/records/`，且不参与工作区冻结、Git 交付或 clone-ready 判断。
- 质量复盘只接受有界、脱敏、字段白名单的 JSON 文件；任务状态、当前任务包版本、范围、Gate 和证据类型由控制器提取，智能体不能覆盖。
- 每个 `task-id` 只保存一条不可变快照；相同内容幂等返回 `already_recorded`，不同内容返回 `record_conflict` 且不覆盖历史。
- 项目初始化不创建空账本，升级与 `project uninstall --purge-runtime` 均保留个人质量记录。

## 1.1.4 - 2026-08-03

- `run` 与 plan context 共享动态方案合同；初始范围为空时骨架自动要求“执行范围”。
- 方案首次绑定范围后完整重跑 Gate、规则、方案字段和验收要求，以新任务包版本继续原任务。
- `--facts`、`--plan`、`--authorization`、`--evidence` 统一使用安全文件加载合同，内联或无效输入返回脱敏结构化错误。
- 带 `next_action` 的响应统一返回 `reason_code`、`next_command_argv` 和适用的 `artifact_ref`，减少重复任务和命令推导。

## 1.1.3 - 2026-08-03

- Git 项目安装前检查控制器、受管入口、配置和逐规则文件；未跟踪且被忽略时零写入并返回 `git_delivery_ignored`。
- `project init/upgrade/check` 区分本地运行健康与当前 HEAD 交付状态；必需文件未进入 HEAD 时返回 `needs_delivery`，不再误报新 clone 可用。
- 增加真实 Git 提交与新 clone 回归，验证配置、规则快照和任务规则路由能够跨工作副本交付。

## 1.1.2 - 2026-08-03

- 保留任务首次创建的工作区快照作为不可变验收基线，重新准入不再把既有改动吸收到新冻结点。
- 工作区冻结纳入 `.docs-harness/config.json` 与规则快照，仅排除非 Git 项目的 `.docs-harness/runs/`。
- 正式方案与任务包执行范围不一致时返回“重新准入”，不再静默忽略方案范围。
- 目标项目内执行 `project init/upgrade/diff` 时明确返回 `invalid_source`；生命周期变更必须从来源包发起。
- 非 Git 快照超过 4096 个文件时失败关闭，且不留下半初始化任务状态。

## 1.1.1 - 2026-08-03

- 修复 `run` 在规则目录缺失或没有合法 active 规则时仍以空规则准入的问题，统一为失败关闭。
- `project check` 新增 Git 交付检查：配置或规则快照被 `.gitignore` 排除时返回 red。
- 明确 Git 项目只把运行状态写入 Git 内部目录，`.docs-harness/config.json` 与规则快照必须进入版本控制面。

## 1.1.0 - 2026-08-02

- 激活 8 条通用规则，覆盖 API、文档、安全、发布、范围变化、测试、UI 和 Windows PowerShell。
- 项目安装改为携带仓库内规则快照，移除配置中的绝对源码路径。
- 规则目录缺失、快照漂移或 active 规则为空时失败关闭。
- 项目配置升级为 `docs-harness/project-config/v2`。
- Git 项目的工作区冻结只纳入已跟踪和未忽略文件，避免构建产物、依赖缓存等忽略内容误触发范围重新准入；非 Git 项目保留有界目录快照。

## 1.0.0 - 2026-08-02

- 建立独立 Docs Harness 技能、任务控制器和 Harness Home。
- 实现 direct、planned、extended 三种执行路线和六种准入状态。
- 实现任务包、上下文回执、授权回执、复杂任务进度、证据索引和同源验收。
- 实现 Git/非 Git 独立运行状态目录。
- 实现项目 init、upgrade、uninstall、check、diff 和 self-test。
- 建立通用规则文档骨架；规则正文保持为空，运行时使用 `rules=[]`。
