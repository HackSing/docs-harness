# 2026-10-22 下游数据核对与检查器降噪

## 背景

用户要求把下游日常使用数据作为判断依据，重点核对 zbuddy-mobile。数据来自 8 个下游的 `.docs-harness/usage/*.jsonl`、收尾报告、方案/验收资产与提交记录。

## 发现

- 8 个下游共 1,669 次调用（2026-09-14 至 10-22）；命令集中在 assets-check（718）、acceptance record（166）、plan create（108）、structure check（81）。
- assets-check 493/718 次有 WARN（69%）；zbuddy-desktop 355/373（95%），历史单次最多 829 条。
- 收尾报告（10-14 后 96 份）五项字段齐全仅 8 份（8%）；「验收层」33 份（34%）；退出码证据 31 份（32%）。
- 代码提交（10-01 后 134 个）同时含「验证：/未覆盖：」107 个（80%），项目间 0–91%。
- zbuddy-mobile：475 次调用；assets-check 279 次，112 次有 WARN（40%）；10-14 后 70 次调用中 25 次 exit 1/2（36%），集中在 acceptance settle/record。
- zbuddy-mobile：66 份活方案、49 份已实施、17 份有效；47 份验收中 37 passed、10 pending；12 份任务清单中 8 份引用 Plan；10-14 后 23 份报告中五项齐全 1 份。
- 用 2.31 源码对 zbuddy-mobile 跑 assets-check 产生 88 条 WARN，其中 79 条 CODEMAP、7 条 ADR、2 条 Plan；经核对，Dart 字段、枚举成员、带类型标注赋值、shell 环境变量、带点引用被误判为失活。

## 改动

- `scripts/structure_check.py`：符号存活改为去注释后的词边界匹配；支持 Dart/Kotlin 字段、枚举成员、类型标注赋值、shell 环境变量、带点引用；注释中的符号不再算存活。
- `scripts/managed_assets.py`：ADR/Knowledge 状态比较忽略括号内核对备注与 INDEX 截断的右括号，避免把人工核对备注当成投影漂移。
- `tests/test_structure.py`：新增 11 组 `symbol_hit` 正反例。
- `tests/test_knowledge.py`：新增状态备注不触发投影漂移的回归测试。
- `CHANGELOG.md`：2.31.0 增加检查器降噪条目。

## 验证

- 聚焦测试：`tests.test_structure tests.test_knowledge tests.test_adr tests.test_acceptance tests.test_assets_check`，74 tests OK（skipped=3），退出 0。
- 全量测试：`python -m unittest discover -s tests -p "test_*.py"`，277 tests OK（skipped=9），退出 0。
- 源包严格检查：`assets-check --target . --strict`，0 失败 0 警告，退出 0。
- zbuddy-mobile 实测：修复前 88 条 WARN；修复后 4 条（2 条 Plan INDEX 与冻结方案不一致，2 条 CODEMAP 符号仅存在于注释）。
- zbuddy-desktop 实测：修复后 33 条 WARN（29 条 CODEMAP、4 条 Plan）；历史单次最多 829 条来自旧检查器，不能直接对比为全部误报。

## 验收层

- 单元测试层：检查器正反例与投影状态回归。
- 本地运行层：对 zbuddy-mobile、zbuddy-desktop 的真实仓库执行只读检查。
- 未做完整 package/install 层验证。

## 未覆盖

- 未升级任何下游到 2.31.0，2.31 的实际调用失败率与 WARN 率尚未复测。
- zbuddy-desktop 的 `plan check` 仍超过 180 秒；性能未在本次修复。
- zbuddy-desktop 剩余 29 条 CODEMAP 警告未逐条裁决，可能包含真实失效条目。
- behavior evals 仍未运行，无法给出规则遵循率的前后对比。
