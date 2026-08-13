# Docs Harness 2.1.0 架构

本文件只描述当前产品架构。1.x 控制器状态机已经退出 2.x 可运行架构。

## 1. 默认架构

```text
Codex Direct Executor
├─ Optional Knowledge Provider
├─ Optional Plan Selector + Template Registry
└─ Optional Acceptance Recorder
```

- Codex Direct Executor 是普通任务入口。Harness 未安装或全部可选能力关闭时，任务仍可完整执行。
- Knowledge Provider 是显式只读查询器，只返回短事实和引用，不在启动时自动注入或维护知识。
- Plan Selector 按复杂度层级与领域 Profile 选择模板；简单任务不生成方案。
- Acceptance Recorder 只记录已经发生的真实验收，不运行旧合同补证循环。
- 高风险动作使用 Codex 原生授权与沙箱，Harness 不建立 Gate、preflight、Host Adapter 或 usage 采集层。

## 2. 数据流

### 2.1 直接任务

```text
用户目标 → Codex 读取当前真源 → 执行 → 最小充分验收 → 回复用户
```

Harness 调用数为 0。

### 2.2 知识辅助

```text
具体缺失事实 → 有界只读检索 → facts + refs + constraints + conflicts → Codex
```

候选、评分、检索历史和历史方案不进入模型上下文。当前源码和运行态始终高于知识摘要。

### 2.3 方案辅助

```text
结构化复杂度与修改面 → plan select → 模型填写已选字段 → plan create
→ 冻结方案 → execution_projection → Codex 执行
```

执行阶段不继承模板选择过程和无关字段。

### 2.4 验收记录

```text
已发生的聚焦/全量测试、运行、包/安装、真实设备或用户交接事实
→ acceptance record
→ 固定 evidence_layer、最小状态、分项失败归因与证据引用
```

记录器不替 Codex 决定测试，不自动启动环境，也不把 Contract Check 提升为 Behavior Acceptance。`focused_test`、`repository_full_test`、`local_runtime`、`package_or_install` 与 `real_device` 分别记录，不能互相提升或替代；用户主观确认仍是独立合同。

## 3. 存储边界

- 方案模板位于 `plan-templates/`；正式方案写入用户指定的项目内路径。
- 可选验收记录位于 Git 元数据下的 `docs-harness/v2/`，非 Git 项目位于 `.docs-harness/v2/`。
- 不建立任务级 usage、授权或控制遥测。
- 历史设计资料位于 `docs/history/`，不进入 npm 对外文档集合和默认知识候选。

## 4. 安装边界

`project init` 同步受管宿主说明、控制器、方案模板和 v6 配置。`project upgrade` 在同一安装面之外，先预览并清理所有权明确的旧规则、知识地图、受管版本区块和旧 Runtime；项目正文与归属不明文件不进入自动删除范围。

安装不创建项目知识正文，不自动启动知识 bootstrap 或后台治理 Job，也不修改项目自己的文档版本标记。

## 5. ADR 职责

架构 Profile 必须明确 `adr_decision`。主 Codex 读取当前代码、架构文档和相关 ADR，比较候选并写入最终 ADR。复杂、高风险、跨模块或不可逆决策可以由只读子智能体复审；主 Codex 仍是唯一写作者。已接受 ADR 通过新 ADR 的 supersession 链更新，不原地重写历史。

## 6. 1.x 退出与迁移隔离

旧 Run、Gate、Evidence、Verify、Readmission、后台 Job 和 Receipt 的运行实现与 CLI 入口已经删除；`--legacy-opt-in` 不存在。旧规则和 Runtime 只由 upgrade 迁移器按所有权识别并清理。2.x Runtime 只用于可选 `acceptance record`，不承担任务准入或项目管理。

## 7. 事实来源

- `scripts/harness.py`
- `docs/contracts.md`
- `SKILL.md`
- `package.json`
