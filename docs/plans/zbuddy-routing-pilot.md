> 状态：已实施-仅追溯（代码已是真源，2026-10-23 核对）
<!-- docs-harness:plan-document/v1 -->

# zbuddy 下游路由试点接入（mobile + desktop）

- 冻结合同：`sha256:289521e078492e3a5a7fbdf07203962f8995f0699096525900e430ccf4a682e1`
- 关键符号：`load_registry`、`_uses_docs_harness`、`shadow_log_path`

## 目标

在 zbuddy-mobile 和 zbuddy-desktop 中以最小侵入方式 opt-in Docs Harness 路由注册表，让用户级 Qoder hook 在 shadow 阶段只记录路由决策、不改变执行，并保留一键回滚。

## 范围

只向下游复制 routing/registry.json 快照与一页 README；不安装路由脚本、不改变下游 docs-harness 受管文件、不注入契约、不提交下游仓库。依赖本机用户级 Qoder hook 与本仓 route_hook.py。

## 关键步骤

1. 校验源注册表版本/指纹；2. 在两个下游项目创建 routing/registry.json 与 README；3. 用 load_registry 校验两份快照；4. 在各自项目用 fake backend 跑一次 user-hook.sh，确认项目门禁命中且写出 shadow 事件，随后删除合成日志；5. 记录回滚方式：删除 routing/registry.json 后 hook 静默跳过。

## 验收方案

两个项目均有 routing/registry.json 且 load_registry 通过；user-hook.sh 在各自项目命中门禁并写出 shadow 事件；shadow 阶段无 additionalContext；删除 registry 后 hook 静默跳过；下游 docs-harness 受管文件无改动，工作区只新增 routing/ 目录。

<!-- docs-harness:plan-governance:start -->
## 资产治理

- 关联验收：无
<!-- docs-harness:plan-governance:end -->
