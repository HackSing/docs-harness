# Docs Harness 测试事实

## 自动化入口

- 完整回归：`npm test`
- 控制器自检：`npm run self-test`
- 发布包清单：`npm run pack:check`

## 验收分层

- 源码层要求完整回归、自检与打包检查通过。
- 临时项目层要求覆盖 init/upgrade、任务准入、知识生命周期、后台 Job、兼容迁移和幂等路径；复杂路线必须覆盖 prepare → dispatched → running → progress → verify。
- 后台控制面专项覆盖 Git/非 Git Runtime、部分工件、显式 repair、指纹篡改、进度非法倒退、兼容别名、retry attempt 隔离、脱敏事件去重和摘要 prune。
- 工作量专项分别验证大仓单文件增量使用 `change_scoped`，bootstrap 保持 `project_wide`，且 `source_fingerprint` 与后台幂等键不因路由口径修正而漂移。
- 文档路由专项覆盖五类真源、显式优先、唯一候选、多候选、缺失、非法路径、符号链接、零写阻塞 Job、稳定去重、retry 重建、旧 Job 取消迁移、类别锁与运行前漂移。
- 安装升级专项验证合法 `document_routes` preserve-and-merge、非法配置 preview/apply 失败关闭，以及旧在途治理 Job 的人工迁移清单。
- 下游层分别核对安装控制器、项目知识状态与宿主派发；Git 交付和 fresh clone 需要独立证据。
- 测试通过不等于已提交、已推送、已安装或真实宿主已完成派发。

## 事实来源

- `package.json`
- `tests/test_harness.py`
- `scripts/harness.py self-test`
