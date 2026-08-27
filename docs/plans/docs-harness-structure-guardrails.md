> 状态：已实施-仅追溯（代码已是真源，2026-08-27 核对）
<!-- docs-harness:plan-document/v1 -->

# Docs Harness 2.10.0 结构护栏：增量体量检查、CODEMAP 能力索引与骨架先行

- 冻结合同：`sha256:95305ae28b3505b742905fb38f5c0e085ec7f96dc9063bd3db82467227f081b7`
- 关键符号：`check_structure`、`structure_report`、`CODEMAP_RELATIVE`、`module_interfaces`

## 背景

- 大模型写代码是局部贪心的：不主动抽公共模块、单文件越写越大、重复实现导致改一处牵动多处。现有编码质量规范（先复用/重复即抽象/体量红线）是行为约束，纯靠模型自律，无机械暴露渠道。
- 已有 ADR《新增 ScriptHygiene 作为 assets-check 第五个 checker，不建独立资产类型》确立先例：机械检查以 checker 形式挂入 assets-check，不扩资产类型。
- 与用户讨论收敛的结论：检查用增量（diff vs HEAD）而非存量阈值，避免遗留大文件的 WARN 疲劳；复用失败的根因是检索失败，需要代码能力索引（CODEMAP）；复杂任务需要把全局设计前置为可冻结的接口骨架；存量结构债走定期整理任务而非功能任务顺手重构。

## 目标

- 新增 Structure checker（scripts/structure_check.py）挂入 assets-check：增量体量检查（新文件超红线、既有文件本次突破红线、已超标文件本次大幅膨胀、Python 新增/大幅增长函数超 60 行）+ CODEMAP 一致性检查（登记模块存在、符号存活、本次新增代码文件已登记），全部 WARN 级。
- 新增 harness structure 子命令：structure check（单独跑增量检查）与 structure report（存量结构债报告：超红线文件/函数、CODEMAP 覆盖缺口，供定期整理任务使用）。
- 建立 docs/CODEMAP.md 能力索引：本仓登记 scripts/ 全部模块的职责与公开接口；project install/upgrade 为目标项目脚手架空 CODEMAP。
- full 级方案模板新增必填字段 module_interfaces（模块划分与接口骨架），把骨架先行冻结进复杂任务合同；brief 级不加，保持简单任务零负担。
- 同步提示词（_GENERIC_STANDARDS）：编码质量规范补『抽象同样要证据』条款；新增『结构护栏』段写明 CODEMAP 查询/登记义务、骨架先行、增量检查消费方式与定期整理节拍。
- 版本升级 2.9.1 → 2.10.0，release sync --apply 同步全部版本真源，LEGACY_PLAN_TEMPLATE_FINGERPRINTS 登记 2.9.1 模板指纹保证已装项目可升级。

## 非目标

- 不做跨语言的函数级解析：函数长度检查仅覆盖 Python（ast），其他语言只做文件级净增检查，边界写入模块文档与报告。
- 不做重复代码检测（需引入第三方工具，未经确认不加依赖）。
- 不把结构检查升级为 FAIL：全部 WARN 级，处方权留给人；CI --strict 下增量检查天然为空（diff vs HEAD 已提交），仅 CODEMAP 存量一致性在 CI 生效。
- 不为 CODEMAP 建受管 JSON 资产类型（沿用 ScriptHygiene ADR 先例，纯 Markdown 文档 + checker 校验）。
- 不清理本仓既有存量超标文件（harness.py 约 4400 行）——存量债走后续定期整理任务，本次只建立护栏。

## 成功标准

- tests/ 两个测试文件全绿（含新增 Structure 检查聚焦测试）。
- 本仓 assets-check 通过；release sync --strict 一致；self-test 通过。
- 在临时项目实测：新增 600 行文件产生 Structure WARN；非 git 目标 checked=0 不误报；CODEMAP 死符号产生 WARN。
- plan select --complexity complex 输出含 module_interfaces 必填字段。
- CLAUDE.md/AGENTS.md 受管区块经 project upgrade --apply 刷新后包含结构护栏规则。

## 执行范围

- 新增 scripts/structure_check.py；修改 scripts/asset_checks.py（run_assets_check 增加 structure_checker）、scripts/harness.py（接线、structure 子命令、MANAGED_MODULE_RELATIVE_FILES、_GENERIC_STANDARDS、project_doc_scaffolds、VERSION）、scripts/plan_governance.py（LEGACY_PLAN_TEMPLATE_FINGERPRINTS 增 2.9.1）。
- 修改 plan-templates/levels/full.json（module_interfaces 字段）；release sync --apply 触及 VERSION/SKILL.md/package.json/evals/evals.json 与全部模板 version 字段。
- 新增 docs/CODEMAP.md；更新 CHANGELOG.md、CLAUDE.md/AGENTS.md 受管区块；tests/test_v2_direct.py 新增测试与既有断言适配。
- 治理资产：本 Plan、关联 Acceptance、一条 ADR（Structure 作为第六 checker + CODEMAP 文档形态决策）、更新既有 Knowledge《Docs Harness 四资产治理执行机制》。

## 执行内容

- 批次A（检查内核）：写 scripts/structure_check.py（对外仅 check_structure/structure_report 与阈值常量；git IO、diff 解析、ast 函数测量、CODEMAP 解析分层为私有函数）；asset_checks.run_assets_check 增加 structure_checker 参数与 Structure 汇总；harness.py 接线 command_assets_check、新增 structure {check,report} 子命令、MANAGED_MODULE_RELATIVE_FILES 增 structure_check.py；tests 新增聚焦测试；跑新增测试与 assets-check 相关既有测试锁定。
- 批次B（模板与版本）：plan_governance.LEGACY_PLAN_TEMPLATE_FINGERPRINTS 登记 2.9.1 八个模板 LF 归一指纹；full.json 增 module_interfaces 必填字段；harness.py VERSION 改 2.10.0；release sync --apply 同步真源；CHANGELOG 顶部加 2.10.0；跑 release/模板相关测试锁定。
- 批次C（提示词与索引）：_GENERIC_STANDARDS 增『抽象同样要证据』与『结构护栏』段；project_doc_scaffolds 增 docs/CODEMAP.md 脚手架；project upgrade --apply 刷新本仓 CLAUDE.md/AGENTS.md；手写本仓 docs/CODEMAP.md 登记 scripts/ 九个模块；跑受影响测试。
- 批次D（全量回归与治理收尾）：跑 tests/ 全部测试；acceptance record 逐条真实证据；knowledge update 五 checker → 六 checker 事实；adr create；acceptance settle；plan settle --governance-input；assets-check 收尾；提交。

## 验收方案

- 合同层：新增单测覆盖增量文件红线、突破红线、超标膨胀、Python 函数红线、CODEMAP 符号存活、非 git 跳过、structure report 存量清单。
- 模块层：tests/test_v2_direct.py 与 tests/test_release_version_sync.py 全量通过（assets-check 契约变化触发受影响模块完整测试集）。
- 运行层：本仓真实运行 assets-check / structure report / plan select / self-test / release sync --strict，附退出码与关键输出。
- 安装层：临时目录 project init 验证 CODEMAP 脚手架落位、structure_check.py 随装、装后 assets-check 通过。

## 是否需要 Acceptance 资产闭环

```json
true
```

## Knowledge 影响

updated

## 约束

- 全部检查走 git 语义（tracked/untracked 遵守 .gitignore），不建目录排除清单；非 git 目标 checked=0 跳过，与 ScriptHygiene 同口径。
- 阈值必须为具名常量单一来源：FILE_RED_LINE=500、FUNC_RED_LINE=60、OVERSIZE_FILE_GROWTH_ALERT=50、FUNC_GROWTH_ALERT=10。
- HEAD 版本或当前文件 ast 解析失败时跳过该文件函数级判定（不误报、不吞错：文件级检查仍执行）；空仓（无 HEAD）时全部代码文件按新增处理。
- 不引入任何第三方依赖，仅标准库 + git 子进程。

## 风险与回滚

- 风险：既有测试对 assets-check summary/checked 键有断言 → 批次A 跑全部 assets-check 相关测试逐个适配。
- 风险：CODEMAP 符号存活检查误报（符号改名未同步索引）→ 该 WARN 正是设计意图，由 WARN 消费规则转达用户。
- 回滚：改动集中于新模块与少量接线点，单提交 revert 即可整体回滚；模板指纹登记保证 2.9.1 项目升级路径不断。

## 当前约束

- run_assets_check 以显式 checker 参数注入（非注册表），新增 checker 必须改签名与全部调用点（command_assets_check 与测试）。
- 模板 version 字段必须等于 harness VERSION，模板内容变更必然伴随版本升级与 legacy 指纹登记，否则已装项目 upgrade 会把旧模板误判为用户修改。
- CLAUDE.md/AGENTS.md 为受管投影，规则改动只能落在 _GENERIC_STANDARDS 再经 project upgrade 刷新，不得手改。

## 候选方案

- A1 存量阈值检查（扫全仓超标文件）：实现最简，但遗留大文件每次必 WARN，疲劳后全部被无视，且责任归属不清。
- A2 增量检查（diff vs HEAD，本方案）：只对本次改动归责，无历史包袱；代价是 CI 中增量恒空，需 CODEMAP 存量检查补 CI 面。
- A3 CODEMAP 建受管 JSON 资产（指纹+生命周期）：一致性更强，但违背 ScriptHygiene ADR 确立的『不轻易扩资产类型』方向，且索引是高频轻量编辑场景，指纹校验会造成编辑摩擦。
- A4 引入 jscpd/radon 等现成工具做重复与复杂度检测：能力更强，但引入第三方依赖需单独确认，且跨平台安装成本高，列为非目标。

## 真实取舍

- 增量检查换来低噪音，代价是已提交的结构债不可见——用 structure report 存量报告 + 定期整理任务补偿，两者共用同一套测量函数。
- 函数级检查只支持 Python，换来零依赖与实现可靠；非 Python 项目获得文件级保护，边界如实写入文档。
- WARN 级而非 FAIL 保住处方权与豁免通道（体量红线本有『说明理由』出口），代价是约束力弱——靠 WARN 消费规则强制转达兜底。

## 最终决策

采用 A2 增量检查 + CODEMAP 纯 Markdown 文档 + WARN 级 Structure checker 挂入 assets-check，配套 full 模板 module_interfaces 字段与提示词结构护栏段，版本升至 2.10.0。

## 边界与接口

- structure_check.py 对外仅暴露：check_structure(target)->dict（assets-check checker 契约：status/failures/warnings/checked）、structure_report(target)->dict、阈值常量与 CODEMAP_RELATIVE；git 交互、diff 统计、ast 测量、CODEMAP 解析均为模块私有。
- asset_checks.run_assets_check 新增 structure_checker: AssetChecker 参数，汇总标签 Structure，checked 键 structure。
- harness structure 子命令仅是 CLI 投影，不含业务逻辑，直接调用上述两个函数。
- CODEMAP 行契约：`- `模块路径` — 职责：一句话；公开接口：`sym`、`sym``，解析宽松（不匹配行忽略），路径为仓库相对 POSIX 风格。

## 兼容与迁移

- 已装 2.9.1 项目：upgrade 时模板指纹命中 LEGACY_PLAN_TEMPLATE_FINGERPRINTS['2.9.1'] 允许覆盖升级；structure_check.py 随 MANAGED_MODULE_RELATIVE_FILES 安装；docs/CODEMAP.md 仅缺失时脚手架，不覆盖用户内容。
- 无 CODEMAP 的项目：CODEMAP 相关检查整体跳过，不产 WARN，避免未采纳项目的噪音。
- 既有 v2/v3 plan 资产不受影响：module_interfaces 只进入新创建的 full plan。

## 回滚或替代路径

单提交整体 revert；若仅 Structure checker 噪音过大，可后续以 ADR 决策下调阈值或缩窄检查面，不需要回滚版本。

## 架构验收

以临时项目端到端验证 init→写码→assets-check WARN→CODEMAP 登记→WARN 消除 的闭环，加上本仓 upgrade 后 CLAUDE.md 规则与代码门禁一致（提示词与代码流程同步规范）。

## ADR 处理

新增一条 ADR：Structure 增量检查作为 assets-check 第六个 checker，CODEMAP 采用纯 Markdown 文档形态（不建资产类型），阈值常量单一来源于 structure_check.py。

<!-- docs-harness:plan-governance:start -->
## 资产治理

- 关联验收：`docs/acceptance/docs-harness-structure-guardrails.json`
- 需要 Acceptance：true
- Knowledge 影响：updated
<!-- docs-harness:plan-governance:end -->
