> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# Structure 函数级检查扩展到 Go 与 TS/JS 验收

- 修订：2
- 关键符号：`_ts_function_spans`、`_go_functions`、`function_language`、`TS_MODULE_DIR_ENV`
- 资产指纹：`sha256:ed24404d85925cab896c2b4a19cfcebe102d6ea3963ed8a8f32bd301979f2248`
- 关联方案：`docs/plans/structure-function-check-multilanguage.json`
- 关联知识：`docs/knowledge/docs-harness-assets-governance.json`

## 验收目标

structure check 与 structure report 的函数级检查覆盖 Python、Go、TS/JS（.ts/.tsx/.js/.jsx/.cjs/.mjs）；harness 自身保持零第三方依赖，TS 解析借用目标项目 node_modules 里的 typescript，缺失时降级为文件级并输出 WARN；测试文件不做函数级判定；随 2.15.0 发布并可平滑升级到下游。

## 验收标准

### `c1` 版本一致、自检、打包清单与严格资产检查

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`docs/acceptance/evidence/structure-function-check-multilanguage/report.md`

### `c2` 结构检查新增用例与仓库全量回归

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/structure-function-check-multilanguage/report.md`

### `c3` 下游 zbuddy-desktop 升级到 2.15.0 后护栏生效

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`docs/acceptance/evidence/structure-function-check-multilanguage/report.md`
