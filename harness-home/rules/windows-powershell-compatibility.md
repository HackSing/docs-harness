---
status: active
rule_id: DH-WINDOWS-POWERSHELL-COMPATIBILITY
content_fingerprint: sha256:1a3f35826b63f22aa9c4081c9adccf4966ea495cfb25bb2b28b918fc53829e1e
gates:
keywords: windows powershell,powershell.exe,.ps1,windows 脚本
plan_fields: PowerShell 宿主与语法
evidence_types: test_result
failure_mode: Windows shell 宿主、版本或语法兼容性未确认时停止
---

# Windows PowerShell 兼容规则

## 适用条件

任务新增或修改 Windows PowerShell、`.ps1`、BAT 到 PowerShell 的调用链或 Windows 自动化命令时生效。

## 必需的方案字段

方案必须冻结目标宿主；未明确要求 PowerShell 7 时默认 Windows PowerShell 5.1，并避免混用 Bash、CMD 或 `pwsh` 专属语法。

## 验收条件

新增或实质修改的脚本必须先完成静态语法检查，再在目标 Windows 宿主验证关键成功和失败路径。

## 失败处理方式

宿主版本不明、命令不可用、复杂引号未脚本化或静态检查失败时，不得执行待检脚本。
