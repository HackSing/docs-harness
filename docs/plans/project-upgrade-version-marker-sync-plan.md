# Docs Harness 项目升级版本标记同步方案

状态：已实现  
实现版本：Docs Harness v1.4.1  
适用范围：`project init`、`project diff`、`project upgrade`、`project check`

## 1. 背景与问题定义

当前 `project upgrade` 会更新项目内的控制脚本、规则快照、`.docs-harness/config.json`，并替换 `AGENTS.md` 与 `CLAUDE.md` 的受管入口区块，但不会统一同步项目可见的 Docs Harness 版本信息：

- `AGENTS.md` 顶部可能仍显示旧版本；
- 已存在的 `docs/INDEX.md` 可能仍显示旧版本；
- `docs/modules/INDEX.md` 等旧知识索引可能仍保留旧版 Harness 条目。

结果是项目实际控制器已经升级，但入口文档仍显示旧版本，upgrade 输出、项目检查与人工判断不能形成同一结论。

## 2. 目标

1. 由升级器确定性维护 Docs Harness 自己拥有的项目版本标记。
2. preview 在写入前完整报告版本变化和人工迁移项。
3. preserve-and-merge 项目文档，只修改受管区块或可唯一识别的旧模板。
4. 无法确认所有权时失败关闭，不猜测、不全局替换版本号。
5. `project check` 能识别配置、控制器和受管版本标记不一致。
6. upgrade apply 幂等，重复执行不产生新变化。

## 3. 非目标与产品边界

- 不自动创建项目 ADR。
- 不自动修改 ADR 索引或项目 Changelog。
- 不删除 `docs/modules/`，也不把模块知识静默改写为功能知识。
- 不修改项目自己的产品版本、模块版本或发布版本。
- 不自动提交、推送、发布或修改 `.gitignore`。

ADR、ADR 索引和 Changelog 属于项目事实。upgrade 只能输出建议同步项，或由正式任务完成后的后台治理合同另行处理；没有项目证据和宿主执行结果时，不得宣称已经更新。

## 4. 版本真源与受管边界

### 4.1 版本真源

- 来源包版本：根目录 `VERSION`。
- 控制器运行版本：`scripts/harness.py` 的 `VERSION`；发布检查必须证明它与根目录 `VERSION` 一致。
- 项目安装版本：`.docs-harness/config.json` 的 `version`。
- 项目可见版本：由同一次来源包版本生成，不再单独手工维护。

### 4.2 `AGENTS.md`

版本信息进入现有受管区块：

```text
<!-- docs-harness:managed-entry:start -->
Docs Harness 当前版本：&lt;来源包版本&gt;
...
<!-- docs-harness:managed-entry:end -->
```

区块外即使出现旧版本文字，也默认属于项目内容。升级器不直接覆盖，而是在 preview 中返回迁移提示，避免误改用户规则。

### 4.3 `docs/INDEX.md`

新增独立、最小的版本受管区块：

```text
<!-- docs-harness:managed-version:start -->
Docs Harness 当前版本：&lt;来源包版本&gt;
<!-- docs-harness:managed-version:end -->
```

升级器只创建或替换该区块，不重排标题、索引和项目说明。

### 4.4 旧知识索引

对于 `docs/modules/INDEX.md` 等旧索引，只自动处理：

1. 已存在 `docs-harness:managed-version` 区块；
2. 与登记旧模板完全匹配、且语义唯一的 Docs Harness 版本行。

其他包含版本号的正文不自动修改，返回 `needs_manual_migration`。不得用宽泛正则扫描和替换整个 `docs/`。

## 5. 命令合同

### 5.1 `project init`

- 新建 `AGENTS.md` 时，在入口受管区块写入当前版本。
- 新项目创建 `docs/INDEX.md` 时，同时写入版本受管区块。
- 已有 `docs/` 的项目继续保持安装阶段零内容覆盖；版本区块由 upgrade preview/apply 处理。

### 5.2 `project diff` 与 upgrade preview

安全变化返回：

```json
{
  "path": "docs/INDEX.md",
  "action": "update_managed_version",
  "from_version": "<已安装版本>",
  "to_version": "<来源包版本>"
}
```

归属不明时返回：

```json
{
  "path": "docs/modules/INDEX.md",
  "action": "needs_manual_migration",
  "reason_code": "unowned_legacy_version_reference"
}
```

preview 不写文件。存在人工迁移项时，结果必须显式保留风险，不能只报告控制器可以升级。

### 5.3 `project upgrade --apply`

执行顺序：

1. 校验来源包版本真源一致；
2. 完成现有控制脚本和规则冲突检查；
3. 更新 `AGENTS.md` 入口受管区块；
4. preserve-and-merge `docs/INDEX.md` 版本区块；
5. 更新可唯一识别的旧索引受管版本；
6. 写入 `.docs-harness/config.json`；
7. 重新执行项目检查，返回实际变化、人工迁移项和 Git 交付状态。

归属不明的旧版本正文不得覆盖。是否允许控制器部分升级由实现评审决定，但最终状态不能使用无条件 `upgraded` 隐藏残留。

### 5.4 `project check`

新增检查码：

- `managed_entry_version_mismatch`：`AGENTS.md` 受管版本与配置不一致；
- `knowledge_index_version_mismatch`：`docs/INDEX.md` 受管版本与配置不一致；
- `legacy_version_reference`：登记路径中仍有可识别的旧版 Harness 标记；
- `source_version_inconsistent`：来源包 `VERSION`、控制器版本和技能元数据不一致。

普通业务文档中的版本号不得被误报。

## 6. 实现范围

计划修改：

- `scripts/harness.py`
  - 增加版本区块常量与生成函数；
  - 扩展 `project_changes()`、`apply_project_install()`、`project_findings()`；
  - 增加旧模板白名单与人工迁移结果；
  - 增加来源版本一致性检查。
- `tests/test_harness.py`
  - 增加初始化、预览、应用、检查、冲突、幂等和 Git 交付回归。
- `README.md`、`SKILL.md`、`docs/contracts.md`
  - 同步当前 upgrade 合同、返回字段和人工迁移语义。

不把目标项目 ADR 或 Changelog 模板放入来源包升级路径。

## 7. 验收矩阵

| 场景 | 预期结果 |
| --- | --- |
| 旧版 `AGENTS.md` 受管入口 | preview 报告更新；apply 写入当前版本并保留区块外内容 |
| 已有 `docs/INDEX.md`，没有版本区块 | apply 只插入最小区块 |
| `docs/INDEX.md` 受管版本过期 | preview 和 check 报告；apply 更新 |
| 旧索引完全匹配登记模板 | 转换为受管区块并保留其他条目 |
| 旧索引版本描述归属不明 | 不覆盖，返回 `needs_manual_migration` |
| 项目正文包含产品自身版本号 | 不修改、不误报 |
| 控制脚本存在用户改动 | 继续拒绝覆盖 |
| 连续执行两次 upgrade apply | 第二次 `changed=[]` |
| Git 项目升级后未提交 | 返回 `needs_delivery`，不宣称跨机器完成 |
| fresh clone | 受管版本、配置、控制器和规则快照一致 |

## 8. 回滚与兼容

- 新版本区块是增量格式，不改变现有入口标记。
- 旧控制器会把新版本区块视为普通内容，不影响任务入口。
- 文件写入继续使用原子替换，不得留下半个标记区块。
- 卸载只删除 Docs Harness 明确拥有的区块，保留项目正文。
- 旧索引迁移保留原条目上下文；删除另立语义迁移需求。

## 9. 文档真源、索引与残留

- 本文档是版本标记同步改造的方案真源；实现版本待用户确认后补充。
- `docs/todo.md` 只保留任务入口与验收摘要，并链接本文档。
- 实现完成后更新 `README.md`、`SKILL.md` 和 `docs/contracts.md` 的当前合同。
- 项目 ADR、ADR 索引与 Changelog 不属于自动 upgrade 的完成证据。
- 验收扫描旧受管标记和登记模板残留，不对项目正文执行无边界替换。

## 10. 实现决策

1. `needs_manual_migration` 不覆盖归属不明的正文；允许安全的控制器和受管区块升级，但 apply 以退出码 `3` 和非完成状态返回。
2. `docs/INDEX.md` 版本区块固定插入在首个 H1 标题之后，其他项目内容顺序不变。
3. 首批白名单只包含 `docs/modules/INDEX.md` 中唯一、完全匹配的 `Docs Harness 当前版本：<semver>` 行；其他表达一律人工迁移。
