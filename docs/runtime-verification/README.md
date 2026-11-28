# 运行态验证证据

复杂或 UI 运行态任务的证据包放在 `docs/runtime-verification/<task>/packet.json`，证据文件放在同目录 `evidence/`，随仓库提交。普通小改动的证据包放在 `.docs-harness/runtime/<task>/`，不入库。

验证默认在后台或隐藏窗口执行，不弹窗、不抢焦点，不自动打开资源管理器、图片查看器或文件夹；截图与日志直接写入 `evidence/`。只有真实硬件、系统权限、原生弹窗等无法后台的层才上前台，并按 [docs/contracts.md](../contracts.md) 第 4c 节的前台例外协议提前说明、收尾记录。

证据包字段、状态/数据覆盖矩阵、UI 视口与文案/可访问性要求，以及 `runtime check` 的拒绝规则见 [docs/contracts.md](../contracts.md) 第 4b 节。运行：

```bash
python3 scripts/harness.py runtime check --target . \
  --packet docs/runtime-verification/<task>/packet.json --json
```

大任务全量实机闭环（`live_e2e`）：先用 `acceptance create` 冻结 `live_e2e` 契约与逐条 `pass_criteria`/`fail_criteria`（默认停下等用户确认再跑实机），再在证据包填写 `acceptance_ref`、`flows[].criterion_id`、`iterations[].deploy_ref` 与终轮 `rechecked_criteria`；`runtime check` 硬拒 `mock=true`、漏测实机标准与未重部署复测，`acceptance record` 与 `assets-check` 同步联动校验提交态 `packet.json`。

前端交互原型与产品视觉总监审查：新增页面、核心弹窗或布局/交互大改先输出 `.docs-harness/views/<task>-prototype.html` 供用户确认；UI 视觉审查由只读子智能体以「产品视觉总监」实读双视口截图分级裁决并记入 `ui.visual_review`（关联 `acceptance_ref` 的 UI 包必填且终态须 `approved`）。

证据包只证明结构和观察覆盖成立，不证明截图与实际页面一致，也不替代真实用户验收。
