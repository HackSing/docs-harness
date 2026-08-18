# dsh-docs-harness

Docs Harness 是一套「方案 → 验收 → 知识」的项目治理纪律,由一份 Python 引擎
(`harness.py`)实现,装在**用户自己的仓库里**。这个插件把它接进 dsh 图形界面:

- 把项目自己的治理规则注入 agent 的系统提示词;
- 把方案(plan)生命周期做成 agent 能调用的工具族;
- 把当前方案的进度做成输入框上方的一枚气泡;
- 把引擎在项目里的**安装 / 升级 / 移除**做成只有用户能点的入口。

它不是一个「AI 自动帮你建流程」的插件。恰恰相反,它的大部分设计成本花在**限制**上:
写盘由谁发起、规则谁说了算、关掉之后还剩什么。

## 三条边界

**1. 写盘只由用户发起。**
`project init` / `upgrade` / `uninstall` 会往用户仓库里写文件,因此它们**不是工具**——
agent 的工具表里根本没有这三个动作,只有 HTTP 路由,而路由只由输入框上方的提示条和
「设置 → 插件 → Docs Harness」触发。agent 在未启用的项目里调用方案工具,拿到的是一句
明确的说明:*不要自己启用,告诉用户去那两个入口*。

**2. 总开关默认开,关掉即等于没装。**
关掉后整个子 fiber 被 dispose:不注册工具、不注入提示词、不建投影、不挂项目路由。
会话行为与没安装这个包完全一致,而不是「装着但沉默」。唯一留下的是设置读写这一条
控制面路由——它是把开关拨回来的通道,拆了它关闭就成了单行道。

**3. 注入的规则是项目自己的规则,一字不改。**
文本取自项目 `AGENTS.md` 的受管块原文(按 mtime 缓存),整段注入;插件只在后面追加
一小段说明,把「怎么调用」从命令行改写为工具名。项目文件损坏时回落到同版本的内置
种子文本——已经被标记为「装了 Docs Harness」的项目,不该因为一个文件坏掉就静默失去
治理。

## 安装

插件随 [DSH Buddy](https://github.com/HackSing/dsh-buddy) 的 web profile 预装。手工装入
某个 profile:

```bash
dsh plugin --profile web add dsh-docs-harness
```

运行需要用户机器上有 Python 3(`python3` 或 `python` 在 PATH 上)。没有时,启用动作会
报出一条带下载地址的说明,而不是静默失败。

## 界面

| 位置 | 内容 |
|---|---|
| 输入框上方(dock) | 方案进度气泡:`进度 3/7` + 本方案累计改动行数;悬停或聚焦展开条目清单 |
| 输入框上方(dock) | 启用 / 升级提示条:说明将写入什么,按钮触发,可「不再提示」(按项目记住) |
| 工具卡片 | `plan_progress` 等四个工具的专用卡片,渲染清单而不是原始 JSON |
| 设置 → 插件 | 总开关、自动启用、自动升级、从当前项目移除 |

## 工具族

| 工具 | 作用 |
|---|---|
| `harness_plan_select` | 取方案模板的字段契约 |
| `harness_plan_create` | 冻结方案;先经用户确认卡片批准,退回则方案不成立 |
| `harness_plan_settle` | 结算方案(implemented / deprecated) |
| `plan_progress` | 发布整张清单(整表替换语义),驱动气泡与卡片 |

`plan_progress` 与内置 `todo_write` 的关键区别:**它是常驻状态**。内置待办每轮清空,而
冻结的方案要跨轮次活着——它描述的是这次任务的合同,不是这一轮的便签。

## 开发

```bash
npm test          # node --test:host + client 全量单测
npm run build     # esbuild 产出 lib/client.js(__ModuleLoader__ 工厂包装)
npm run verify    # 发布自检:产物、种子完整性、manifest 字段
npm run extract-block   # 从内置引擎重新生成 vendor/harness/managed-entry.md
```

目录:

- `src/host/` —— host 半边:工具族、投影、规则注入、项目状态检测、HTTP 路由
- `src/client/` —— 浏览器半边:气泡、提示条、工具卡片、设置卡片
- `src/shared/` —— 两边都要的纯常量与纯窄化函数(不含任何 `node:` 导入)
- `vendor/harness/` —— 引擎种子:`scripts/harness.py` 及其模块、`plan-templates/`、
  以及与引擎写出的受管块逐字节一致的 `managed-entry.md`

## 已知边界与 roadmap

- **自定义会话事件不可用**。`KNOWN_SESSION_EVENT_TYPES` 是封闭集合,写入表外类型会让
  会话日志在重启后加载失败(用户的对话直接丢)。所以方案投影折叠的是本插件自己的
  `tool/call` / `tool/result`,项目安装状态则走 HTTP 而不是投影。
- **自定义确认卡片意图不可用**。确认卡片的意图是封闭联合类型,因此方案批准复用了
  内置的 `plan-review` 意图——渲染效果正是要的那张卡,且零客户端代码。
- **第三方设置命名空间不过网关**。`settings.describe` / `settings.update` 只服务网关
  编译进去的命名空间白名单,插件自己注册的命名空间会被读时过滤、写时拒绝(上游注释
  称「插件自暴露」是 deferred work)。所以本插件的开关走自己的
  `/docs-harness-settings` loopback 路由,host 侧仍经 `settings` 服务读写,settings.yaml
  仍是唯一真源。
- [ ] knowledge / acceptance 资产的前端可视化(目前只有方案一条线上了界面)
- [ ] 引擎种子升级的应用层增量语义:版本戳分流,未改动整体替换、有自定义则只加不改
- [ ] 发布到 npm 后,宿主清单条目从本地 tarball 转为钉死版本

## License

MIT
