# Docs Harness 2.3.0 生命周期审计报告

> 审计日期：2026-08-13
> 审计对象：D:\Project\docs-harness（上游源包，VERSION=2.3.0，harness.py 107322→107618 字节，含本轮文案修复）
> 审计环境：Windows 25H2，Python 3.11（uv），PowerShell 5.1，非提权会话
> 事实基线（本轮前置已取证）：上游与 ZBuddy fork harness.py 逐字节一致、受管块断言通过、e2e fresh init 通过、unittest 基线 35 用例 1F/5E

## 总览

| 级别 | 数量 | 说明 |
| --- | --- | --- |
| 阻断 | 0 | 无 |
| 缺陷（已修） | 2 | invalid_source 文案误导；测试夹具 Windows 换行失真 |
| 行为设计缺口（已修） | 1 | 安装副本自跑 upgrade 的源包定位问题（已实施 `--source` 参数） |
| 体验 | 3 | 幂等状态措辞、uninstall preview 保留清单、acceptance 缺字段提示 |
| 文档（已修） | 1 | SKILL/README 命令面缺口与占位符不一致 |
| 环境未覆盖 | 2 | symlink 权限（WinError 1314）×4 用例、npm 缺失 ×1 用例 |

本轮直接修复（随上游 2.3.0 未提交改动一并待验收）：

1. `scripts/harness.py`：`validate_project_source` 错误文案补提示（见缺陷 D1）。
2. `tests/test_v2_direct.py`：`write_v5_install` 写规则文件加 `newline=""`（见缺陷 D2）。
3. `SKILL.md` / `README.md`：补齐 `project check|diff|uninstall`、`docs-check`、`self-test` 用法，统一 `<docs-harness-2.3.0-source>` 占位符（见文档 F1）。
4. 上游自托管自我 upgrade：AGENTS.md/CLAUDE.md 受管块与 config 从 2.0.0 刷新到 2.3.0（已验证改动严格限于受管块与 config，块外内容逐字节不变）。
5. ZBuddy fork 同步 upgrade：`scripts/harness.py` 与 `.docs-harness/config.json` 指纹刷新，两仓库重新逐字节一致；ZBuddy self-test 与 docs-check 均 passed。

未做任何 git 提交/推送；上游 check 剩余 `pending_commit`（red=0）与 ZBuddy 工作区改动留待用户裁决提交。

## 审计一：全新安装流程（临时目录矩阵）

夹具目录：`%TEMP%\dh-audit-230\`（非 git 场景），证据见 ZBuddy `output/audit-2.3.0/a1-*.txt`。

| 步骤 | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `project init --target p1-fresh --apply` | 0 | 12 个产物齐全（AGENTS.md/CLAUDE.md/scripts/harness.py/8 模板/.docs-harness/config.json），harness.py 与源包 hash 一致，config 为 v6 schema 含脚本与模板指纹 |
| 2a | `self-test` | 0 | 7 项检查全过 |
| 2b | `docs-check` | 0 | 期望 skipped，reason 明确（docs/plans、docs/INDEX.md 不存在） |
| 2c | `project check` | 0 | passed，red=0 |
| 2d | `project diff` | 0 | changes=[]，无漂移 |
| 3a | 重复 `project init --apply` | 0 | planned_changes=[]、changed=[]，幂等 |
| 3b | 重复 `project upgrade --apply` | 0 | 同上幂等（措辞为 installed/upgraded 而非 already_consistent，见体验 E1） |
| 4a | `project uninstall`（preview） | 0 | would_remove 列出受管块/config/owned 脚本/模板 |
| 4b | `project uninstall --apply --purge-runtime` | 0 | 12 项全删；USER-NOTES.md 与 docs/mydoc.md 保留；AGENTS.md/CLAUDE.md 仅剩标题行 |
| 4c | 卸载后 `project check` | 1 | 不崩溃，报 missing_config（red=1），语义正确 |
| 4d | 卸载后 `project diff` | 0 | 列出完整重装 diff，语义正确 |
| 5a | git init 后 `project init --apply` | 3 | status=needs_delivery、delivery_status=pending_commit、required_commit_paths 完整（commit 闭环门禁，未执行任何提交） |
| 5b | .gitignore 忽略安装文件后 init/check | 3/1 | `git_delivery_ignored` 防护触发，init 拒绝写入 |

补充取证：目标目录位于外部 git 仓库的 ignored 子目录（ZBuddy `output/`）时，init 同样被 `git_delivery_ignored` 拒绝（EXIT=3）——防护按最近 git 根判定，行为正确。

## 审计二：升级流程

证据见 `output/audit-2.3.0/a2-*.txt`。

### 2.1 滞后项目 2.0.0 → 2.3.0（git archive 1fe8454 取 2.0.0 源包）

| 步骤 | 结果 |
| --- | --- |
| 2.0.0 源包 init 滞后项目 | 成功，config version=2.0.0，指纹为 2.0.0 脚本 |
| 2.3.0 `project upgrade` preview | from_version=2.0.0 → to_version=2.3.0，apply_completion_possible=true，preview 不写入（快照一致由单测覆盖） |
| `project upgrade --apply` | upgraded；脚本字节一致（hash True）、config version=2.3.0、AGENTS.md/CLAUDE.md 受管块头为 2.3.0 |
| 升级后 `self-test` | passed |

### 2.2 安装副本自跑 upgrade 的缺口（缺陷 D1 + 行为缺口 B1）

- 复现：项目内副本模板被删一个（bugfix.json）后从副本跑 `project upgrade` → `invalid_source: 来源包缺少完整 2.3.0 方案模板`，EXIT=2。
- 根因：`SCRIPT_ROOT = Path(__file__).resolve().parents[1]`，`command_project` 以 `source_root = SCRIPT_ROOT` 取源；从安装副本调用时源包即目标项目自身。模板完整时静默 no-op（不会从更新源升级），不完整时报错且文案误导用户"来源包"有问题。
- 已修（文案，安全）：两条 `invalid_source` 消息追加提示"若你正从项目内已安装的副本运行 init/upgrade，请改用完整的 Docs Harness 2.3.0 源包，或先恢复项目内缺失的 plan-templates 文件"。修复后经同步副本复测，新文案生效（EXIT=2 不变）。
- **已实施（用户裁决采用选项 B，2026-08-13）**：`project init|upgrade` 新增 `--source <源包目录>`，允许项目内安装副本显式指定完整源包。校验：必须为真实目录（拒绝符号链接）、通过 `validate_project_source`、版本与当前控制器一致（`VERSION` 文件优先，否则解析源包 scripts/harness.py，不符报 `source_version_mismatch` 并提示跨版本升级须直接运行源包控制器）；`--source` 与 check/diff/uninstall 组合报 `invalid_request`。preview/apply payload 新增 `source` 与 `source_is_target` 字段，"源即目标"的自升级 no-op 场景从此在输出中显式可见。新增单测 2 例（`test_upgrade_source_flag_repairs_installed_copy`、`test_upgrade_source_flag_rejects_version_mismatched_source`），SKILL/README 同步补命令与约束。
- 注：SKILL.md/README.md 已明确"必须从源包运行 upgrade"（本轮补全文档同时写入该约束），文案修复与文档约束互为表里。

### 2.3 既有失败归因：test_upgrade_v5_preview_apply_cleanup_and_repeat_are_one_way（缺陷 D2，已修）

- 现象：期望 `('.docs-harness/harness-home/rules/owned.md', 'remove_owned_legacy')` 出现在 cleanup plan，实际被判为 preserved。
- 根因链：`write_v5_install` 用 `write_text`（Windows 默认 `\r\n`）写规则文件，但 `installed_rule_fingerprints` 用 LF 内容计算 sha256；`legacy_cleanup_plan` 以 `file_fingerprint`（读原始字节）比对 → 不匹配 → preserved。独立最小复现证明 Windows 上 `write_text` 磁盘字节含 CRLF 且与 LF 指纹不等。
- 定性：测试夹具失真，非判定链缺陷（其余条目 knowledge-map/INDEX/runtime 全部正确命中；生产安装路径由同一写函数同时写字节与指纹，不存在该问题）。
- 修复：夹具写规则文件加 `newline=""`。修复后该测试单跑 OK，全量 35 用例该 F 消失。

### 2.4 symlink 用例与 npm 用例（环境归因，未覆盖）

- 4 个 symlink 用例（knowledge docs symlink / init scripts 父级 symlink / upgrade runtime root symlink / legacy rule symlink）均报 `OSError: [WinError 1314] 客户端没有所需的特权`。
- 尝试提权重跑：`Start-Process -Verb RunAs` 后 UAC 未获授权（输出文件未产生）；注册表无 `AllowDevelopmentWithoutDevLicense`（开发者模式未开）。按授权边界不再升级尝试，归因环境，标注**未覆盖**。
- 第 5 个 ERROR `test_package_exposes_only_current_public_docs`：`npm` 不在 PATH（FileNotFoundError WinError 2），与 symlink 无关，同为环境归因。

## 审计三：项目内日常命令（安装态实测）

证据见 `output/audit-2.3.0/a3-*.txt` 与 `.py` 脚本。

### 3.1 knowledge query 分支

| 场景 | 结果 |
| --- | --- |
| 无 docs/（p2-legacy） | EXIT=0，facts=[]，mode=knowledge_assist |
| 有 docs/（p1-fresh，docs/mydoc.md） | 命中 `docs/mydoc.md:1` |
| 有 `.qoder/repowiki/zh/content/` | 命中 repowiki 条目，ref 正确 |

### 3.2 plan select / create

- select 抽样：simple+general → `plan_level=none`（direct execution）；complex+frontend_ui+cross-module → full/frontend_ui 含 12 字段；moderate+bugfix+high-risk → full/bugfix 含 4 项结构化合同字段；显式 `--level brief --profile general` → brief 4 字段。全部 EXIT=0，`selection_fingerprint` 稳定。
- create：冻结成功（EXIT=0，`docs_hygiene_hint` 存在）；同内容重放指纹一致且幂等；异内容同输出 → `plan_already_frozen` EXIT=3；缺必填字段 → `invalid_plan_content` EXIT=2 且指明 `steps`。

### 3.3 acceptance record v3

| 用例 | 退出码 | 结果 |
| --- | --- | --- |
| passed + behavior_acceptance + evidence_layer=focused_test + method + 证据文件存在 | 0 | `claim=behavior_accepted`，记录落盘 `.docs-harness/v2/acceptance/` |
| failed + failure_attributions(environment) | 3 | 记录落盘；failed 返回 3 为设计（非错误码） |
| evidence_layer 与 layer 不匹配（L3 vs focused_test→L2） | 2 | `invalid_acceptance_input`，消息指明应记录在 L2 |
| passed 缺 method | 2 | "行为验收通过必须提供方法和证据"（见体验 E3） |

非法输入拒绝的更多分支（重复归因、未知类别、证据缺失、user_pending 合同等）由单测覆盖确认，未逐一重放。

### 3.4 docs-check

| 场景 | 退出码 | 结果 |
| --- | --- | --- |
| 违规临时项目（无横幅 + 无索引条目） | 1 | 2 条 FAIL 精确命中；`--strict` 同样 EXIT=1（failures 本身就非 0；--strict 语义为 WARN 也计入失败，已从代码确认） |
| ZBuddy 实跑 | 0 | passed：活文档 26、归档 9、扫描 1474 份 markdown、违规 0 |

### 3.5 提示词投影核对（安装态逐一打勾）

ZBuddy AGENTS.md 受管块与全文引用的命令/路径：

- `python scripts/harness.py docs-check` → 实跑 passed ✔
- `docs/INDEX.md`、`docs/plans/`、`.qoder/repowiki/zh/content/`、`zbuddy/scripts/electron-visual/`、`zbuddy/docs/testing.md`、`scripts/windows/internal/test-powershell-contract.ps1`、`plan-templates/`、`smartclaw/docs/ARCHITECTURE.md`、`zbuddy/docs/INDEX.md` → 全部存在 ✔
- `npm run verify:electron-ui` → package.json 中定义存在 ✔（未实跑，会启动 Electron 构建）

## 审计四：文档与自托管一致性

### 4.1 SKILL.md / README.md（文档 F1，已修）

修复前覆盖度：SKILL 缺 `project check|diff|uninstall`、`docs-check`、`self-test`；README 缺 `project uninstall`、`docs-check`；SKILL 占位符 `<docs-harness>` 与 `<docs-harness-2.3.0-source>` 混用。
修复后：12 条命令（init/upgrade/check/diff/uninstall/docs-check/knowledge query/plan select/plan create/acceptance record/self-test/release）在两份文档全覆盖；占位符统一为 `<docs-harness-2.3.0-source>`；补充 uninstall 保留语义、docs-check `--strict` CI 语义与"upgrade 不得从滞后安装副本取源"约束。

### 4.2 上游自托管

- 审计初跑 `project check`：3 red（version_mismatch/script_drift 判定来自 config 版本 2.0.0 与受管块漂移），diff 列 3 项（两个受管块 + config）。
- 自我 upgrade preview 仅 3 项 owned 变更，符合"受管块外内容不动"边界；apply 后用脚本剥离受管块对比：AGENTS.md/CLAUDE.md 块外内容**逐字节不变**。
- 升级后 check：red=0，仅剩 `pending_commit`（EXIT=3，等待用户提交，授权边界内不提交）。

### 4.3 evals.json / CHANGELOG

- evals.json：schema v2、version=2.3.0、19 个行为断言用例；含旧命令 token 的用例均为负向断言（no-verify、pre-v2-one-way-migration 等），与 2.3.0 单向迁移设计一致。
- CHANGELOG 2.3.0/2.2.0/2.1.0/2.0.0 条目与本轮实测行为逐条吻合（docs-check skipped 语义、CLAUDE 共享受管内容、v3 验收合同、证据层映射等）。

## 最终回归

`python -m unittest discover -s tests`（上游，修复后）：Ran 35，**0 failures / 5 errors**；B1 实施后复跑：Ran 37（新增 2 例全过），仍为 **0 failures / 5 errors**（5E 不变，均为环境归因）。
对比基线 1F/5E：1F（test_upgrade_v5...）已修复；5E 全部为环境归因（4× WinError 1314 symlink 权限 + 1× npm 不在 PATH），与本轮修改无关，未覆盖项已在 2.4 标注。

## 遗留事项（待用户裁决）

1. ~~**B1 行为缺口**~~：已按用户裁决实施方案 (b)（`--source` 参数），见 2.2 节更新说明。
2. 上游与 ZBuddy 两仓库的全部改动（含本报告）均未提交；上游 check 为 pending_commit 状态，是否提交留待用户。
3. symlink 4 用例与 npm 1 用例需在提权/开发者模式或具备 npm 的环境补覆盖。

## 体验类观察（未改代码）

- E1：重复 init/upgrade 返回 `status: installed/upgraded` + 空 changed；`already_consistent` 措辞仅 release 命令使用，语义口径不完全一致。
- E2：uninstall preview 的 `would_preserve` 为空数组，不枚举将保留的用户文件（实际保留行为正确，仅预览信息不充分）。
- E3：acceptance passed 缺 `method` 时报"必须提供方法和证据"，未指明具体缺失字段名。

## 证据索引（ZBuddy output/audit-2.3.0/）

- a1-1-init.txt / a1-2-installed-cmds.txt / a1-3-repeat.txt / a1-4-uninstall.txt / a1-5-git.txt
- a2-1-upgrade.txt / a2-2-installed-copy-upgrade.txt / a2-3-failing-test.txt / a2-4-unittest-mid.txt / a2-4-symlink-elevated.txt（未产生=UAC 未授权）
- a3-1-knowledge.txt / a3-2-plan.txt / a3-2-plan-create.txt / a3-3-acceptance.txt / a3-4-docscheck.txt
- a4-1-docs-coverage.py / a4-1-docs-fix.py / a4-2-selfhost.txt / a4-2-selfupgrade-preview.txt / a4-2-AGENTS.before.md / a4-2-CLAUDE.before.md / a4-2-verify-blocks.py / a4-3-evals.py / a4-3-evals-ctx.py / a4-zbuddy-upgrade-preview.txt
- a5-final-unittest.txt
- 修复脚本：fix-invalid-source-msg.py / fix-test-newline.py
