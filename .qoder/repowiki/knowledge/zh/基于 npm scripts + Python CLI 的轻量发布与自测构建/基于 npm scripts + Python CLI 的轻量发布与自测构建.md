---
kind: build_system
name: 基于 npm scripts + Python CLI 的轻量发布与自测构建
category: build_system
scope:
    - '**'
source_files:
    - package.json
    - VERSION
    - scripts/harness.py
    - tests/test_harness.py
---

## 1. 使用的系统/方法

该仓库没有 Makefile、Dockerfile、CI 流水线或跨编译脚本。构建与发布完全依赖两个极简机制：

- **npm 包元数据**：`package.json` 将项目声明为 `private: true` 的 npm 包，通过 `files` 字段精确控制打包产物（仅包含 `CHANGELOG.md`、`README.md`、`SKILL.md`、`VERSION`、`docs/`、`evals/`、`harness-home/`、`scripts/harness.py`、`tests/test_harness.py`），从而定义“发布物”的边界。
- **npm scripts**：`test` 使用 `python3 -m unittest discover -s tests -p test_*.py` 运行单元测试；`self-test` 调用 `python3 scripts/harness.py self-test --target . --json` 对 harness 自身做端到端自检；`pack:check` 用 `npm pack --dry-run` 校验打包清单。
- **Python CLI**：`scripts/harness.py` 是唯一的运行时入口，硬编码 `VERSION = "1.7.2"`，并通过 `argparse` 暴露 `run`、`verify`、`background`、`context`、`self-test` 等子命令，作为被发布的制品。

## 2. 关键文件

| 文件 | 作用 |
|---|---|
| `package.json` | 包名、版本、`files` 白名单、`scripts.test/self-test/pack:check` |
| `VERSION` | 纯文本语义化版本号（`1.7.2`），与 `package.json.version` 和 `scripts/harness.py` 中的 `VERSION` 保持同步 |
| `scripts/harness.py` | 单一可执行 Python 模块，内含所有业务逻辑与子命令 |
| `tests/test_harness.py` | unittest 套件，由 `npm test` 触发 |

## 3. 架构与约定

- **无外部构建工具链**：不引入 webpack、esbuild、Make、Rake、tox 等；Python 代码直接以源码形式随 npm 包分发。
- **版本三处同步约定**：版本号同时出现在 `VERSION` 文件、`package.json.version`、`scripts/harness.py` 顶部的 `VERSION` 常量中，形成三重事实源；任何发布前需确保三者一致。
- **测试即构建验证**：`npm test` 是默认构建步骤，`npm run self-test` 是内置的自回归检查，`npm run pack:check` 用于在发布前确认 `files` 白名单正确。
- **私有包策略**：`private: true` 表明该包不通过 npm registry 发布，而是作为本地/内部依赖分发，因此不存在 `publish` 脚本。
- **CLI 自举**：`harness.py` 通过 `#!/usr/bin/env python3` shebang 可直接执行，也可通过 `python3 scripts/harness.py <command>` 调用，无需安装依赖。

## 4. 约定与约束

- **发布产物由 `package.json.files` 严格限定**：不在该列表中的文件不会被 `npm pack` 包含，这是发布物的唯一约束来源。
- **测试必须通过 `unittest` 框架**：`test_*.py` 命名约定由 `discover` 自动发现，新增测试需遵循此命名。
- **版本号必须三处一致**：`VERSION`、`package.json.version`、`scripts/harness.py` 中的 `VERSION` 常量需同步更新，否则会导致运行时版本与包版本不一致。
- **无 CI/CD 配置**：仓库根目录及 `.github/` 下未发现 CI 配置文件，构建与发布流程未在仓库内自动化。
- **无容器化**：不存在 `Dockerfile`、`docker-compose.yml` 或 `.dockerignore`。
- **无 Makefile / shell 构建脚本**：所有构建动作均通过 `npm scripts` 完成。
