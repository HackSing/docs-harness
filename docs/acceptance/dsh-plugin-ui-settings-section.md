> 状态：已验收-仅追溯
<!-- docs-harness:acceptance-document/v1 -->

# dsh 插件 UI 优化验收：settings.section 设置页、覆盖重置、通知条重试与气泡 pin

- 修订：7
- 关键符号：`HarnessSettingsCard`、`settings.section`、`HarnessSettingsStore`、`NoticeBarView`
- 资产指纹：`sha256:95839a21f1e850e5ab64901e295c7b3d72f72a0c647565811508ad001b0015d3`
- 关联方案：`docs/plans/dsh-plugin-ui-settings-section-plan.json`

## 验收目标

设置面迁移为一级 settings.section 设置页，开关支持已覆盖/恢复默认，通知条错误可重试，气泡 popover 可点击钉住；聚焦测试、构建与包校验通过，真实运行态由用户确认。

## 验收标准

### `c1` 注册面迁移：settings.plugin.item 不再出现于 src/，settings.section 注册带 id/order/label/locale

- 状态：passed
- 类型：contract_check
- 层级：L1
- 证据：`dsh-plugin/src/client/index.jsx`、`dsh-plugin/src/shared/constants.js`

### `c2` dsh-plugin 聚焦测试全绿（client-registration/client-render/settings-store/notice-state 及新增断言）

- 状态：passed
- 类型：behavior_acceptance
- 层级：L2
- 证据：`dsh-plugin/tests/client-registration.test.js`、`dsh-plugin/tests/client-render.test.js`、`dsh-plugin/tests/settings-store.test.js`、`dsh-plugin/tests/settings-routes.test.js`

### `c3` npm run build 与 npm run verify 通过

- 状态：passed
- 类型：behavior_acceptance
- 层级：L4
- 证据：`dsh-plugin/lib/client.js`、`dsh-plugin/scripts/verify-package.mjs`

### `c4` 真实 dsh 运行态：设置导航出现 Docs Harness 页、开关可写、通知条可重试、气泡可 pin

- 状态：passed
- 类型：user_acceptance
- 层级：L5
- 证据：
