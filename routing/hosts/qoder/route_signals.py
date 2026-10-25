"""Qoder hook 的确定性任务切换信号。

2026-10-24 的 shadow 数据里有两类缓存误用：plan 缓存被重启/配置问题复用，
code 缓存被报错消息复用但缺 bugfix。这里只在缓存命中前做保守检查；命中
风险时让出缓存、重新路由，由路由模型决定，不在消费者层直接改画像。

2026-10-25 回放显示，单独的“报错了”重路由会退化为 answer_only：路由器
看不到截图内容，绕开 code 缓存反而更差。因此 bug 信号只用于让 plan 缓存
让路，不让 code 缓存让路；07:10 的 bugfix 缺口保留为上下文限制。
"""

from __future__ import annotations

from typing import Any, Mapping

EXECUTION_SIGNALS = (
    "重启",
    "启动",
    "运行",
    "执行",
    "打包",
    "构建",
    "编译",
    "安装",
    "检测",
    "验证",
    "修复",
    "优化",
    "改成",
    "改为",
    "删掉",
    "删除",
    "补上",
    "做了",
    "做一下",
    "弄一下",
    "跑一下",
    "拉取",
    "拉起",
    "部署",
    "提交",
)
BUG_SIGNALS = ("报错", "错误", "失败", "异常", "崩溃", "闪退", "bug", "error", "fail", "crash")
QUESTION_SIGNALS = (
    "吗",
    "呢",
    "？",
    "?",
    "是什么",
    "是开是关",
    "还是",
    "在哪",
    "怎么",
    "为什么",
    "是否",
    "多少",
    "哪些",
    "哪个",
)


def cache_bypass_reason(
    prompt: str, cached_profile: Mapping[str, Any]
) -> str | None:
    intents = cached_profile.get("intents")
    intent_set = set(intents) if isinstance(intents, (list, tuple)) else set()
    if "plan_decision" in intent_set and (
        _has_execution_signal(prompt)
        or _has_question_signal(prompt)
        or _has_bug_signal(prompt)
    ):
        return "plan_task_switch"
    return None


def _has_execution_signal(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(signal in lowered for signal in EXECUTION_SIGNALS)


def _has_bug_signal(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(signal in lowered for signal in BUG_SIGNALS)


def _has_question_signal(prompt: str) -> bool:
    return any(signal in prompt for signal in QUESTION_SIGNALS)
