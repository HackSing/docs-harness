---
name: docs-harness
description: "默认不介入普通任务；仅按需提供项目知识、方案模板和真实验收记录。"
metadata:
  version: 2.11.0
  status: active
---

# Docs Harness 2.9.1

Docs Harness 是可选的项目辅助能力，不是每个任务必须经过的工单系统。

## 默认规则

- 普通问答、只读检查、代码修改、构建和测试由 Codex 直接完成。
- 默认不运行 `run`、`context`、`progress` 或旧 `verify`，不创建任务包，不生成 Gate，不自动加载知识或方案。
- 用户明确说“不使用 Harness”时，必须直接执行；不得暗中恢复旧流程。
- 不在没有证据或没有明确维护任务时自动更新 Knowledge、ADR、Changelog、TODO 或质量账本。

## Knowledge 生命周期

只有缺少的项目事实会改变目标、范围、方案或验收时才启用。

优先级：当前源码和运行态 → 相关 ADR/架构文档 → 项目知识摘要 → 历史记录。找到足够事实后立即停止，不全量加载文档。

```bash
python3 scripts/harness.py knowledge query --target . --query "<缺少的具体事实>" --json
```

模型只消费 `facts`、`refs`、`constraints`、`conflicts` 和 `omitted`。候选、评分、收据与检索历史不进入任务上下文。需要沉淀可复用事实时，使用 `knowledge create`；事实变化用 `knowledge update`，废弃/替代用 `knowledge settle`，收尾用 `knowledge check`。每条事实必须有项目内 `source_refs`，不得凭猜测自动写入。

## 按需方案

简单任务不生成方案。用户要求方案，或任务复杂、跨模块、高风险、验收路径需提前设计时，先按实际修改面选择模板：

```bash
python3 scripts/harness.py plan select --target . \
  --complexity complex --surface architecture --json
```

- `none`：直接执行；
- `brief`：目标、范围、关键步骤、验收；
- `full`：完整通用模板，加一个主领域 Profile；
- Profile：`general|frontend_ui|backend_service|bugfix|architecture|migration_release`。

`full + bugfix` 必须填写结构化 `affected_modules`、`verification_scope`、`full_regression_trigger` 和 `failure_attribution`。默认选择 `affected_modules`；`repository_full` 只接受跨模块、公共契约、共享基础设施、依赖/共享夹具或发布门禁原因码。四项字段进入 `execution_projection`。

所有 Full Plan 必须填写 `acceptance_required=true|false` 与单字段
`knowledge_impact=updated|unchanged`。Acceptance 创建后由 Harness 自动登记到
`Plan.acceptance_refs[]`；任务按 Knowledge → Acceptance → Plan 顺序结算。

用户明确指定模板时优先采用。前后端等复合任务仍只有一份主方案，次级 Profile 只补会改变执行或验收的字段。

模型按选择结果生成内容 JSON 后，由 Harness 校验并冻结：

```bash
python3 scripts/harness.py plan create --target . \
  --selection <selection.json> --content <content.json> \
  --output docs/plans/<plan>.json --json
```

命令会同步生成同名 Markdown 并维护 `docs/INDEX.md`。执行阶段只消费
`execution_projection`，不继承模板选择过程或候选讨论；任务收尾必须运行：

```bash
python3 scripts/harness.py plan settle --target . \
  --plan docs/plans/<plan>.json --status implemented \
  --governance-input <plan-governance.json> --json
```

废弃或被替代时改用 `--status deprecated`，可追加 `--replacement <plan.md>`。

## 风险与授权边界

Git 写入、删除、发布、安装和外部系统写入等高风险动作完全使用 Codex 原生授权与沙箱。不得调用第二套 Harness Gate、preflight 或授权流程。

## Acceptance 生命周期

复杂任务先用 `acceptance create` 建立目标并可关联 Plan/Knowledge，再把真实结果按 `criterion_id` 写入：

验收按修改面选择最低成本但能直接覆盖用户目标的真实流程：

- L1：lint、类型、编译、静态合同；
- L2：聚焦测试或仓库级全量测试行为；
- L3：本地应用或服务真实流程；
- L4：构建、包或安装产物；
- L5：真实设备行为，或与其分离的用户可见、权限和主观体验。

```bash
python3 scripts/harness.py acceptance record --target . \
  --input <acceptance.json> --acceptance docs/acceptance/<task>.json --json
```

Contract Check、Behavior Acceptance 和 User Acceptance 必须分开。Behavior Acceptance 使用 `evidence_layer=focused_test|repository_full_test|local_runtime|package_or_install|real_device`，并固定映射到 L2/L2/L3/L4/L5；任一层不得替代另一层。失败必须用 `failure_attributions[]` 分项记录 `change_related|unrelated|pre_existing|environment|flaky`、阻断性和证据。结项后重验必须显式 `--reaccept`；只有收到用户明确确认后才能用 `--user-confirmed` 登记 User Acceptance 通过。最后运行 `acceptance settle` 与 `acceptance check`。

## 输入形状

四类资产输入 JSON 必须携带各自 `schema_version` 与注册字段；校验失败时报错直接附期望形状。各输入 JSON 的完整字段形状、示例与按状态必填规则统一见 `python3 scripts/harness.py <cmd> --help`：`knowledge create|update` → `docs-harness/knowledge-input/v1`，`acceptance create` → `docs-harness/acceptance-target-input/v1`，`acceptance record` → `docs-harness/acceptance-input/v3`，`adr create` → `docs-harness/adr-input/v1`，`plan settle --governance-input` → `docs-harness/plan-governance-input/v1`；`plan create --content` 字段动态，以 `plan select` 输出的 `fields` 为准。

## ADR

ADR 只用于会长期约束架构边界、公共接口、兼容、安全、数据或基础设施的决策。主 Codex 是唯一写作者，通过 `adr create` 登记（定稿不可改，没有 update）；复杂、高风险或跨模块决策可以使用只读子智能体复审替代方案、兼容、迁移、回滚和验收，但子智能体不直接写 ADR。决策失效时用 `adr settle --status deprecated|superseded`（superseded 需 `--replacement`）归档，后续新决策通过 `supersedes` 记录取代关系。

## 2.0.0 迁移边界

旧控制流程已经移除，不存在兼容入口。旧命令和 `--legacy-opt-in` 不属于 2.x CLI；升级旧项目时先读取 `docs/migrations/v2.0.0.md` 并运行 preview，只清理可证明归属的旧工件，项目文档和归属不明内容必须保留。

升级 pre-2.0 项目必须使用当前 2.9.1 来源包中的控制器，不能使用目标项目尚未升级的旧控制器。

## 项目安装

```bash
python3 <docs-harness-2.9.1-source>/scripts/harness.py project init --target <project> --json
python3 <docs-harness-2.9.1-source>/scripts/harness.py project upgrade --target <project> --json
python3 <docs-harness-2.9.1-source>/scripts/harness.py project upgrade --target <project> --apply --json
python3 scripts/harness.py project upgrade --target . --source <docs-harness-2.9.1-source> --apply --json
python3 scripts/harness.py project check --target . --json
python3 scripts/harness.py project diff --target . --json
python3 scripts/harness.py project uninstall --target <project> --json
python3 scripts/harness.py project uninstall --target <project> --apply --json
python3 scripts/harness.py plan check --target .
python3 scripts/harness.py assets-check --target . --strict
python3 scripts/harness.py self-test --target .
```

fresh init 写入受管入口、控制器、资产模块、方案模板、git 钩子和 `project-config/v11`，并初始化 Plan/Knowledge/Acceptance/ADR 四类空目录、archive 与独立索引区块，缺失时生成项目级 CHANGELOG.md、TODO.md、README.md 骨架（已存在绝不覆盖）；不安装旧规则，不生成项目事实或验收结论，不自动启动后台治理 Job，不提交、不推送、不发布。upgrade 是单向迁移：先预览，再补齐四类体系并清理所有权明确的旧规则、知识地图、受管版本区块和旧 Runtime，同时保留四类用户资产、项目正文、质量账本以及已修改或归属不明文件。

安装态可用 `project check` 核对版本、指纹、方案结构与 Git 交付状态，`project diff` 只读列出与来源包的漂移；两者不做任何写入。`project uninstall` 先预览再删除所有权明确的受管程序，项目方案、质量账本和用户正文一律保留。`plan check` 是 Plan 域文档可发现性检查；收尾统一使用 `assets-check`，pre-commit 使用 `--fast`，CI 使用 `--strict`。缺失资产结构返回失败并提示先运行 init/upgrade。`self-test` 运行内置自检。init、upgrade、uninstall、check、diff 必须使用来源包或安装态中版本不低于目标的控制器；upgrade 不能从模板已缺失或滞后的项目内副本取得来源；从项目内安装副本运行 init/upgrade 时必须用 `--source` 显式指定同版本完整源包，跨版本升级必须直接运行源包内的控制器。
