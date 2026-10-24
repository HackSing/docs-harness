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

Qoder hook 在调用核心校验前做一层宿主归一化：`must_clarify=true` 时把额外触发项收敛为 `clarify_required`，避免模型同时给出“澄清”和“动作”信号时整份画像被拒。核心校验器对直接调用者仍保持严格。

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
| 独立、低上下文的强模型调用 | Qoder hooks 支持 `UserPromptSubmit` + `additionalContext`；国内版 `qodercn` 已登录并完成真实路由调用，默认使用 CLI 当前配置模型 `dfmodel` | 已确认 |
| 结构化 JSON 输出 | 四份强模型预测文件均可被 `score.py` 解析和评分，两组 held-out 各两次 50/50；真实 CLI 返回合法 routing profile | 已确认 |
| model/version 记录 | hook 从 CLI `modelUsage` 取模型名，从 `--version` 取 CLI 版本；真实值 `dfmodel` / `1.1.78` | 已确认 |
| token、latency 记录 | CLI JSON 含 `usage`、`duration_ms`、`total_cost_usd`、`total_credits`；真实路由延迟约 4.7–5.5s，`dfmodel` 报告 0 tokens / 0 Credits | 字段与延迟已确认；`dfmodel` 用量为 0 |
| feature flag 与回滚开关 | `DOCS_HARNESS_ROUTER_ENABLED` + `DOCS_HARNESS_ROUTER_BACKEND`；回滚等价于移除 hook 条目 | 原型已确认；宿主级 flag 未确认 |
| shadow sink | 真实 hook 已写本地 JSONL 与缓存；同一 session 后续消息命中缓存、不启动 CLI | 已接通；Desktop 端到端未确认 |
| 20–50 条真实任务基线 | 目前只有手工真实 prompt；尚无 1–2 周真实任务统计 | 未开始 |

结论：A 在 Qoder 上已从“可行”变成“真实可调用”：国内账号已登录，`dfmodel` 完成真实路由，同会话缓存避免了每条消息启动 CLI。下一步是在新 Qoder 会话安装 `UserPromptSubmit` hook，跑 1–2 周真实任务 shadow，采集关键漏配、返工、延迟与用量。Hook 只能追加 context，不能移除已加载的 AGENTS.md；要拿到 token 收益仍需拆分内核与模块契约。

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

- `routing/hosts/qoder/route_hook.py`：命令 hook。读取 stdin，加载注册表，调用 `_route_task`，校验画像，写 Shadow 事件，输出选中的模块契约。
- `routing/hosts/qoder/fake_profile.json`：fake backend 的静态 code_task 画像。
- `routing/hosts/qoder/settings.example.json`：fake backend 的 Qoder hooks 配置示例。
- `routing/hosts/qoder/settings.cli.example.json`：Qoder CLI backend 的配置示例。

行为：

- `DOCS_HARNESS_ROUTER_ENABLED=1` 时启用；默认关闭。
- `DOCS_HARNESS_ROUTER_BACKEND=fake|cli`；默认 `fake`，`cli` 调用 Qoder CLI 无头模式。
- 没有 `routing/registry.json`、画像非法、phase 非法或后端不可用时，hook 不注入、退出 0，把错误写入 stderr 和 `.docs-harness/routing/hook-errors.jsonl`。
- `direct_override` 直接跳过；`must_clarify` 只记 Shadow，不注入；无模块时不注入。
- Shadow 事件不写 prompt 原文，只写 `task_hash`、字符数和结构化画像。
- 注入内容只来自注册表契约；内核规则仍由 AGENTS.md 提供。

### CLI backend

CLI backend 用 **Qoder 国内版 CLI（`qodercn`）** 的无头模式调用 Qoder 模型服务，消耗国内账号 Credits：

```bash
qodercn -p "<task>" \
  --output-format json \
  --max-turns 1 \
  --tools "" \
  --permission-mode default \
  --no-session-persistence \
  --cwd <empty-dir> \
  --config-dir <host-config-dir> \
  --system-prompt "<router prompt>"
```

国际版 `@qoder-ai/qodercli` 不使用；默认路径已指向国内版 `qodercn`。默认**不传 `--model`**，使用你在 CLI `/model` 里选中的模型；只有设置 `DOCS_HARNESS_ROUTER_MODEL` 时才覆盖。之前显式传 `auto` 会覆盖你的选择并触发回退，已移除。

hook 会额外传入 `--settings '{"general":{"enableAutoUpdate":false}}'`，并在子进程环境里移除 Qoder Desktop 注入的 `QODER_AGENT_SDK_*`、`QODER_SDK_AUTH_PAYLOAD_FILE`、`QODER_CONFIG_DIR`、`QODERCN_CONFIG_DIR` 和国际版 `QODER_PERSONAL_ACCESS_TOKEN`，再设置隔离的 `QODERCN_CONFIG_DIR`，避免 CLI 被误判为 SDK 入口或误用国际账号。

CLI 的 JSON 结果包含 `result`、`usage.input_tokens`、`usage.output_tokens`、`duration_ms`、`total_cost_usd`、`total_credits` 和 `modelUsage`；hook 把这些写入 Shadow 事件的 `model` 元数据（Credits 字段为 `credits`）。

本机安装与认证（宿主侧，不进仓库）：

```bash
npm install --prefix ~/.qoder-cn/docs-harness-router/cn @qodercn-ai/qoderclicn
~/.qoder-cn/docs-harness-router/qoder-cn-cli
# 在 CLI 里执行 /login，完成后 /status 查看国内账号与额度，再 /quit
```

如果交互登录不可用，改用 `QODERCN_PERSONAL_ACCESS_TOKEN`（在 `https://qoder.cn/account/integrations` 生成），不要写进仓库或对话。国内 CLI 文档：`https://docs.qoder.cn/cli/installation`。

后端环境：

- `DOCS_HARNESS_ROUTER_BACKEND=cli`
- `DOCS_HARNESS_QODER_CLI`：CLI 可执行文件路径；默认 `~/.qoder-cn/docs-harness-router/cn/node_modules/.bin/qodercn`
- `DOCS_HARNESS_QODER_CONFIG_DIR`：国内 CLI 认证配置目录；默认 `~/.qoder-cn/docs-harness-router/cn-config`
- `DOCS_HARNESS_QODER_EMPTY_DIR`：无 AGENTS.md 的空工作目录；默认 `~/.qoder-cn/docs-harness-router/empty`
- `DOCS_HARNESS_ROUTER_MODEL`：可选；不设置时使用 CLI 当前 `/model` 配置，设置时作为 `--model` 覆盖
- `DOCS_HARNESS_QODER_CLI_VERSION`：可选，覆盖记录的 CLI 版本
- `DOCS_HARNESS_ROUTER_CACHE_TTL_SECONDS`：会话路由缓存 TTL，默认 7200；设为 0 禁用

### 同会话路由缓存

`UserPromptSubmit` 在每条用户消息提交时都会触发。如果每条都启动 CLI，同一会话的后续消息会重复付费。hook 现在按 `session_id` 缓存上一次成功路由：

- 首条任务：正常路由，写 `.docs-harness/routing/sessions/<hash>.json`，注入完整契约。
- 后续消息：命中缓存，不启动 CLI；注入一段短提醒“沿用上次路由”。
- 新任务标记（“新任务/换个任务/new task”等）或 `/route-reset`：强制重路由或清缓存。
- 缓存 TTL 默认 2 小时；注册表指纹变化自动失效。
- 澄清、低置信或空模块不写缓存，下一条消息重新路由。

代价：如果后续消息没有新任务标记但实际换了任务，缓存会沿用旧路由。主 agent 收到短提醒后，如发现交付物变化，应从 `routing/registry.json` 读取对应模块契约；用户也可以发 `/route-reset`。这是用少量注入换取每条消息不启动 CLI。

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

1. 在项目 `.qoder/settings.local.json` 合并 `settings.example.json`（fake）或 `settings.cli.example.json`（真实 CLI）的 `hooks` 块；该文件不入库。
2. 确认项目有 `routing/registry.json`，或设置 `DOCS_HARNESS_REGISTRY`。
3. 新建一个 Qoder 会话，提交一个与 fake profile 匹配的 code_task 提示；检查 `additionalContext` 是否出现、Shadow 日志是否新增。
4. 回滚：删除该 hook 条目或 settings 文件。

用户级安装时，把 `route_hook.py` 复制到 `~/.qoder-cn/hooks/`，在 hook 的 `env` 里设置 `DOCS_HARNESS_ROOT` 指向本仓，并把 `command` 指向复制后的脚本。不要在没有 `DOCS_HARNESS_ROOT` 的情况下复制脚本。

限制：

- fake profile 是静态 code_task；启用 fake backend 会把所有提示都按 code_task 注入。只用于带匹配提示的链路测试。
- 国内 CLI 已登录，`dfmodel` 完成真实路由；CLI 对该模型报告 0 tokens / 0 Credits，暂时无法用它校准 token/成本预算。
- CLI 是完整 Agent Runtime：首条任务和重路由会多一次启动开销；同会话后续消息走缓存，不再每条启动。真实路由延迟约 4.7–5.5s。
- 缓存可能沿用旧路由：后续消息换了任务但没有“新任务/换个任务”等标记时，主 agent 需要从 registry 读取新契约，或用户发 `/route-reset`。真实同会话缓存已验证“CLI 路径不存在仍复用”。
- Hook 只能追加 context，不能移除已加载的 AGENTS.md；token 收益仍要等内核/模块契约拆分。
- Qoder Desktop 的真实 `UserPromptSubmit` 触发尚未验证；当前真实调用是脚本级 hook。
- 国内账号已能在 CLI 登录；是否与 Desktop 套餐共享额度，以 CLI `/status` 和实际 Credits 为准。
- 每次宿主重启或配置变化后要重新确认 hook 是否加载。

## 11. 未覆盖与待定

- B2–B5 的真实 shadow、canary、强制放量尚未开始。
- 国内版 `qodercn` 已登录并能真实调用；`dfmodel` 的 token/credit 计量为 0，Desktop 端到端触发、1–2 周 shadow 和回滚演练未完成。
- 会话缓存已用真实同会话两条消息验证一次，但尚未在多任务、长会话、上下文压缩和 `/route-reset` 场景统计命中率与误复用。
- 20–50 条真实任务基线尚未建立。
- 延迟、token、成本、Credits、澄清和返工阈值尚未校准。
- 内核/模块契约尚未拆分，当前 hook 只追加契约，不减少 AGENTS.md token。
- 路由器尚未安装到任何下游项目；下游仍使用 2.33.0 的提示词规则。
- 离线强模型证据是引导式、同模型家族的 curated 集，不能当作生产准确率。
