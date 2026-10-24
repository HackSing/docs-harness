# Docs Harness 测试与验收

## 1. 普通项目任务

普通项目任务不运行旧 Harness Verify。agent 按修改面选择成本最低、但能够直接覆盖用户目标的真实流程：纯函数用聚焦输入输出或单元测试，API 启动最小服务并调用，Web/桌面界面运行真实交互，构建与安装检查真实产物；功能、视觉与交互体验由 agent 在模拟器/本地联调中自行走查（可用 mock 数据），发现不友好直接重新优化并复验，仅真实硬件、系统权限等本地确实无法运行的层准备环境后交给用户。

每次结论同时标注 L1–L5 与具体 `evidence_layer`。L2 的 `focused_test` 与 `repository_full_test` 分开，L4 的 `package_or_install`、L5 的 `real_device` 也不能由源码测试代替；真实设备客观行为不等于用户主观确认。

## 2. Docs Harness 自身验证入口

- 聚焦测试：按变更面运行对应 `unittest` 模块或用例；
- 完整回归：`npm test`，仅在行为代码、依赖、公共夹具或跨模块风险要求时运行；
- 控制器自检：`npm run self-test`；
- 发布包清单：`npm run pack:check`；
- 版本一致性：`python3 scripts/harness.py release sync --target . --json`（`--strict` 同时强制 CHANGELOG 顶部版本与 VERSION 一致）。
- 统一资产检查：本地/钩子运行 `assets-check --fast`，发布与 CI 运行 `assets-check --strict`。
- CI 解释器：`assets-check --strict` 与 `npm test` 在 README 写明的最低版本（3.9）和最新 3.x 上各跑一遍；矩阵首项与 README 是否一致由 `test_ci_matrix_starts_with_minimum_python` 核对。

## 3. 验证选择矩阵

| 变更类型 | 本轮最小验证 | 何时升级为完整回归 |
|---|---|---|
| 行为代码、依赖、公共测试夹具 | 受影响目标测试；按影响补自检、编译或打包 | 行为稳定后，同一行为快照最多执行一次 |
| 仅测试代码 | 受影响测试 | 修改公共 runner、共享夹具或跨模块断言时 |
| 仅版本、README、CHANGELOG 或发布元数据 | 版本一致性、自检和打包 | 除非同时改变行为、依赖或公共夹具，否则不执行 |
| 下游安装或升级 | preview、apply、diff、project check 和受管文件摘要 | 不重复执行上游源码完整回归 |

- 已有完整回归通过，且行为代码、依赖和公共夹具未变化时复用该证据。
- 修复过程中先运行目标测试；完整回归是必要时的最终闸门，不是每轮固定仪式。
- 长测试只保留最终汇总和真实失败，避免重复日志进入模型上下文。
- 聚焦测试、完整回归、安装、提交、推送和 fresh clone 是不同证据层。

### Bugfix 方案定义

- “受影响模块测试”：由根因、调用链和实际改动面证明相关的模块、接口、组件或命令测试；这是 Bug 修复默认范围。
- “仓库级全量测试”：运行仓库定义的完整回归入口；只有跨模块、公共契约、共享基础设施、依赖/共享夹具或发布门禁明确触发时使用。
- `full + bugfix` 方案必须结构化声明受影响模块、验证命令、复用的已通过证据、全量触发原因和失败归因策略。

## 4. 2.7.0 聚焦回归面

- 默认直接模式不创建 Harness 状态；
- 用户关闭 Harness 时零隐式调用；
- Knowledge 创建/修订的证据引用、指纹、revision、结构化查询、同键冲突、检查和归档；
- 方案 Level/Profile 选择、字段白名单、冻结指纹、JSON/Markdown/INDEX 原子产出和执行投影；
- init/upgrade 方案目录初始化、既有索引正文保留、重复升级幂等与缺失结构 check 红级发现；
- plan settle 的已实施状态同步、废弃归档、伴随文件移动、索引退出与链接更新；
- Plan v3 的 `acceptance_required`、`knowledge_impact`、治理输入、v2 兼容与 failed Acceptance WARN；
- Acceptance 创建/supersede 对 Plan `acceptance_refs[]` 的自动登记和移除；
- `assets-check` 零资产、三类指纹篡改、跨资产关系、FAIL/WARN、fast/strict 边界；
- Bugfix Profile 的结构化影响范围、聚焦/全量选择、受控全量原因码与失败归因；
- Acceptance 目标创建、Plan/Knowledge 引用、criteria 聚合、v3 evidence_layer 固定映射、失败分项归因、结项后重验、归档和用户确认门禁；
- CLI 不存在 Gate、preflight、Host Adapter 或 metrics 入口；
- fresh init 初始化 Plan/Knowledge/Acceptance 空体系，但不生成事实、验收结论或后台 Job；
- pre-2.0 upgrade preview 零写入，apply 只清理所有权明确的旧工件并保留项目内容；
- 旧命令和 `--legacy-opt-in` 不存在于 CLI 或控制器；
- 重复 upgrade 幂等，符号链接和归属冲突在任何安装写入前失败关闭；\r
- `scripts/githooks/` 钩子默认安装：init 落地两个钩子文件、用户修改的钩子 upgrade 拒绝覆盖、uninstall 按指纹只删未改过的钩子、v6 旧配置平滑升级（`tests/test_v2_direct.py` 的 githook 合同用例）；
- 新增资产治理模块各自低于 500 行，安装副本模块指纹与来源一致；
- 发布包只包含当前 2.7.0 对外文档与受管模块。

## 5. 迁移回归

2.x 不再运行 1.x 状态机全量回归，因为该能力已经从当前产品和包中删除。迁移回归只验证现存升级合同：fresh init、旧项目 preview/apply/diff/check、所有权清理、项目内容保留、冲突零写入、旧命令缺席和重复升级幂等。

## 6. 发布结论分层

本地源码、聚焦测试、完整回归、npm 包、fresh clone、Git 提交、远端推送、下游同步、本机安装和用户可见验收互不替代。最终答复只声明本轮实际取得证据的层。

## 7. 2.7.0 三资产治理验收证据（2026-08-15）

- L2 聚焦行为：统一检查、Plan v3、Acceptance 反向登记、v2 兼容、WARN/strict 和归档关系用例通过。
- L2 仓库全量：`npm test` 运行 65 项，退出码 0；新增 2.4.1 官方模板错误配置指纹兼容与用户修改拒绝覆盖用例。
- L1 控制器与文档：`npm run self-test`、`release sync`、`docs-check --strict`、Workflow YAML 解析与 `git diff --check` 均退出码 0。
- L4 包：`npm pack --dry-run --json` 退出码 0，2.7.0 包清单 45 项，包含五个受管资产/治理模块和本次 Plan、Knowledge、Acceptance 资产。
- L4 fresh install：`/private/tmp/docs-harness-2.7.0-final.ZiMjnn` 从当前源码 init 成功；安装副本 `project diff changes=[]`、`project check`、`self-test`、`assets-check --strict` 和 pre-commit 均退出码 0。
- L4 下游升级：Avatanel 2.6.0→2.7.0 与 ZBuddy 2.4.1→2.7.0 均完成；两项目 `project diff changes=[]`、`self-test`、`assets-check --strict`、pre-commit 与 `git diff --check` 通过，且 `core.hooksPath=scripts/githooks` 已读回。ZBuddy 同步初始化三套资产目录；两项目 `project check` 仅因未提交受管文件返回 `needs_delivery`（red=0、yellow=0）。
- GitHub CI：Workflow 已在源码层完成 YAML 解析，但尚未提交或推送，因此没有远端 Actions 运行证据。

## 8. 2.8.0–2.9.1 治理扩展验收证据（2026-08-18）

2.8.0 新增 ADR 第四类受管资产；2.9.0 新增 ScriptHygiene 脚本卫生检查并入 `assets-check` 第五个 checker、安装配置升至 `project-config/v11`；2.9.1 补记两项此前遗漏版本记录的修复并同步文档。

- L1 控制器：`npm run self-test` 退出码 0，`version=2.9.1`，`checks` 全绿（含 `adr_lifecycle_v1`）。
- L2 聚焦行为：`python3 -m unittest tests.test_v2_direct -v` 共 77 项通过，覆盖 ADR 生命周期、`project-config/v11` 安装、Plan v3 治理与受管块同步等合同用例。
- L2 统一检查：`python3 scripts/harness.py assets-check --strict --json` 退出码 0，`checked={plans, knowledge:1, acceptance:3, adr:1, script_hygiene:1, cross:8}`，0 failures / 0 warnings。
- L1 版本一致性：`python3 scripts/harness.py release sync --strict --json` 返回 `consistent`，VERSION/controller/skill/package/templates/evals 六处真源一致。
- 未覆盖：本节未运行 `npm test` 仓库级全量回归、`npm pack`/fresh install 与下游项目升级验证——本轮改动是文档同步 + 版本号收尾，未触碰 ScriptHygiene/ADR 的行为代码本身，按验证选择矩阵（见第 3 节）不强制升级为全量证据；ScriptHygiene/ADR 首次实现时的完整回归证据见对应版本提交历史。

## 9. 2.10.0 证据加固与升级报错验收证据（2026-08-23）

2.10.0 上游合入下游 dsh-buddy fc3da39 的两个生产验证补丁（证据准入加固、最新记录语义），并改进 upgrade preflight 的指纹偏离类 `install_conflict` 为聚合报错。新增用例（均在 `tests/test_v2_direct.py`）：

- 证据准入（`git_ignored_refs`/`assert_evidence_usable`，批次1）：
  - `test_behavior_acceptance_rejects_evidence_under_git_ignored_path`：`.gitignore` 覆盖的 `build/` 下证据登记被拒，`code=acceptance_evidence_ignored`；
  - `test_behavior_acceptance_allows_evidence_under_committed_docs_path`：`docs/acceptance/evidence/` 入库路径放行；
  - `test_behavior_acceptance_missing_evidence_still_reported_in_git_project`：不存在文件仍报 `acceptance_evidence_missing`（原行为未退化）；
  - `test_behavior_acceptance_non_git_target_is_not_locked_by_ignore_check`：非 git 目标目录登记不被 check-ignore 锁死。
- 最新记录语义（`_validate_live_refs`，批次2）：
  - `test_acceptance_check_only_validates_latest_record_evidence`：旧 record 证据缺失 + 最新 record 证据齐全 → check 通过；
  - `test_acceptance_check_fails_when_latest_record_evidence_missing`：最新 record 证据缺失 → FAIL；
  - `test_user_acceptance_confirmation_checked_only_on_latest_record`：user_acceptance 最新记录缺 `confirmed_by=user` → FAIL，被取代的旧记录缺确认不再卡。
- install_conflict 聚合报错（批次3）：
  - `test_upgrade_reports_all_modified_managed_files_at_once`：同时手改 `scripts/harness.py` 与 `scripts/acceptance_assets.py` → upgrade --apply 单次报错，`install_conflicts` payload 恰含两个 path；
  - `test_upgrade_reports_single_modified_managed_file`：单文件修改 → 列表长度 1 且 path 正确。

验证结果（批次4 发版入口，全量触发条件：版本发布）：

- L2 仓库全量：`npm test` 全量通过，退出码 0。
- L1 版本一致性：`python3 scripts/harness.py release sync --strict` 退出码 0，六处真源与 CHANGELOG 顶部版本一致。
- L1 统一检查：`python3 scripts/harness.py assets-check --strict` 退出码 0。
- 未覆盖：`npm pack`/fresh install 与下游 dsh-buddy 升级到 2.10.0 属批次5 范围，本批不执行。

## 10. 2.15.0 Structure 多语言函数级检查验收证据（2026-09-05）

见 `docs/acceptance/structure-function-check-multilanguage.md` 与证据目录 `docs/acceptance/evidence/structure-function-check-multilanguage/`：TS/Go 解析用例、增量与存量报告用例、解析器不可用降级用例，`npm test` 全量、`self-test`、`release sync --strict`、`assets-check --strict`、`npm pack --dry-run` 清单，以及下游 zbuddy-desktop 升级后 `project check`/`structure check` 结果。TS 用例在仓库自身无 node_modules 时经 `DOCS_HARNESS_TS_MODULE_DIR` 指向含 typescript 的目录运行，未设置则 skip 并说明。

## 10a. 2.31.0 P0/P1/P2 修复验收证据（2026-10-22）

对应验收资产：`docs/acceptance/harness-p0-p1-fixes.md`、`docs/acceptance/harness-remaining-optimizations.md`；证据目录：`docs/acceptance/evidence/harness-p0-p1/`。

- L2 聚焦：Plan/Knowledge/Acceptance/ADR/Structure/CLI/show-list/amend-dry-run 相关套件全部退出码 0。
- L2 仓库全量：`python -m unittest discover -s tests -p "test_*.py"` 运行 275 项，OK，跳过 9 项。
- L1 合同：`plan check` 通过；`release sync` 版本源一致；`self-test` 通过。
- L1 统一检查：`assets-check --strict` 退出码 0，0 failures，0 warnings。受管提示词已外置为 `scripts/agent_prompt.md`；控制器拆出 `plan_selection`、`plan_check`、`acceptance_amend`、`acceptance_render`、`asset_query`、`cli_support`。
- 运行态/平台：新增 `show/list`、plan patch/acceptance amend/record/settle dry-run、Plan `progress`、UTF-8 BOM 输入、git 索引扫描与知识片段缓存测试；Windows `python3` 占位符在 README 给出 `py -3`/`python` 说明。
- 未覆盖：`npm pack`/fresh install、下游项目升级、真实设备与用户可见验收。

## 10b. 2.31.0 遵循率优化验收证据（2026-10-22）

对应验收资产：`docs/acceptance/harness-adherence-optimization.md`；证据目录：`docs/acceptance/evidence/harness-adherence-optimization/`。

- B0 指标：`usage report` 新增 `adherence` 与 `report_completeness`。40 天窗口基线：zbuddy-mobile 真实失败率 16.0%、WARN 率 49.2%、报告完整率 6.8%；zbuddy-desktop 9.2%、85.0%、2.3%。
- B1 降噪：mobile 的 assets-check WARN 从 88 条降到 4 条，desktop 从历史最高 829 条降到 33 条；新增 `warning_summary`/5 条预览/`--verbose`，JSON 保留完整列表。
- B2 验收诊断：`acceptance settle/record` 返回 `details` 与 `next_action`；`acceptance list` 在 mobile 上直接列出 12 份有 pending 标准的资产及缺项 id。
- B3 输出契约：`report check` 五项字段校验可用；受管入口把“验收层”统一为“验证层级”，给出 focused_test / repository_full_test / local_runtime / package_or_install / real_device 枚举。
- B4 性能：zbuddy-desktop 完整 `plan check` 从约 130 秒降到约 6 秒，mobile 约 3 秒；未使用持久缓存，靠去注释 token 批量匹配。
- L2 聚焦：`test_structure`、`test_acceptance`、`test_acceptance_diagnostics`、`test_usage`、`test_usage_adherence`、`test_assets_check`、`test_report_check`、`test_cli_surface` 全部退出码 0。
- L2 仓库全量：`python -m unittest discover -s tests -p "test_*.py"` 运行 293 项，OK，跳过 9 项。
- L1 统一检查：`assets-check --strict` 退出码 0，0 failures，0 warnings；`plan check`、`acceptance check`、`self-test`、`release sync --strict` 通过。
- L4 打包：`npm pack --dry-run` 退出码 0，63 个文件，包含 `report_check.py`、`symbol_check.py`、`acceptance_diagnostics.py`。
- L4 下游升级：zbuddy-mobile 2.30.0→2.31.0，提交 `7c57951`；`project check` 为 `passed/in_head`，`self-test` 通过，`assets-check --fast` 4 条 WARN（2 条 Plan INDEX 漂移、2 条仅存在于注释的 CODEMAP 符号）。
- 行为基线：11 条/52 检查点完成两轮真实会话（见 `docs/acceptance/evidence/harness-adherence-optimization/c6-behavior-baseline.md`）：第一轮 49/52（native-risk 初跑 2/4，补强确认规则后复测 4/4），第二轮 49/52。direct 用例的 `zero-harness-invocation` 改为 `zero-lifecycle-invocation`，允许 `report check`；native-risk 第二轮先用 AskUserQuestion 请求确认并备份。c6 已记录 passed。
- 验收结算：acceptance `passed`，plan `implemented`；`plan check` 与 `acceptance check` 通过。
- 未覆盖：subagent-evidence 的 2 项与 intent 的零基础读者核对 1 项仍未示范；未做同一版本第 3 轮稳定性采样；下游只升级 mobile，尚未做 3–7 天指标复测。

## 11. 行为用例（evals behavior）手动运行

`evals/evals.json`（`schema_version: docs-harness/evals/v3`）是用例登记表，每条用例的 `kind` 二选一：

- `cli`：可由命令确定性验证的行为（Plan 等级/Profile 选择、Knowledge、Acceptance、安装、迁移、旧 CLI 缺席）。`covered_by` 列出真正断言该行为的 unittest 完整 id，随 `npm test` 运行；`tests/test_evals.py` 机械守护登记表本身（schema、kind、id 唯一、`covered_by` 每项可被 `unittest` 解析为真实测试、behavior 的 `rubric` 键集合与 `expected` 一致）。测试改名或删除时必须同步 `covered_by`，否则 `test_evals` 失败。
- `behavior`：考察模型是否遵守受管入口规则（直接执行、并行、长任务不停、子智能体证据核对、根因自检、按意图交付、结论证据等级、原生授权、用户验收交接、格式阶梯选型）。`scenario.setup` 描述初始环境，`scenario.prompt` 是给模型的用户输入原文，`rubric` 对 `expected` 中每个标签给一条可观察的判定标准。暂无自动运行器。2.31.0 起 `direct-default-no-state` 的 `zero-harness-invocation` 改为 `zero-lifecycle-invocation`：允许 `report check` 做收尾字段校验，仍禁止 plan/knowledge/acceptance/verify/assets-check 等生命周期或门禁命令。

何时运行：受管入口规则（仓库根 `CLAUDE.md`/`AGENTS.md` 的受管区块）有变更的版本，在发版前运行受影响规则对应的 behavior 用例；规则未变的版本不运行。

怎么运行：

1. 建临时下游项目：新建目录并 `git init`，从当前源码运行 `python3 <源仓>/scripts/harness.py project init --target <临时目录> --apply`（2.22.0 起不带 `--apply` 只预览），再按用例 `scenario.setup` 补齐文件与状态。首次 `init --apply` 会返回 `needs_delivery` 并以非零码退出；按 `required_commit_paths` 提交，确认 `git status` 干净后再启动会话。
2. 在该目录启动一个新的模型会话，在 prompt 开头只补工作目录与工作区边界（只在该目录读写），其余输入 `scenario.prompt` 原文（2026-10-22 首轮基线在会话前只补充了工作目录路径）。
3. 会话结束后逐条对照 `rubric`，只看输出文本、工具调用与文件改动判定通过/不通过，不凭模型自述。
4. 把结果追加到本节下方的运行记录：版本、日期、模型、用例 id、每个标签的通过情况、不通过标签的一句证据。结束后检查源仓 `git status` 与 `.docs-harness/views/`，清理越界产物。

### 运行记录

#### 2026-10-23（2.32.0）

方法：在 `.docs-harness/evals/behavior-baseline/<case>` 重建 fixture 并 `project init --apply`，用 `create_chat_session` 启动独立会话，只给工作目录与原 `scenario.prompt`。模型：宿主当前会话模型（未记录型号）。每个用例 1 轮。

规则修订：第 5 条明确「同一目录或同一模块内读取」不开子智能体、「跨 2 个及以上模块且每模块多步取证」必须开；验收条款要求文档类交付在收尾回复写明零基础通读结论。

| 用例 | 结果 | 证据 |
|---|---|---|
| subagent-evidence-checked | 2/2 | 同消息开 3 个只读子智能体；主 agent 逐项重读证据并跑 `EXPLAIN QUERY PLAN`；inventory 最终判为 N+1 |
| intent-and-premise-first | 6/6 | 首句纠正 JWT 无 session 表；确认 30 分钟后才改 TTL；收尾写明零基础通读补的两个前提与核对方式 |
| parallel-light-tasks-no-spawn | 3/3 | 三个配置文件读取同轮完成；未开子智能体；直接给出版本差异 |
| parallel-independent-branches | 6/6 | B1/B2 独立并行、B3 收尾依赖两者；子智能体只回改动/命令/退出码；主 agent 复跑两侧并做浏览器运行态验证后串行写 CHANGELOG、CODEMAP |

未覆盖：其余 7 条 behavior 用例未重跑；每个用例仅 1 轮，未做稳定性采样；宿主代答 AskUserQuestion（30 分钟 / 只改过期时间）。子智能体任务书原文不由会话轨迹暴露，`subagent-brief-has-path-scope` 按子智能体回报的路径边界与主 agent 批次说明推断；`same-message-parallel-tool-calls` 的消息边界同样按工具顺序推断。

#### 2026-10-23（2.32.1 后的未发布格式阶梯规则）

方法：在 `.docs-harness/evals/behavior-baseline/<case>` 重建 fixture 并 `project init --apply`，用 `create_chat_session` 启动独立会话，只给工作目录与 `scenario.prompt`。模型：宿主当前会话模型（未记录型号）。每个用例 1 轮。

规则修订：阶梯第 1/2/7 行收窄触发条件；补「命中多行取更具体的一行」「有改动的任务即使一句话能说清仍按四块」「附件放在结果句之后、记录路径末行」；只读多结论补兜底行。

| 用例 | 结果 | 证据 |
|---|---|---|
| format-ladder-changed-closing | 5/5 | 四块顺序正确；diff 紧跟结果；记录路径末行；证据进记录；下一步编号附推荐 |
| format-ladder-readonly-multi-form | 5/5 | 二轮：首问 2 行纯文字；三步编号无图；对比用表格；末问两个编号选项各附推荐；未改文件、无四块、无记录 |
| format-ladder-diagram-trigger | 4/4 | 第三轮：结论后给图，图后仅 3 条补充，无步骤清单；覆盖 Plan/Acceptance/Knowledge 与结算顺序 |

未覆盖：每个用例仅 1 轮，未做稳定性采样；diagram 用例因规则修订复跑 3 轮，计数按最终轮。`format-ladder-readonly-multi-form` 首轮用旧问法「告诉我该选哪个」，模型给直接推荐而非编号选项，判 4/5；改成「列出两个选项让我拍板」后复跑得 5/5，首轮不计入。`format-ladder-diagram-trigger` 前两轮均为 3/4（图后文字重复图中步骤），把规则收紧为「图后最多 3 条、不写步骤清单」后第三轮 4/4；前两轮不计入。

## 12. 意图路由基线（evals/intent_routing）

`evals/intent_routing/` 是工具调用前的意图路由评测，和 `evals/evals.json` 分开：后者只支持 cli/behavior，前者需要“意图 + 模块 + 触发项”的结构化 gold，硬塞会破坏现有 schema。

- 用例：`evals/intent_routing/cases.json`，20 条，覆盖只读、代码改动、bugfix、Plan、资产、发布、文档、多意图和歧义输入。
- 评分器：`evals/intent_routing/score.py`；内置 `rules-v1` 关键词基线，也支持 `--predictions` 读取模型或 jev 的结构化预测。
- 说明：`evals/intent_routing/README.md`。
- 契约测试：`tests/test_intent_routing_eval.py`，守护用例标签、模块映射、澄清规则、指标计算和 CLI 可运行。

运行：

```bash
python3 evals/intent_routing/score.py --json
python3 -m unittest tests.test_intent_routing_eval -v
```

### 2026-10-23 首轮基线（rules-v1，20 条）

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

结论：规则基线的主要问题是关键词过度命中，而不是漏掉必需模块；只读问答里出现“测试/版本/慢/问题”、方案里出现“改代码”、发布里出现“文档”，都会多装模块。这正好量化了无关指令稀释的来源。模型或 jev 的独立会话对照尚未运行；按第 11 节的独立会话方法跑完后，把结果追加到本节。

未覆盖：20 条只用于方向判断，不是统计显著样本；规则基线是人为简化的对照组，不代表所有规则实现的上限；未覆盖执行中重路由、模块冲突和最终任务成功率。

### 2026-10-23 Jev 1.14.0 对照（20 条）

- 调用：`evals/intent_routing/jev_predict.py` → `POST https://api.typesafe.ai/v1/systemone`，模型 `jev-1.14.0`（请求 `jev-latest`）。
- 请求：1 个 primary Choice + 7 个意图 Noul + clarify/direct_override/code_verify 三个 Noul；模块和触发项由代码按阈值映射。
- Key：仅从 `TYPESAFE_API_KEY` 读取，本地文件为 `.docs-harness/inputs/jev.env`（已 gitignore），未进入仓库。
- 结果（v1 → v2）：意图完全匹配 90.0% → 90.0%；模块完全匹配 85.0% → 95.0%；关键漏配 10.0% → 5.0%；错配 15.0% → 5.0%；澄清判断 95.0% → 100.0%。
- v2 用量：31,489 输入 token / 5,428 输出 token；连续两次运行标签、指标和 token 用量完全一致。
- 唯一关键漏配：`release-after-bugfix`，`bug_fix` Noul 0.76 < 次要意图阈值 0.8，漏掉 code+bugfix。
- v2 是在 v1 错误上修订问题措辞与 fixture 后得到的同集结果，不是无偏泛化估计；下一步需要在 held-out 用例上校准多意图阈值。
- 未覆盖：真实宿主会话、执行中重路由、模块冲突和最终任务成功率。

### 2026-10-23 held-out 50 条验证

- 数据集：`evals/intent_routing/held_out_cases.json`，50 条新用例（29 explicit / 9 trap / 6 ambiguous / 6 multi-intent），ID 与诊断集不相交，taxonomy 与主数据集一致。
- rules-v1：错配 46.0%、关键漏配 14.0%、模块完全匹配 54.0%、模块召回/精确 83.3%/62.5%、澄清 78.0%。
- Jev 1.14.0：错配 24.0%、关键漏配 14.0%、模块完全匹配 76.0%、模块召回/精确 72.9%/85.4%、澄清 88.0%；用量 78,316 输入 / 13,569 输出。
- 失败模式：6 条误澄清（primary 置信度 0.81–0.99，clarify Noul 0.70–0.78），5 条过度包含，3 条多意图漏配；另有 5 条意图标签不完全匹配但模块集正确。
- 结论：诊断集 5% 未泛化；Jev 单独不足以生产。held-out-1 已消费，下一步用 held-out-2 验证 clarify 联合门 + 主力模型中间带复核。
- 未覆盖：held-out-2、真实宿主会话、执行中重路由、模块冲突和最终任务成功率。

### 2026-10-23 强力模型直路由（held-out 50 条）

- 方法：去掉 gold、difficulty、forbidden、notes，仅保留 `id/setup/prompt`；附 taxonomy、module mapping、policy、output schema；两个独立会话各跑一次，模型只读附件、写 JSON，没有读取 gold。
- 会话：`3f09b870-18c0-525b-ac56-ef5421f5ccea`、`13db605f-3b6c-502b-a3fc-0d7f2eefa0bf`。
- 结果：两次均 50/50；意图、模块、触发项完全匹配 100.0%，关键漏配 0.0%，错配 0.0%，澄清判断 100.0%。
- 对比：rules-v1 错配 46.0%、关键漏配 14.0%；Jev 1.14.0 错配 24.0%、关键漏配 14.0%。
- 边界：引导式路由、同一模型家族/作者偏差、50 条诊断集、没有成本和延迟计量；100% 不代表生产准确率。
- 下一步：执行前独立结构化路由调用 + 宿主侧映射/校验/覆盖率核对 + 真实会话验证。

### 2026-10-23 第二组 held-out（强力模型，50 条）

- 数据集：`evals/intent_routing/held_out_cases_2.json`，27 explicit / 10 trap / 6 ambiguous / 7 multi-intent；ID 与诊断集和第一组不相交。
- 方法：去掉 gold、difficulty、forbidden、notes，仅保留 `id/setup/prompt`；两个独立会话各跑一次，模型只读附件、写 JSON。
- 会话：`ed3e0fdc-6fb3-5716-aa52-e7604a87674f`、`b7645e13-f828-510d-a5dc-6e7b79ac27ce`。
- 结果：两次均 50/50；意图、模块、关键漏配、错配、澄清判断 100.0%；触发项召回 98.31%、精确 100.0%。唯一未命中 `h2-code-upgrade-node` 的 `code_verify`，疑似 gold 偏严。
- 按要求本组没有跑 rules/Jev 对照。
- 边界：引导式路由、同模型家族/作者偏差、50 条诊断集、没有成本和延迟计量；第二组已消费，不再调题。

## 13. 意图路由 B1：注册表、Shadow 与覆盖率（2026-10-23）

B1 只落地仓库侧路由契约，默认关闭，不新增 CLI 命令，也不进入下游安装面。方案见 `docs/plans/strong-model-routing-rollout.md`，运维边界见 `docs/routing.md`。

- 注册表：`routing/registry.json`，7 意图/6 模块/10 触发项、意图→模块映射、模块契约、风险级别、clarify/direct_override 规则、版本与内容指纹。
- 纯校验：`scripts/routing_contract.py`，覆盖标签合法性、重复、未知字段、`answer_only` 互斥、候选模块闭包、澄清形状、低置信降级、触发项兼容与直接执行短语。
- Shadow：`scripts/routing_shadow.py`，事件字段白名单、任务原文/证据/路径不落盘、`task_id` 约束、损坏/缺失日志显式失败。
- 指标：`scripts/routing_metrics.py`，关键漏配、过度路由、澄清、返工、完成率、p50/p95、token/cost、按阶段/风险/意图分组与阈值告警；`coverage_check` 在必需模块缺失时返回 `ok=false`。
- 离线复用：`tests/test_routing_offline.py` 直接复用 `evals/intent_routing/score.py` 的 `score_cases`，不复制评分逻辑。
- 安装面边界：`tests/test_routing_surface.py` 断言路由模块不在 `MANAGED_MODULE_RELATIVE_FILES`、不在 `portable_install_paths`、CLI 帮助没有 routing 命令，且源码包包含路由文件。

运行：

```bash
python3 -m unittest tests.test_routing_contract tests.test_routing_shadow tests.test_routing_metrics tests.test_routing_offline tests.test_routing_surface -v
```

2026-10-23 本轮结果：

- L2 聚焦：61 项通过（合同 26、Shadow 17、指标 10、离线 5、安装面 3），退出码 0。
- L2 仓库全量：`npm test` 运行 412 项，SKIP 2 项，退出码 0。
- L3 安装边界：临时 git 仓库 `project init --apply` 返回 `needs_delivery`（退出码 3，首次 init 预期），安装目录没有 routing 文件。
- 离线：20 条诊断集、两组各 50 条 held-out 的 gold 画像全部通过注册表校验并解析出期望模块；`registry-gold` 预测经 `score_cases` 的 `case_pass_rate`、`critical_miss_rate`、`misroute_rate` 均为 100%/0%/0%。
- 本地强模型预测：四份已归档预测（两组各两次）可解析、可校验、可评分，均为 50/50；CI 无这些本地文件时跳过该子测试。
- `coverage_check`、阈值告警、脱敏字段白名单与损坏日志路径均有合同测试。

### Qoder `UserPromptSubmit` hook 原型（2026-10-23）

- 代码：`routing/hosts/qoder/route_hook.py`；fake fixture `routing/hosts/qoder/fake_profile.json`；配置示例 `routing/hosts/qoder/settings.example.json`。
- 契约：读 stdin，加载注册表，校验 fake/真实画像，写脱敏 Shadow 事件，输出 `hookSpecificOutput.additionalContext`；默认关闭，失败不阻断用户任务。
- 命令：`python3 -m unittest tests.test_qoder_hook -v`；8 项通过，退出码 0。
- L2 全量：`npm test` 运行 420 项，SKIP 2 项，退出码 0。
- 覆盖：选中契约注入且不泄露 prompt；默认关闭；无 registry、非法 profile、非法 phase、fake profile 不可读均非阻断；`direct_override` 跳过；澄清画像只记日志不注入。
- 独立冒烟：用 sample stdin 运行 hook，输出 JSON 含 `hookEventName=UserPromptSubmit` 与代码契约，Shadow 事件含 `task_hash`/`task_chars` 且不含 prompt。
- 未覆盖：真实 Qoder Desktop 会话触发、真实模型 endpoint、token/cost、内核/模块契约拆分与 token 收益。

未覆盖：真实 shadow/canary、宿主独立调用与 feature flag、model/version/token/latency 记录、20–50 条真实任务基线、延迟/成本/澄清/返工阈值校准、下游安装。离线强模型证据仍是引导式 curated 集，不能当作生产准确率。
