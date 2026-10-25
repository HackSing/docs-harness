# 运行态验证证据

复杂或 UI 运行态任务的证据包放在 `docs/runtime-verification/<task>/packet.json`，证据文件放在同目录 `evidence/`，随仓库提交。普通小改动的证据包放在 `.docs-harness/runtime/<task>/`，不入库。

证据包字段、状态/数据覆盖矩阵、UI 视口与文案/可访问性要求，以及 `runtime check` 的拒绝规则见 [docs/contracts.md](../contracts.md) 第 4b 节。运行：

```bash
python3 scripts/harness.py runtime check --target . \
  --packet docs/runtime-verification/<task>/packet.json --json
```

证据包只证明结构和观察覆盖成立，不证明截图与实际页面一致，也不替代真实用户验收。
