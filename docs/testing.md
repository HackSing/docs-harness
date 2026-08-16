# Docs Harness 2.7.1 测试与验收

## 1. 普通项目任务

普通项目任务不运行旧 Harness Verify。Codex 按修改面选择成本最低、但能够直接覆盖用户目标的真实流程：纯函数用聚焦输入输出或单元测试，API 启动最小服务并调用，Web/桌面界面运行真实交互，构建与安装检查真实产物，权限、硬件和主观体验准备环境后交给用户。

每次结论同时标注 L1–L5 与具体 `evidence_layer`。L2 的 `focused_test` 与 `repository_full_test` 分开，L4 的 `package_or_install`、L5 的 `real_device` 也不能由源码测试代替；真实设备客观行为不等于用户主观确认。

## 2. Docs Harness 自身验证入口

- 聚焦测试：按变更面运行对应 `unittest` 模块或用例；
- 完整回归：`npm test`，仅在行为代码、依赖、公共夹具或跨模块风险要求时运行；
- 控制器自检：`npm run self-test`；
- 发布包清单：`npm run pack:check`；
- 版本一致性：`python3 scripts/harness.py release sync --target . --json`。
- 统一资产检查：本地/钩子运行 `assets-check --fast`，发布与 CI 运行 `assets-check --strict`。

## 3. 验证选择矩阵

| 变更类型 | 本轮最小验证 | 何时升级为完整回归 |
|---|---|---|
| 行为代码、依赖、公共测试夹具 | 受影响目标测试；按影响补自检、编译或打包 | 行为稳定后，同一行为快照最多执行一次 |
| 仅测试代码 | 受影响测试 | 修改公共 runner、共享夹具或跨模块断言时 |
| 仅版本、README、CHANGELOG 或发布元数据 | 版本一致性、自检和打包 | 除非同时改变行为、依赖或公共夹具，否则不执行 |
| 下游安装或升级 | preview、apply、diff、project check 和受管文件摘要 | 不重复执行上游源码完整回归 |

- 已有完整回归通过，且行为代码、依赖和公共夹具未变化时复用该证据。
- 修复过程中先运行目标测试；完整回归是必要时的最终闸门，不是每轮固定仪式。
- 长测试只保留最终汇总和真实失败，避免重复日志进入模型上下文。
- 聚焦测试、完整回归、安装、提交、推送和 fresh clone 是不同证据层。

### Bugfix 方案定义

- “受影响模块测试”：由根因、调用链和实际改动面证明相关的模块、接口、组件或命令测试；这是 Bug 修复默认范围。
- “仓库级全量测试”：运行仓库定义的完整回归入口；只有跨模块、公共契约、共享基础设施、依赖/共享夹具或发布门禁明确触发时使用。
- `full + bugfix` 方案必须结构化声明受影响模块、验证命令、复用的已通过证据、全量触发原因和失败归因策略。

## 4. 2.7.0 聚焦回归面

- 默认直接模式不创建 Harness 状态；
- 用户关闭 Harness 时零隐式调用；
- Knowledge 创建/修订的证据引用、指纹、revision、结构化查询、同键冲突、检查和归档；
- 方案 Level/Profile 选择、字段白名单、冻结指纹、JSON/Markdown/INDEX 原子产出和执行投影；
- init/upgrade 方案目录初始化、既有索引正文保留、重复升级幂等与缺失结构 check 红级发现；
- plan settle 的已实施状态同步、废弃归档、伴随文件移动、索引退出与链接更新；
- Plan v3 的 `acceptance_required`、`knowledge_impact`、治理输入、v2 兼容与 failed Acceptance WARN；
- Acceptance 创建/supersede 对 Plan `acceptance_refs[]` 的自动登记和移除；
- `assets-check` 零资产、三类指纹篡改、跨资产关系、FAIL/WARN、fast/strict 边界；
- Bugfix Profile 的结构化影响范围、聚焦/全量选择、受控全量原因码与失败归因；
- Acceptance 目标创建、Plan/Knowledge 引用、criteria 聚合、v3 evidence_layer 固定映射、失败分项归因、结项后重验、归档和用户确认门禁；
- CLI 不存在 Gate、preflight、Host Adapter 或 metrics 入口；
- fresh init 初始化 Plan/Knowledge/Acceptance 空体系，但不生成事实、验收结论或后台 Job；
- pre-2.0 upgrade preview 零写入，apply 只清理所有权明确的旧工件并保留项目内容；
- 旧命令和 `--legacy-opt-in` 不存在于 CLI 或控制器；
- 重复 upgrade 幂等，符号链接和归属冲突在任何安装写入前失败关闭；\r
- `scripts/githooks/` 钩子默认安装：init 落地两个钩子文件、用户修改的钩子 upgrade 拒绝覆盖、uninstall 按指纹只删未改过的钩子、v6 旧配置平滑升级（`tests/test_v2_direct.py` 的 githook 合同用例）；
- 新增资产治理模块各自低于 500 行，安装副本模块指纹与来源一致；
- 发布包只包含当前 2.7.0 对外文档与受管模块。

## 5. 迁移回归

2.x 不再运行 1.x 状态机全量回归，因为该能力已经从当前产品和包中删除。迁移回归只验证现存升级合同：fresh init、旧项目 preview/apply/diff/check、所有权清理、项目内容保留、冲突零写入、旧命令缺席和重复升级幂等。

## 6. 发布结论分层

本地源码、聚焦测试、完整回归、npm 包、fresh clone、Git 提交、远端推送、下游同步、本机安装和用户可见验收互不替代。最终答复只声明本轮实际取得证据的层。

## 7. 2.7.0 三资产治理验收证据（2026-08-15）

- L2 聚焦行为：统一检查、Plan v3、Acceptance 反向登记、v2 兼容、WARN/strict 和归档关系用例通过。
- L2 仓库全量：`npm test` 运行 65 项，退出码 0；新增 2.4.1 官方模板错误配置指纹兼容与用户修改拒绝覆盖用例。
- L1 控制器与文档：`npm run self-test`、`release sync`、`docs-check --strict`、Workflow YAML 解析与 `git diff --check` 均退出码 0。
- L4 包：`npm pack --dry-run --json` 退出码 0，2.7.0 包清单 45 项，包含五个受管资产/治理模块和本次 Plan、Knowledge、Acceptance 资产。
- L4 fresh install：`/private/tmp/docs-harness-2.7.0-final.ZiMjnn` 从当前源码 init 成功；安装副本 `project diff changes=[]`、`project check`、`self-test`、`assets-check --strict` 和 pre-commit 均退出码 0。
- L4 下游升级：Avatanel 2.6.0→2.7.0 与 ZBuddy 2.4.1→2.7.0 均完成；两项目 `project diff changes=[]`、`self-test`、`assets-check --strict`、pre-commit 与 `git diff --check` 通过，且 `core.hooksPath=scripts/githooks` 已读回。ZBuddy 同步初始化三套资产目录；两项目 `project check` 仅因未提交受管文件返回 `needs_delivery`（red=0、yellow=0）。
- GitHub CI：Workflow 已在源码层完成 YAML 解析，但尚未提交或推送，因此没有远端 Actions 运行证据。
