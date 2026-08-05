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

## 系统与架构

Docs Harness 使用基于 JSON 的项目级配置文件 `.docs-harness/config.json`，由 Python 控制器 `scripts/harness.py` 在运行时加载、校验并维护。配置采用 schema_version 版本化（当前为 `docs-harness/project-config/v4`），通过安装流程自动创建/升级，并通过指纹校验保证文件一致性。

## 核心文件与位置

- **配置文件**：`<target>/.docs-harness/config.json` — 每个被管理项目的唯一配置源
- **规则目录**：`<target>/.docs-harness/harness-home/rules/` — 随安装复制的规则快照
- **运行时目录**：`<target>/docs-harness/runs/`（Git 仓库根下）或 `<target>/.docs-harness/runs/`（非 Git 环境）
- **知识索引**：`<target>/docs/knowledge-map.json` — 知识库映射文件
- **入口脚本**：`<target>/scripts/harness.py` — 受管的任务控制脚本

## 配置结构与字段

配置文件包含以下主要段：

- **schema_version**: 固定为 `docs-harness/project-config/v4`
- **version**: 控制器版本号，用于检测版本漂移
- **rules_root**: 规则目录相对路径（默认 `.docs-harness/harness-home/rules`）
- **installed_script_fingerprint**: 已安装脚本的 SHA256 指纹，用于检测篡改
- **installed_rule_fingerprints**: 规则文件的指纹映射
- **background_governance**: 后台治理配置，包括 enabled、non_blocking、workload_estimator、simple_threshold、complex_threshold、host_dispatch、document_routes 等
- **knowledge**: 知识库配置，包括 root、map、target_level、post_completion_sync、allow_degraded_admission、bootstrap_async、block_main_completion、docs_preexisting_at_install、inventory_include 等
- **verification**: 验证配置，包括 volatile_paths（字符串数组）、command_cache_enabled（布尔值）、auto_attribute_in_scope（布尔值）
- **installed_at**: 安装时间戳

## 加载与校验机制

1. **读取**：`project_config(target)` 函数从 `<target>/.docs-harness/config.json` 读取 JSON 对象
2. **校验**：所有配置项都有严格的类型检查，非法配置会抛出 `HarnessError` 并附带错误码（如 `invalid_project_config`、`invalid_document_route_config`）
3. **安全限制**：`volatile_paths` 必须是以工作区子目录开头的 glob 模式，禁止访问 `.git`、`.docs-harness` 等敏感目录
4. **文档路由**：`background_governance.document_routes` 支持显式配置 architecture、changelog、todo、adr_root、reviews_root 等文档路径，支持自动发现回退

## 安装与维护约定

- **自动创建**：`apply_project_install()` 会在首次安装时创建配置文件和规则目录
- **版本同步**：安装过程比较已安装指纹与当前源码指纹，不一致时拒绝覆盖（需人工 preserve-and-merge）
- **配置迁移**：升级时会保留现有用户配置（如 document_routes、knowledge.inventory_include、verification.volatile_paths），仅更新必要字段
- **完整性检查**：`project_findings()` 会检测配置缺失、版本不匹配、脚本漂移、入口链缺失等问题

## 约束与规则

- 配置文件必须是有效的 JSON 对象，否则返回 None
- `verification.volatile_paths` 必须是字符串数组，每个元素长度不超过 256，不能包含特殊字符或绝对路径
- `verification.command_cache_enabled` 和 `verification.auto_attribute_in_scope` 必须是布尔值
- 文档路由路径不能是符号链接，必须在目标目录内，且类型匹配（文件 vs 目录）
- 配置中的 version 必须与控制器 VERSION 常量一致，否则报告版本漂移
- 规则文件和脚本的指纹变化会触发保护性错误，防止意外覆盖用户修改