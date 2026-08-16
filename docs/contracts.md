# Docs Harness 2.7.1 产品合同

本文件只描述 2.7.1 当前能力。1.x 的 Run、Gate、Evidence、Verify、Readmission、规则和后台 Job 已从可运行合同移除；旧项目统一按 [2.0.0 单向迁移指南](migrations/v2.0.0.md) 升级。

## 1. 默认合同

普通任务由 Codex 直接执行。默认不调用 Harness，不创建任务包，不生成 Gate，不自动加载知识或方案，也不建立任务遥测。

用户明确关闭 Harness 时必须尊重。Harness 未安装、不可用或全部可选能力关闭时，普通问答、只读检查、代码修改、构建和测试仍能完整进行。

2.8.0 保留四组相互独立、可串联的按需资产能力，并增加统一检查入口：

```text
knowledge create | update | query | settle | check
plan select | plan create | plan settle | plan check
acceptance create | record | settle | check
adr create | settle | check
assets-check [--fast] [--strict]
```

## 2. 按需知识合同

### 2.1 触发条件

只有缺少的项目事实会改变目标、范围、方案或验收时，才调用 `knowledge query`。当前源码、符号、运行态和真实产物优先于知识摘要；已经能从当前真源回答时立即停止。

### 2.2 输入

- `--query`：具体缺失事实，必填；
- `--scope`：可选项目内范围；
- `--limit`：1–10 条；
- `--max-chars`：500–12000 字符。

默认排除 `docs/plans/`、`docs/knowledge/`、`docs/reviews/` 和 `docs/history/` 的普通文档扫描；受管 Knowledge JSON 由结构化查询器优先读取，历史目录不参与候选。

### 2.3 模型可见输出

```json
{
  "mode": "knowledge_assist",
  "facts": [{"text": "...", "ref": "path:line"}],
  "refs": ["path:line"],
  "constraints": [],
  "conflicts": [],
  "conflict_check": "managed_knowledge_assets_evaluated",
  "omitted": {"count": 0, "reason": null},
  "source_priority": "current_source_and_runtime_remain_authoritative"
}
```

`query` 只读，当前源码和运行态仍高于所有 Knowledge 资产。它优先返回受管事实，再用剩余预算检索普通项目文档；同一 fact id 在活跃资产中出现不同 statement 时，`conflicts` 必须显式返回。

### 2.4 Knowledge 资产生命周期

`knowledge create` 只接受 `docs-harness/knowledge-input/v1`，输出固定为 `docs/knowledge/<name>.json`。输入必须含单行标题、2–4 个关键符号、摘要和非空 facts；每条 fact 使用稳定 id、单行 statement 和至少一个项目内已存在的 `source_refs`。

JSON `docs-harness/knowledge-asset/v1` 是事实真源，Markdown 是可读投影，`docs/INDEX.md` 是发现入口。`knowledge update` 校验当前资产指纹后递增 revision，并保存上一修订指纹；手工篡改、证据缺失、同键冲突均由 `knowledge check` 失败关闭。

`knowledge settle --status deprecated|superseded` 将同名 JSON/Markdown 移入 archive、退出活索引并更新明确链接；superseded 必须提供有效 replacement。Harness 不在没有证据或没有明确维护任务时自动创建、修改 Knowledge。

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

`plan create` 只接受未篡改的 `docs-harness/plan-selection/v2`、只含已注册字段的内容 JSON，以及 `docs/plans/<name>.json` 输出路径。所有 brief/full 方案必须提供单行 `title` 与 2–4 个唯一 `key_symbols`。

成功结果同时写入冻结的 `docs-harness/plan/v3` JSON、同名可审查 Markdown，以及 `docs/INDEX.md` 受管区块内的状态/关键符号条目。v2 方案保持只读兼容且不回填新字段；已有不同内容的 JSON 或 Markdown 均失败关闭。所有 Full Plan 必须声明 `acceptance_required=true|false` 和 `knowledge_impact=updated|unchanged`；`full + bugfix` 还要求以下结构化字段：

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

### 3.3 生命周期收尾

`plan settle --status implemented` 对 v3 Full Plan 先执行治理终验：`acceptance_required=true` 时至少一个关联 Acceptance 必须已经结项；`knowledge_impact=updated` 时治理输入必须列出存在且 active 的 Knowledge，`unchanged` 时必须提供单行理由。Acceptance 以 failed 结项仍可表达“已实施但验收失败”，但输出 WARN。验证后 Markdown 与索引同步为“已实施-仅追溯”。`--status deprecated` 将同名 JSON/Markdown 移入 `docs/plans/archive/`、移出活索引，并更新明确匹配的 Markdown 链接；`--replacement` 可记录替代方案。

### 3.4 ADR

架构 Profile 必须包含 `adr_decision`。主 Codex 是唯一写作者；复杂、高风险、跨模块或不可逆决策可以使用只读子智能体复审。已接受 ADR 不原地改写决策，后续通过新 ADR 的 `Supersedes` 保留历史。

## 4. 真实验收合同

`acceptance create` 使用 `docs-harness/acceptance-target-input/v1`，输出固定为 `docs/acceptance/<name>.json`。目标包含标题、2–4 个关键符号、objective 和非空 criteria；可用 `plan_ref` 与 `knowledge_refs` 关联上游受管资产。引用 v3 Plan 时 Harness 自动维护其 `acceptance_refs[]`，模型无需手填；Acceptance superseded 时移除旧反向引用。每条 criterion 固定 id、类型、L 层与必要的 evidence_layer。

`acceptance record` 继续使用 `docs-harness/acceptance-input/v3`，只登记已经发生的验收，不自动执行测试，也不决定应该跑全量还是聚焦验证。带 `--acceptance` 时必须提供 criterion_id，记录进入 `docs-harness/acceptance-asset/v1` 并更新该标准和总体聚合状态；不带资产时保留 2.0 的独立 Runtime 记录兼容路径。

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

L1 不能声明行为正确。真实设备 Behavior Acceptance 可以记录 L5 客观行为，但不能替代 User Acceptance；独立记录路径不接受 `user_acceptance + passed`。只有关联 Acceptance、输入含明确 confirmation，且 agent 已收到用户确认原话后显式使用 `--user-confirmed`，才能登记用户验收通过。

通过必须提供实际方法和项目内已存在的常规证据文件；User Acceptance 的明确 confirmation 是独立证据门禁。失败必须提供总体原因、下一步和非空 `failure_attributions[]`；每项包含 `category`、`summary`、`blocking` 与非空 `evidence_refs`，类别只允许 `change_related|unrelated|pre_existing|environment|flaky`。归因重复、类别未知或证据不存在时拒绝记录。`user_pending` 必须包含已自动验证内容、待用户检查项、最短步骤和 `environment_ready=true`。

结项后的资产再次记录必须显式 `--reaccept`；`acceptance settle --status passed|failed` 必须与逐条标准聚合状态一致，`superseded` 需要 replacement 并归档。`acceptance check` 校验指纹、投影、索引、上游引用和通过证据。

## 4a. 架构决策（ADR）合同

`adr create` 使用 `docs-harness/adr-input/v1`，输出固定为 `docs/adr/<name>.json`：标题、2–4 个关键符号、context、decision、consequences 与可选 `supersedes`（每项必须是已存在的 ADR 资产）。ADR 定稿后不可更新（无 update action，revision 恒为 1）；失效时 `adr settle --status deprecated|superseded` 归档并退出活索引，superseded 必须提供活跃 ADR 作为 replacement。`adr check` 校验指纹、投影、索引与 supersedes 引用有效性。

## 5. 统一资产检查合同

`assets-check` 聚合 Plan、Knowledge、Acceptance、ADR 领域检查及跨资产正反向关系。结构、Schema、指纹、索引、活引用和已结算合同破坏属于 FAIL；声明矛盾、pending 验收指向归档 Plan、长期未结项等属于 WARN。默认只有 FAIL 返回非零，`--strict` 使 WARN 也失败；`--fast` 跳过 Plan 符号存活和 Git 历史时效检查，供 pre-commit 使用。

零资产但四类安装结构完整的项目检查通过。命令不得从 Git diff、提交信息或任务文本推断必须创建资产。

## 6. 风险、授权与数据边界

Docs Harness 不提供任务级 Gate、动作 preflight、授权文件、Host Adapter 或 usage metrics。Git 写入、删除、发布、安装和外部系统写入使用 Codex 原生授权与沙箱。

Harness 不采集用户授权、不解析 Codex usage、不保存原始用户聊天或模型推理。需要评估产品效果时，另行进行明确的只读抽样审查，不能让每个业务任务承担遥测成本。

## 7. 安装合同

项目安装只提供：

- 受管的 direct-first `AGENTS.md` 与 `CLAUDE.md` 区块；
- `scripts/harness.py` 与受管资产生命周期模块；
- 版本化 `plan-templates/`；
- `scripts/githooks/`；
- `docs/plans/`、`docs/knowledge/`、`docs/acceptance/`、`docs/adr/`、各自 archive 与 `docs/INDEX.md` 独立索引区块；
- 缺失时的项目级 `CHANGELOG.md`、`TODO.md`、`README.md` 骨架（已存在绝不覆盖）；
- `.docs-harness/config.json`（`docs-harness/project-config/v10`）。

fresh init 初始化四类空资产目录、受管索引区块与缺失的项目级文档骨架，但不生成项目事实、验收结论、规则目录或任务 Runtime，不自动启动知识、ADR、Changelog、TODO 或后台治理 Job。upgrade 先补齐四类体系，再清理指纹归属明确的旧规则、已识别知识地图、旧版本受管区块和旧 Runtime；四类用户资产、项目文档、质量账本、已修改或归属不明文件保留。`release sync --strict` 要求 CHANGELOG 顶部版本与 VERSION 一致；`project check` 对缺失的 CHANGELOG/TODO 出 red、TODO 条目格式问题出 yellow。

2.4.1 曾发布错误的方案模板配置指纹。upgrade 只把与 2.4.1 官方发布文件逐字匹配的已知指纹作为兼容归属；内容有任何额外修改仍拒绝覆盖。成功升级后统一写回当前真实文件指纹，不长期保留双重归属状态。

## 8. 迁移与移除边界

`run|context|progress|verify|task|background|authorization`、`--legacy-opt-in` 和知识维护 Job 已从 2.x CLI 与控制器删除。2.x 不读取、创建、继续或验证 1.x 任务状态；旧项目只通过 `project upgrade` 执行单向迁移。

旧规则目录和 1.x 状态机测试不进入源码当前产品面或 npm 包。`docs/history/` 只在仓库中保留历史证据，不进入默认知识检索和安装包。完整清理、保留和失败关闭规则见 [2.0.0 迁移指南](migrations/v2.0.0.md)。
