---
status: index
active_rules: [DH-API-COMPATIBILITY, DH-DOCUMENTATION-CHANGES, DH-EXTERNAL-INPUT-SECURITY, DH-RELEASE-AUTHORIZATION-ROLLBACK, DH-SCOPE-CHANGE-READMISSION, DH-TESTING-RELEASE, DH-UI-COMPLETE-STATES, DH-WINDOWS-POWERSHELL-COMPATIBILITY]
---

# 通用规则目录

## 目录状态

本目录包含 Docs Harness v1.6.0 随项目安装的通用规则快照。项目运行时不得依赖源码目录的绝对路径；Git 项目必须让本目录、`.docs-harness/config.json` 和 `docs/knowledge-map.json` 声明的知识文档进入版本控制面，只有当前 HEAD 包含完整安装清单时才可声明 `clone_ready=true`。任务冻结必须覆盖控制器、规则、配置与项目知识，只排除任务 Runtime、后台知识 Job 和个人本地质量账本目录。

## 生效规则

- `DH-API-COMPATIBILITY`
- `DH-DOCUMENTATION-CHANGES`
- `DH-EXTERNAL-INPUT-SECURITY`
- `DH-RELEASE-AUTHORIZATION-ROLLBACK`
- `DH-SCOPE-CHANGE-READMISSION`
- `DH-TESTING-RELEASE`
- `DH-UI-COMPLETE-STATES`
- `DH-WINDOWS-POWERSHELL-COMPATIBILITY`

## 规则文件

- `api-compatibility.md`
- `external-input-security.md`
- `ui-complete-states.md`
- `testing-release.md`
- `release-authorization-rollback.md`
- `documentation-changes.md`
- `scope-change-readmission.md`
- `windows-powershell-compatibility.md`

## 激活条件

控制器按 Gate 或关键词匹配规则。只有 `status: active`、规则 ID 唯一、正文指纹正确且合同字段完整的规则才能进入任务包。

## 加载约定

项目安装时复制固定规则快照，并在配置中记录逐文件指纹。规则缺失、增加或变化均失败关闭，必须通过来源包升级或人工 preserve-and-merge。
