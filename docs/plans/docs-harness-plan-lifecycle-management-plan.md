> 状态：已实施-仅追溯（代码已是真源，2026-08-14 核对）
<!-- docs-harness:plan-document/v1 -->

# Docs Harness 完整方案管理生命周期实施方案

## 背景

Docs Harness 2.4.1 已能选择和冻结结构化方案，也能检查已有 `docs/plans/` Markdown；但安装不会初始化方案体系，`plan create` 只写 JSON，任务收尾不会更新状态、索引或归档。这导致方案能力停留在孤立工具，而不是项目可持续使用的产品链路。

## 产品目标

建立以下闭环：

`project init/upgrade 初始化` → `plan create 生成 JSON + Markdown` → `任务执行引用` → `plan settle 更新状态` → `废弃方案归档` → `docs-check/pre-commit 持续治理`。

简单任务仍然直接执行，不强制生成方案；只有复杂、跨模块、高风险或用户明确要求的任务进入方案管理。

## 实施范围

1. `project init/upgrade` 对缺失体系创建 `docs/plans/`、`docs/plans/archive/` 和 `docs/INDEX.md` 方案索引区块，保留现有项目文档。
2. `plan create` 保留冻结 JSON 合同，同时生成可审查 Markdown，并自动登记带状态和 2–4 个关键符号的索引条目。
3. 新增显式方案收尾能力：已实施方案保留在活目录并标记为仅追溯；废弃方案移动到 archive，同步 JSON、索引和明确匹配的 Markdown 链接。
4. `docs-check` 验证初始化结构、横幅、索引、归档链接、关键符号和时效；安装态不再因目录缺失而静默跳过。
5. 同步受管 `AGENTS.md`/`CLAUDE.md`、README、SKILL、架构、测试、Changelog、模板和版本真源。
6. 源仓库验证通过后，用正式 `project upgrade` 将能力应用到 Avatanel，作为真实下游验收。

## 核心接口与边界

- `plan_create`：方案生产者，输出不可变执行 JSON、可审查 Markdown和索引条目。
- `apply_project_install`：初始化方案文档结构，只创建缺失资产或维护独立受管索引区块。
- `plan settle`：唯一生命周期写入口，处理“已实施”与“已废弃”两类收尾动作。
- `command_docs_check`：只读验证者，不自动修复内容。
- `PLAN_INDEX_BEGIN` / `PLAN_INDEX_END`：隔离 Harness 维护的方案索引，项目现有 `docs/INDEX.md` 正文不被接管。

项目文档、质量账本和归属不明内容继续由项目所有；不恢复 1.x Gate、后台 Job 或全任务状态机，不引入第三方依赖，不自动提交或推送。

## 分批实施

### 第一批：初始化与生成

- 定义方案目录、索引区块、状态和文档渲染的单一接口。
- 扩展安装预览、应用、diff/check，使缺失方案结构可观察、可补齐、可验证。
- 扩展 `plan create`，形成 JSON、Markdown、索引三者一致的原子产品结果。

验收：初始化幂等；用户现有文档保留；方案创建三项产物一致；已有不同内容时失败关闭。

### 第二批：收尾与归档

- 新增 `plan settle --status implemented|deprecated`。
- 已实施：更新横幅和索引状态，保留根目录追溯。
- 已废弃：移动 Markdown 与伴随 JSON 到 archive，移出活索引，更新明确链接。
- 同步当前步骤提示词，让 agent 在任务收尾显式调用 settle。

验收：状态单字段驱动明确动作；重复执行幂等；畸形、越界或非 Harness 方案拒绝处理。

### 第三批：治理、文档和下游

- 强化 `docs-check` 与 pre-commit 消费链。
- 补齐受影响模块合同测试、版本真源、产品文档和包清单。
- 执行源项目回归，然后升级 Avatanel 并验证安装态。

验收：源测试、`self-test`、`docs-check --strict`、`git diff --check`、`npm pack --dry-run` 通过；Avatanel `project diff` 零漂移、`project check` 无红黄项、`self-test` 通过且方案体系存在。

## 风险与回滚

- 索引误改风险：只操作独立受管区块；标记畸形时失败关闭。
- 方案覆盖风险：同路径已有不同内容时拒绝覆盖。
- 归档死链风险：只改明确的方案相对链接，再由 `docs-check` 复核。
- 下游风险：Avatanel 不提交；若验证失败，修正源实现后重新 preview/apply，不以重置破坏既有工作区。

## 完成判定

只有源码合同、受影响模块测试、包/自检、Docs Harness 文档治理以及 Avatanel 本地安装态全部取得证据，才可声明本方案实施完成。Git 提交、推送、发布和其他下游项目升级均单独报告，不由本次本地验收替代。
