# Docs Harness 2.0.0

Docs Harness 2.0.0 的核心变化是：**Codex 默认直接工作，Harness 只在确实能增加价值时提供一项独立能力。**

1.x 把任务准入、Gate、上下文、Plan、Evidence、Verify 和 Readmission 串成一条强制流程。实际项目审查发现，这条控制链会把大量项目管理工作、重复状态和补证动作放进模型上下文，导致用户任务更慢、注意力被分散。2.0.0 不再优化这条强制链，而是改变默认产品合同。

## 默认任务流程

```text
用户提出任务
→ Codex 直接理解和读取必要文件
→ 需要时单独查询知识或生成方案
→ Codex 执行任务
→ 运行能直接覆盖本次变化的最小真实验收
→ 自动不了的部分准备好环境并交给用户验收
→ 明确回复已验证、待用户验证和未验证层级
```

普通任务 Harness 调用数应为 0。没有安装 Docs Harness，Codex 也必须能完整完成普通问答、只读检查、代码修改、构建和测试。

## 默认模式与三项按需能力

| 能力 | 何时使用 | 不做什么 |
|---|---|---|
| 直接模式 | 默认所有普通任务 | 不创建任务包、Gate、Plan 或 Verify 循环 |
| `knowledge query` | 缺少项目事实会改变目标、范围、方案或验收 | 不自动注入、不全量加载、不自动维护知识 |
| `plan select/create` | 复杂、跨模块、高风险或用户明确要求方案 | 不要求简单任务填表，不拼接多份完整模板 |
| `acceptance record` | 已经执行真实测试、运行、构建、安装或用户验收 | 不用合同检查代替功能正确性 |

这些能力可以单独启用或全部关闭。关闭后仍回到 Codex 直接执行，不需要恢复 1.x 强制流程。

## 快速使用

### 按需查项目知识

先搜索当前源码、符号和运行态。仍缺架构、产品原因或历史约束时：

```bash
python3 scripts/harness.py knowledge query --target . \
  --query "语音退出流程由哪些模块负责" --json
```

可用 `--scope` 限定知识文件，用 `--limit` 和 `--max-chars` 控制返回量。响应只包含可消费事实、引用、约束、冲突状态和省略数量。

### 选择方案模板

```bash
python3 scripts/harness.py plan select --target . \
  --complexity complex --surface frontend_ui --json
```

方案深度：

- `none`：无方案，直接执行；
- `brief`：目标、范围、步骤、验收；
- `full`：全面通用结构，并叠加真实相关的领域字段。

领域 Profile：

- `general`：通用复杂任务；
- `frontend_ui`：用户流程、完整状态、交互、视觉、可访问性和真实页面验收；
- `backend_service`：接口、数据、一致性、失败、幂等、安全、性能和服务验收；
- `bugfix`：精确复现、完整时间线、首次偏离、根因和回归路径；
- `architecture`：候选、取舍、决策、边界、兼容、迁移、回滚和 ADR 处理；
- `migration_release`：版本、产物、灰度、数据安全、停止条件、回滚和交付层。

选择不读取任务关键词猜测，而由用户明确选择或宿主按复杂度、实际修改面和验收难度提交结构化信号。模型填好选择返回的字段后冻结：

```bash
python3 scripts/harness.py plan create --target . \
  --selection selection.json --content content.json \
  --output docs/plans/task.json --json
```

### 风险与授权边界

Docs Harness 不提供第二套 Gate、preflight 或授权系统。Git 写入、删除、发布、安装和外部写入等高风险动作完全使用 Codex 原生授权与沙箱；Harness 不介入，也不向模型注入额外控制内容。

### 记录真实验收

```bash
python3 scripts/harness.py acceptance record --target . \
  --input acceptance.json --json
```

验收层级互不替代：

| 层级 | 能证明什么 |
|---|---|
| L1 | 源码、类型、编译或静态合同一致 |
| L2 | 聚焦行为在测试、接口、组件或命令中成立 |
| L3 | 本地应用或服务真实流程成立 |
| L4 | 构建、包或安装产物成立 |
| L5 | 用户可见、权限、硬件或主观体验成立 |

独立 CLI 不接受 `user_acceptance + passed` 的自我声明，只记录 `user_pending`；用户确认完成必须由可信宿主通道或最终用户界面登记。

Contract Check 只证明范围、格式或授权一致，永远不返回 `behavior_verified`。失败响应只包含真实失败原因和下一步。Codex 无法完成 L5 时，必须先准备运行环境，再返回最短用户验收步骤。

## ADR 规则

只有会长期约束架构边界、公共接口、兼容、安全、数据或基础设施的决策才写 ADR。普通 Bug、局部重构、临时实验和 UI 样式不写。

主 Codex 负责读取相关源码和既有 ADR、比较候选、写入最终 ADR。复杂、高风险、跨模块或不可逆决策可选使用只读子智能体复审；子智能体不直接写文件。已接受 ADR 不原地改写决策，后续通过新 ADR 的 `Supersedes` 建立替代关系。

## 2.0.0 单向迁移边界

2.0.0 不兼容运行旧文档系统。`run|context|progress|verify|task|background|authorization` 与 `--legacy-opt-in` 均已从 CLI 和控制器删除；旧 Gate、规则、后台 Job 和 Runtime 不再参与任务。升级会清理所有权明确的旧工件，保留项目文档和归属不明内容，详见 [2.0.0 迁移指南](docs/migrations/v2.0.0.md)。

## 安装与升级

```bash
python3 <docs-harness-2.0.0-source>/scripts/harness.py project init --target <project> --json
python3 <docs-harness-2.0.0-source>/scripts/harness.py project upgrade --target <project> --json
python3 <docs-harness-2.0.0-source>/scripts/harness.py project upgrade --target <project> --apply --json
```

pre-2.0 项目必须用新取得的 2.0.0 来源包执行 upgrade；不能调用目标项目里仍是旧版本的 scripts/harness.py 来完成换代。安装后的项目脚本可用于 project check、project diff、知识查询、方案和验收。

2.0.0 安装内容包括：

- 受管 `AGENTS.md` 与 `CLAUDE.md` 区块；
- `scripts/harness.py`；
- `plan-templates/` 版本化模板；
- `.docs-harness/config.json`（`project-config/v6`）。

fresh init 不创建项目知识正文，不自动派发知识、ADR、Changelog、TODO 或后台治理 Job，不修改 `.gitignore`，不提交、不推送、不发布。旧项目 upgrade 会先只读预览，再删除指纹归属明确的旧规则、已识别知识地图、旧版本受管区块和旧 Runtime；项目正文、质量账本、已修改或归属不明文件一律保留并报告。

## 验证与发布边界

源码、聚焦测试、全量回归、npm 包、fresh clone、Git 提交、远端推送、下游同步、本机安装和用户可见验收是不同层。任何一层通过都不能代替后续层。

```bash
npm test
npm run self-test
npm run pack:check
```

本地版本号为 2.0.0 不等于已经提交、推送、发布、同步到 ZBuddy 或完成真实用户验收。

文档入口见 [docs/README.md](docs/README.md)，详细合同见 [docs/contracts.md](docs/contracts.md)，完整产品与实施依据见 [2.0.0 方案](docs/plans/docs-harness-v2.0.0-direct-first-plan.md)。
