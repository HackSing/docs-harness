# Changelog

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
