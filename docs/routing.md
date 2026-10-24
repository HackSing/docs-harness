# 意图路由：注册表、校验、Shadow 与放量

状态：B1 已实现，默认关闭。B2–B5 尚未开始。本文件描述仓库侧能力与宿主接入边界。

## 1. 职责边界

意图路由是执行前的独立路由层，不替代常驻内核。

```text
用户任务
→ 常驻内核（安全、授权、权限、不可逆确认、输出契约）
→ 独立路由调用（强力模型，只接收 taxonomy、一页契约和任务文本）
→ 宿主校验（标签、依赖闭包、冲突、澄清、低置信）
→ 执行前覆盖率核对（必需模块必须已加载）
→ 主模型执行
→ 收尾记录路由、模块与结果
```

- 模型只输出意图画像和候选模块，不直接决定执行。
- 宿主只信任通过 `validate_profile` 的画像。
- `resolve_modules` 按注册表映射和依赖闭包解析模块。
- `coverage_check` 在执行前核对必需模块是否加载；缺失时阻断或修复。
- 内核的安全、授权、权限和不可逆确认始终高于路由结果。
- B1 不新增 CLI 命令，不改变执行行为，也不把路由器安装到下游项目。

## 2. 注册表

单点真源：`routing/registry.json`。

注册表包含：

- 7 个意图、6 个模块、10 个触发项；
- 意图到模块的映射；
- 模块依赖（`bugfix` 依赖 `code`）与渲染顺序；
- 每个模块的一页契约（范围、规则、验证）；
- 常驻内核契约；
- 模块共存规则（如 `plan` + `code`）；
- 风险级别（`code`/`docs` 低、`bugfix` 中、`plan`/`assets`/`release` 高）；
- 澄清规则与直接执行短语；
- 预算与阈值；
- 版本与内容指纹。

`load_registry` 会验证 schema、标签、映射、契约、风险级别、预算和指纹。指纹按除 `fingerprint` 外的 JSON 规范化内容计算。手工修改内容但不重算指纹会被拒绝，错误码为 `registry_fingerprint_mismatch`。受控修改后必须重算指纹，再跑合同测试。

预算和阈值当前标为 `pending_shadow`。`critical_miss_rate_max` 固定为 `0.0`；其他阈值保持 `null`，等 B2 真实数据校准。不得在已消费的诊断集或 held-out 上继续调阈值。

## 3. 校验与解析

```python
from routing_contract import load_registry, validate_profile, resolve_modules

registry = load_registry("routing/registry.json")
profile = {
    "intents": ["code_task"],
    "triggers": ["code_edit"],
    "must_clarify": False,
    "confidence": 0.93,
    "evidence": ["用户要求修改具体文件并跑测试"],
}
result = validate_profile(profile, registry)
if not result.ok:
    raise SystemExit([issue.to_dict() for issue in result.errors])
modules = resolve_modules(result.profile, registry)
```

`validate_profile` 的硬性规则：

- 标签必须属于注册表 taxonomy；列表不得重复；顶层字段必须在 schema 内。
- `answer_only` 不能与任何动作意图共存。
- 候选模块必须是意图闭包的子集；宿主会补齐缺失模块。
- `must_clarify=true` 时模块必须为空，触发项只能是 `clarify_required`。
- 非澄清画像必须有至少一个意图。
- 置信度低于注册表阈值时，画像降级为澄清，不进入执行。
- 触发项与意图必须兼容。答案、缺陷、方案、资产、发布、文档的定义型触发项由代码补齐；`code_task` 缺少 `code_edit`/`code_verify` 时只告警，由宿主决定补问还是按安全超集执行。

`profile_schema(registry)` 输出 JSON Schema，供宿主的模型输出约束使用。schema 关闭未知字段，避免模型把任务原文或路径塞进画像。

`direct_override_requested(task_text, registry)` 提供确定性的直接执行短语识别，作为模型 `direct_override` 触发的兜底。模型信号仍是主路径。

## 4. Shadow 事件

事件模块：`scripts/routing_shadow.py`。默认日志路径：`.docs-harness/routing/shadow-YYYY-MM.jsonl`。

```python
from routing_shadow import (
    append_shadow_event,
    build_shadow_event,
    read_shadow_events,
    shadow_log_path,
)

event = build_shadow_event(
    "task-7f3a",
    profile,
    ["code"],
    {"clarify_asked": False, "rework": [], "completed": True},
    registry=registry,
    model={
        "name": "strong-router",
        "version": "2026-10",
        "tokens_in": 1200,
        "tokens_out": 180,
        "latency_ms": 2300,
        "cost_usd": 0.004,
    },
    needed_modules=["code"],
    task_text=task_text,
)
append_shadow_event(event, shadow_log_path("."))
events = read_shadow_events(shadow_log_path(".").parent)
```

事件只保留结构化字段：

- 路由画像：意图、候选模块、触发项、是否澄清、置信度、证据条数；
- 解析模块、实际加载模块、可选的观测所需模块；
- 阶段（`shadow`/`canary`/`enforced`）、风险级别、注册表版本和指纹；
- 返工枚举、完成状态、模型名/版本、token、延迟、成本、缓存命中；
- 可选的 `task_hash` 与字符数。

事件不写任务原文、证据文本、文件路径或资产名。`validate_shadow_event` 用字段白名单拒绝未知字段。`task_id` 必须是不含空白的短标识；宿主自行保存任务 ID 到原始任务的私有映射。`task_text` 只用于计算哈希和字符数，不落盘。

日志写入失败、日志缺失、日志损坏都抛出 `RoutingShadowError`，不静默放行。写入时在日志目录创建内容为 `*` 的嵌套 `.gitignore`。日志只保存在本地或受管理的观察面，保留期和访问控制由宿主负责。

## 5. 指标与覆盖率

```python
from routing_metrics import coverage_check, summarize_shadow

coverage = coverage_check(
    {"modules": modules, "must_clarify": result.effective_clarify},
    loaded_modules,
)
if not coverage.ok:
    raise SystemExit(coverage.to_dict())

summary = summarize_shadow(
    events,
    thresholds={**registry.budgets, **registry.thresholds},
)
```

`coverage_check` 返回必需模块、已加载模块、缺失模块、额外模块和覆盖率。缺失模块时 `ok=false`；高风险任务必须阻断并记录。

`summarize_shadow` 输出：

- 覆盖率失败、关键漏配、过度路由、澄清、返工、完成率；
- p50/p95 路由延迟；
- 输入/输出 token 总量与单任务 token；
- 总成本和单任务成本；
- 按阶段、风险级别和意图分组的同一组指标；
- 阈值告警。

关键漏配的定义是“观测所需模块未被路由选中”。过度路由的定义是“路由选中了观测不需要的模块”。观测所需模块来自任务后的 `needed_modules`。没有 `needed_modules` 的事件计入 `quality_unverified_count`，不参与关键漏配率和过度路由率的分母，避免用未标注数据伪造准确率。

覆盖率失败始终产生 `critical` 告警。阈值未校准时只对覆盖率失败和关键漏配告警；延迟、token、成本和澄清/返工阈值在 B2 数据上校准。

## 6. B0 宿主能力审计

| 能力 | 证据 | 状态 |
|---|---|---|
| 独立、低上下文的强模型调用 | Qoder hooks 支持 `UserPromptSubmit`，在主 Agent 处理前触发；`command` handler 可执行独立模型调用。2.33.0 评测另用两个独立会话确认过模型层能力 | Qoder hook 路径已确认；真实模型 endpoint 未接 |
| 结构化 JSON 输出 | 四份强模型预测文件均可被 `score.py` 解析和评分，两组 held-out 各两次 50/50 | 已确认 |
| model/version 记录 | 原型记录 `fake-router/prototype`；真实路由模型名称与版本待接 | 原型已记录；生产未确认 |
| token、latency 记录 | 原型记录 hook 内路由调用 latency；token/cost 待真实模型返回 | latency 部分确认；token/cost 未确认 |
| feature flag 与回滚开关 | 原型用 `DOCS_HARNESS_ROUTER_ENABLED` 开关；回滚等价于移除 hook 条目 | 原型已确认；宿主级 flag 未确认 |
| shadow sink | 仓库侧 `routing_shadow` + Qoder hook 原型写本地 JSONL；Desktop 真实会话未触发 | 原型已接通；端到端未确认 |
| 20–50 条真实任务基线 | 现有 usage 只记录 harness 命令面，不含任务级路由结果 | 未开始 |

结论：A 在 Qoder 上可行，入口是 `UserPromptSubmit` + `additionalContext`；原型已通过独立 stdin 测试，下一步接真实模型并在新 Qoder 会话做端到端触发。Hook 只能追加 context，不能移除已加载的 AGENTS.md；要拿到 token 收益仍需拆分内核与模块契约。

## 7. B2 运行手册

宿主侧接口（本仓外）：

```text
route_task(request, metadata) -> RoutingProfile
render_contracts(profile) -> list[Message]
feature_flag(name) -> bool
shadow_sink(event)
rollback()
```

每次任务：

1. 加载注册表，记录 `version` 与 `fingerprint`。
2. 只把 taxonomy、一页契约和任务文本发给强力模型；不发送完整 AGENTS.md 或目录。
3. 解析结构化画像，调用 `validate_profile`。
4. 校验失败、低置信或显式澄清时，问一个澄清问题；不问第二个。
5. Shadow 阶段不改变实际加载模块；记录 `actual_modules` 和任务后的 `needed_modules`。
6. 用 `build_shadow_event` 和 `append_shadow_event` 落日志；日志缺失按失败处理。
7. 每日或每周运行 `summarize_shadow`，按风险级别和意图查看关键漏配、过度路由、澄清、返工、p95 延迟和 token 成本。

停止条件：

- 任何覆盖率失败；
- 关键漏配率高于当前基线；
- 返工率高于当前基线；
- p95 延迟或单任务 token 成本超出校准后的预算；
- 日志缺失或损坏；
- 宿主模型版本变化且未重新校准。

出现任一条件时，先修契约或阈值；无法定位时关闭 feature flag。

## 8. 回滚

- 一级：关闭宿主 feature flag，恢复当前内核/规则行为。shadow 日志保留。
- 二级：停止对应任务类型的 canary，人工复核受影响任务。
- 三级：回退注册表版本并重放离线评分；不删除日志，不做数据迁移。
- 高风险动作始终走原生授权或人工确认；路由回滚不涉及权限系统。

注册表内容修改后必须重算指纹并重跑合同测试。不要手工复制一份平行注册表。

## 9. 验证命令

```bash
python3 -m unittest tests.test_routing_contract tests.test_routing_shadow tests.test_routing_metrics tests.test_routing_offline -v
python3 scripts/harness.py assets-check --strict --json
python3 scripts/harness.py release sync --strict --json
npm run pack:check
```

## 10. Qoder hook 原型（A 路径）

状态：原型，默认关闭，未安装到任何项目。它验证 A 的宿主注入链路，不改变下游安装面。

Qoder 官方 hooks 文档确认：`UserPromptSubmit` 在用户提交 prompt 后、主 Agent 处理前触发；`command` handler 可从 stdin 读取事件 JSON，并向 stdout 输出 `hookSpecificOutput.additionalContext`。原型使用这个入口。

文件：

- `routing/hosts/qoder/route_hook.py`：命令 hook。读取 stdin，加载注册表，调用 `_route_task`（当前读 fake profile），校验画像，写 Shadow 事件，输出选中的模块契约。
- `routing/hosts/qoder/fake_profile.json`：原型用的静态 code_task 画像。
- `routing/hosts/qoder/settings.example.json`：Qoder hooks 配置示例。

行为：

- `DOCS_HARNESS_ROUTER_ENABLED=1` 时启用；默认关闭。
- 没有 `routing/registry.json`、画像非法、phase 非法或 fake profile 不可读时，hook 不注入、退出 0，把错误写入 stderr 和 `.docs-harness/routing/hook-errors.jsonl`。
- `direct_override` 直接跳过；`must_clarify` 只记 Shadow，不注入；无模块时不注入。
- Shadow 事件不写 prompt 原文，只写 `task_hash`、字符数和结构化画像。
- 注入内容只来自注册表契约；内核规则仍由 AGENTS.md 提供。

独立测试：

```bash
python3 -m unittest tests.test_qoder_hook -v
```

手工冒烟：

```bash
echo '{"hook_event_name":"UserPromptSubmit","session_id":"demo","cwd":"'"$PWD"'","prompt":"修改 routing/registry.json 并跑测试"}' | \
  QODER_PROJECT_DIR="$PWD" DOCS_HARNESS_ROUTER_ENABLED=1 \
  python3 routing/hosts/qoder/route_hook.py
```

安装测试（项目级，推荐先用临时项目）：

1. 在项目 `.qoder/settings.local.json` 合并 `settings.example.json` 的 `hooks` 块；该文件不入库。
2. 确认项目有 `routing/registry.json`，或设置 `DOCS_HARNESS_REGISTRY`。
3. 新建一个 Qoder 会话，提交一个与 fake profile 匹配的 code_task 提示；检查 `additionalContext` 是否出现、Shadow 日志是否新增。
4. 回滚：删除该 hook 条目或 settings 文件。

用户级安装时，把 `route_hook.py` 复制到 `~/.qoder-cn/hooks/`，在 hook 的 `env` 里设置 `DOCS_HARNESS_ROOT` 指向本仓，并把 `command` 指向复制后的脚本。不要在没有 `DOCS_HARNESS_ROOT` 的情况下复制脚本。

限制：

- fake profile 是静态 code_task；在真实模型接入前，启用它会把所有提示都按 code_task 注入。只用于带匹配提示的链路测试。
- 没有真实模型调用、token/cost 记录和真实路由质量数据。
- Hook 只能追加 context，不能移除已加载的 AGENTS.md；token 收益仍要等内核/模块契约拆分。
- Qoder Desktop 的真实会话触发尚未验证；先用独立 stdin 和临时项目确认。
- 每次宿主重启或配置变化后要重新确认 hook 是否加载。

## 11. 未覆盖与待定

- B2–B5 的真实 shadow、canary、强制放量尚未开始。
- 宿主独立调用、model/version、token/latency、feature flag、shadow sink 和回滚开关尚未在宿主侧确认。
- 20–50 条真实任务基线尚未建立。
- 延迟、token、成本、澄清和返工阈值尚未校准。
- 路由器尚未安装到任何下游项目；下游仍使用 2.33.0 的提示词规则。
- 离线强模型证据是引导式、同模型家族的 curated 集，不能当作生产准确率。
