---
kind: build_system
name: 构建与发布系统（npm 包 + Python CLI）
category: build_system
scope:
    - '**'
source_files:
    - package.json
    - VERSION
    - scripts/harness.py
    - tests/test_harness.py
    - README.md
    - SKILL.md
    - harness-home/rules/INDEX.md
    - evals/evals.json
---

## 1. 使用的系统与工具
- **npm 包管理**：项目以 npm 私有包形式分发，`package.json` 声明包名 `docs-harness`、版本 `1.6.8` 以及打包文件清单。
- **Python CLI 作为核心可执行体**：所有构建、验证、任务编排逻辑集中在 `scripts/harness.py`，通过 `python3 scripts/harness.py <command>` 暴露 run/verify/background/ledger/project/knowledge/task 等子命令。
- **单元测试框架**：使用 Python 标准库 `unittest`，由 `package.json` 的 `test` 脚本驱动。
- **无 Makefile/Dockerfile/CI 配置**：仓库根目录未发现 Makefile、Dockerfile、docker-compose、`.github/workflows`、`.travis.yml`、`Jenkinsfile` 等 CI/容器化构建文件。

## 2. 关键文件与位置
- `package.json`：定义包元数据、`files` 白名单、`scripts.test/self-test/pack:check` 三个 npm 脚本。
- `VERSION`：单行文本存放当前版本号 `1.6.8`，与 `package.json.version` 和 `scripts/harness.py` 顶部 `VERSION = "1.6.8"` 三处同步。
- `scripts/harness.py`：约 10k 行的主控制器，集中实现所有 CLI 子命令、Schema 常量、Gate 规则、Git 预检/后检、后台 Job 状态机、证据收据与上下文缓存等全部业务逻辑。
- `tests/test_harness.py`：基于 `unittest discover` 的测试入口。
- `README.md` / `SKILL.md`：安装、日常任务、验收命令的使用说明，是外部消费契约文档真源之一。
- `harness-home/rules/*.md`：运行时加载的规则文件集合（INDEX.md 为索引）。
- `evals/evals.json`：评估输入数据。

## 3. 架构与约定
- **单一可执行入口**：所有功能通过 `scripts/harness.py` 的 argparse 子命令暴露，没有多语言编译步骤，也没有构建产物（如 .pyc/.dist）纳入版本控制。
- **版本三元同步**：`VERSION` 文件、`package.json.version`、`scripts/harness.py` 顶部的 `VERSION` 常量必须保持一致；升级时需同时修改这三处。
- **npm 脚本即构建入口**：
  - `npm test` → `python3 -m unittest discover -s tests -p test_*.py`
  - `npm run self-test` → `python3 scripts/harness.py self-test --target . --json`
  - `npm run pack:check` → `npm pack --dry-run` 校验打包清单
- **打包范围受控**：`package.json.files` 显式列出允许进入 npm 包的文件/目录，仅包含 README、CHANGELOG、SKILL、VERSION、docs、evals、harness-home、scripts/harness.py、tests/test_harness.py。
- **Runtime 隔离**：运行期工件写入 `<git-dir>/docs-harness/runs|background|quality-ledger` 或 `.docs-harness/*`，不进入 Git 追踪，也不影响构建产物。
- **无跨平台编译/交叉编译**：纯 Python 脚本，依赖 `python3` 解释器，未定义 cross-compile 或平台特定构建步骤。

## 4. 约定与约束
- **构建/测试命令约定**：开发者必须通过 `npm test`、`npm run self-test`、`npm run pack:check` 进行本地验证，这些命令在 README 开发与验收章节中明确列出。
- **版本一致性约束**：`VERSION` 文件、`package.json.version`、`scripts/harness.py` 中的 `VERSION` 常量三者必须同步更新，否则会导致 CLI 输出、包元数据不一致。
- **包内容白名单约束**：只有 `package.json.files` 中列出的路径会被 `npm pack` 打包，新增文件需手动加入该列表才能随包分发。
- **测试覆盖约束**：`self-test` 子命令要求以 `--target .` 指向当前源码目录，用于对 harness 自身进行自测。
- **无 CI/容器化约束**：仓库未提供 CI 流水线或 Docker 构建定义，发布与部署流程未在代码中固化，需在外部流程中补充。

## 5. 适用性判断
本仓库是一个以 npm 包形式分发的 Python CLI 工具，构建系统极其轻量——仅依赖 `npm` 脚本与 `python3 -m unittest`，没有 Makefile、Dockerfile、CI 配置或复杂构建管线。因此本类别“build_system”在该仓库中属于**最小可用形态**，主要体现为 npm 包管理与 Python 单元测试脚本的组合。