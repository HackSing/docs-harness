# Docs Harness 2.7.1 架构

本文件只描述当前产品架构。1.x 控制器状态机已经退出 2.x 可运行架构。

## 1. 默认架构

```text
Codex Direct Executor
├─ Optional Knowledge Lifecycle Manager
├─ Optional Plan Lifecycle Manager
├─ Optional Acceptance Lifecycle Manager
└─ Asset Governance Checker（按已有资产启用）
```

- Codex Direct Executor 是普通任务入口。Harness 未安装或全部可选能力关闭时，任务仍可完整执行。
- Knowledge Lifecycle Manager 管理带证据的事实创建、修订、查询、冲突、替代与归档；启动时不自动生成事实。
- Plan Lifecycle Manager 按复杂度与领域选择模板，并管理方案生成、索引、完成和归档；简单任务不生成方案。
- Acceptance Lifecycle Manager 先定义验收目标和标准，再逐条记录已发生的真实验收，支持重验、结项与归档；不运行旧合同补证循环。
- 高风险动作使用 Codex 原生授权与沙箱，Harness 不建立 Gate、preflight、Host Adapter 或 usage 采集层。

## 2. 数据流

### 2.1 直接任务

```text
用户目标 → Codex 读取当前真源 → 执行 → 最小充分验收 → 回复用户
```

Harness 调用数为 0。

### 2.2 知识辅助

```text
具体缺失事实 → 受管事实 + 有界文档检索 → facts + refs + conflicts → Codex

当前证据 → knowledge create/update → JSON + Markdown + INDEX
→ query/check → supersede/deprecate → archive
```

候选、评分、检索历史和历史方案不进入模型上下文。当前源码和运行态始终高于知识摘要。

### 2.3 方案辅助

```text
结构化复杂度与修改面 → plan select → 模型填写已选字段 → plan create
→ JSON + Markdown + INDEX → execution_projection → Codex 执行
→ Knowledge/Acceptance 先结算 → plan settle 治理终验
→ 已实施追溯或废弃归档 → assets-check
```

执行阶段不继承模板选择过程和无关字段。

### 2.4 验收生命周期

```text
Plan/Knowledge 引用 + 验收目标与标准 → acceptance create
→ 自动登记 Plan.acceptance_refs
→ 已发生的聚焦/全量测试、运行、包/安装、真实设备或用户交接事实
→ acceptance record → 标准与总体状态聚合 → reaccept/settle/check/archive
```

记录器不替 Codex 决定测试，不自动启动环境，也不把 Contract Check 提升为 Behavior Acceptance。`focused_test`、`repository_full_test`、`local_runtime`、`package_or_install` 与 `real_device` 分别记录，不能互相提升或替代；用户主观确认仍是独立合同。

### 2.5 多重治理执行面

```text
领域命令边界校验
→ Plan v3 声明合同与 settle 终验
→ assets-check 聚合三类资产与正反向引用
→ pre-commit --fast（FAIL 阻断、WARN 提示）
→ GitHub CI --strict（WARN 也阻断）
```

检查只消费已存在资产和 Plan 明确声明，不读取 Git diff 或提交信息推断是否应创建资产。

## 3. 存储边界

- 方案模板位于 `plan-templates/`；正式方案固定写入 `docs/plans/`，冻结 JSON 与可审查 Markdown 同名共存，`docs/INDEX.md` 受管区块提供发现入口。
- Knowledge 资产位于 `docs/knowledge/`，Acceptance 目标资产位于 `docs/acceptance/`，均使用同名 JSON/Markdown 和独立 INDEX 区块。
- 不关联目标的兼容验收记录仍位于 Git 元数据下的 `docs-harness/v2/`，非 Git 项目位于 `.docs-harness/v2/`。
- 不建立任务级 usage、授权或控制遥测。
- 历史设计资料位于 `docs/history/`，不进入 npm 对外文档集合和默认知识候选。

## 4. 安装边界

`project init` 同步受管宿主说明、控制器、资产模块、方案模板、git 钩子和 v9 配置，并初始化 `docs/plans/`、`docs/knowledge/`、`docs/acceptance/`、各自 archive 与 `docs/INDEX.md` 独立索引区块。`project upgrade` 先预览、补齐三类体系，再清理所有权明确的旧规则、知识地图、受管版本区块和旧 Runtime；用户资产、项目正文与归属不明文件不进入自动删除范围。

安装不创建项目知识事实或验收结论，不自动启动知识 bootstrap 或后台治理 Job；三类索引只维护各自独立标记区块，不修改项目自己的索引正文。

## 5. ADR 职责

架构 Profile 必须明确 `adr_decision`。主 Codex 读取当前代码、架构文档和相关 ADR，比较候选并写入最终 ADR。复杂、高风险、跨模块或不可逆决策可以由只读子智能体复审；主 Codex 仍是唯一写作者。已接受 ADR 通过新 ADR 的 supersession 链更新，不原地重写历史。

## 6. 1.x 退出与迁移隔离

旧 Run、Gate、Evidence、Verify、Readmission、后台 Job 和 Receipt 的运行实现与 CLI 入口已经删除；`--legacy-opt-in` 不存在。旧规则和 Runtime 只由 upgrade 迁移器按所有权识别并清理。2.x Runtime 只用于可选 `acceptance record`，不承担任务准入或项目管理。

## 7. 事实来源

- `scripts/harness.py`
- `scripts/managed_assets.py`
- `scripts/asset_checks.py`
- `scripts/plan_governance.py`
- `scripts/knowledge_assets.py`
- `scripts/acceptance_assets.py`
- `scripts/adr_assets.py`
- `docs/contracts.md`
- `SKILL.md`
- `package.json`
