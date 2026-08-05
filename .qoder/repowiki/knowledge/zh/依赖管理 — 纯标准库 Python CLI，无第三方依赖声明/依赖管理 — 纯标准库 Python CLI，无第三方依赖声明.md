---
kind: dependency_management
name: 依赖管理 — 纯标准库 Python CLI，无第三方依赖声明
category: dependency_management
scope:
    - '**'
source_files:
    - scripts/harness.py
    - package.json
    - tests/test_harness.py
    - VERSION
---

## 1. 使用的系统/方法
该仓库是一个以 Python 3 为核心的独立 CLI 工具（`scripts/harness.py`），**未使用任何第三方 Python 包或 Node.js 依赖**。所有功能均通过 Python 标准库实现，包括 `argparse`、`subprocess`、`json`、`hashlib`、`pathlib`、`tempfile`、`urllib.parse`、`fnmatch`、`re`、`shutil`、`contextlib`、`datetime`、`uuid`、`time` 等。项目通过 `package.json` 仅作为 npm 元数据包装器存在，用于定义包名、版本和脚本命令，但并未声明任何 `dependencies` 或 `devDependencies`。

## 2. 关键文件与包
- `scripts/harness.py`：核心 Python 实现，全部使用标准库，无任何 `pip install` 或 `npm install` 需求
- `package.json`：仅包含包元数据和测试脚本，`private: true` 表示不发布到公共 npm 仓库
- `tests/test_harness.py`：单元测试，同样仅依赖标准库
- `VERSION`：版本号文件，与 `package.json` 中的 `version` 字段保持一致

## 3. 架构与设计决策
- **零外部依赖策略**：选择完全依赖 Python 标准库，确保工具在任何安装了 Python 3 的环境中可直接运行，无需虚拟环境或依赖解析
- **npm 包装层**：使用 `package.json` 作为包的元数据容器和脚本入口，便于通过 `npm pack` 打包分发，但实际代码不包含任何 JavaScript/Node.js 依赖
- **自包含设计**：CLI 工具通过 `#!/usr/bin/env python3` 直接执行，支持 `python3 scripts/harness.py <command>` 方式调用
- **版本同步**：Python 代码中的 `VERSION = "1.6.5"` 常量与 `package.json` 的 `version` 字段保持同步

## 4. 约定与约束
- **无依赖锁定文件**：由于没有第三方依赖，不存在 `requirements.txt`、`poetry.lock`、`package-lock.json` 等锁定文件
- **无虚拟环境要求**：工具设计为可在系统 Python 环境中直接运行
- **跨平台兼容**：通过 `os.path`、`pathlib.Path` 等标准库抽象处理路径差异
- **安全边界**：所有外部命令调用（如 git）都通过 `subprocess.run` 并设置超时限制，避免无限等待
- **测试策略**：通过 `python3 -m unittest discover` 运行测试，无需额外测试框架

这种依赖管理方式体现了「最小化外部依赖」的设计哲学，使 Docs Harness 成为一个真正独立的、可移植的工具包。