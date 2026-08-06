---
kind: dependency_management
name: 依赖管理（npm 包装层）
category: dependency_management
scope:
    - '**'
source_files:
    - package.json
    - VERSION
    - scripts/harness.py
---

本仓库是一个以 npm 包形式封装 Python CLI 的 Docs Harness，其依赖管理策略非常轻量：仓库本身不声明任何第三方运行时依赖，所有外部工具通过白名单机制在运行时安全调用。

**使用的系统与工具**
- npm 仅作为包的元数据与脚本入口，`package.json` 中未声明 `dependencies`/`devDependencies`，包标记为 `private: true`，表明该包不发布到公共 registry，而是作为内部技能包使用。
- Python 是实际实现语言，但仓库未提供 `requirements.txt`、`setup.py` 或 `pyproject.toml`，Python 解释器由宿主环境提供。
- 构建与测试通过 `scripts/harness.py` 统一暴露命令（run/verify/background/ledger），并通过 `npm test`、`npm run self-test`、`npm run pack:check` 三个 npm scripts 触发。

**关键文件与位置**
- `package.json`：定义包名 `docs-harness`、版本号 `1.6.8`、打包文件清单（files）、以及三个 npm scripts。
- `VERSION`：与 package.json 中的 version 字段保持同步的单一版本来源。
- `scripts/harness.py`：核心逻辑所在，包含验证命令白名单与安全校验（SAFE_COMMANDS、FORBIDDEN_ARGS），限制可执行的本地工具集。

**架构与约定**
- 无锁文件（无 `package-lock.json`、`yarn.lock`、`pnpm-lock.yaml`），因为不安装任何依赖。
- 无 vendoring 策略；Python 代码直接依赖系统已安装的 Python 解释器及标准库。
- 对外暴露的工具通过白名单控制：`SAFE_COMMANDS = {"python", "python3", "pytest", "npm", "node", "bun", "swift", "go", "cargo", "make", "git"}`，且对每个工具的参数进行严格过滤（如 npm 仅允许 `test` 或 `run <检查脚本>`，其中脚本名必须包含 test/check/lint/type/build 之一）。
- 包打包时通过 `files` 字段精确控制纳入内容，排除 `node_modules`、`vendor`、`.venv`、`venv`、`dist`、`build` 等目录。

**约束与规则**
- 版本管理：`package.json` 的 `version` 字段与 `VERSION` 文件需保持一致，当前均为 `1.6.8`。
- 验证命令安全：`scripts/harness.py` 中的 `normalize_verification_command` 强制要求所有验证命令必须在白名单内，禁止危险参数（push/publish/deploy/release/reset/clean/checkout/rm/uninstall），并对 git、python、node、npm、bun、swift、go、cargo、make 等工具的子命令进行细化限制。
- 包发布：`npm pack --dry-run` 用于预检打包产物，确保只包含受控文件。