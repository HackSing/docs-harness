> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# Docs Harness 2.10.0 结构护栏验收（Structure checker、CODEMAP、骨架先行模板）

- 修订：6
- 关键符号：`check_structure`、`structure_report`、`CODEMAP_RELATIVE`、`module_interfaces`
- 资产指纹：`sha256:6c0b79d0e43e9f3f4579bbdc1b2afd68a4ea4508bb3deb8960f09113ece957a6`
- 关联方案：`docs/plans/docs-harness-structure-guardrails.json`

## 验收目标

验证结构护栏三层落地：Structure 增量检查挂入 assets-check 且行为符合契约、CODEMAP 索引建立并被检查消费、full 模板含 module_interfaces、版本真源同步且受管提示词刷新。

## 验收标准

### `c1` Structure 检查合同：新增聚焦单测覆盖新文件红线、突破红线、超标膨胀、Python 函数红线、CODEMAP 符号存活、非 git 跳过与 structure report 存量清单，全部通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/testing/logs/structure-guardrails/c1-focused-tests.log`、`scripts/structure_check.py`、`tests/test_v2_direct.py`

### `c2` 受影响模块完整测试集：tests/test_v2_direct.py 与 tests/test_release_version_sync.py 全量通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/testing/logs/structure-guardrails/c2-full-suite.log`、`tests/test_v2_direct.py`、`tests/test_release_version_sync.py`

### `c3` 本仓真实运行：assets-check 通过、structure report 输出存量债、plan select 含 module_interfaces、self-test 通过、release sync --strict 一致

- 状态：passed
- 类型：behavior_acceptance
- 层级：L3
- 证据：`docs/testing/logs/structure-guardrails/c3-runtime.log`、`docs/CODEMAP.md`

### `c4` 安装层：临时项目 project init 后 structure_check.py 随装、docs/CODEMAP.md 脚手架落位、装后 assets-check 通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L4
- 证据：`docs/testing/logs/structure-guardrails/c4-install.log`
