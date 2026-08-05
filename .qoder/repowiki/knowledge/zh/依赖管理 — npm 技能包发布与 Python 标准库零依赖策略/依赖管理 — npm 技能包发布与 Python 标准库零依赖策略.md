---
kind: dependency_management
name: 依赖管理 — npm 技能包发布与 Python 标准库零依赖策略
category: dependency_management
scope:
    - '**'
source_files:
    - package.json
    - scripts/harness.py
    - tests/test_harness.py
    - VERSION
---

本仓库采用「npm 包外壳 + Python 纯标准库实现」的混合依赖管理模式：以 `package.json` 作为对外发布的元数据与脚本入口，实际运行时不引入任何第三方 Python 包，所有功能均基于 Python 标准库实现。