> 状态：已实施-仅追溯（代码已是真源，2026-08-14 核对）
<!-- docs-harness:plan-document/v1 -->

# Docs Harness Plan、Knowledge、Acceptance 资产全生命周期方案

- 冻结合同：`sha256:fa81ed227ee8b3785aec07abeb95488f14365845362eaa83af362a52d6a36d4d`
- 关键符号：`knowledge_create`、`knowledge_settle`、`acceptance_create`、`acceptance_settle`

## 背景

Docs Harness 2.5.0 已补齐 Plan 的创建、冻结、索引、结项、归档和检查，但 Knowledge 仍只有只读 query，Acceptance 仍只有脱离目标资产的单次 record。三类能力没有形成从事实、方案到验收再回流事实的完整资产闭环，也无法在新装和升级时为项目初始化对应的资产目录。

## 目标

让 Plan、Knowledge、Acceptance 分别拥有可创建、读取、更新或记录、结项、归档、索引和检查的完整资产生命周期，并通过显式引用形成 Knowledge → Plan → Acceptance → Knowledge 的产品闭环；完成 Docs Harness 源码、契约、安装升级与下游 Avatanel 验证。

## 非目标

- 不恢复 pre-2.0 的 Run、Gate、后台 Job 或第二套任务状态机
- 不让模型在没有证据时自动生成或更新项目事实
- 不把合同检查、源码测试、构建、安装、真实运行和用户可见验收混成同一层
- 不自动提交或推送 Docs Harness 与 Avatanel 的 Git 改动

## 成功标准

- init/upgrade 为三类资产建立 docs/plans、docs/knowledge、docs/acceptance 及各自 archive，并维护 docs/INDEX 的托管索引块
- Knowledge 支持 create、update、query、settle、check，事实必须绑定可验证 source_refs，修订可追溯，同键冲突可见，废弃或被取代资产可归档
- Acceptance 支持 create、record、settle、check，可关联 Plan，逐条维护验收标准、证据层级和状态；用户验收通过必须经显式 user-confirmed 入口
- Plan 继续使用 2.5.0 生命周期，并在提示词与文档中和 Knowledge、Acceptance 串成线性工作流
- 源码全量测试、打包检查、release sync、self-test、严格文档检查通过
- Avatanel 升级后 source diff 为零，三类目录与索引存在，安装副本能完成 Knowledge 和 Acceptance 的最小真实生命周期验证

## 执行范围

- scripts/harness.py 及新增的可复用资产生命周期模块
- tests/test_v2_direct.py 与必要的新测试夹具
- VERSION、package.json、SKILL.md、README、CHANGELOG、架构/契约/测试文档与托管提示词
- 安装、升级、diff、check、uninstall、package 与 self-test 消费链
- /Users/aiware/projects/avatanel 的本地升级和非业务层验证

## 执行内容

- 抽取通用资产目录、JSON/Markdown 投影、索引块、归档和指纹校验能力，避免 Plan、Knowledge、Acceptance 各写一套重复 IO
- 定义 Knowledge v1 输入与资产契约：标题、关键符号、摘要、带稳定 id 的事实、source_refs、修订号、替代关系和指纹；create/update/settle/check 均在所有者边界校验
- 扩展 query：优先返回当前可审计 Knowledge 事实，同时保留按需检索现有项目文档的兼容能力；同 fact id 不同 statement 显式报告 conflicts
- 定义 Acceptance v1 目标资产：标题、关键符号、可选 plan_ref、criteria；record 复用 v3 证据层规则并更新对应 criterion 与总体状态，settle 管理通过、失败、取代与归档
- 为用户验收通过增加显式 --user-confirmed 门禁和确认字段，托管提示词明确只有收到用户原话确认后才能使用
- 把三类结构纳入 init/upgrade/diff/check/uninstall 保留语义、docs-check 或专用 check、打包清单和 self-test
- 升级版本到 2.6.0，同步全部版本真源和文档，再升级 Avatanel 验证

## 验收方案

- 先以新增聚焦测试验证 Knowledge 与 Acceptance 的 create/update/record/settle/check、冲突、证据缺失、用户确认门禁和归档链接
- 验证生产者到消费者链：资产写入 → Markdown 投影 → INDEX → query/check → project diff/check → package/install
- 公共 CLI、安装协议和跨模块契约发生变化，因此执行 npm test 全量回归与 npm run pack:check
- 运行 release sync、self-test、docs-check --strict 和 git diff --check
- 用最终源码升级 Avatanel，验证三类目录/索引、source diff、自检、严格文档检查，并在临时验证项目内跑最小资产生命周期，避免污染 Avatanel 业务文档

## 约束

- 保留两个仓库现有未提交改动，不重置、不清理用户内容
- 不新增第三方依赖，只使用 Python 标准库
- 当前源码和运行态高于 Knowledge 历史资产；检查发现冲突必须显式输出而不是静默覆盖
- 只有证据存在时才能登记通过；用户验收不能由 agent 自行声明
- 新逻辑放入独立模块，避免继续扩大已超单文件红线的历史控制器

## 风险与回滚

- 风险：新增托管文件使旧项目出现 pending_commit；通过 preview、apply、diff 分层展示，不把待提交误报为安装失败
- 风险：结构化 Knowledge 与现有 RepoWiki/Markdown 重叠；保留 query 兼容检索，并只把显式创建的事实视为受管资产
- 风险：Acceptance 状态自动聚合产生过度声明；总体状态只由逐条标准计算，用户验收通过另设显式确认门禁
- 回滚：移除 2.6.0 控制器新增的命令和空目录托管，不删除已产生的 Knowledge/Acceptance 用户资产；uninstall 默认保留三类资产

## 当前约束

- 2.5.0 Plan 已有 JSON 冻结合约、Markdown 投影、INDEX、settle 和 docs-check，必须复用其产品语义
- knowledge query 当前只扫描文档片段且不维护资产
- acceptance record v3 当前写入 Git Runtime，能区分 L1-L5 和 evidence_layer，但没有验收目标、criteria、索引和归档
- scripts/harness.py 是历史单文件控制器，新能力不得继续无边界堆叠

## 候选方案

- 方案 A：只给 Knowledge/Acceptance 增加目录和 README；成本低但没有生命周期，不满足产品目标
- 方案 B：复制 Plan 的 JSON/Markdown/INDEX 逻辑到两个命令组；交付快但形成三套漂移实现
- 方案 C：建立通用资产投影与索引内核，三类资产保留各自领域规则；一次改造面较大，但能形成一致且可维护的完整能力

## 真实取舍

选择方案 C。通用层只负责路径、指纹、投影、索引和归档，不抽象领域状态机；Knowledge 的证据/冲突/修订与 Acceptance 的层级/标准/用户确认仍由各自模块拥有，避免为了复用抹平产品差异。

## 最终决策

Docs Harness 2.6.0 采用三类受管文档资产模型：Plan 延续冻结与结项；Knowledge 为可修订、证据绑定的事实资产；Acceptance 为关联目标与逐条证据记录的验收资产。三者通过路径引用连接，不引入任务运行态。

## 边界与接口

- 通用模块对外只暴露资产结构初始化、索引投影、JSON 指纹、归档移动和 Markdown 链接重写接口
- knowledge create/update/query/settle/check 拥有事实 Schema、source_refs、revision 与 conflict 语义
- acceptance create/record/settle/check 拥有 criteria、L1-L5、evidence_layer、user-confirmed 与总体状态聚合
- project init/upgrade/diff/check 消费三类结构；uninstall 删除控制器但保留用户资产
- 托管提示词只描述当前必需步骤，不把三类生命周期变成所有简单任务的强制流程

## 兼容与迁移

- 保留 knowledge query 原参数与现有文档检索结果结构的核心字段
- 保留 acceptance record --input 的独立记录兼容路径；只有带 --acceptance 时才写入目标资产
- 旧项目升级只新增空结构和托管索引块，不迁移、不删除现有业务文档与历史 Runtime 记录
- Plan 2.5.0 已冻结资产继续可校验和 settle

## 回滚或替代路径

代码层可回退到 2.5.0 控制器；数据层不删除 docs/knowledge 与 docs/acceptance，2.5.0 会把它们当普通项目文档保留。Avatanel 验证只升级托管层，不修改业务源码，必要时可用 2.5.0 来源重新 project upgrade。

## 架构验收

- 新增通用模块函数均小于 60 行，领域校验与 IO 投影分离
- 三类索引块可并存且只修改自己的托管区域，原 docs/INDEX 内容字节级保留
- 任意受管 JSON 被手工篡改后 check 失败，Markdown/INDEX 漂移可定位
- 安装副本不依赖源码仓库额外文件即可运行全部新命令

## ADR 处理

本次不单独新增 ADR；架构决策、边界、备选与取舍完整冻结在本方案，后续代码和 docs/architecture.md 成为现行事实。若未来引入外部 Knowledge 存储或自动用户验收身份体系，再单独立 ADR。

## 源与目标

源为 /Users/aiware/projects/docs-harness 当前 2.5.0 未提交工作树，目标为 Docs Harness 2.6.0 源码与 /Users/aiware/projects/avatanel 的本地安装副本。

## 版本与产物

- 版本真源统一为 2.6.0
- npm 包包含控制器、通用资产模块、模板、契约文档和本方案 JSON/Markdown
- Avatanel 安装副本版本与最终源码控制器指纹一致

## 兼容与灰度

先在 Docs Harness 源项目自升级并通过全量测试、打包和自检，再升级 Avatanel。Avatanel 只验证托管层，若 project diff 非零、self-test 或严格检查失败立即停止，不继续制造下游资产。

## 数据安全

- init/upgrade 只创建缺失目录、README、.gitkeep 和托管索引块
- update 必须校验现有资产指纹和 revision，冲突不覆盖
- settle 归档前重写项目 Markdown 显式链接；不删除 JSON/Markdown
- uninstall 默认保留 Plan、Knowledge、Acceptance 资产

## 监控与停止条件

- 聚焦测试发现 Schema 或状态语义无法向后兼容时停止并重新评估版本边界
- 源码或 Avatanel project diff 无法收敛为零时停止
- 任何检查发现修改了 docs/INDEX 非托管内容或删除用户资产时停止并回滚该批

## 回滚

源码保持未提交，按批次可精确回退新增模块和对应调用；不使用 git reset。Avatanel 如验证失败，保留证据并用明确的 2.5.0 source 做受控回退，仍不删除已存在用户资产。

## 交付层分离

- 方案层：JSON 冻结合约、Markdown 和 INDEX 可发现
- 源码层：实现、测试和文档一致
- 包层：npm pack dry-run 与安装副本依赖闭合
- 项目升级层：Avatanel 托管文件同步、diff/self-test/check 通过
- 业务层：本次不改变 Avatanel 业务代码，不声称其业务功能被验收
- Git 层：不提交、不推送，分别报告两个仓库未提交边界
