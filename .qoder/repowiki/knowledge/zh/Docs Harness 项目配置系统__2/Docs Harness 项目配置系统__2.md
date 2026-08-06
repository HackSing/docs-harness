---
kind: configuration_system
name: Docs Harness 项目配置系统
category: configuration_system
scope:
    - '**'
source_files:
    - scripts/harness.py
    - .docs-harness/config.json
    - harness-home/rules/INDEX.md
---

## 配置系统与契约

Docs Harness 采用**单文件 JSON 项目配置 + 运行时状态目录**的轻量配置体系，所有配置与运行时数据均位于目标仓库根目录下，不依赖外部配置文件或环境变量。

### 核心配置位置与加载机制

- **项目配置**: `.docs-harness/config.json`，通过 `project_config(target)` 函数读取，返回 `None` 表示无配置（使用默认值）
- **运行时目录**: Git 仓库内为 `docs-harness/runs/`，非 Git 仓库为 `.docs-harness/runs/`
- **规则目录**: `.docs-harness/harness-home/rules/`，集中存放治理规则文档

配置加载遵循严格校验：`read_json()` 对缺失文件和无效 JSON 抛出带 `missing_file`、`invalid_json` 错误码的 `HarnessError`，确保配置完整性。

### 配置结构与设计决策

配置系统围绕 `CONFIG_SCHEMA = "docs-harness/project-config/v4"` 版本化契约构建，主要包含：

1. **验证配置 (`verification`)**: 控制命令缓存、自动归因、易变路径白名单等行为
   - `command_cache_enabled`: 是否启用验证命令结果缓存
   - `auto_attribute_in_scope`: 是否在 write_scope 内自动归因写入
   - `volatile_paths`: 临时文件 glob 白名单，必须是非空字符串数组且不能以 `.git`、`.docs-harness` 开头

2. **文档路由配置 (`background_governance.document_routes`)**: 声明式映射文档类型到具体路径
   - 支持 `architecture`、`changelog`、`todo`、`adr_root`、`reviews_root` 等类型
   - 路径必须相对、非绝对、不在受保护目录、符合文件/目录类型预期
   - 非法配置直接拒绝而非回退，确保契约一致性

3. **知识地图**: `docs/knowledge-map.json` 作为功能知识的权威索引

### 配置解析与安全约束

- **路径安全**: 所有路径解析后必须仍在目标目录内，禁止符号链接和路径穿越
- **类型严格**: 每个配置字段都有明确的类型检查和长度限制（如路径 ≤ 512 字符）
- **白名单模式**: 易变路径、验证命令等均采用显式白名单，默认拒绝未知项
- **不可变约定**: `.git`、`.docs-harness` 目录被硬编码为受保护，不允许配置覆盖

### 运行时状态管理

配置系统同时管理丰富的运行时状态：
- 任务状态: `task-package.json`、`compiled-task.json`、`events.jsonl` 等
- 证据索引: `evidence-index.json`、`context-receipts.jsonl`、`authorization-receipts.jsonl`
- 冻结快照: `freeze.json` 用于幂等性保证
- 质量账本: `quality-ledger/records/` 存储评审记录

所有状态文件采用原子写入（先写临时文件再 `os.replace`），确保并发安全和数据一致性。事件日志使用 JSON Lines 格式追加写入，支持增量消费。

### 配置演进策略

通过 schema_version 字段实现向后兼容，当前 v4 配置在多处进行版本检查（如 `config.get("schema_version") == CONFIG_SCHEMA`），确保新特性不会破坏旧配置的使用场景。