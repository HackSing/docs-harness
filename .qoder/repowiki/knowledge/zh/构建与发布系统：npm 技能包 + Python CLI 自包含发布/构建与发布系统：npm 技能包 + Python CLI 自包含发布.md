---
kind: build_system
name: 构建与发布系统：npm 技能包 + Python CLI 自包含发布
category: build_system
scope:
    - '**'
source_files:
    - package.json
    - VERSION
    - scripts/harness.py
    - tests/test_harness.py
    - harness-home/rules/INDEX.md
---

## 1. 使用的系统与工具
- npm 包管理：以 package.json 作为项目元数据与脚本入口，将 Python CLI（scripts/harness.py）连同文档、规则、测试等文件打包为可发布的 npm 技能包。
- Python 标准库测试框架：使用 unittest 进行单元测试，通过 python3 -m unittest discover 自动发现 tests/test_*.py。
- 无 Makefile/Dockerfile/CI 配置：仓库未包含 Makefile、Dockerfile、GitHub Actions 或其他 CI/CD 配置文件，构建与发布完全依赖 npm 脚本与 Python 子进程调用。

## 2. 核心文件与职责
- package.json：定义包名 docs-harness、版本 1.6.6、files 白名单（包含 CHANGELOG.md、README.md、SKILL.md、VERSION、docs/、evals/、harness-home/、scripts/harness.py、tests/test_harness.py），以及三个脚本：test（运行 unittest 套件）、self-test（调用 python3 scripts/harness.py self-test --target . --json 执行自测）、pack:check（npm pack --dry-run 校验打包产物）。
- VERSION：单一版本号源 1.6.6，与 package.json 的 version 字段保持一致。
- scripts/harness.py：Docs Harness 主控制器，内部硬编码 VERSION = "1.6.6"，并提供 project、run、context、verify、background、self-test 等子命令。
- tests/test_harness.py：完整的集成测试套件，验证安装、Git 操作、Gate 判定、证据链、后台任务等所有关键路径。
- harness-home/rules/*.md：运行时规则集，由 INDEX.md 索引，测试中强制要求每个规则文件包含 status: active、rule_id: DH-...、content_fingerprint: sha256:...。

## 3. 架构与约定
- 单文件 CLI 模式：整个 Docs Harness 以单个 Python 脚本形式分发，不依赖第三方包，仅使用 Python 标准库，确保在任何有 Python3 的环境中可直接运行。
- 版本同步约定：package.json 的 version、VERSION 文件、scripts/harness.py 中的 VERSION 常量三者必须保持一致（当前均为 1.6.6），这是跨语言版本契约的核心约束。
- 打包白名单机制：package.json 的 files 字段精确控制哪些内容进入 npm 包，未列出的文件不会被发布，避免泄露敏感信息。
- 测试即契约：tests/test_harness.py 不仅验证功能，还断言规则文件的结构（status: active、rule_id、content_fingerprint）、安装后目录结构、Git 行为等，是构建系统的隐性约束来源。
- 自包含发布模型：通过 npm pack 生成的 .tgz 包内包含完整可执行的 Python 脚本和所有必要资源，目标项目只需解压并运行 scripts/harness.py，无需额外安装依赖。

## 4. 约定与约束
- 版本一致性：package.json、VERSION、scripts/harness.py 三处版本号必须同步更新，否则会导致运行时版本与包版本不一致。
- 规则文件结构约束：每个规则 Markdown 文件必须包含 status: active、rule_id: DH-[A-Z-]+、content_fingerprint: sha256:[0-9a-f]{64} 三个字段，由测试强制验证。
- 测试覆盖要求：新增功能必须在 tests/test_harness.py 中添加对应测试用例，测试套件通过 python3 -m unittest discover -s tests -p test_*.py 自动发现并执行。
- Git 操作安全约束：所有 Git 操作必须通过 git_command 函数调用，支持超时控制（默认 20 秒），并对 LFS、Submodule 可用性进行预检。
- 错误码规范：所有异常通过 HarnessError 抛出，包含 code 和 exit_code 字段，测试中严格断言返回码（如 expected=1、expected=2、expected=3、expected=4）。
- JSON 输出契约：所有子命令在 --json 模式下输出结构化 JSON，测试通过解析 stdout 验证响应结构。
- 无外部依赖约束：scripts/harness.py 仅使用 Python 标准库，确保在任何环境中无需 pip install 即可运行。

## 5. 缺失的构建基础设施
- 无自动化 CI/CD 流水线：未发现 GitHub Actions、Jenkins、GitLab CI 等配置文件。
- 无 Docker 容器化：无 Dockerfile 或 docker-compose.yml。
- 无 Makefile/Shell 构建脚本：所有构建逻辑集中在 package.json 的 scripts 中。
- 无依赖管理文件：无 requirements.txt、pyproject.toml、setup.py，因为项目不依赖任何第三方包。

该构建系统采用极简设计：通过 npm 包管理分发 Python 工具，利用 Python 标准库实现零依赖运行，通过严格的测试套件保证契约一致性。