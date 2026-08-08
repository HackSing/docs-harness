# TODO

## v1.7.3 验收循环修复：五原因码全治理

- 状态：已完成源码实施与测试，文档与 evals 已同步。
- 方案：[v1.7.3 验收循环修复方案](plans/v1.7.3-verify-loop-fix-plan.md)
- 背景：ZBuddy v1.7.2 真实运行数据（08-07）显示 verify 平均 2.0 轮、一次通过率仅约 28%，五类非完成原因（`missing_evidence_types` 18、`write_scope_violation` 17、`stale_evidence` 5、`missing_receipts` 4、`concurrent_drift_overlap` 4）全部纳入治理。
- 结果：A. `incrementally_extend_write_scope`：合同稳定、纯越界、无新 Gate、direct/planned、无授权、非 git_sync、上限 3 次（事件扫描计数）时 verify 同一次调用内以 write_scope 严格超集重编译任务包（`STABLE_FIELDS_MINUS_SCOPE` 逐字段一致 + 候选 scope 覆盖并集硬断言），证据按新指纹重绑（`scope_superset_extension` 全审计字段），写 `scope_extension_readmission` 事件，响应含 `scope_extended`/`extended_paths`；任一前置不满足失败关闭回退全量重准入。B. 准入三处响应携带 `evidence_checklist` 四段与 `ensure_evidence_skeletons` 预生成骨架（含 `_instructions`），消灭 missing_evidence_types/missing_receipts 首轮必现。C. 越界全量重准入携带 `readmission_hint`（facts_template 只含 write_scope + example_argv）。D. `task changes-preview` 只读 action（零状态变更，state 目录逐字节一致）+ stale_evidence 双清单载荷。E. concurrent_drift_overlap 双选项 readmission_hint（只保证失败后一次重准入即过）。F. 三处响应 `pending_context_receipts` 状态位前置。附带环境宽容修复：验证命令缺失失败关闭（`verification_command_unavailable`）不崩溃、autocrlf 行尾宽容指纹不触发 script_drift、release sync 目标非文件整体拒绝。
- 验收摘要：新增 30 个 `test_v173_*` 测试（T1–T23 合同 + V1 回放复现 + V2 失败关闭矩阵，T19–T23 为外部审查发现修复的回归守护）全部通过；V4 修复全部历史失败后全量 455 项**无豁免全绿**；V3 影子验收脚本 [v1.7.3-v3-shadow-acceptance.py](plans/v1.7.3-v3-shadow-acceptance.py) 安装副本全链路 25 项断言通过（含 changes-preview 前后 state 逐字节一致）；V5 evals 新增五原因码用例；版本升 1.7.3，以自身 `release sync --apply --target-version 1.7.3` 自举完成四源同步。V6 自托管门禁闭环（任务 `dh-20260807T234649-c9ff62760f`）：准入响应实际携带 evidence_checklist 四段与 pending_context_receipts；越界写入（`tests/test_release_version_sync.py` + `package.json` 登记）经 `task changes-preview` 零试探检出（state 目录逐字节不变）；verify 一次调用内增量扩围并完成（`scope_extended`/`extended_paths` 真实命中），新增发版门禁回归测试守护四源与 evals 版本一致；self-test、release sync 检查模式、`npm run pack:check` 全部通过。V7 外部审查闭环：claude code 卡住后按预案切 kimi CLI 审查（报告 [v1.7.3-verify-loop-fix-kimi-code-review.md](reviews/v1.7.3-verify-loop-fix-kimi-code-review.md)，无 P0），4 个 P1 + 选定 P2 全部修复并补回归守护：扩围前 supplied 证据 write_set 硬校验与 artifact 审计补齐、pending_context_receipts 覆盖工作包、concurrent 选项 1 补 read_scope 剔除、行尾宽容指纹 1MiB chunk 边界 CRLF 修正、changes-preview legacy/缺基线防护与 first_run_payload manifest 守卫一致。
- 安全边界：不改 Gate/授权/证据装订语义；授权任务扩围必然改变授权合同指纹强制全量重准入；changes-preview 零状态变更；不自动提交推送 git。
- 下一步：ZBuddy 升级 v1.7.3 后用账本数据复核轮次目标（平均 verify 轮次 2.0 → ~1.2，一次通过率 28% → ~70%）；`concurrent_drift_overlap` 受环境制约不计入承诺。

## v1.7.2 后台治理合并快路径

- 状态：已完成源码实施与测试，文档与 evals 已同步。
- 方案：[v1.7.2 后台治理合并快路径方案](plans/v1.7.2-background-merged-dispatch-plan.md)
- 背景：复杂路线 `prepare → dispatched → running → progress×N → verify` 需 5+N 次 CLI 往返，对 change_scoped 中小型复杂 Job 是固定税；v1.7.0/v1.7.1 两阶段均未覆盖此卡点。
- 结果：`background dispatch --job-status running --prepare-and-run` 单命令顺序执行 prepare→dispatched→running，工件校验、绑定、attempt、工作包全集、指纹、路由合同复验全部原样保留（dispatch 执行体抽取为 `dispatch_background_job_status`，分步与合并共享同一份闸门代码），任一闸门失败停在该步并返回与分步执行相同的出口；已 prepared 且指纹一致时复用 `already_prepared` 幂等跳过。资格限制：仅 `background_goal` + `change_scoped` + `raw_score < 60`，phased/oversized/direct/非 change_scoped/分数 ≥60 以 `background_prepare_and_run_not_eligible` + 精确 `eligibility_reason_code` 拒绝。`background progress --all completed` 逐包连续推进全部工作包到 completed（复用逐包状态机、事件逐包记录），非法前置态整体拒绝不部分提交（`background_progress_all_blocked` + 阻断清单）。控制面不变量不变，`knowledge` 别名共享同门禁，`background_direct` 行为不变。
- 验收摘要：新增 4 个 `test_v172_*` 测试（事件序列与分步逐条一致+幂等跳过、闸门失败停步且出口相同、批量推进+阻断不部分提交、phased/高分/direct 拒绝+声明制缺参失败关闭）全部通过；分步路径不回归（全量 unittest 除两个已知无关失败外全绿）；版本升 1.7.2，以自身 `release sync --apply --target-version 1.7.2` 自举完成四源同步。
- 安全边界：只做声明制合并不自动推断；所有既有校验闸门原样保留；`--all completed` 不部分提交；不自动提交推送 git。
- 下一步：ZBuddy 等下游项目按发布节奏升级安装副本后，用真实复杂 Job 对照往返次数验证提效；资格阈值 60 待账本数据回流后评估是否校准。

## v1.7.0 低风险任务轻量准入通道

- 状态：已完成源码实施与测试，文档与 evals 已同步。
- 方案：[v1.7.0 低风险任务轻量准入通道方案](plans/v1.7.0-low-risk-fast-track-admission-plan.md)
- 背景：v1.6.9 已把准入轮次压到 ≤2 轮，但所有任务不分大小走同一条重流程，低风险小任务的证据装订与 plan/TODO 前置物开销常超过实现成本。
- 结果：facts 声明制 `fast_track` 轻量通道落地（direct 路线、无 high gate/安全底线 Gate、write_scope 全为文档/规则/测试路径、无 work_packages），不满足即静默降级并标注 `fast_track_denied_reason` 受控原因码；`completion_manifest` 新增 `evidence_profile`，fast_track 收敛为 `code_diff`（+声明验证命令时 `test_run`）最小证据集并显式标注；运行期 `new_risk_gate`/`high_risk_drift` 触发单向降级（任务包写回 `fast_track=false`、记录 `fast_track_downgraded` 事件、按普通证据集校验）；`inline_note`（≤200 字）仅 fast_track 可用并落任务包不写 `docs/plans/`。耗时度量补齐 admission/planning/business_action 真实 `duration_ms`，`task status` 新增 `overhead_summary`（harness_total_ms/wall_clock_ms/harness_share）作为 ≤1/10 开销目标复算口径。
- 验收摘要：新增 7 个 `test_v170_*` 测试（合法 fast_track、验证命令最小集、high gate 降级+非布尔拒绝、运行期降级、非 fast_track 不回归、inline_note、overhead_summary）全部通过；全量 unittest 除 v1.6.8 遗留 Windows 用例 `test_cross_platform_task_detection`（失败原因与改前一致）外全绿；版本升 1.7.0，CHANGELOG/contracts/evals 已同步。
- 安全边界：不改 Gate/授权/证据装订语义；fast_track 只声明不推断、不豁免任何 Gate；降级单向。
- 下一步：ZBuddy 等下游项目按发布节奏升级安装副本后，用真实 fast_track 任务对照 `overhead_summary` 验证 ≤1/10 目标。

## v1.7.1 发版同步与验收提效

- 状态：已完成源码实施与测试，文档与 evals 已同步。
- 方案：[v1.7.1 发版同步与验收提效方案](plans/v1.7.1-release-sync-and-verify-efficiency-plan.md)
- 背景：每次发版需手工核对四处版本真源与 CHANGELOG/contracts 同步；四层验收（源码/安装副本/Git/fresh clone）中间产物重复计算。
- 结果：新增 `release sync [--apply] [--target-version]` 单命令原子版本同步——检查模式扫描四处版本真源（复用 `validate_project_source` 读取逻辑）输出 JSON 差异报告（exit 0/2/1），CHANGELOG 顶部条目仅提示不生成；`--apply` 以 `VERSION` 常量为唯一真源，三处受管文件先写临时文件并校验再统一替换，任一失败整体回滚无部分写入；`--target-version` 冲突失败关闭（`release_version_conflict`）。验收层中间产物按（路径， 清单/内容摘要， 合同版本， target_identity）键做会话内进程级缓存（快照指纹、安装副本 SHA-256），verify 响应新增 `layer_reuse` 有界遥测；四层判定结论保持独立。self-test `script_version` 扩展为四源比对。版本升 1.7.1，以自身 `release sync --apply` 自举完成四源同步。
- 验收摘要：新增 7 个 `test_v171_*` 测试（四源一致 exit 0、package.json 不一致精确差异、--apply 原子写入、只读目标回滚无部分写入、--target-version 冲突、会话内复用命中+合同版本变化重算、verify 响应 layer_reuse）全部通过；既有 delivery_layers 测试不回归（全量 unittest 除两个已知无关失败外全绿）。
- 安全边界：不改变验收层独立性语义；release sync 只写受管文件，归属不明失败关闭；不自动提交推送。
- 下一步：ZBuddy 等下游项目按发布节奏升级安装副本后，用真实 verify 对照 `layer_reuse` 观测提效效果。

## v1.6.9 准入效率修复

- 状态：已完成。源码、测试、文档、ZBuddy 安装与真实回归全部通过。
- 方案：[v1.6.9 准入效率修复方案](plans/v1.6.9-admission-efficiency-fix-plan.md)
- 背景：ZBuddy 质量账本 `dh-20260806T173420-72df04e033` 显示 harness 准入修复与补证据约占任务总时长 2/3，重准入循环约 6 轮；用户要求 harness 自身耗时 ≤ 任务总时长 1/4。
- 结果：`validate_scope` 拒绝 JSON 形 scope（`invalid_scope_json` + suggested_fix）；`next_step_payload` 全路径携带 `contract_snapshot`（三 scope 实际值、plan_fields、所需证据类型）；非 blocked/scope_changed 下 `--facts` 返回 `facts_ignored` 警示；Windows `/tmp` 类路径缺文件错误附工作区相对路径提示；托管指引与 SKILL.md 同步。194 个测试通过（1 个失败为 v1.6.8 已有 Windows 平台相关用例 `test_cross_platform_task_detection`，与本次无关）；版本升 1.6.9，CHANGELOG/contracts/evals 已同步。ZBuddy 已升级 v1.6.9（安装副本与源码 SHA-256 一致），四项真实回归通过：JSON scope 当场拒绝、facts_ignored 警示、needs_plan 自描述缺失字段+三 scope+证据类型、补全后一轮通过；回归任务已 cancel 终态化，project check 无 red 发现，delivery 为 pending_commit（ZBuddy 仓库提交由其自身决定）。
- 影响：`--scope` JSON 数组静默接受、scope 三字段部分修复、Windows 路径提示缺失、plan_fields 与证据要求事前不可见、`--facts` 非 blocked 状态静默忽略。
- 目标：输入防呆 + 每步响应自描述（contract_snapshot）+ 指引层更新，同类任务准入轮次 ≤2。
- 安全边界：不改 Gate/授权/证据装订语义；不触碰 ZBuddy（安装另行授权）。
- 验收摘要：5 个账本失败模式各有测试且通过；全量 unittest 通过；版本 1.6.9。
- 下一步：条目关闭。后续真实任务的账本记录可对照验证 harness 耗时占比 ≤1/4。

> **TODO 写入原则**：新增 TODO 前，必须先在 `docs/plans/` 中建立独立的方案文档，并在 TODO 条目中使用相对链接引用该文档。TODO 只记录状态、问题说明、影响、目标、安全边界、验收摘要和下一步，不复制方案正文；同一问题已有条目时更新原条目，不新增重复入口。缺少方案文档或有效引用时，不得登记 TODO。

## Runtime 生命周期与交付回执语义治理

- 状态：已完成源码实施、ZBuddy 安装与 Runtime 治理；物理清理经用户授权提前执行完毕。
- 方案：[Runtime 生命周期与交付回执语义治理方案](plans/runtime-lifecycle-and-delivery-receipt-plan.md)
- 背景：历史任务与后台 Job 缺少完整终结入口，通用完成回执又无条件显示远端未验证，导致 Runtime 待办与交付边界失真。
- 结果：新增 `task cancel|archive|list|prune` 受控终结合同与 `delivery_layers` 回执分层；ZBuddy 21 条废弃任务与 13 条废弃 Job 全部终态化并按期物理清理，严重发现单独结论后关闭，`rollback-check` 恢复通过。
- 版本说明：按方案约定本批次不绑定新版本号；版本标记、Changelog 与发布由后续发布阶段决定。
