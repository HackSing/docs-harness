# Docs Harness 2.7.1 同步验证清单

> 状态：有效（现行事实/实施中）
> 生成：2026-08-15，针对本次同步（bugfix 模板形状 + 输入报错自解释 + 受管入口 schema 门禁）

适用范围：ZBuddy、avatanel 两个已升级项目。以下均为只读检查，不改动任何文件。

## 1. 文件同步完整性

- [ ] `python3 scripts/harness.py project diff --target . --json` → `changes: []`
- [ ] `python3 scripts/harness.py project check --target . --json` → 无 `failures`（`needs_delivery` 仅表示未提交，非失败）

## 2. 受管入口已更新

- [ ] `grep -n "schema_version 与注册字段" AGENTS.md` → 命中 1 行
- [ ] `grep -n "schema_version 与注册字段" CLAUDE.md` → 命中 1 行
- [ ] `grep -c "docs-harness:managed-entry:start" AGENTS.md` → 1（区块完整无重复）

## 3. bugfix 模板 guidance 带形状

- [ ] `grep -n "按对象填写" plan-templates/profiles/bugfix.json` → 命中 3 处（verification_scope / full_regression_trigger / failure_attribution）
- [ ] `grep -n "separate_non_change_failures" plan-templates/profiles/bugfix.json` → 命中 1 处

## 4. 报错自解释（可选，用非法输入实测）

- [ ] knowledge schema 报错附期望值：
  `python3 -c "import sys;sys.path.insert(0,'scripts');import knowledge_assets;knowledge_assets.validate_input(__import__('pathlib').Path('.'),{'schema_version':'x'})"` → 输出含 `docs-harness/knowledge-input/v1`
- [ ] acceptance criterion 映射报错附映射表：
  `python3 -c "import sys;sys.path.insert(0,'scripts');import acceptance_assets;acceptance_assets._criterion({'id':'c1','title':'t','acceptance_type':'behavior_acceptance','layer':'L3','evidence_layer':'focused_test'})"` → 输出含 `focused_test→L2`

## 5. 资产治理闭环

- [ ] `python3 scripts/harness.py assets-check --target . --fast --json` → `status: passed`
- [ ] `python3 scripts/harness.py self-test --target . --json` → `status: passed`

## 6. 提交交付（各自仓库）

- [ ] 上述 9 个升级产物已 `git add` 并提交（`project check` 的 `required_commit_paths` 清空）
- [ ] pre-commit 钩子已激活（新克隆机器先 `bash scripts/githooks/setup.sh`）
