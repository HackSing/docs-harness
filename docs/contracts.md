# Docs Harness 2.1.0 产品合同

本文件只描述 2.1.0 当前能力。1.x 的 Run、Gate、Evidence、Verify、Readmission、规则和后台 Job 已从可运行合同移除；旧项目统一按 [2.0.0 单向迁移指南](migrations/v2.0.0.md) 升级。

## 1. 默认合同

普通任务由 Codex 直接执行。默认不调用 Harness，不创建任务包，不生成 Gate，不自动加载知识或方案，也不建立任务遥测。

用户明确关闭 Harness 时必须尊重。Harness 未安装、不可用或全部可选能力关闭时，普通问答、只读检查、代码修改、构建和测试仍能完整进行。

2.1.0 只有三项相互独立的按需能力：

```text
knowledge query
plan select | plan create
acceptance record
```

## 2. 按需知识合同

### 2.1 触发条件

只有缺少的项目事实会改变目标、范围、方案或验收时，才调用 `knowledge query`。当前源码、符号、运行态和真实产物优先于知识摘要；已经能从当前真源回答时立即停止。

### 2.2 输入

- `--query`：具体缺失事实，必填；
- `--scope`：可选项目内范围；
- `--limit`：1–10 条；
- `--max-chars`：500–12000 字符。

默认排除 `docs/plans/`、`docs/reviews/` 和 `docs/history/`。显式 scope 可以读取当前任务指定的方案，但历史目录始终不参与自动候选。

### 2.3 模型可见输出

```json
{
  "mode": "knowledge_assist",
  "facts": [{"text": "...", "ref": "path:line"}],
  "refs": ["path:line"],
  "constraints": [],
  "conflicts": [],
  "conflict_check": "not_evaluated_against_runtime",
  "omitted": {"count": 0, "reason": null},
  "source_priority": "current_source_and_runtime_remain_authoritative"
}
```

未与真实运行态比对时必须明确 `conflict_check=not_evaluated_against_runtime`。该命令只读，不写知识正文、运行状态或长期记忆。

## 3. 方案合同

### 3.1 选择维度

- `plan_level=none|brief|full`；
- `plan_profile=general|frontend_ui|backend_service|bugfix|architecture|migration_release`。

用户明确选择优先。自动选择只使用结构化的复杂度、实际修改面、跨模块程度、风险和“用户要求方案”信号，不从任务正文关键词猜模板。

- `none`：直接执行；
- `brief`：目标、范围、步骤、验收；
- `full`：全面通用字段，加一个主领域 Profile。

字段与任务无关时不出现，不填写空数组、“无”或“不适用”。复合任务仍只有一份主方案，次级 Profile 只补会改变执行或验收的字段。

### 3.2 冻结与执行

`plan create` 只接受未篡改的 `docs-harness/plan-selection/v2`、只含已注册字段的内容 JSON，以及项目内无符号链接逃逸的输出路径。

成功结果写入 `docs-harness/plan/v2` 与选择指纹。`full + bugfix` 额外要求以下结构化字段：

```json
{
  "affected_modules": ["module-a"],
  "verification_scope": {
    "mode": "affected_modules",
    "commands": ["pytest tests/module_a"],
    "reused_passed_evidence": []
  },
  "full_regression_trigger": {
    "required": false,
    "reason_codes": [],
    "rationale": "影响分析未跨出 module-a"
  },
  "failure_attribution": {
    "categories": ["change_related", "unrelated", "pre_existing", "environment", "flaky"],
    "separate_non_change_failures": true,
    "evidence_required": true
  }
}
```

`repository_full` 只接受 `cross_module_change|public_contract_change|shared_infrastructure_change|dependency_or_shared_fixture_change|release_gate` 原因码；`affected_modules` 模式必须声明 `required=false` 且不得携带全量原因码。上述四项进入 `execution_projection`，其余模板选择过程、候选讨论或控制器状态不进入执行上下文。

### 3.3 ADR

架构 Profile 必须包含 `adr_decision`。主 Codex 是唯一写作者；复杂、高风险、跨模块或不可逆决策可以使用只读子智能体复审。已接受 ADR 不原地改写决策，后续通过新 ADR 的 `Supersedes` 保留历史。

## 4. 真实验收合同

`acceptance record` 使用 `docs-harness/acceptance-input/v3`，只登记已经发生的验收，不自动执行测试，也不决定应该跑全量还是聚焦验证。

三种验收类型必须分开：

- `contract_check`：范围、格式和记录一致性；
- `behavior_acceptance`：测试、接口、应用、服务、构建、包或安装的直接行为证据；
- `user_acceptance`：主观体验、权限、硬件和 Codex 无法判断的最终结果。

验收层级：

| 层级 | 含义 |
|---|---|
| L1 | 源码、类型、编译或静态合同一致 |
| L2 | 聚焦测试或仓库级全量测试行为成立 |
| L3 | 本地应用或服务真实流程成立 |
| L4 | 构建、包或安装产物成立 |
| L5 | 真实设备行为成立，或用户可见、权限和主观体验经用户确认 |

Behavior Acceptance 必须声明下列 `evidence_layer`，且只能使用固定 L 层；任一证据层通过都不能替代其他层：

| evidence_layer | 固定层级 | 证明边界 |
|---|---|---|
| `focused_test` | L2 | 受影响模块或目标行为 |
| `repository_full_test` | L2 | 当前仓库全量回归 |
| `local_runtime` | L3 | 本地应用或服务流程 |
| `package_or_install` | L4 | 包、安装器或已安装产物 |
| `real_device` | L5 | 真实设备上的客观行为 |

L1 不能声明行为正确。真实设备 Behavior Acceptance 可以记录 L5 客观行为，但不能替代 User Acceptance；独立 CLI 不接受 `user_acceptance + passed`，只能记录 `user_pending`。

通过必须提供实际方法和项目内已存在的常规证据文件。失败必须提供总体原因、下一步和非空 `failure_attributions[]`；每项包含 `category`、`summary`、`blocking` 与非空 `evidence_refs`，类别只允许 `change_related|unrelated|pre_existing|environment|flaky`。归因重复、类别未知或证据不存在时拒绝记录。`user_pending` 必须包含已自动验证内容、待用户检查项、最短步骤和 `environment_ready=true`。

## 5. 风险、授权与数据边界

Docs Harness 不提供任务级 Gate、动作 preflight、授权文件、Host Adapter 或 usage metrics。Git 写入、删除、发布、安装和外部系统写入使用 Codex 原生授权与沙箱。

Harness 不采集用户授权、不解析 Codex usage、不保存原始用户聊天或模型推理。需要评估产品效果时，另行进行明确的只读抽样审查，不能让每个业务任务承担遥测成本。

## 6. 安装合同

项目安装只提供：

- 受管的 direct-first `AGENTS.md` 与 `CLAUDE.md` 区块；
- `scripts/harness.py`；
- 版本化 `plan-templates/`；
- `.docs-harness/config.json`（`docs-harness/project-config/v6`）。

fresh init 不创建项目知识正文、规则目录或任务 Runtime，不自动启动知识、ADR、Changelog、TODO 或后台治理 Job。upgrade 清理指纹归属明确的旧规则、已识别知识地图、旧版本受管区块和旧 Runtime；项目文档、质量账本、已修改或归属不明文件保留。

## 7. 迁移与移除边界

`run|context|progress|verify|task|background|authorization`、`--legacy-opt-in` 和知识维护 Job 已从 2.x CLI 与控制器删除。2.x 不读取、创建、继续或验证 1.x 任务状态；旧项目只通过 `project upgrade` 执行单向迁移。

旧规则目录和 1.x 状态机测试不进入源码当前产品面或 npm 包。`docs/history/` 只在仓库中保留历史证据，不进入默认知识检索和安装包。完整清理、保留和失败关闭规则见 [2.0.0 迁移指南](migrations/v2.0.0.md)。
