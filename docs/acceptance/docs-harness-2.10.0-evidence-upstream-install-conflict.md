> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# 2.10.0 证据准入加固与升级冲突聚合报错治理验收

- 修订：6
- 关键符号：`assert_evidence_usable`、`acceptance_evidence_ignored`、`install_conflicts`
- 资产指纹：`sha256:967807932199303eb192f4a0a94c32398d2b3110af46a78c10996f80247ffc78`
- 关联方案：`docs/plans/docs-harness-2.10.0-evidence-upstream-install-conflict-plan.json`

## 验收目标

验收 2.10.0 证据准入加固与 install_conflict 聚合报错：合同层 npm test 全量通过；真实流程验证 git 忽略路径证据登记被拒、入库路径放行；临时项目升级一次列全全部冲突且 payload 形状正确；下游 dsh-buddy 升级后受管文件与上游一致、治理检查通过。

## 验收标准

### `c1` 合同层：npm test 全量通过，退出码 0

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/docs-harness-2.10.0-evidence-upstream-install-conflict/c1-npm-test.txt`

### `c2` 真实流程·证据加固：临时项目 fresh init + git init + .gitignore 含 build/，向 build/ 登记证据被拒（acceptance_evidence_ignored），向 docs/acceptance/evidence/ 登记通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/docs-harness-2.10.0-evidence-upstream-install-conflict/c2-evidence-hardening.txt`

### `c3` 真实流程·升级报错：2.10.0 安装的临时项目手改两个受管文件，upgrade --apply 一次列全两个文件且 install_conflicts payload 形状正确；恢复后 upgrade 成功

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/docs-harness-2.10.0-evidence-upstream-install-conflict/c3-upgrade-conflict.txt`

### `c4` 下游真实项目 dsh-buddy：assert_evidence_usable grep 命中、config version=2.10.0、受管文件与上游一致、assets-check 通过、adr --help 尾部完整单行

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/acceptance/evidence/docs-harness-2.10.0-evidence-upstream-install-conflict/c4-dsh-buddy.txt`
