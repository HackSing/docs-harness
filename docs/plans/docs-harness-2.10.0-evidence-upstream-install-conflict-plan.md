> 状态：有效（实施中）
<!-- docs-harness:plan-document/v1 -->

# 上游合入 dsh-buddy 证据加固补丁并改进 install_conflict 报错（2.10.0）

- 冻结合同：`sha256:2ffb9f1b1d32ac5c3ef2a4c371a1eb8ce9ee729bc823e4ec98c5c961904f540c`
- 关键符号：`assert_evidence_usable`、`git_ignored_refs`、`_validate_live_refs`、`install_conflicts`

## 背景

下游项目 dsh-buddy（/Users/aiware/projects/dsh-buddy）在提交 fc3da39（2026-08-22）中直接修改了两个受管文件：scripts/harness.py 新增 git_ignored_refs()/assert_evidence_usable()，在验收证据与失败归因证据登记入口追加 git check-ignore 判定，证据落在 git 忽略路径（如 build/）直接拒绝登记（code=acceptance_evidence_ignored），杜绝“登记时通过、证据从不进仓库、清理后引用永久失效”的复发；scripts/acceptance_assets.py 的 _validate_live_refs 改为只对每个 criterion 的最新一条 record 校验证据存在性与用户确认，被重验取代的历史记录成为纯留痕，不再永久卡住 acceptance check。这两个修复是通用能力，主仓 2.9.1 均不包含（消费点 normalize_failure_attributions 与 build_stored_acceptance_record 仍只查文件存在性）。

副作用：dsh-buddy 升级 2.9.1 时 upgrade preflight 按合同（docs/contracts.md §7 指纹归属 fail-closed）报install_conflict“scripts/harness.py 存在用户修改，拒绝覆盖”。该拒绝本身正确——覆盖会静默抹掉下游修复；但报错体验差：先撞先报只列第一个偏离文件（实际偏离两个：harness.py 与 acceptance_assets.py），无结构化 payload，不给任何出路，人和 agent 都无法据此行动。

## 目标

1) 把 dsh-buddy 两个补丁逐字移植进主仓 docs-harness；2) upgrade preflight 的指纹偏离类 install_conflict 改为一次列出全部偏离文件，message 附三条出路（恢复安装版本/上游合入后升级/保留分叉跳过升级），extra_payload 携带结构化 install_conflicts 清单供 agent 消费；3) 发布 2.10.0；4) dsh-buddy 恢复受管文件官方指纹后升级到 2.10.0，补丁能力由官方版本承接，下游不再持有分叉。

## 非目标

- 不改控制脚本 fail-closed 覆盖语义：不做代码文件增量合并、不加 --force 覆盖开关（合同见 docs/contracts.md §7）。
- 不为 dsh-buddy 补丁指纹开兼容白名单：2.4.1 白名单先例仅适用于官方发布事故，不适用于下游分叉。
- symlink、非常规文件、config 不安全、git 忽略安装文件等结构性 preflight 错误保持即时抛，不并入冲突收集。
- 不改 .docs-harness/config.json schema（保持 project-config/v11，本次无配置形状变化）。
- 不新增第三方依赖，不做与本方案无关的重构。

## 成功标准

- 主仓 scripts/harness.py 存在 git_ignored_refs/assert_evidence_usable，验收证据与失败归因证据两处消费点共用同一函数；git 忽略路径证据登记被拒（acceptance_evidence_ignored），docs/acceptance/evidence/ 等入库路径放行，不存在的文件仍报 acceptance_evidence_missing，非 git 目标不被 check-ignore 锁死。
- _validate_live_refs 只对最新 record 校验；旧记录证据缺失或旧 user_acceptance 记录缺确认不再卡 check，最新记录违规仍 FAIL。
- upgrade 遇多文件指纹偏离时一次性报全：message 列出全部偏离文件与三条出路；payload.install_conflicts 每项含 path/reason/actual_fingerprint/allowed_fingerprints；code=install_conflict 与 exit_code 不变。
- npm test 全量通过；release sync --strict 通过；assets-check --strict 通过。
- dsh-buddy 升级后 .docs-harness/config.json version=2.10.0、全部受管文件指纹匹配、grep assert_evidence_usable scripts/harness.py 命中、assets-check 通过。

## 执行范围

主仓 docs-harness：scripts/harness.py（新增两函数、两处消费点替换、preflight 冲突收集、受管区块模板文案、VERSION）、scripts/acceptance_assets.py（_validate_live_refs）、tests/test_v2_direct.py（新增用例）、CHANGELOG.md、package.json、docs/contracts.md、docs/testing.md、docs/knowledge/docs-harness-assets-governance.json（knowledge update 追加 2.10.0 facts）。
下游 dsh-buddy：scripts/harness.py 与 scripts/acceptance_assets.py（恢复官方指纹后由 upgrade 改写）、.docs-harness/config.json（upgrade 自动改写）。

## 执行内容

分 5 批执行，每批改完→验证→提交锁定，再进下一批。行号为 2.9.1 快照参考值，一律以符号定位为准。

【批次1｜移植补丁A：证据准入加固（scripts/harness.py）】
1. 取补丁真源：cd /Users/aiware/projects/dsh-buddy && git show fc3da39 -- scripts/harness.py。逐字移植，含 docstring，不重写。
2. 在 git_root()（约 :304）之后插入 git_ignored_refs(target, refs)：refs 为空或非 git 仓库返回 []；git check-ignore 返回码非 0（1=无匹配，128=非仓库/git 不可用）返回 []——加固手段不得反向锁死资产登记。
3. 在 evidence_path()（约 :1569）之后插入 assert_evidence_usable(target, refs, what)：先逐条查存在（缺失报 acceptance_evidence_missing，消息含 ref），再查忽略路径（命中报 acceptance_evidence_ignored，消息列出命中路径并指引改存 docs/acceptance/evidence/<验收名>/）。
4. 两处消费点替换为共用调用：normalize_failure_attributions（约 :1605-1607 的存在性循环）→ assert_evidence_usable(target, refs, "失败归因证据")；build_stored_acceptance_record（约 :1745-1747）→ assert_evidence_usable(target, refs, "验收证据")。除这两处不得再有平行的证据存在性检查。
5. 提示词同步（受管区块模板是代码流程的投影）：harness.py 受管文本中“执行中逐条记录真实证据并结项”（约 :462）追加“；证据文件必须位于随仓库提交的路径（如 docs/acceptance/evidence/<验收名>/），git 忽略路径会被拒绝登记”。
6. tests/test_v2_direct.py 新增用例：a) .gitignore 覆盖的 build/ 下证据登记被拒，code=acceptance_evidence_ignored；b) docs/acceptance/evidence/ 下证据放行；c) 不存在文件仍报 acceptance_evidence_missing（原行为未退化）；d) 非 git 目标目录登记不被锁死。
7. 验证：python3 -m unittest tests.test_v2_direct -k evidence（含新增及既有 acceptance 相关用例）全绿，提交本批。

【批次2｜移植补丁B：最新记录语义（scripts/acceptance_assets.py）】
1. _validate_live_refs（约 :441）的 criterion 循环改为 dsh-buddy 版本（真源：/Users/aiware/projects/dsh-buddy/scripts/acceptance_assets.py 工作区当前实现，含注释块逐字移植）：records 为空 continue；只取 criterion["records"][-1]；user_acceptance 确认检查与 passed 证据存在性检查均只对该最新记录生效；settled 豁免原样保留。
2. 新增用例：a) 旧 record 证据缺失+最新 record 证据齐全 → check 通过；b) 最新 record 证据缺失 → FAIL；c) user_acceptance 最新记录缺 confirmed_by=user → FAIL，被取代的旧记录缺确认不再卡。
3. 验证：acceptance/assets-check 相关用例全绿，提交本批。

【批次3｜install_conflict 聚合报错（scripts/harness.py）】
1. preflight_owned_files（约 :2374-2404）：指纹偏离不再即时 raise，改为向调用方传入的 conflicts 列表追加 {"path": "<install_relative>/<relative>", "reason": "modified", "actual_fingerprint": ..., "allowed_fingerprints": sorted(allowed)}；symlink/非常规文件/安装指纹无效仍即时 raise（结构性错误，性质不同）。
2. install_preflight（约 :2407-2503）：建立 conflicts 列表；scripts/harness.py 自身指纹检查（约 :2448-2457）偏离时同样只收集；三次 preflight_owned_files 共用同一列表；全部归属检查完成后统一判定：conflicts 非空 → raise HarnessError(code="install_conflict", extra_payload={"install_conflicts": conflicts})。
3. message 文案（产品体验合同，两句以内、一次报全、给出路）：“受管文件存在本地修改，升级未写入：<path1>、<path2>。恢复安装版本后重试升级；确需保留的修改请合入 docs-harness 随新版本升级；保持分叉则跳过升级。”
4. code=install_conflict 与默认 exit_code 不变——现有 6 处用例（tests/test_v2_direct.py:1354/1368/1675/1712/1725/1833）只断言 code，必须保持通过。
5. 新增用例：2.9.1 已安装项目同时手改 scripts/harness.py 与 scripts/acceptance_assets.py → upgrade --apply 单次报错、payload["install_conflicts"] 恰含两个 path；单文件修改 → 列表长度 1 且 path 正确。
6. 验证：install/upgrade 相关用例全绿，提交本批。

【批次4｜版本、文档与治理资产】
1. VERSION（scripts/harness.py:62）与 package.json version → 2.10.0。
2. CHANGELOG.md 顶部新增 2.10.0 条目（风格对齐既有条目）：三项改动各写动机；注明证据加固与最新记录语义源自下游 dsh-buddy fc3da39 的生产验证，本次上游合入。
3. docs/contracts.md：验收合同段补证据准入规则（存在＋不落 git 忽略路径＋只校验最新记录）；§7 安装合同补一句报错行为（指纹偏离一次性列出全部文件并附恢复/上游/分叉出路，extra_payload.install_conflicts 携带结构化清单）。
4. docs/testing.md 登记本次新增用例。
5. knowledge update 追加 2.10.0 facts 到 docs/knowledge/docs-harness-assets-governance.json（证据准入加固、最新记录语义、install_conflict 聚合报错；输入形状先看 python3 scripts/harness.py knowledge update --help）。
6. 全量验证（发版入口，满足仓库级全量触发条件）：npm test；python3 scripts/harness.py release sync --strict；python3 scripts/harness.py assets-check --strict。全绿后提交本批。

【批次5｜下游 dsh-buddy 升级（在 /Users/aiware/projects/dsh-buddy 执行）】
1. 恢复两个受管文件为 2.8.1 官方版本：git checkout ea4785a -- scripts/harness.py scripts/acceptance_assets.py。
2. 【陷阱，勿踩】此时不要运行 assets-check / acceptance check：恢复后暂回旧校验语义，docs/acceptance/plugin-incremental-update.json 的历史记录会 FAIL——这是中间状态的预期现象，直接进行下一步升级。
3. 立即升级：python3 scripts/harness.py project upgrade --apply --source /Users/aiware/projects/docs-harness（在 dsh-buddy 仓库根执行；命令形状以 project upgrade --help 为准）。
4. 验证：grep -n assert_evidence_usable scripts/harness.py 命中；.docs-harness/config.json 的 version=2.10.0；python3 scripts/harness.py assets-check 通过（历史记录被最新记录语义放行）；按 dsh-buddy 提交惯例提交升级改动。

## 验收方案

用 acceptance create 建立验收资产并关联本 Plan，criteria 至少四条，逐条 acceptance record 附真实证据（证据一律放 docs/acceptance/evidence/<验收名>/——本方案自己引入的忽略路径规则自己先遵守）：
- C1 合同层：npm test 全量输出，退出码 0。
- C2 真实流程·证据加固：临时目录 fresh init + git init + .gitignore 含 build/；向 build/ 登记证据被拒（acceptance_evidence_ignored），向 docs/acceptance/evidence/ 登记通过；附命令与输出。
- C3 真实流程·升级报错：2.9.1 安装的临时项目手改两个受管文件 → upgrade --apply 一次列全两个文件且 install_conflicts payload 形状正确；恢复文件后 upgrade 成功落 2.10.0；附命令与输出。
- C4 下游真实项目：dsh-buddy 升级完成的四项验证输出（grep 命中、config 版本、指纹匹配、assets-check 通过）。
失败修复后显式 --reaccept；全部通过后 acceptance settle 结项；收尾运行 assets-check。结算顺序：knowledge update → acceptance settle → plan settle --status implemented（--governance-input 的 updated_knowledge_refs 指向 docs-harness-assets-governance）。

## 是否需要 Acceptance 资产闭环

```json
true
```

## Knowledge 影响

updated

## 约束

- 两个补丁以 dsh-buddy 实现为唯一真源逐字移植（含 docstring 与注释），不重写、不“顺手优化”；偏离真源的每一处都必须在收尾报告中说明理由。
- 遵守仓库 CLAUDE.md 全部编码规范（先复用后新写、错误不许吞、边界一次校验等）；harness.py 超 500 行属既有事实，本次不做无关拆分。
- 现有测试用例除新增外不得改动断言语义；install_conflict 的 code 与 exit_code 是对外合同，不得变。
- 批次之间不得跳批合并提交；批次5 的第 2 步顺序陷阱不得跳过阅读。

## 风险与回滚

- 风险1·行为收紧：证据落忽略路径的登记从放行变拒绝，下游项目的新登记可能开始被拒——这是设计目的，报错文案已给出正确存放位置；既有已登记资产不受影响（只影响新登记）。
- 风险2·校验放松：最新记录语义使被取代的历史记录不再校验——该语义已在 dsh-buddy 生产验证，且重验必须走正规 acceptance record 流程，不构成绕过；测试覆盖正反用例。
- 风险3·抛错时机变化：preflight 从第一处即抛改为收集后统一抛，只影响错误路径，成功路径零变化。
- 回滚：三项改动独立提交、可单独 revert；发版后发现问题以 2.10.1 前滚修复，不回收 2.10.0。

<!-- docs-harness:plan-governance:start -->
## 资产治理

- 关联验收：无
- 需要 Acceptance：true
- Knowledge 影响：updated
<!-- docs-harness:plan-governance:end -->
