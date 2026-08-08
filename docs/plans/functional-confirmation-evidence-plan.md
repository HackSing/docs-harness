# 功能确认证据——Docs Harness 扩展方案

> 状态：待确认  
> 制定日期：2026-08-08  
> 适用范围：Docs Harness 控制器 `scripts/harness.py` + `docs/knowledge-map.json` + 功能测试卡  
> 上位真源：`docs/testing.md`（分层验收）、`docs/plans/agent-ui-simulation-test-plan.md`（UI 模拟测试）

## 1. 背景

当前智能体完成代码变更后，验证链路覆盖代码正确性（typecheck、vitest、go test）和 UI 呈现（`verify:electron-ui`），但不覆盖用户可感知的功能正确性。智能体可以在编译通过后报告"完成"，而从未启动应用验证功能是否跑通。

Docs Harness 的 `verify` 已有完整的证据类型检查机制：准入时累加 `required_evidence_types`，验收时逐项核对，缺失则返回退出码 3。但当前无 `functional_confirmation` 证据类型，因此功能确认不在验收回路中。

方案为通用治理能力：代码中不硬编码具体产品功能 ID 或仓库路径，所有功能门槛全部来自目标项目的 `docs/knowledge-map.json`（或等效知识源）配置。目标项目升级时，只需更新目标项目知识地图/测试卡，不需要改 `harness.py` 的核心判断路径。

## 2. 当前事实

### 2.1 已有机制

| 机制 | 位置 | 作用 | 局限 |
|------|------|------|------|
| Gate 证据 | `GATE_DEFS["frontend-design"]["evidence"] = ("ui_acceptance",)` | 前端任务要求 UI 验收证据 | 只验呈现，不验功能 |
| 规则叠加 | `rules/ui-complete-states.md` | 要求完整状态截图 | 只验状态，不验产物 |
| 条件证据 | `build_completion_manifest()` | 写入型 + 验证命令 → 要求 `test_result` | 只验测试，不验端到端 |
| 功能路由 | `resolve_feature_knowledge()` | 任务匹配功能 ID，加载知识文档 | 只用于知识加载，不影响证据要求 |

### 2.2 核心缺口

- `known_evidence_types()` 无 `functional_confirmation`。
- `package["feature_ids"]` 已在准入时解析，但不参与证据要求决策。
- `knowledge-map.json` 的功能记录无功能确认配置字段。
- 各项目目标的 `testing.md` 可能有"真实流程"小节，但多数为手工描述，未编码为可校验断言。

## 3. 设计决策

以下三项已与用户确认：

| 决策点 | 选择 | 理由 |
|--------|------|------|
| skip_conditions | 改动仅涉及文档或测试文件时自动跳过功能确认 | 文档/测试改动不影响用户可感知行为 |
| tier D 处理 | 外部账号/硬件依赖功能设 `required: false`，不强制 | 依赖真实账号/硬件，无法全链路自动化 |
| 实施节奏 | Phase 1 只做最小源码改动验证链路，不加规则 | 先验证机制可用，再逐步开启 |

## 4. 功能分档（按目标项目配置，不在方案中绑定固定功能）

`harness.py` 不维护任何项目专属功能清单；功能分档来源于目标项目 `docs/knowledge-map.json` 中的 `feature` 定义。以下为当前仓库示例，实际交付时请替换为目标项目现有功能。

| 档位 | 功能 ID（示例） | 功能名（示例） | `required` | `tier` | `mode` | 理由 |
|------|---------|--------|-----------|--------|--------|------|
| A | `feature-a` | 功能 A | `true` | A | desktop | 产物可程序校验 |
| B | `feature-b` | 功能 B | `true` | B | desktop | 流程可程序校验 |
| C | `feature-c` | 功能 C | `true` | C | desktop | 状态流转可程序校验 |
| D | `feature-d` | 功能 D | `false` | D | manual | 依赖外部账号/硬件 |

## 5. 实施方案

### Phase 1：Harness 源码最小改动

目标：让 `functional_confirmation` 作为证据类型可用，功能级开关通过 `knowledge-map.json` 控制。改完后不影响现有任务（没有功能声明该字段就不触发）。

#### 5.1 改动 1：注册证据类型

**文件**：`scripts/harness.py`  
**位置**：`known_evidence_types()` 函数（约 L5751）

```python
def known_evidence_types() -> set[str]:
    result = {
        "workspace_attribution",
        "source_trace",
        # ... 现有类型 ...
        "release_acceptance",
        "functional_confirmation",  # ← 新增
    }
    for spec in GATE_DEFS.values():
        result.update(str(item) for item in spec.get("evidence", ()))
    return result
```

#### 5.2 改动 2：功能感知的证据注入

**文件**：`scripts/harness.py`  
**位置**：准入流程中 gate 证据累加之后、manifest 构建之前（约 L3262-L3315）

在现有 gate → `semantic_evidence` 累加逻辑之后，插入功能级证据注入：

```python
# ---- 现有代码（不改）----
semantic_evidence = normalize_string_list(
    facts.get("semantic_evidence_requirements"), "semantic_evidence_requirements"
)
for gate in gates:
    auth_requirements.extend(GATE_DEFS[gate].get("authorization", ()))
    semantic_evidence.extend(GATE_DEFS[gate]["evidence"])
intent_evidence = { ... }
semantic_evidence.extend(intent_evidence[task_intent])

# ---- 新增：功能确认证据注入 ----
if mutation_profile in {"workspace_write", "external_write"}:
    fc_features = resolve_functional_confirmation(
        target, knowledge_context, write_scope,
    )
    if any(item.get("required", False) for item in fc_features):
        semantic_evidence.append("functional_confirmation")

# ---- 现有代码继续 ----
auth_requirements = list(dict.fromkeys(auth_requirements))
semantic_evidence = list(dict.fromkeys(semantic_evidence))
```

#### 5.3 改动 3：功能确认解析函数

**文件**：`scripts/harness.py`  
**位置**：新函数，放在 `resolve_feature_knowledge()` 附近

```python
def resolve_functional_confirmation(
    target: Path,
    knowledge_context: dict[str, Any],
    write_scope: Sequence[str],
) -> list[dict[str, Any]]:
    """检查匹配功能是否要求 functional_confirmation，返回要求确认的功能列表。"""
    selected = knowledge_context.get("selected_features", [])
    if not selected:
        return []

    # write_scope 全部为文档或测试文件时跳过
    skip_suffixes = (
        ".md", ".test.ts", ".test.tsx", ".spec.ts",
        ".spec.tsx", "_test.go", ".test.js", ".test.jsx",
    )
    skip_prefixes = ("docs/",)
    normalized_scope = [
        str(Path(path).as_posix()).strip().lower().removeprefix("./").removesuffix("/")
        for path in (write_scope or [])
    ]
    if write_scope and all(
        any(path.endswith(suffix) for suffix in skip_suffixes)
        or any(path.startswith(prefix) for prefix in skip_prefixes)
        for path in normalized_scope
    ):
        return []

    km_path = knowledge_map_path(target)
    if not km_path.is_file():
        return []
    try:
        km = json.loads(km_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    by_id = {f["feature_id"]: f for f in km.get("features", []) if isinstance(f, dict)}
    result: list[dict[str, Any]] = []
    for fid in selected:
        feature = by_id.get(fid)
        if not feature:
            continue
        fc = feature.get("functional_confirmation")
        if not isinstance(fc, dict):
            continue
        result.append({
            "feature_id": fid,
            "name": feature.get("name", fid),
            "tier": fc.get("tier", ""),
            "mode": fc.get("mode", ""),
            "assertions": fc.get("assertions", []),
            "testing_ref": feature.get("documents", {}).get("testing", ""),
            "required": fc.get("required", False),
            "skip_reason": fc.get("skip_reason", ""),
        })
    return result
```

**skip 判定逻辑说明**：

检查 `write_scope`（任务声明的写入范围）而非 `changed_paths`（实际改动路径）。原因：准入时实际改动尚未发生，只有 `write_scope` 可用。如果 `write_scope` 中所有路径都是文档或测试文件，则跳过功能确认。

边界情况：
- `write_scope` 含 `"<project_root>/src"` 等宽泛路径 → 不全命中 skip → 触发功能确认 ✓
- `write_scope` 含 `"docs/features/<feature_id>/testing.md"` → 全命中 skip → 不触发 ✓
- `write_scope` 为空（read_only 任务）→ `mutation_profile` 不是 `workspace_write`，外层已过滤 ✓

#### 5.4 改动 4：verify 响应附带功能确认契约

**文件**：`scripts/harness.py`  
**位置**：`verify_task()` 函数中构建 `missing_payload` 处（约 L7774）

在 `missing_evidence_types` 包含 `functional_confirmation` 时，附带功能确认的操作指引：

```python
# ---- 现有代码（不改）----
missing_payload: dict[str, Any] = {
    "task_id": package["task_id"],
    "result": "补充证据",
    "missing_evidence_types": missing_types,
    # ... 其他字段 ...
}

# ---- 新增：附带功能确认契约 ----
if "functional_confirmation" in missing_types:
    fc_contract: list[dict[str, Any]] = []
    fc_features = package.get("functional_confirmation_features") or []
    for item in fc_features:
        if not isinstance(item, dict) or not item.get("required", False):
            continue
        fc_contract.append({
            "feature_id": item.get("feature_id"),
            "name": item.get("name", item.get("feature_id")),
            "tier": item.get("tier", ""),
            "mode": item.get("mode", ""),
            "assertions": item.get("assertions", []),
            "testing_ref": item.get("testing_ref", ""),
        })
    missing_payload["functional_confirmation_contract"] = fc_contract
```

#### 5.5 改动 5：准入响应包含功能确认状态

**文件**：`scripts/harness.py`  
**位置**：准入 package 构建处（约 L3342-L3400）

在 package 中记录功能确认要求，供智能体和 verify 后续使用：

```python
# 在 package 字典中新增字段
"functional_confirmation_features": fc_features,  # 改动 2 中解析的结果
```

同时在准入响应的 `contract_snapshot` 中透出，让智能体在准入时就知道需要功能确认：

```python
# contract_snapshot 中
"functional_confirmation_required": bool(fc_features),
"functional_confirmation_features": [
    {
        "feature_id": f.get("feature_id"),
        "name": f.get("name"),
        "tier": f.get("tier"),
        "mode": f.get("mode"),
        "assertions": f.get("assertions", []),
        "testing_ref": f.get("testing_ref", ""),
        "required": f.get("required", False),
        "skip_reason": f.get("skip_reason", ""),
    }
    for f in fc_features
],
```

#### 5.6 改动 6：非强制功能的 verify 提示

**文件**：`scripts/harness.py`  
**位置**：`verify_task()` 中验收通过的分支（约 L7788-L7792）

验收通过时，检查是否有 `required: false` 的功能未执行功能确认，附带提示：

```python
    # ---- 在 compiled["verification_status"] = "passed" 之前 ----
    fc_skipped: list[dict[str, str]] = []
    for item in package.get("functional_confirmation_features") or []:
        if (
            isinstance(item, dict)
            and not item.get("required", False)
            and str(item.get("tier", "")).upper() == "D"
        ):
            fc_skipped.append({
                "feature_id": item.get("feature_id"),
                "reason": item.get("skip_reason", "tier D，需真实账号/硬件"),
            })

# ---- 在返回 payload 中 ----
if fc_skipped:
    payload["functional_confirmation_skipped"] = fc_skipped
```

### 5.7 阶段 1 关键遗漏修正（必修）

1. `functional_confirmation_features` 作为唯一真源

`resolve_functional_confirmation()` 的输出要在 `run` 阶段持久化到 `package`，`verify_task()` 只读 package，不再直接重读 knowledge-map。避免 admission 与 verify 因知识地图变化导致合同漂移和反复阻断。

```python
fc_features = resolve_functional_confirmation(...)
package["functional_confirmation_features"] = fc_features
if any(item.get("required", False) for item in fc_features):
    semantic_evidence.append("functional_confirmation")
```

2. 保留 Knowledge Map 扩展字段

`normalize_knowledge_map()` 与写回逻辑要保留扩展字段（至少 `functional_confirmation`），否则在 `update`/`audit` 时会被清空，配置看似存在但下次读取失效。

3. 契约快照与 verify 一致

`contract_snapshot` 已有 `functional_confirmation_features` 时，`verify` 拼 `functional_confirmation_contract` 只基于这份快照，避免混用 `read_knowledge_map()` 与 package 的分裂数据源。

### 5.8 性能与稳定性优化建议（防止效率下降）

1. 路径判定标准化复用

`write_scope` 在 5.3 中统一标准化后判定 `skip`，减少 Windows 路径、大小写和前后空格误判，降低 false positive 触发的二次验证循环。

2. 避免 verify 阶段二次读图谱

`functional_confirmation_contract` 从 package 读取，`verify` 不再执行额外的 `read_knowledge_map()`，减少 I/O 与并发抖动。

3. contract 字段最小化

`fc_contract` 只返回 `feature_id`、`name`、`tier`、`mode`、`assertions`、`testing_ref`、`required`、`skip_reason`，避免携带无关原始 feature 全量对象导致 payload 膨胀。

### Phase 2：Knowledge Map 与功能测试卡（本阶段不执行）

在 Phase 1 验证通过后，逐个功能开启：

1. 在 `docs/knowledge-map.json` 的 feature 记录中添加 `functional_confirmation` 字段。
2. 在 `docs/features/<id>/testing.md` 中新增"功能确认"小节，定义输入、动作、产物断言、排除项。
3. 可选：在 `.docs-harness/harness-home/rules/` 新增 `functional-confirmation.md` 规则，叠加 plan 字段要求。

Phase 2 的功能开启顺序建议：先从 tier A（产物可校验）开始，因为断言最明确、误报最少。

### Phase 3：功能测试卡扩充模板（本阶段不执行）

每个功能的 `testing.md` 新增小节格式：

```markdown
## 功能确认

### 输入
- 主题文本"项目管理"（思维导图）/ 脱敏样本文件（抠图、发票）/ ...

### 动作
- 形态 C 桌面态，侧栏进入 → 输入 → 生成/转换/抠图

### 产物断言
- [ ] 工作空间出现预期产物文件
- [ ] 文件格式合法（可打开 / 结构正确）
- [ ] 文件内容满足最小标准（尺寸 >0 / 含根元素 / 行数 >0）

### 不验什么
- 生成内容的质量、美观度、与主题的相关性（归人工）

### 跳过条件
- 改动仅涉及文档或测试文件
```

## 6. 场景验证

### 场景 1：改了目标项目核心功能代码

1. 智能体改了目标项目核心业务文件（例如 `app/src/feature_x/` 目录）。
2. `harness run` 准入：匹配目标功能 `feature-a`，`write_scope` 含非文档/测试路径。
3. `resolve_functional_confirmation()` 读取 knowledge-map，发现 `feature-a.functional_confirmation.required = true`。
4. `"functional_confirmation"` 加入 `required_evidence_types`。准入响应包含 `functional_confirmation_required: true`。
5. 智能体完成代码改动，提交 `code_diff` + `test_result` + `ui_acceptance`。
6. `harness verify` 返回退出码 3：`missing_evidence_types: ["functional_confirmation"]`，附带 `functional_confirmation_contract`（含断言列表和 testing.md 路径）。
7. 智能体读取测试卡功能确认小节，启动桌面态执行断言，采集证据。
8. 提交 `functional_confirmation` 证据，再次 `verify`，全绿，完成。

### 场景 2：改了目标项目测试文件

1. 智能体改了 `app/src/shared/foo.test.ts`。
2. `harness run` 准入：匹配目标功能 `feature-a`，`write_scope` 全部为 `.test.ts` 文件。
3. `resolve_functional_confirmation()` 检测到 write_scope 全部命中 skip patterns，返回空列表。
4. `"functional_confirmation"` 不进入 `required_evidence_types`。
5. 智能体正常提交 `code_diff` + `test_result`，`verify` 通过。

### 场景 3：改了目标项目非自动化依赖功能代码

1. 智能体改了目标项目某外部通道/硬件相关文件（例如 `app/src/integrations/manual_channel.rs`）。
2. `harness run` 准入：匹配 `feature-d`。
3. `resolve_functional_confirmation()` 读取 knowledge-map，发现 `feature-d.functional_confirmation.required = false`。返回空列表。
4. `"functional_confirmation"` 不进入 `required_evidence_types`。
5. 智能体提交 `code_diff` + `test_result`，`verify` 通过。
6. verify 通过时检测到 `feature-d` 是 tier D 功能，返回 `functional_confirmation_skipped: [{"feature_id": "feature-d", "reason": "tier D，需真实账号/硬件"}]`。
7. 智能体在完成汇报中标注："该功能确认未执行，需真实账号/硬件手工验证。"

### 场景 4：纯文档改动，未匹配到功能

1. 智能体改了 `docs/architecture.md`。
2. `harness run` 准入：未匹配到任何 feature（或 `mutation_profile` 为 `read_only`）。
3. 功能确认逻辑整体不触发。
4. 正常验收，无额外要求。

## 7. 影响分析

### 不影响什么

- 现有任务流程：Phase 1 完成后，只要 knowledge-map 中没有功能声明 `functional_confirmation`，所有现有任务行为不变。
- `verify_task()` 核心逻辑：不修改证据收集、归因、过期检查等流程，新类型通过已有 `missing_types` 路径自然工作。
- `build_completion_manifest()` 结构：不修改函数签名或条件证据机制，新类型通过上游 `semantic_evidence` 注入。
- 证据骨架机制：`ensure_evidence_skeletons()` 自动为新类型生成声明骨架模板。
- fast_track 路径：fast_track 只保留 `code_diff` + `test_run`，功能确认不会进入 fast_track 的最小证据集。

### 需要注意

- `knowledge-map.json` 的 `functional_confirmation` 字段为可选。`normalize_knowledge_map()` 无需强制校验该字段；但可以加入格式校验（tier 枚举、required 布尔等），防止拼写错误静默失效。
- skip 判定基于 `write_scope` 而非 `changed_paths`，因此宽泛的 `write_scope`（如 `"<project_root>/src"`）即使实际只改了测试文件，仍会触发功能确认。这是有意为之：准入时保守触发，verify 时如果实际无功能变更，智能体可以在功能确认证据中说明跳过原因。
- 多功能命中时（如同时匹配多个 feature），只要任一功能声明 `required: true`，就触发功能确认。`functional_confirmation_contract` 会列出所有要求确认的功能，智能体逐个执行。

### 核心遗漏（必须修完再扩量）

- `normalize_knowledge_map` 若不保留 `functional_confirmation`，Phase 2 写入的字段会被清空，效果“明面配置有，运行时无效”。
- `verify()` 若不依赖 `package` 快照构建合同，会与 admission 口径产生漂移，导致同一任务在不同时间反复阻塞。
- `resolve_functional_confirmation` 的 skip 判定必须标准化路径后再判断，避免路径风格差异导致误触发。

## 8. 执行计划

| 阶段 | 内容 | 前置 | 验收 |
|------|------|------|------|
| Phase 1 | harness.py 改动 1-6（含 5.7/5.8） | 无 | 对 Phase 1 完成后的 harness.py 执行 `python3 -m py_compile`；用一个 mock 任务验证：`functional_confirmation_required`、`functional_confirmation_features` 在准入和 verify contract 中一致 |
| Phase 2 | knowledge-map.json 添加字段 + 功能测试卡扩充 | Phase 1 | 选一个目标项目实际功能（例如 `feature-a`），跑完整准入→执行→verify 链路，验证场景 1 和场景 2 |
| Phase 3 | 可选规则 `functional-confirmation.md` | Phase 2 | 验证规则触发时 plan 字段要求生效 |

Phase 1 与 Phase 2 之间可以间隔任意时间。Phase 1 落地后，功能确认能力在框架层就绪但不激活，按需通过 knowledge-map 逐个功能开启。
