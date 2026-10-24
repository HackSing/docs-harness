# 2026-10-23 Windows 原生 CLI 与 Qoder hook 跨平台接入

## 改动路径

- `routing/hosts/qoder/user-hook.sh`：去掉 `/usr/bin/python3` 硬编码，按 `python3` → `python` 顺序探测并用 `-c "import sys"` 验证可用性；项目门禁改由 `route_hook.py` 读取 hook 输入里的 `cwd` 完成。
- `routing/hosts/qoder/user-hook.cmd`：新增 Windows 批处理入口，按 `python` → `python3` → `py -3` 顺序探测解释器，失败时写 stderr 并退出 0。
- `routing/hosts/qoder/route_hook.py`：stdin 改从 `sys.stdin.buffer` 按 UTF-8 解码；stdout/stderr 统一重配为 UTF-8；CLI 子进程输出按 UTF-8 解码；新增 `_default_cli()` 从 PATH 解析 `qoderclicn`/`qodercn`。
- `tests/test_qoder_hook.py`：fake CLI 在 Windows 用 `.cmd` shim、POSIX 用 shell 包装器；测试 stdin/stdout 显式 UTF-8；用户级入口测试在 Windows 执行 `user-hook.cmd`；两条 CLI 参数转发测试在 Windows 跳过（cmd 无法转发多行路由提示）。
- `routing/hosts/qoder/README.md`、`docs/routing.md`：补 Windows PowerShell 安装、原生 CLI 必需、`py.exe -3` 入口、UTF-8 与嵌套 `cmd /c` 限制；用户级门禁描述改为由 `route_hook.py` 用 cwd 完成。
- `docs/CODEMAP.md`：登记 `user-hook.cmd`，更新两个入口职责。
- 宿主侧（不入库）：`~/.qoder-cn/settings.json` 写入用户级 `UserPromptSubmit` hook，命令为 `C:/Windows/py.exe -3 D:/AIWareTop/Agent/docs-harness/routing/hosts/qoder/route_hook.py`，模型 `dfmodel`、原生 CLI 与隔离 config 均为绝对路径；备份为 `settings.json.bak-20261023234402`、`settings.json.bak-20261023234759`。
- 宿主侧（不入库）：原生 CLI `C:\Users\freed\.qoder-cn\bin\qoderclicn\qoderclicn.exe` 1.1.78；`cn-config` 从 `~/.qoder-cn` 复制 `.auth`/`.models` 继承登录；npm 全局包 `@qodercn-ai/qoderclicn` 已卸载。
- 本地 ignore（不入库）：docs-harness、zbuddy-mobile、zbuddy-desktop 的 `.git/info/exclude` 增加 `.docs-harness/routing/`。

## 验证

- `python -m unittest tests.test_qoder_hook -v`：22 项，OK（skipped=2），退出码 0；验证层级：focused_test。跳过项为 Windows 下 cmd fake CLI 无法转发多行路由提示，原生 CLI 后端改由真实 Desktop 会话验证。
- `python -m unittest tests.test_routing_shadow tests.test_routing_contract tests.test_routing_metrics tests.test_routing_offline`：59 项，OK（skipped=1），退出码 0；验证层级：focused_test。
- `python scripts/harness.py assets-check`：status=passed，failures=[]，warnings=[]，退出码 0；验证层级：contract_check。
- 原生 CLI：`qoderclicn.exe --version` 返回 1.1.78；`--config-dir cn-config --list-models` 返回模型列表、退出码 0；`--model dfmodel` 单轮调用返回 `OK`，1.08s，0 Credits；验证层级：local_runtime。
- npm 卸载：`npm uninstall -g @qodercn-ai/qoderclicn` 移除 10 个包、退出码 0；`npm ls -g --depth=0` 不再列出该包；npm shim 已删除；原生 CLI 仍返回 1.1.78；验证层级：package_or_install。
- 按最终 `settings.json` 的 `py.exe` 命令在临时项目执行代码任务：退出码 0，`phase=shadow`，模型返回澄清画像（`modules` 为空），`dfmodel` 6644.7ms、0 Credits，stderr 为空；验证层级：local_runtime。
- 同一 CLI 后端另一次代码提示通过 `.cmd` 包装器执行：`phase=shadow`、`modules=["code"]`、risk low、`dfmodel` 4551.5ms、0 Credits；说明路由画像存在模型波动，shadow 事件本身均正常落盘；验证层级：local_runtime。
- Qoder Desktop 真实会话 `4c3ebf62-7502-5ad8-a859-43429d79b13c`（docs-harness）：`shadow-2026-10.jsonl` 新增 `phase=shadow`，profile `answer_only/read_only`，`actual_modules` 6 个，`dfmodel` 3603.0ms、0 Credits；Qoder 日志 `source="user" success=true exit_code=0`；验证层级：local_runtime。
- Qoder Desktop 真实会话 `57c897a4-86e5-58dd-a5eb-a999c47b04f3`（zbuddy-mobile）：新增 `phase=shadow`，`dfmodel` 4117.8ms、0 Credits；hook 日志成功；验证层级：local_runtime。
- Qoder Desktop 真实会话 `4c8f131e-e0bb-51a2-a663-44fdea64e967`（zbuddy-desktop）：新增 `phase=shadow`，`dfmodel` 3847.5ms、0 Credits；hook 日志成功；验证层级：local_runtime。
- 独立 fake 后端冒烟：`user-hook.sh` 与 `user-hook.cmd` 均写出 `phase=shadow`、`modules=["code"]`；验证层级：local_runtime。

## 自查

- 复用：路由、缓存、Shadow 写入继续使用现有 `route_hook.py`、`route_cache.py`、`scripts/routing_shadow.py`，没有复制路由逻辑；`.sh`/`.cmd` 只是平台入口适配器，业务门禁唯一留在 `route_hook.py`。
- 新增抽象：`_configure_stdio` 只负责 UTF-8 标准输入输出；`_default_cli` 只负责 PATH 解析 CLI；两个入口只负责解释器探测与委托。职责单一，没有为未出现的平台预留抽象。
- 无新增第三方依赖；模型 `dfmodel`、原生 CLI 路径和隔离 config 都放在宿主设置，不写进仓库代码。
- 根因与影响面：`/usr/bin/python3` 硬编码导致 Windows 无解释器；locale 解码导致中文 stdin 崩溃；Qoder 不设置 `QODER_PROJECT_DIR` 导致包装器门禁误跳过；Qoder 0.4.11 不执行嵌套 `cmd /c`。四处均按状态所有者修复，未在消费者层加兜底。

## 未覆盖

- 未在本机复跑 macOS；`user-hook.sh` 仍优先 `python3`，Mac 侧路径未删除，但没有 macOS 运行证据。
- Qoder 0.4.11 下 `cmd /c user-hook.cmd` 会报告成功但不执行批处理；`user-hook.cmd` 只在普通 shell 中验证，Qoder 用户级入口改用 `py.exe -3`。
- 两条 Windows CLI 参数转发测试跳过；原生 CLI 后端由真实 Desktop 会话覆盖，但 fake CLI 的多行参数路径没有 Windows 单测。
- 三个 Desktop 会话都是只读任务，事件模块为空；代码路由只在临时项目出现一次 `modules=["code"]`，同一提示另一次返回澄清画像，尚未在 Desktop UI 会话复验代码路由。
- `dfmodel` 报告 0 tokens / 0 Credits，token/成本阈值仍无法校准；1–2 周真实 shadow、回滚演练和 Mac 复验未完成。
- 原生安装器更新了用户 PATH；已运行的终端/Qoder 进程需重启才能在 PATH 中看到 `qoderclicn`；hook 使用绝对路径，不受影响。
