> 状态：有效（现行决策）
<!-- docs-harness:adr-document/v1 -->

# Structure 增量检查作为 assets-check 第六 checker，CODEMAP 采用纯 Markdown 文档形态

- 关键符号：`check_structure`、`structure_report`、`CODEMAP_SCAFFOLD`
- 资产指纹：`sha256:8bd34d428e9f01c609a3fd6ed632a0197bb4f6ada524ecb1b82d920f9796cdd4`

## 背景

大模型写代码局部贪心：不抽公共模块、单文件持续膨胀、重复实现导致维护困难。行为规范（编码质量规范）纯靠模型自律无机械暴露渠道；存量阈值检查对遗留大文件恒报会造成 WARN 疲劳；复用失败的根因是检索失败（模型不知道已有什么可复用）。既有 ADR 已确立『机械检查以 checker 形式挂入 assets-check，不轻易扩资产类型』的方向。

## 决策

体量检查采用增量归责（工作区+暂存+未跟踪 vs HEAD），只对本次改动出 WARN，不做 FAIL——处方权留给人；实现为 scripts/structure_check.py 单模块，作为 assets-check 第六 checker 接入，阈值常量（FILE_RED_LINE=500、FUNC_RED_LINE=60、OVERSIZE_FILE_GROWTH_ALERT=50、FUNC_GROWTH_ALERT=10）单一来源于该模块。CODEMAP 能力索引采用纯 Markdown 文档（docs/CODEMAP.md，条目=模块路径—职责—公开接口），不建受管 JSON 资产：索引是高频轻量编辑场景，指纹密封会造成编辑摩擦；一致性由 Structure checker 校验（路径存在、符号存活、新增文件登记提醒）。存量结构债由 structure report 按需报告，供定期整理任务消费，不进常驻检查。

## 影响

收益：每条 WARN 都可归责到当次任务，无历史包袱噪音；CI --strict 下增量天然为空，仅 CODEMAP 存量一致性生效，不阻塞既有项目；无 CODEMAP 的项目整体跳过相关检查实现渐进采纳。代价：已提交的结构债对常驻检查不可见（由 structure report 补偿）；函数级检查仅覆盖 Python（ast，零依赖），其他语言只有文件级保护；CODEMAP 无指纹防篡改，失活靠符号存活检查兜底。约束：新增 checker 需修改 run_assets_check 显式签名与全部调用点；阈值调整只改 structure_check.py 一处。
