> 状态：已实施-仅追溯（代码已是真源，2026-08-27 核对）
<!-- docs-harness:plan-document/v1 -->

# Docs Harness 2.11.0 收敛：结构护栏在主仓 converge-2.11 分支重建到 2.10.2 之上

- 冻结合同：`sha256:943e1bb74b839c368d21fb66424954b334887e6d6a2545fa1af6a933791ddc6d`
- 关键符号：`check_structure`、`command_structure`、`_managed_content`、`LEGACY_PLAN_TEMPLATE_FINGERPRINTS`

## 背景

- 本地 main 基于 2.9.1 快照交付结构护栏（自标 2.10.0）与测试拆分；origin/main 已被其他会话推进 12 笔至 2.10.2。两侧分叉且 2.10.0 撞号。原始提交保留在 backup/pre-converge 分支。
- 下游现状：dsh 2.9.0、AIGlasses/dsh-buddy/opc-skills 2.10.2、dispatch/ZBuddy 2.10.3（带 1 行未合上游的 CHANGELOG/TODO 纪律规范行，位于 _managed_content 运行模式清单末尾）。六项目 config 模板指纹与磁盘全部一致，升级预检不依赖 legacy 指纹表——故撤销本地曾添加的无证据 2.9.1 legacy 条目（防御代码准入），legacy 表保持仅 2.4.1。
- 远端对 tests/test_v2_direct.py 为纯新增（16 测试 + 3 辅助，0 删改）；本地已将该文件拆分为 harness_test_base + 10 个领域文件。
- 执行方式（exec-flow/kimi，用户指令跳过 worktree 环节）：主仓切至基于 origin/main 的 converge-2.11 分支，Kimi CLI 分批移植文件改动（禁止 git 写操作、禁碰 docs/ 与 CLAUDE.md/AGENTS.md）；git 提交、docs 治理层、受管块刷新、终审由主 agent 执行。直接标 2.11.0，不经过撞号中间态。

## 目标

- 批次1：结构护栏引擎与版本移植——structure_check.py、asset_checks/harness 接线、结构护栏与『抽象同样要证据』规范、CODEMAP 脚手架接线、config schema v12、full 模板 module_interfaces 字段、_managed_content 合入 2.10.3 纪律行、VERSION 2.11.0 与 release sync、CHANGELOG 2.11.0 条目。
- 批次2：测试重建——落入 harness_test_base + 10 领域文件（含 v12/体量上限/MANAGED_MODULES 适配），把远端新增 16 测试 + 3 辅助转植入对应领域文件，删除 test_v2_direct.py，全量 101 项绿。
- 主 agent 收尾：docs 层移植（CODEMAP、结构护栏四资产、INDEX 条目）、knowledge 版本事实修正、project upgrade --apply 刷新受管块、本方案结项、分批提交、终审后合并 main 并 push。

## 非目标

- 不执行下游 6 项目升级与 dsh-plugin 发版（另行任务）。
- 不修改远端 12 笔的任何内容；不改写已密封历史资产（结构护栏资产标题中的 2.10.0 字样保留为历史）。
- 不新增 legacy 模板指纹条目（含撤销 2.9.1）。
- 不做 force push。

## 成功标准

- converge-2.11 分支上：unittest discover 101 项全绿（85+16，4 项既有环境跳过）；release sync --strict consistent（2.11.0）；self-test passed；assets-check --strict（提交后）0 违规 0 警告。
- CLAUDE.md/AGENTS.md 受管块同时含结构护栏段、第 10 条『抽象同样要证据』与 CHANGELOG/TODO 纪律行。
- plan_governance 的 LEGACY_PLAN_TEMPLATE_FINGERPRINTS 保持仅 2.4.1。
- main fast-forward 到 converge-2.11 并 push，origin/main == main。
- backup/pre-converge 保留原始提交可回溯。

## 执行范围

- Kimi 批次1：scripts/structure_check.py（新）、scripts/asset_checks.py、scripts/harness.py、plan-templates/levels/full.json、VERSION、SKILL.md、package.json、evals/evals.json、其余 7 个模板 version 字段（release sync --apply 产物）、CHANGELOG.md。
- Kimi 批次2：tests/harness_test_base.py 与 10 个领域测试文件（新）、tests/test_v2_direct.py（删除）。
- 主 agent：docs/CODEMAP.md、docs/plans|acceptance|adr 的结构护栏资产文件、docs/INDEX.md 受管块、docs/knowledge/docs-harness-assets-governance.*、CLAUDE.md、AGENTS.md、.docs-harness/config.json、本方案资产。

## 执行内容

- 批次1（Kimi，规格 .exec-flow-tmp/batch-1.md）：参考材料在 .exec-flow-tmp/ref/（本地版本文件以 .txt 后缀存放避免结构检查噪音）。以分支现行 2.10.2 代码为基座逐点合入：新增文件按 ref 原样落盘；harness.py 按规格列出的接线点合入（保留远端 2.10.x 的 install_conflict 聚合、acceptance 最新记录校验、ADR_EPILOG 元组修复）；_managed_content 运行模式清单末尾加纪律行；VERSION 常量改 2.11.0 后运行 release sync --apply；CHANGELOG 按 ref 文本插入 2.11.0 条目。验证：py_compile 全部 scripts、self-test、release sync --strict、structure check。
- 批次2（Kimi，规格 .exec-flow-tmp/batch-2.md）：从 ref/tests/ 落入 11 个文件；按规格映射把原 test_v2_direct.py 中远端新增的 16 测试与 3 辅助原样搬入指定领域文件（ADR_EPILOG→test_adr，4 个 plan_check→test_plan_lifecycle，2 个 supersede backref→test_plan_governance，2 个 upgrade_reports→test_project_upgrade，3 辅助+7 测试→test_acceptance）；删除 test_v2_direct.py。验证：unittest discover 101 项全绿。
- 每批结束由主 agent 审查（独立重跑验证 + git diff 对照允许清单）并提交该批（只 add 清单内文件）；返工走 kimi -c 续跑，最多 2 轮，仍失败由主 agent 接管。
- 主 agent 阶段：复制 docs 层资产并补 INDEX 受管条目；knowledge update 修正版本表述；project upgrade --apply 刷新 CLAUDE/AGENTS 与 config（v12）；本方案 plan settle；最终提交；终审报告后合并 main 并 push。

## 验收方案

- 批次验证由 Kimi 执行、主 agent 独立重跑核实，不采信执行方自述。
- L2：unittest discover 101 项；L3：self-test / release sync --strict / structure check / assets-check --strict（提交后）；发布层：push 后 origin/main == main。
- 越界防线：每批 git diff 必须落在该批允许文件清单内，越界即回退该批。

## 是否需要 Acceptance 资产闭环

```json
false
```

## Knowledge 影响

updated

## 约束

- Kimi 以 kimi -p 非交互执行（与 --auto/-y 互斥），cwd 为主仓根目录，规格经 --add-dir 授权的 .exec-flow-tmp 引用；执行器禁止 git 写操作、禁改 CLAUDE.md/AGENTS.md 与 docs/、禁新增依赖、禁动 .exec-flow-tmp。
- 密封资产文件以字节复制移植，不重新生成、不手改内容。
- 所有提交只 add 清单内文件，不使用 git add -A；.exec-flow-tmp/ 收尾前删除，永不入库。

## 风险与回滚

- 风险：harness.py 双侧改动合并遗漏——以接线点清单 + 101 项全量测试 + strict 检查兜底；风险：转植测试漏搬——计数不足 101 即点名。
- 风险：Kimi 越界改动——终审逐文件 diff 对照，越界回退该批次。
- 回滚：converge-2.11 为独立分支，任何阶段可弃分支重来；main 与 backup/pre-converge 在合并前不动；push 后问题以 2.11.1 前滚。

## 源与目标

源：origin/main 928ed55（2.10.2）为基座 + backup/pre-converge 541313e（本地结构护栏与测试拆分）为移植素材；目标：converge-2.11 分支产出 2.11.0，fast-forward 合并回 main 后 push。

## 版本与产物

2.10.2（远端现行）与本地自标 2.10.0（撞号，弃用）→ 2.11.0；版本真源七处由 release sync --apply 同步；产物为 git 提交，无二进制分发物。

## 兼容与灰度

config schema v12 兼容 v1-v11 单向升级；2.10.3 纪律行合入上游后 dispatch/ZBuddy 升级不丢补丁；下游升级与 dsh-plugin seed 更新按既定清单另行执行。

## 数据安全

只动 git 与仓内文件；原始提交保留于 backup/pre-converge；密封资产字节级复制；.exec-flow-tmp 脚手架与证据日志不入库；不触碰密钥与用户数据。

## 监控与停止条件

Kimi 批次后台运行，Monitor 60 秒轮询会话流字节数与进程探测；活跃信号 5 分钟无变化告警，连续两次告警停进程转返工或接管；每批验证未过不进下一批；push 前 strict 全绿为发布闸门。

## 回滚

批次内失败：git checkout -- 恢复或弃分支重建；合并前任何问题不影响 main；push 后以 2.11.1 前滚，不改写远端历史。

## 交付层分离

L2 全量测试 → L3 运行层 strict 检查 → 发布层 main==origin/main；下游安装层不在本次交付。

<!-- docs-harness:plan-governance:start -->
## 资产治理

- 关联验收：无
- 需要 Acceptance：false
- Knowledge 影响：updated
<!-- docs-harness:plan-governance:end -->
