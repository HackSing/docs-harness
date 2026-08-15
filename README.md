<div align="center">

# Docs Harness

**面向 AI Agent 的轻量项目文档治理工具**

默认直接完成任务；仅在确有长期价值时，管理 Plan、Knowledge、Acceptance 三类项目资产的完整生命周期。

[![Version](https://img.shields.io/badge/version-2.7.1-2563eb.svg)](CHANGELOG.md)
[![Assets Check](https://github.com/HackSing/docs-harness/actions/workflows/assets-check.yml/badge.svg)](https://github.com/HackSing/docs-harness/actions/workflows/assets-check.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776ab.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/runtime%20dependencies-0-16a34a.svg)](scripts/harness.py)

[快速开始](#快速开始) · [工作方式](#工作方式) · [命令参考](#命令参考) · [设计文档](docs/README.md) · [更新日志](CHANGELOG.md)

</div>

---

## 为什么需要 Docs Harness

AI Agent 可以直接读取代码、修改文件和运行测试，但复杂项目中的方案、事实和验收结果经常散落在对话里，难以长期发现、更新和审查。

Docs Harness 将这些内容沉淀为项目内、可版本管理的资产，同时避免把所有任务都变成重型流程：

- 普通问答、只读检查、局部修改、构建和测试默认直接执行，Harness 调用数可以为 0；
- 复杂、跨模块、高风险任务按需创建方案和验收资产；
- 只有具备当前源码或项目文档证据的可复用事实才进入 Knowledge；
- 已有资产受到 Schema、指纹、引用、状态、索引和归档检查；
- 不建立第二套任务审批、授权或运行状态机。

> 核心原则：**宽松启用，严格治理；没有证据，不宣称完成。**

## 核心能力

| 能力 | 解决的问题 | 默认行为 |
|---|---|---|
| Direct-first | 避免简单任务被流程拖慢 | Agent 直接执行，不创建任务控制状态 |
| Plan 生命周期 | 方案容易丢失、过期或无法追溯 | 按需创建冻结 JSON、Markdown 和索引 |
| Knowledge 生命周期 | 项目事实缺少来源、更新和冲突管理 | 只记录有 `source_refs` 的可复用事实 |
| Acceptance 生命周期 | 测试、运行、安装和用户验收容易混为一谈 | 按标准和证据层逐条记录真实结果 |
| `assets-check` | 三类资产分散检查，关系容易漂移 | 本地、pre-commit 和 CI 多层持续检查 |
| 安全升级 | 旧版本或用户修改可能被误覆盖 | preview 优先，只覆盖指纹归属明确的文件 |

## 快速开始

### 环境要求

- Git；
- Python 3.9 或更高版本；
- Node.js 与 npm 仅用于开发者运行仓库测试，不是目标项目的运行依赖。

Docs Harness 当前通过源码分发，`package.json` 标记为 `private`，不提供 npm registry 安装入口。

### 1. 获取源码

```bash
git clone https://github.com/HackSing/docs-harness.git
cd docs-harness
```

### 2. 初始化新项目

```bash
python3 /path/to/docs-harness/scripts/harness.py \
  project init --target /path/to/project --json
```

初始化会安装受管入口、控制器、资产模块、方案模板和 Git Hook 文件，并创建：

```text
docs/
├── INDEX.md
├── plans/
├── knowledge/
└── acceptance/
```

它不会生成虚构的项目事实或验收结果，不修改业务代码，也不会自动提交或推送。

### 3. 升级已有项目

先预览，再应用：

```bash
python3 /path/to/docs-harness/scripts/harness.py \
  project upgrade --target /path/to/project --json

python3 /path/to/docs-harness/scripts/harness.py \
  project upgrade --target /path/to/project --apply --json
```

跨版本升级必须使用新版本源码中的控制器。升级会保留项目正文、三类用户资产、质量账本以及已修改或归属不明的文件。

### 4. 启用提交前检查

```bash
cd /path/to/project
sh scripts/githooks/setup.sh
```

该命令将仓库本地 `core.hooksPath` 设置为 `scripts/githooks`。之后每次提交都会运行：

```bash
python3 scripts/harness.py assets-check --target . --fast
```

### 5. 验证安装

```bash
python3 scripts/harness.py project diff --target . --json
python3 scripts/harness.py project check --target . --json
python3 scripts/harness.py self-test --target . --json
python3 scripts/harness.py assets-check --target . --strict --json
```

理想结果是 `project diff` 返回 `changes=[]`，其余检查没有红色问题。`project check` 返回退出码 3、状态为 `needs_delivery` 时，表示受管文件尚未提交，不代表安装失败；提交后才能取得 `clone_ready=true`。

## 工作方式

### 默认任务路径

```text
用户提出任务
    ↓
Agent 读取必要事实并直接工作
    ↓
仅在需要时创建或消费项目资产
    ↓
运行最小充分的真实验证
    ↓
明确报告已验证、待用户验证和未覆盖层
```

简单任务不要求 Plan、Knowledge 或 Acceptance。复杂任务通过三类资产形成可追溯闭环：

```text
Knowledge：提供有来源、可冲突检测的项目事实
       ↓
Plan：基于当前事实形成可执行方案
       ↓
Acceptance：验证实施后产生的真实结果
       ↓
当前源码与事实经证据确认后更新 Knowledge
```

### Plan 生命周期

```text
初始化 → 选择模板 → 创建 JSON/Markdown → 执行引用
→ settle 收尾 → 废弃/替代 → 归档 → docs-check
```

复杂任务先选择 Level 与 Profile：

```bash
python3 scripts/harness.py plan select --target . \
  --complexity complex --surface architecture --json
```

- Level：`none | brief | full`；
- Profile：`general | frontend_ui | backend_service | bugfix | architecture | migration_release`；
- Full Plan 必须声明 `acceptance_required=true|false` 与 `knowledge_impact=updated|unchanged`。

创建和结项：

```bash
python3 scripts/harness.py plan create --target . \
  --selection selection.json --content content.json \
  --output docs/plans/task.json --json

python3 scripts/harness.py plan settle --target . \
  --plan docs/plans/task.json --status implemented \
  --governance-input plan-governance.json --json
```

`plan create` 会同时生成冻结 JSON、可读 Markdown，并维护 `docs/INDEX.md`。已实施方案留在活目录作为追溯记录；废弃或被替代的方案成对移入 `docs/plans/archive/`。

### Knowledge 生命周期

```text
初始化 → 从当前真源创建 → 登记来源与关键符号 → query 消费
→ update 与冲突检测 → deprecated/superseded → 归档 → knowledge check
```

按需查询：

```bash
python3 scripts/harness.py knowledge query --target . \
  --query "运行时所有权由哪些模块负责" --json
```

创建、更新和检查：

```bash
python3 scripts/harness.py knowledge create --target . \
  --input knowledge.json --output docs/knowledge/runtime-owner.json --json

python3 scripts/harness.py knowledge update --target . \
  --input knowledge-v2.json \
  --knowledge docs/knowledge/runtime-owner.json --json

python3 scripts/harness.py knowledge check --target . --json
```

每条事实必须引用项目内已存在的 `source_refs`。当前源码、运行态和真实产物始终高于 Knowledge 资产；Harness 不凭模型猜测自动写入事实。

### Acceptance 生命周期

```text
初始化 → 创建目标与 criteria → 绑定 Plan/Knowledge
→ record 真实结果 → pending/passed/failed → reaccept/替代
→ settle/归档 → acceptance check
```

```bash
python3 scripts/harness.py acceptance create --target . \
  --input acceptance-target.json \
  --output docs/acceptance/task.json --json

python3 scripts/harness.py acceptance record --target . \
  --input acceptance-result.json \
  --acceptance docs/acceptance/task.json --json

python3 scripts/harness.py acceptance settle --target . \
  --acceptance docs/acceptance/task.json --status passed --json
```

验收层级不能相互替代：

| 层级 | 证据范围 |
|---|---|
| L1 | 源码、类型、编译或静态合同 |
| L2 | 聚焦测试或仓库级全量测试 |
| L3 | 本地应用或服务真实流程 |
| L4 | 构建、包或安装产物 |
| L5 | 真实设备行为，或与其分离的用户确认 |

Behavior Acceptance 使用 `focused_test | repository_full_test | local_runtime | package_or_install | real_device` 作为 `evidence_layer`。只有收到用户明确确认后，才能使用 `--user-confirmed` 登记 User Acceptance 通过。

## 多重治理机制

```text
创建/更新边界校验
        ↓
settle 关系终验
        ↓
assets-check 统一检查
        ↓
pre-commit --fast
        ↓
GitHub Actions --strict
```

`assets-check` 聚合 Plan、Knowledge、Acceptance 及其跨资产关系：

- FAIL 始终返回失败；
- WARN 默认提示，在 `--strict` 下返回失败；
- `--fast` 跳过 Plan 的源码符号存活与 Git 时效慢检查；
- 零资产项目只要目录结构完整即可通过；
- 不根据 Git diff、提交信息或任务关键词推断“必须创建资产”。

## 命令参考

| 命令 | 用途 |
|---|---|
| `project init` | 初始化受管入口和三类资产目录 |
| `project upgrade` | 预览或应用单向升级 |
| `project diff` | 只读查看安装态与来源包差异 |
| `project check` | 检查版本、指纹、结构和 Git 交付状态 |
| `project uninstall` | 预览或移除所有权明确的受管程序 |
| `knowledge create/update/query/settle/check` | 管理 Knowledge 生命周期 |
| `plan select/create/settle` | 管理 Plan 生命周期 |
| `acceptance create/record/settle/check` | 管理 Acceptance 生命周期 |
| `docs-check` | 检查 Plan 文档、索引、符号与链接 |
| `assets-check` | 统一检查三类资产和跨资产关系 |
| `self-test` | 运行安装副本的内置合同检查 |
| `release sync` | 检查版本真源是否一致 |

完整输入 Schema、状态机和退出语义见 [docs/contracts.md](docs/contracts.md)。

## 安全与兼容边界

- `project init` 直接初始化目标项目；`upgrade` 与 `uninstall` 默认只预览，只有 `--apply` 才写入；
- 不使用旧项目中的旧控制器执行跨版本升级；
- 用户修改或归属不明的文件失败关闭，不强制覆盖；
- pre-2.0 项目只通过当前控制器执行单向迁移，不继续运行旧任务控制流程；
- Git 提交、推送、发布、签名、设备和用户可见验收是独立交付层。

1.x 项目迁移请先阅读 [2.0.0 单向迁移指南](docs/migrations/v2.0.0.md)。

## 仓库结构

```text
docs-harness/
├── scripts/harness.py           # CLI 控制器
├── scripts/*_assets.py          # Knowledge/Acceptance 与共享资产逻辑
├── scripts/asset_checks.py      # 统一检查和跨资产关系
├── scripts/plan_governance.py   # Plan v3 治理合同
├── scripts/githooks/            # 入库 Git Hook
├── plan-templates/              # Level 与 Profile 模板
├── docs/                        # 产品、合同、测试和三类资产
├── tests/                       # Python unittest 回归
└── .github/workflows/           # GitHub 严格检查
```

## 开发与验证

```bash
npm test
npm run self-test
npm run pack:check
python3 scripts/harness.py assets-check --target . --strict --json
```

发布检查覆盖仓库回归、源码自检、严格资产检查、打包和下游升级。最新命令、结果与未覆盖层记录在 [测试策略与证据](docs/testing.md)；源码测试、Git 提交、远端 CI、下游同步、安装包和用户验收不能互相替代。

## 文档

- [文档导航](docs/README.md)
- [架构设计](docs/architecture.md)
- [CLI 与资产合同](docs/contracts.md)
- [测试策略与证据](docs/testing.md)
- [更新日志](CHANGELOG.md)
- [Docs Harness 2.7.0 实施方案](docs/plans/docs-harness-assets-governance-2.7.0.md)

## 参与项目

欢迎通过 [Issues](https://github.com/HackSing/docs-harness/issues) 报告可复现问题，并通过 Pull Request 提交聚焦、带测试和文档同步的改动。请勿在 Issue、日志或验收资产中提交密钥、Token、私人对话或原始用户数据。

## 许可证

当前仓库尚未包含开源许可证文件。公开分发或接受外部贡献前，请由项目所有者选择并添加适用的 `LICENSE`。
