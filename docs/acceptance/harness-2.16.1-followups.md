> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# 2.16.1 收尾四项验收：下游结构检查排除、包清单守卫、inputs 约定、usage 提示

- 修订：6
- 关键符号：`is_source_package`、`TASK_INPUTS_RELATIVE`、`usage_enabled_notices`
- 资产指纹：`sha256:f41dc091ca9766404537ad5b0e0d4b386bca8e583342cb776c6916b779a10b13`
- 关联方案：`docs/plans/harness-2.16.1-followups.json`

## 验收目标

验证 2.16.1 四项收尾在合同、下游运行、安装与发布四层均有真实证据：下游 structure check 不再报 harness 自带文件且对损坏的 package.json / 非 UTF-8 SKILL.md 不崩、源包守卫不被削弱；package.json 无死条目且守卫覆盖；.docs-harness/inputs/ 落盘不入库不被清理；v12→v13 升级出一次性 usage 提示、v13 再升级不出；版本六源同步到 2.16.1。

## 验收标准

### `contract.suite` 合同层：全量 unittest 全绿、self-test passed、assets-check --strict 除预期 Structure WARN 外无 FAIL

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/harness-2.16.1-followups/contract-suite.txt`

### `runtime.downstream` 运行层：下游型现场 structure check 零 WARN 且对损坏 package.json 与非 UTF-8 SKILL.md 不崩、源包型现场 WARN 保留、v12 升级出 notices、inputs 目录与 gitignore 落盘且 check-ignore 命中

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/harness-2.16.1-followups/structure-exempt.txt`、`docs/acceptance/evidence/harness-2.16.1-followups/usage-notice.txt`

### `install.surface` 安装层：project init/upgrade 到 fixture 零 finding、inputs 不被 legacy 清理、package.json files 每项存在、npm pack --dry-run 清单含两个受管模块

- 状态：passed
- 类型：behavior_acceptance
- 层级：L4
- 证据：`docs/acceptance/evidence/harness-2.16.1-followups/install-surface.txt`

### `release.consistency` 发布层：release sync --strict 退 0、CHANGELOG 顶部为 2.16.1、本仓库受管区块同步、plan check 退 0

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/harness-2.16.1-followups/release-consistency.txt`
