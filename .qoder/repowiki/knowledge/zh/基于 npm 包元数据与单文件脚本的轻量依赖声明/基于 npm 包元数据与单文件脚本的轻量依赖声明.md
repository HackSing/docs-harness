---
kind: dependency_management
name: 基于 npm 包元数据与单文件脚本的轻量依赖声明
category: dependency_management
scope:
    - '**'
source_files:
    - package.json
    - VERSION
    - scripts/harness.py
    - tests/test_harness.py
---

## 1. 使用的系统/方法

该仓库是一个以 npm 包形式分发的 Python CLI（`docs-harness`），其“依赖管理”非常轻量：

- **包清单**：仅使用根目录 `package.json` 声明包名、版本、描述和发布文件白名单（`files`）。没有 `dependencies` / `devDependencies`，也没有 `pnpm-lock.yaml`、`yarn.lock` 等锁文件。
- **Python 运行时依赖**：通过 `scripts/harness.py` 在运行期调用 `python3 -m unittest` 及标准库模块；测试命令 `npm test` 直接执行 `python3 -m unittest discover -s tests -p test_*.py`。仓库中未发现 `requirements.txt`、`pyproject.toml`、`setup.py`、`Pipfile`、`poetry.lock` 等任何 Python 依赖清单。
- **无 vendoring / 私有 registry**：未检出 `vendor/`、`node_modules/`、`.npmrc`、`pip.conf` 等，也未见任何私有源或代理配置。
- **版本来源**：包的 `version` 字段与根级 `VERSION` 文件保持同步（当前均为 `1.7.2`），由外部流程维护，而非由工具自动解析。

## 2. 关键文件

| 文件 | 作用 |
|---|---|
| `package.json` | 唯一对外可见的包清单，定义包名、版本、发布文件集合、`test` / `self-test` / `pack:check` 脚本 |
| `VERSION` | 与 `package.json.version` 共同作为单一事实源，供发布流程读取 |
| `scripts/harness.py` | 运行时入口，通过 `subprocess` 调用 `python3` 执行子命令（run/verify/background/ledger/self-test），不引入第三方 Python 依赖 |
| `tests/test_harness.py` | 单元测试，仅依赖 Python 标准库 `unittest` |

## 3. 架构与约定

- **零第三方依赖策略**：整个 CLI 仅依赖 Python 标准库（`argparse`、`subprocess`、`json`、`pathlib`、`unittest` 等），因此无需锁定第三方版本。
- **npm 仅作为分发壳**：`package.json` 的 `files` 字段精确控制打包产物，排除源码之外的无关文件；`private: true` 表明它不是要发布到公共 npm registry，而是内部技能包。
- **测试即依赖验证**：`npm test` 和 `npm run self-test` 是唯一的依赖正确性验证手段——如果运行环境缺少 `python3` 或标准库行为不一致，测试会失败。
- **版本同步约定**：`package.json` 与 `VERSION` 必须保持一致，这是发布契约的一部分（由文档/计划驱动，而非工具强制）。

## 4. 约定与约束

- **禁止新增第三方依赖**：从现有实现看，所有功能均通过标准库 + 子进程调用实现；若需新增依赖，应首先评估是否可通过 `subprocess` 复用宿主已安装工具（如 `python3`、`git` 等）。
- **不使用 lockfile**：由于没有第三方依赖，仓库未生成也不维护 `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml`。
- **发布前校验**：`npm run pack:check` 通过 `npm pack --dry-run` 验证 `files` 白名单与实际内容一致，防止遗漏必要文件或误打包。
- **运行环境约束**：使用者必须提供 `python3` 可执行且位于 PATH，否则 `scripts/harness.py` 的所有子命令都会失败。