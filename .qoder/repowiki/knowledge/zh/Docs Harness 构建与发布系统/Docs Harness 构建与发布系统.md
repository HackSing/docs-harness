---
kind: build_system
name: Docs Harness 构建与发布系统
category: build_system
scope:
    - '**'
source_files:
    - scripts/harness.py
    - package.json
    - VERSION
    - SKILL.md
    - docs/architecture.md
    - docs/contracts.md
---

## 构建系统与交付策略

### 核心工具链
- **Python CLI**：`scripts/harness.py` 是单一入口，通过 `argparse` 提供 `run/verify/background/ledger/project` 等子命令
- **npm 元数据包装**：`package.json` 仅作为包清单和脚本调度器，不依赖 Node.js 运行时执行业务逻辑
- **版本管理**：`VERSION` 文件与 `package.json.version`、`SKILL.md` frontmatter、控制器内 `VERSION = "1.6.5"` 四源同步（架构文档明确要求一致性）

### 构建与打包流程
- **测试**：`npm test` 调用 `python3 -m unittest discover -s tests -p test_*.py` 运行单元测试
- **自测**：`npm run self-test` 执行 `python3 scripts/harness.py self-test --target . --json`
- **包检查**：`npm pack --dry-run` 验证 `files` 字段包含的产物集合（CHANGELOG.md、README.md、SKILL.md、VERSION、docs/、evals/、harness-home/、scripts/harness.py、tests/test_harness.py）
- **无 Makefile/Dockerfile/CI 配置**：仓库未包含传统构建脚本或持续集成流水线定义

### 发布契约
- **包结构约束**：`package.json.files` 显式声明发布内容，排除 `.gitignore`、`.pyc` 等中间产物
- **版本同步强制**：架构文档规定 `VERSION`、`package.json`、`SKILL.md` frontmatter 与控制器常量必须一致
- **证据链**：通过 `docs-harness/evidence-receipt/v2` 绑定 package fingerprint、可信 producer、时效与读写集合
- **验收分层**：source → local_verification → git_head → remote_delivery → fresh_clone → release_artifact → ui → external_state 八层递进验证

### 约束与规则
- **幂等性**：同一 target、任务文本、事实与工作区快照重复 `run` 时复用活动任务，不复用 `complete|cancelled|failed|blocked` 状态的任务
- **安全底线**：`security-sensitive`、`destructive-data`、`release-external` 三个 Gate 由控制器代码强制并入，宿主声明不可豁免
- **写入隔离**：验证期间临时副产物（`__pycache__`、`.pytest_cache`、`.coverage` 等）进入 `volatile_write_set` 保持可见但不计入额外写入
- **Git 保护**：`.git/**`、`.docs-harness/**` 及 Harness Runtime 文件禁止被后台 Job 直接修改
- **回滚阻断**：存在活动 v2 任务时 `project rollback-check` 必须阻断回滚操作