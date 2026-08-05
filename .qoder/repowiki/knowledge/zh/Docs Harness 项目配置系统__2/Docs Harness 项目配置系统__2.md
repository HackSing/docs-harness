---
kind: configuration_system
name: Docs Harness 项目配置系统
category: configuration_system
scope:
    - '**'
source_files:
    - scripts/harness.py
    - .docs-harness/config.json
---

Docs Harness 的配置系统以 Python CLI（scripts/harness.py）为核心，通过 JSON 配置文件与运行时目录组织项目级设置，采用安装时生成加运行时校验的契约式管理方式。

系统与工具：纯 Python 实现，无外部配置框架依赖。使用 JSON 作为配置格式，通过 project_config() 函数从目标项目的 .docs-harness/config.json 读取配置，并配合严格的 schema 版本控制（CONFIG_SCHEMA = "docs-harness/project-config/v4"）。

核心文件与位置：主配置加载位于 scripts/harness.py 中的 project_config() 函数（第1282行），配置路径约定为 target/.docs-harness/config.json，规则目录为 .docs-harness/harness-home/rules/，运行时状态位于 .docs-harness/runs/、.docs-harness/background/、.docs-harness/knowledge-jobs/、.docs-harness/task-inputs/。

架构设计：分层配置结构，配置分为 background_governance（后台治理）、knowledge（知识库）、verification（验证）三个主要部分，每层都有严格的类型校验和默认值处理。版本契约机制通过 schema_version 字段确保配置格式兼容性，安装时自动升级配置结构，不兼容时抛出明确错误。安全约束方面，配置路径严格限制，禁止访问 .git、.docs-harness 等敏感目录，所有相对路径必须解析到目标项目范围内。指纹验证通过 installed_script_fingerprint 和 installed_rule_fingerprints 追踪已安装的脚本和规则文件完整性。

配置项约定：version 字段表示当前配置版本，必须与控制器 VERSION 一致；rules_root 固定为 .docs-harness/harness-home/rules；background_governance.enabled 控制是否启用后台治理任务；knowledge.root 指定知识文档根目录，默认为 docs；verification.volatile_paths 定义易变文件路径模式，用于跳过变更检测；document_routes 支持 architecture、changelog、todo 等类型的显式文档路由配置。

运行时行为：配置不存在时返回 None，调用方需处理空配置情况；配置存在但格式非法时抛出 invalid_project_config 错误；安装过程中自动生成基础配置，保留用户自定义的 document_routes 和 knowledge.inventory_include 等字段；通过 apply_project_install() 函数统一管理配置文件的创建、更新和迁移。