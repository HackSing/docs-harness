# Docs Harness 架构事实

## 当前结构

- `scripts/harness.py` 是控制器源码真源，负责项目安装与升级、任务准入、上下文、验收、知识生命周期和后台 Job 状态机。
- `harness-home/rules/` 是发布包内的受管规则真源；`project init` 与 `project upgrade --apply` 把固定快照同步到目标项目的 `.docs-harness/harness-home/rules/`。
- `SKILL.md`、`README.md` 与 `docs/contracts.md` 描述对外行为；`VERSION`、`package.json`、`SKILL.md` frontmatter 和控制器版本常量必须一致。
- 复杂后台 Job 的 `job.json`、`plan.json`、`progress.json`、`events.jsonl`、锁与索引属于 Harness 控制面，只能由 CLI 在受管 Runtime 内维护；业务 Job 只写 `allowed_write_scope` 内的数据面。
- 文档治理的数据面由 `docs-harness/document-routes/v1` 统一解析；配置、自动候选、Job scope、指纹与锁都从同一合同派生，控制器不创建 canonical 文档或 canonical 根目录。

## 状态与交付边界

- Git 项目的运行状态写入实际 Git 元数据目录；非 Git 项目写入项目内 `.docs-harness/`。
- Job 控制锁先于知识/业务锁获取；prepare、progress、dispatch、retry 和 verify 在同一 Job 控制锁下重读并更新状态。
- 治理 Job 同时持有路径锁与稳定文档类别锁；prepare、dispatch、verify 前复验路由指纹，防止配置切换或符号链接替换绕过创建时检查。
- 缺失、多候选、非法配置与旧合同迁移都保留父任务完成事实，但治理 Job 以零写权限或执行门禁独立失败关闭。
- 源码通过、本地安装副本、Git HEAD/远端与 fresh clone 是独立验收层，不互相替代。
- 项目升级采用 preserve-and-merge，只同步 Docs Harness 明确拥有的文件或受管区块；归属不明内容失败关闭。

## 事实来源

- `scripts/harness.py`
- `docs/contracts.md`
- `SKILL.md`
- `package.json`
