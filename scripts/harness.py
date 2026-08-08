#!/usr/bin/env python3
"""Docs Harness v1.7.4 独立任务控制器。"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Iterator, Sequence


VERSION = "1.7.4"
TASK_SCHEMA = "docs-harness/task-package/v2"
LEGACY_TASK_SCHEMA = "docs-harness/task-package/v1"
COMPILED_SCHEMA = "docs-harness/compiled-task/v2"
EVENT_SCHEMA = "docs-harness/event/v2"
EVIDENCE_SCHEMA = "docs-harness/evidence-index/v2"
FREEZE_SCHEMA = "docs-harness/freeze/v2"
EVIDENCE_RECEIPT_SCHEMA = "docs-harness/evidence-receipt/v2"
EVIDENCE_DECLARATION_SCHEMA = "docs-harness/evidence-declaration/v1"
EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
RECEIPT_SCHEMA = "docs-harness/context-receipt/v2"
COMPLETION_MANIFEST_SCHEMA = "docs-harness/completion-manifest/v1"
COMPILER_CONTRACT = "docs-harness/compiler/v2"
AUTH_SCHEMA = "docs-harness/authorization-receipt/v2"
AUTH_ADOPTION_SCHEMA = "docs-harness/authorization-adoption/v1"
EVIDENCE_ADOPTION_SCHEMA = "docs-harness/evidence-adoption/v1"
CONTRACT_DELTA_SCHEMA = "docs-harness/contract-delta/v1"
PLAN_DELTA_SCHEMA = "docs-harness/plan-delta-contract/v1"
MANAGED_PLAN_SCHEMA = "docs-harness/managed-plan/v1"
VERIFICATION_RECEIPT_SCHEMA = "docs-harness/verification-command-receipt/v1"
CONFIG_SCHEMA = "docs-harness/project-config/v4"
QUALITY_REVIEW_SCHEMA = "docs-harness/quality-review/v1"
QUALITY_RECORD_SCHEMA = "docs-harness/quality-record/v1"
KNOWLEDGE_MAP_SCHEMA = "docs-harness/knowledge-map/v1"
KNOWLEDGE_ASSESSMENT_SCHEMA = "docs-harness/knowledge-assessment/v1"
KNOWLEDGE_CONSENT_SCHEMA = "docs-harness/knowledge-consent/v1"
WORKLOAD_ESTIMATE_SCHEMA = "docs-harness/workload-estimate/v1"
BACKGROUND_JOB_SCHEMA = "docs-harness/background-job/v2"
LEGACY_BACKGROUND_JOB_SCHEMA = "docs-harness/background-job/v1"
KNOWLEDGE_JOB_SCHEMA = BACKGROUND_JOB_SCHEMA
BACKGROUND_CANDIDATE_SCHEMA = "docs-harness/background-candidate/v1"
BACKGROUND_ASSESSMENT_SCHEMA = "docs-harness/background-assessment/v1"
BACKGROUND_PLAN_SCHEMA = "docs-harness/background-plan/v1"
BACKGROUND_PROGRESS_SCHEMA = "docs-harness/background-progress/v1"
BACKGROUND_ARTIFACT_REVISION = 2
DOCUMENT_ROUTE_SCHEMA = "docs-harness/document-routes/v1"
DOCUMENT_ROUTE_KINDS = ("architecture", "changelog", "todo", "adr_root", "reviews_root")
DOCUMENT_ROUTE_FILE_KINDS = {"architecture", "changelog", "todo"}
DOCUMENT_ROUTE_DIRECTORY_KINDS = {"adr_root", "reviews_root"}
GOVERNANCE_DELIVERABLE_ROUTES = {
    "adr_changelog_todo_review": ("adr_root", "changelog", "reviews_root", "todo"),
}
BACKGROUND_JOB_ID_RE = re.compile(r"^bg-[0-9]{8}T[0-9]{6}-[0-9a-f]{10}$")
LEGACY_KNOWLEDGE_JOB_ID_RE = re.compile(r"^kh-[0-9]{8}T[0-9]{6}-[0-9a-f]{10}$")
KNOWLEDGE_JOB_ID_RE = re.compile(r"^(?:bg|kh)-[0-9]{8}T[0-9]{6}-[0-9a-f]{10}$")
SCRIPT_ROOT = Path(__file__).resolve().parents[1]
TASK_ID_RE = re.compile(r"^dh-[0-9]{8}T[0-9]{6}-[0-9a-f]{10}$")
MANAGED_BEGIN = "<!-- docs-harness:managed-entry:start -->"
MANAGED_END = "<!-- docs-harness:managed-entry:end -->"
MANAGED_VERSION_BEGIN = "<!-- docs-harness:managed-version:start -->"
MANAGED_VERSION_END = "<!-- docs-harness:managed-version:end -->"
CLAUDE_BEGIN = "<!-- docs-harness:claude-bridge:start -->"
CLAUDE_END = "<!-- docs-harness:claude-bridge:end -->"
SEMVER_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+"
LEGACY_VERSION_INDEX_PATHS = ("docs/modules/INDEX.md",)
RUNTIME_FILES = (
    "task-package.json",
    "compiled-task.json",
    "events.jsonl",
    "evidence-index.json",
    "freeze.json",
    "context-receipts.jsonl",
    "authorization-receipts.jsonl",
)
PROJECT_RULES_RELATIVE = ".docs-harness/harness-home/rules"
KNOWLEDGE_ROOT_RELATIVE = "docs"
KNOWLEDGE_MAP_RELATIVE = "docs/knowledge-map.json"
# 外部只消费知识源：项目存在该目录时，harness 不初始化/更新知识库，仅消费其文档。
REPOWIKI_RELATIVE = ".qoder/repowiki"
REPOWIKI_CARD_LIMIT = 1000
KNOWLEDGE_CATEGORIES = ("product", "development", "testing", "design")
FALLBACK_SNAPSHOT_FILE_LIMIT = 4096
BACKGROUND_MAX_ATTEMPTS = 3
GIT_DELETION_THRESHOLD = 100
BACKGROUND_TERMINAL_STATES = {
    "updated",
    "no_change",
    "completed_with_finding",
    "failed",
    "cancelled",
}
BACKGROUND_KNOWN_STATES = BACKGROUND_TERMINAL_STATES | {
    "contract_ready",
    "dispatched",
    "running",
    "waiting_for_dependency",
    "waiting_for_bootstrap_merge",
    "needs_user_input",
    "needs_rebase",
    "queued_manual",
}
BACKGROUND_RETRYABLE_STATES = {"needs_user_input", "needs_rebase", "queued_manual"}
BACKGROUND_TASK_KINDS = {
    "knowledge_bootstrap",
    "knowledge_incremental_sync",
    "delivery_governance",
    "critical_followup",
}
BACKGROUND_ROUTES = {"background_direct", "background_goal", "background_goal_phased"}
BACKGROUND_COMPLEX_ROUTES = {"background_goal", "background_goal_phased"}
BACKGROUND_PROGRESS_STATUSES = {"pending", "in_progress", "completed", "blocked"}
BACKGROUND_REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
VERIFICATION_REASON_CODE_LIMIT = 8
KNOWN_LIMIT_CODES = {
    "source_not_verified",
    "local_runtime_not_verified",
    "ui_not_verified",
    "release_artifact_not_verified",
    "remote_delivery_not_verified",
    "fresh_clone_not_verified",
    "external_state_not_verified",
}
TASK_DISPOSITION_REASON_CODES = {
    "host_task_closed",
    "superseded",
    "duplicate",
    "invalid_admission",
    "operator_abandoned",
}
TASK_DISPOSITION_INDEX_SCHEMA = "docs-harness/task-disposition-index/v1"
DELIVERY_LAYER_ORDER = (
    "source",
    "local_verification",
    "git_head",
    "remote_delivery",
    "fresh_clone",
    "release_artifact",
    "ui",
    "external_state",
)
DELIVERY_READ_ONLY_INTENTS = {"query", "audit", "git_inspect"}
DELIVERY_REMOTE_REQUIRE_RE = re.compile(r"远端|远程|推送|部署|\bpush\b|\bdeploy\b", re.IGNORECASE)
DELIVERY_FRESH_CLONE_RE = re.compile(r"fresh\s*clone|全新克隆|干净克隆", re.IGNORECASE)
DELIVERY_RELEASE_RE = re.compile(r"发布|\brelease\b", re.IGNORECASE)
DELIVERY_INSTALL_RE = re.compile(r"安装到|\binstall\b", re.IGNORECASE)
DELIVERY_LAYER_LIMIT_CODES = {
    "source": "source_not_verified",
    "local_verification": "local_runtime_not_verified",
    "remote_delivery": "remote_delivery_not_verified",
    "fresh_clone": "fresh_clone_not_verified",
    "release_artifact": "release_artifact_not_verified",
    "ui": "ui_not_verified",
    "external_state": "external_state_not_verified",
}
DELIVERY_LIMIT_DETAILS = {
    "source_not_verified": "源码层证据未通过或已失效",
    "local_runtime_not_verified": "本地验证被要求但尚未通过",
    "ui_not_verified": "未取得真实界面验收证据",
    "release_artifact_not_verified": "发布产物被要求但尚未验证",
    "remote_delivery_not_verified": "远端交付被要求但尚未验证",
    "fresh_clone_not_verified": "fresh clone 验收被要求但尚未验证",
    "external_state_not_verified": "外部状态变更被要求但尚未验证",
}
QUALITY_REVIEW_MAX_BYTES = 64 * 1024
QUALITY_TEXT_MAX_CHARS = 500
QUALITY_LIST_MAX_ITEMS = 20
QUALITY_READ_MAX_LIMIT = 20
QUALITY_RECORD_SCAN_LIMIT = 1000
QUALITY_REVIEW_FIELDS = {
    "schema_version",
    "task_summary",
    "record_reason",
    "outcome_summary",
    "delivered_value",
    "issues_and_rework",
    "cost_observations",
    "lessons",
    "residual_risks",
    "next_actions",
}
QUALITY_SECRET_PATTERN = re.compile(
    r"(?i)(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._-]{16,}|\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{12,})"
)

TASK_INTENTS = (
    "query",
    "audit",
    "git_inspect",
    "git_fetch",
    "git_sync",
    "modify",
    "external_write",
)
MUTATION_PROFILES = (
    "read_only",
    "git_metadata_write",
    "workspace_write",
    "external_write",
)
MUTATION_RANK = {name: index for index, name in enumerate(MUTATION_PROFILES)}
INTENT_MUTATION = {
    "query": "read_only",
    "audit": "read_only",
    "git_inspect": "read_only",
    "git_fetch": "git_metadata_write",
    "git_sync": "workspace_write",
    "modify": "workspace_write",
    "external_write": "external_write",
}
INTENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "external_write": ("发布", "上线", "部署", "推送", "发送", "publish", "deploy", "release", "git push"),
    "git_sync": ("git pull", "git merge", "git rebase", "fast-forward", "fast forward", "同步分支", "同步远端"),
    "git_fetch": ("git fetch", "获取远端引用", "获取远端对象", "抓取远端"),
    "git_inspect": ("git status", "git log", "git show", "git diff", "ls-remote", "检查分支", "查看分支", "分支是否可删除"),
    "audit": ("审计", "审查", "评审", "review", "audit"),
    "modify": ("实现", "修改", "调整", "编辑", "新增", "补充", "修复", "重构", "删除", "升级", "迁移", "write", "modify", "implement", "refactor", "fix"),
    "query": ("在哪", "定位", "解释", "比较", "查询", "查找", "查看", "列出", "说明", "where", "explain", "locate", "find", "list"),
}
CONTROLLED_GIT_SCOPE_RE = re.compile(r"^\.git:(?:history|refs/remotes/[A-Za-z0-9._/*-]+)$")
SCOPE_DESCRIPTION_MARKERS = (
    "仅只读",
    "不会写入",
    "不产生",
    "仅限查询",
    "只进行",
    "不要修改",
)
TRUSTED_EVIDENCE_PRODUCERS = {
    ("docs-harness", "git_postcheck"),
    ("docs-harness", "verification_command"),
    ("docs-harness", "auto_attribution"),
    ("docs-harness", "host_declaration"),
    ("codex-host", "file_receipt"),
    ("codex-host", "command_receipt"),
    ("codex-host", "review_receipt"),
    ("independent-reviewer", "review_receipt"),
}
HIGH_RISK_EVIDENCE_TYPES = {
    "security_acceptance",
    "external_state",
    "recovery_acceptance",
    "remote_delivery",
    "fresh_clone_verification",
    "release_acceptance",
}


GATE_ORDER = (
    "product-change",
    "architecture-contract",
    "security-sensitive",
    "destructive-data",
    "release-external",
    "frontend-design",
    "diagnosis-fix",
    "testing-acceptance",
    "review-audit",
    "code-edit",
    "document-edit",
)
GATE_DEFS: dict[str, dict[str, Any]] = {
    "product-change": {
        "terms": ("产品", "需求", "用户流程", "交互逻辑", "product", "requirement"),
        "facts": ("docs/product.md",),
        "plan_fields": ("产品边界", "用户结果"),
        "evidence": ("product_acceptance",),
    },
    "architecture-contract": {
        "terms": ("架构", "api", "接口", "schema", "协议", "数据库", "architecture"),
        "facts": ("docs/architecture.md",),
        "plan_fields": ("兼容策略", "迁移与回滚"),
        "evidence": ("contract_acceptance",),
    },
    "security-sensitive": {
        "terms": ("安全", "鉴权", "权限", "密钥", "隐私", "security", "auth", "token"),
        "facts": ("docs/security.md",),
        "plan_fields": ("安全边界", "负向路径"),
        "evidence": ("security_acceptance",),
    },
    "destructive-data": {
        "terms": ("删除", "清空", "覆盖", "迁移数据", "drop", "truncate", "delete data"),
        "facts": ("docs/architecture.md", "docs/security.md"),
        "plan_fields": ("影响范围", "备份与恢复"),
        "authorization": ("destructive_write",),
        "evidence": ("recovery_acceptance",),
    },
    "release-external": {
        "terms": ("发布", "上线", "部署", "推送", "发送", "publish", "deploy", "release", "push"),
        "facts": ("docs/architecture.md", "docs/testing.md"),
        "plan_fields": ("外部目标", "发布与回滚"),
        "authorization": ("external_write",),
        "evidence": ("external_state",),
    },
    "frontend-design": {
        "terms": ("ui", "界面", "页面", "组件", "视觉", "交互", "frontend", "swiftui"),
        "facts": ("docs/product.md", "docs/design.md"),
        "plan_fields": ("设计状态", "真实页面验收"),
        "evidence": ("ui_acceptance",),
    },
    "diagnosis-fix": {
        "terms": ("诊断", "故障", "报错", "异常", "修复 bug", "debug", "incident", "root cause"),
        "facts": ("docs/architecture.md", "docs/testing.md"),
        "plan_fields": ("首次偏离", "根因证据"),
        "evidence": ("diagnostic_replay",),
    },
    "testing-acceptance": {
        "terms": ("测试", "验收", "回归", "test", "verify", "acceptance"),
        "facts": ("docs/testing.md",),
        "plan_fields": (),
        "evidence": ("test_result",),
    },
    "review-audit": {
        "terms": ("审查", "审计", "review", "audit"),
        "facts": (),
        "plan_fields": (),
        "evidence": ("review_result",),
    },
    "code-edit": {
        "terms": ("代码", "实现", "重构", "函数", "模块", "code", "implement", "refactor"),
        "facts": ("docs/architecture.md",),
        "plan_fields": (),
        "evidence": ("test_result",),
    },
    "document-edit": {
        "terms": ("文档", "说明", "readme", "docs", "markdown"),
        "facts": (),
        "plan_fields": (),
        "evidence": ("document_review",),
    },
}
PLAN_FIELDS = ("背景", "目标", "非目标", "成功标准", "执行内容", "验收结果")
PLAN_FIELD_ALIASES = {
    "背景": ("背景", "background"),
    "目标": ("目标", "goal", "objective"),
    "非目标": ("非目标", "non-goal", "non goal"),
    "成功标准": ("成功标准", "success criteria"),
    "执行内容": ("执行内容", "执行方案", "implementation", "execution"),
    "验收结果": ("验收结果", "验收方案", "acceptance"),
    "执行范围": ("执行范围", "变更范围", "scope"),
}
KNOWLEDGE_SCAFFOLD = {
    "docs/INDEX.md": f"# 项目功能知识库\n\n{MANAGED_VERSION_BEGIN}\nDocs Harness 当前版本：{VERSION}\n{MANAGED_VERSION_END}\n\n## 公共知识\n\n见 `shared/`。\n\n## 功能知识\n\n见 `features/INDEX.md`。\n",
    "docs/shared/architecture.md": "# 公共架构事实\n\n## 当前状态\n\n待项目遍历后补全。\n\n## 事实来源\n\n待确认。\n",
    "docs/shared/security.md": "# 公共安全事实\n\n## 当前状态\n\n待项目遍历后补全。\n\n## 事实来源\n\n待确认。\n",
    "docs/shared/design-system.md": "# 公共设计系统\n\n## 当前状态\n\n待项目遍历后补全。\n\n## 事实来源\n\n待确认。\n",
    "docs/shared/testing-strategy.md": "# 公共测试策略\n\n## 当前状态\n\n待项目遍历后补全。\n\n## 事实来源\n\n待确认。\n",
    "docs/features/INDEX.md": "# 功能知识索引\n\n功能清单由 `docs/knowledge-map.json` 约束。\n",
}

FEATURE_DOC_TEMPLATES = {
    "product": "# {name}：产品事实\n\n## 当前状态\n\n## 用户与场景\n\n## 主流程\n\n## 产品边界\n\n## 已知缺口与待确认\n\n## 事实来源\n",
    "development": "# {name}：研发事实\n\n## 当前状态\n\n## 技术流程\n\n## 模块与公共契约\n\n## 数据与依赖\n\n## 异常与恢复\n\n## 已知缺口与待确认\n\n## 事实来源\n",
    "testing": "# {name}：测试事实\n\n## 当前状态\n\n## 验收标准\n\n## 自动化测试\n\n## 人工验收\n\n## 边界与负向场景\n\n## 已知缺口与待确认\n\n## 事实来源\n",
    "design": "# {name}：设计事实\n\n## 当前状态\n\n## 交互入口与流程\n\n## 完整状态\n\n## 组件、文案与反馈\n\n## 可访问性与平台差异\n\n## 已知缺口与待确认\n\n## 事实来源\n",
}

GATE_KNOWLEDGE_CATEGORIES = {
    "product-change": ("product",),
    "architecture-contract": ("development",),
    "security-sensitive": ("development",),
    "destructive-data": ("development", "testing"),
    "release-external": ("development", "testing"),
    "frontend-design": ("product", "design"),
    "diagnosis-fix": ("development", "testing"),
    "testing-acceptance": ("testing",),
    "code-edit": ("development",),
}

# 宿主权威声明 gate 时仍由代码强制兜底的安全底线集合：模型只能加不能减。
SAFETY_FLOOR_GATES = {"security-sensitive", "destructive-data", "release-external"}
# 底线触发不复用宽泛的 GATE_DEFS 词表：专用精确词表 + 否定守卫，只修剪明显误报。
FLOOR_TERMS: dict[str, tuple[str, ...]] = {
    "security-sensitive": ("安全", "鉴权", "权限", "密钥", "隐私", "security", "auth", "token"),
    "destructive-data": ("清空", "覆盖", "删除数据", "迁移数据", "删库", "drop", "truncate", "delete data"),
    "release-external": ("发布", "上线", "部署", "推送到远端", "推送远端", "git push", "publish", "deploy", "release"),
}
NEGATION_MARKERS = ("不要", "不用", "先不", "无需", "不许", "禁止", "别", "非", "不", "without", "don't", "do not", "no ")


class HarnessError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_request",
        exit_code: int = 2,
        suggested_fix: str | None = None,
        missing_items: list[dict[str, Any]] | None = None,
        actual_vs_expected: dict[str, Any] | None = None,
        extra_payload: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.suggested_fix = suggested_fix
        self.missing_items = missing_items
        self.actual_vs_expected = actual_vs_expected
        self.extra_payload = extra_payload


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def script_fingerprint_tolerant(path: Path) -> str:
    """对控制脚本做行尾宽容指纹：autocrlf 等行尾转换不视为内容漂移。"""
    digest = hashlib.sha256()
    pending_cr = False
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            if pending_cr:
                if chunk.startswith(b"\n"):
                    # 边界 CRLF 归一化为 \n，与 chunk 内的 replace 行为保持一致。
                    chunk = chunk[1:]
                    digest.update(b"\n")
                else:
                    digest.update(b"\r")
                pending_cr = False
            if chunk.endswith(b"\r"):
                chunk = chunk[:-1]
                pending_cr = True
            digest.update(chunk.replace(b"\r\n", b"\n"))
    if pending_cr:
        digest.update(b"\r")
    return "sha256:" + digest.hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(raw, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(raw)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HarnessError(f"缺少文件：{path}", code="missing_file") from exc
    except json.JSONDecodeError as exc:
        raise HarnessError(f"JSON 无效：{path}: {exc}", code="invalid_json") from exc


def looks_like_inline_input(value: str) -> bool:
    stripped = value.lstrip()
    return (
        "\n" in value
        or "\r" in value
        or (stripped.startswith("{") and stripped.rstrip().endswith("}"))
        or (stripped.startswith("[") and stripped.rstrip().endswith("]"))
    )


def load_input_file(
    path_value: str,
    *,
    argument: str,
    max_bytes: int,
    error_code: str,
) -> tuple[Path, str]:
    if looks_like_inline_input(path_value):
        raise HarnessError(
            f"{argument} 只接受文件路径，不接受内联内容；请先保存为文件",
            code="inline_input_not_supported",
        )
    try:
        path = Path(path_value).expanduser().resolve()
        if not path.is_file():
            suggested_fix = None
            if sys.platform == "win32" and path_value.startswith("/"):
                suggested_fix = "Git Bash 的 /tmp 等 POSIX 绝对路径对 Windows Python 不可解析；请改用工作区相对路径"
            raise HarnessError(f"{argument} 文件不存在", code=error_code, suggested_fix=suggested_fix)
        if path.stat().st_size > max_bytes:
            raise HarnessError(f"{argument} 文件超过大小限制", code=error_code)
        text = path.read_text(encoding="utf-8")
    except HarnessError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise HarnessError(
            f"{argument} 文件不可读取或路径无效",
            code=error_code,
        ) from exc
    return path, text


def load_json_object_file(
    path_value: str,
    *,
    argument: str,
    max_bytes: int,
    error_code: str,
) -> tuple[Path, dict[str, Any]]:
    path, text = load_input_file(
        path_value,
        argument=argument,
        max_bytes=max_bytes,
        error_code=error_code,
    )
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            f"{argument} JSON 无效",
            code=error_code,
            actual_vs_expected={
                "actual": f"invalid JSON: {exc}",
                "expected": "valid JSON object",
            },
            suggested_fix=f"检查 {argument} 文件内容是否为合法 JSON；每个 --evidence 参数对应一个 JSON 对象文件",
        ) from exc
    if not isinstance(value, dict):
        raise HarnessError(
            f"{argument} 必须是 JSON 对象",
            code=error_code,
            actual_vs_expected={
                "actual": f"JSON {type(value).__name__}",
                "expected": "single JSON object per --evidence parameter",
            },
            suggested_fix="每个 --evidence 参数对应一个 JSON 对象文件；如需提交多个证据，使用多个 --evidence 参数",
        )
    return path, value


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    result: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HarnessError(f"事件文件第 {number} 行无效：{path}", code="invalid_state") from exc
        if not isinstance(value, dict):
            raise HarnessError(f"事件文件第 {number} 行不是对象：{path}", code="invalid_state")
        result.append(value)
    return result


def safe_target(raw: str | Path) -> Path:
    target = Path(raw).expanduser().resolve()
    if not target.is_dir():
        raise HarnessError(f"目标目录不存在：{target}", code="missing_target")
    if target == Path(target.anchor) or target == Path.home().resolve():
        raise HarnessError("拒绝把文件系统根目录或用户主目录作为项目目标", code="unsafe_target")
    return target


def validate_task_id(task_id: str) -> None:
    if not TASK_ID_RE.fullmatch(task_id):
        raise HarnessError("task-id 格式无效", code="invalid_task_id")


def git_dir(target: Path) -> Path | None:
    probe = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    value = probe.stdout.strip()
    path = Path(value)
    return path.resolve() if path.is_absolute() else (target / path).resolve()


def git_root(target: Path) -> Path | None:
    probe = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    return Path(probe.stdout.strip()).resolve()


def git_command(target: Path, *arguments: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(target), *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise HarnessError("Git 预检超时", code="git_preflight_timeout", exit_code=3) from exc


def sanitized_remote_fingerprint(raw: str) -> str:
    value = raw.strip()
    if "://" in value:
        parsed = urllib.parse.urlsplit(value)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        value = urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    elif "@" in value:
        value = value.split("@", 1)[1]
    return sha256_text(value)


def target_identity(target: Path) -> str:
    root = git_root(target)
    if root == target.resolve():
        remotes = git_command(target, "remote").stdout.splitlines()
        fingerprints: list[str] = []
        for remote in sorted(item.strip() for item in remotes if item.strip()):
            result = git_command(target, "remote", "get-url", remote)
            if result.returncode == 0 and result.stdout.strip():
                fingerprints.append(sanitized_remote_fingerprint(result.stdout))
        if fingerprints:
            return sha256_text(canonical_json({"kind": "git", "remotes": fingerprints}))
    return sha256_text(canonical_json({"kind": "local", "path": str(target.resolve())}))


def git_refs_snapshot(target: Path) -> dict[str, str]:
    result = git_command(target, "for-each-ref", "--format=%(refname)%00%(objectname)")
    if result.returncode != 0:
        raise HarnessError("无法读取 Git refs", code="git_preflight_failed", exit_code=3)
    refs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "\0" not in line:
            continue
        name, oid = line.split("\0", 1)
        refs[name] = oid
    return refs


def git_remote_target(
    target: Path,
    remote: str,
    remote_ref: str,
) -> tuple[str, dict[str, str]]:
    result = git_command(target, "ls-remote", "--refs", remote, remote_ref)
    if result.returncode != 0:
        raise HarnessError("无法读取目标远端引用", code="git_remote_unavailable", exit_code=3)
    refs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{40,64}", parts[0]):
            refs[parts[1]] = parts[0]
    if not refs:
        raise HarnessError("目标远端引用不存在", code="git_remote_ref_missing", exit_code=3)
    if len(refs) == 1:
        return next(iter(refs.values())), refs
    return sha256_text(canonical_json(refs)), refs


def git_name_status_paths(output: str) -> list[str]:
    """解析 `git diff --name-status -M` 输出为重命名前后的完整路径清单。"""
    paths: list[str] = []
    for line in output.splitlines():
        columns = line.split("\t")
        if not columns:
            continue
        status = columns[0]
        members = columns[1:]
        if status.startswith("R") and len(members) == 2:
            paths.extend(members)
        elif members:
            paths.append(members[-1])
    return paths


def git_scope_target(git_scope: Sequence[str], *, require_exact: bool) -> tuple[str, str, str]:
    resources = [item for item in git_scope if item.startswith(".git:refs/remotes/")]
    if not resources:
        raise HarnessError("Git 操作缺少远端 refs 范围", code="git_scope_required", exit_code=3)
    resource = resources[0].removeprefix(".git:refs/remotes/")
    parts = resource.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HarnessError("git_scope 远端引用格式无效", code="invalid_git_scope")
    remote, branch = parts
    if require_exact and any(char in branch for char in "*?["):
        raise HarnessError("git_sync 必须绑定单一远端分支", code="git_sync_scope_ambiguous", exit_code=3)
    remote_ref = f"refs/heads/{branch}"
    controlled = f"refs/remotes/{remote}/{branch}"
    return remote, remote_ref, controlled


def git_preflight_contract(
    target: Path,
    operation: str | None,
    git_scope: Sequence[str],
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    if operation not in {"git_fetch", "git_sync"}:
        return None, [], []
    root = git_root(target)
    if root != target.resolve():
        return None, [], ["目标不是独立 Git 工作树根目录"]
    try:
        remote, remote_ref, controlled_ref = git_scope_target(
            git_scope,
            require_exact=operation == "git_sync",
        )
        remote_url_result = git_command(target, "remote", "get-url", remote)
        if remote_url_result.returncode != 0 or not remote_url_result.stdout.strip():
            raise HarnessError("Git remote 不存在", code="git_remote_unavailable", exit_code=3)
        target_oid, remote_refs = git_remote_target(target, remote, remote_ref)
        head_result = git_command(target, "rev-parse", "HEAD")
        head = head_result.stdout.strip() if head_result.returncode == 0 else "unborn"
        branch_result = git_command(target, "symbolic-ref", "-q", "HEAD")
        current_branch_ref = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
        index_result = git_command(target, "ls-files", "-s", "-z")
        if index_result.returncode != 0:
            raise HarnessError("无法冻结 Git 索引", code="git_preflight_failed", exit_code=3)
        sync_scope: list[str] = []
        deletion_count = 0
        fast_forward = True
        if operation == "git_sync":
            object_result = git_command(target, "cat-file", "-e", f"{target_oid}^{{commit}}")
            if object_result.returncode != 0:
                raise HarnessError("远端目标对象尚未获取，必须先完成 git_fetch", code="git_target_object_missing", exit_code=3)
            if head != "unborn":
                ancestor_result = git_command(target, "merge-base", "--is-ancestor", head, target_oid)
                fast_forward = ancestor_result.returncode == 0
            diff_result = git_command(target, "diff", "--name-status", "-M", head, target_oid)
            if diff_result.returncode != 0:
                raise HarnessError("无法生成 git_sync 变化清单", code="git_preflight_failed", exit_code=3)
            sync_scope = git_name_status_paths(diff_result.stdout)
            deletion_count = sum(
                1
                for line in diff_result.stdout.splitlines()
                if line.split("\t", 1)[0].startswith("D")
            )
        uses_lfs = (target / ".gitattributes").is_file() and "filter=lfs" in (target / ".gitattributes").read_text(encoding="utf-8", errors="ignore")
        lfs_probe = git_command(target, "lfs", "version") if uses_lfs else None
        lfs_available = not uses_lfs or bool(lfs_probe and lfs_probe.returncode == 0)
        uses_submodules = (target / ".gitmodules").is_file()
        submodule_probe = git_command(target, "submodule", "status") if uses_submodules else None
        submodule_available = not uses_submodules or bool(
            submodule_probe
            and submodule_probe.returncode == 0
            and all(not line.startswith(("-", "+", "U")) for line in submodule_probe.stdout.splitlines() if line)
        )
        blockers: list[str] = []
        if operation == "git_sync":
            status_result = git_command(target, "status", "--porcelain=v1", "-z")
            dirty_paths: list[str] = []
            if status_result.returncode == 0:
                for entry in status_result.stdout.split("\0"):
                    if not entry:
                        continue
                    path = entry[3:] if len(entry) > 3 else ""
                    if " -> " in path:
                        dirty_paths.extend(path.split(" -> ", 1))
                    elif path:
                        dirty_paths.append(path)
            overlapping_dirty = [path for path in dirty_paths if scope_covers(path, sync_scope)]
            if overlapping_dirty:
                blockers.append("脏工作区与 git_sync 变化范围重叠：" + ", ".join(sorted(set(overlapping_dirty))))
            if deletion_count > GIT_DELETION_THRESHOLD:
                blockers.append(f"Git 删除数量 {deletion_count} 超过阈值 {GIT_DELETION_THRESHOLD}")
            if not fast_forward:
                blockers.append("远端目标不能从当前 HEAD fast-forward")
        if not lfs_available:
            blockers.append("Git LFS 不可用")
        if not submodule_available:
            blockers.append("Git Submodule 状态不可验证")
        snapshot = {
            "repo_identity": sha256_text(canonical_json({"root_name": root.name, "remote": sanitized_remote_fingerprint(remote_url_result.stdout)})),
            "remote": {
                "name": remote,
                "url_fingerprint": sanitized_remote_fingerprint(remote_url_result.stdout),
                "refspec": remote_ref,
            },
            "preflight_target_oid": target_oid,
            "remote_refs": remote_refs,
            "head": head,
            "index_tree": sha256_text(index_result.stdout),
            "worktree_fingerprint": sha256_text(canonical_json(workspace_snapshot(target))),
            "controlled_refs_namespace": list(dict.fromkeys([
                *git_scope,
                *(
                    f".git:refs/remotes/{match.group(1)}/HEAD"
                    for item in git_scope
                    if (match := re.fullmatch(r"\.git:refs/remotes/([^/]+)/.+", item))
                ),
                *([f".git:{current_branch_ref}"] if operation == "git_sync" and current_branch_ref else []),
            ])),
            "controlled_ref": controlled_ref,
            "refs": git_refs_snapshot(target),
            "lfs_available": lfs_available,
            "uses_lfs": uses_lfs,
            "submodule_available": submodule_available,
            "uses_submodules": uses_submodules,
            "fast_forward": fast_forward,
            "git_sync_scope": list(dict.fromkeys(sync_scope)),
            "deletion_count": deletion_count,
            "captured_at": utc_now(),
        }
        return snapshot, list(dict.fromkeys(sync_scope)), blockers
    except HarnessError as exc:
        return None, [], [f"{exc.code}: {exc}"]


def git_postcheck(target: Path, package: dict[str, Any]) -> dict[str, Any] | None:
    operation = package.get("git_operation")
    snapshot = package.get("git_state_snapshot")
    if operation not in {"git_fetch", "git_sync"}:
        return None
    if not isinstance(snapshot, dict):
        return {
            "passed": False,
            "reason_code": "git_state_snapshot_missing",
            "checks": {},
        }
    remote = str(snapshot.get("remote", {}).get("name", ""))
    remote_ref = str(snapshot.get("remote", {}).get("refspec", ""))
    try:
        current_target, remote_refs = git_remote_target(target, remote, remote_ref)
        refs = git_refs_snapshot(target)
        head_result = git_command(target, "rev-parse", "HEAD")
        head = head_result.stdout.strip() if head_result.returncode == 0 else "unborn"
        current_workspace_fingerprint = sha256_text(canonical_json(workspace_snapshot(target)))
    except HarnessError as exc:
        return {"passed": False, "reason_code": exc.code, "checks": {}}
    before_refs = snapshot.get("refs", {}) if isinstance(snapshot.get("refs"), dict) else {}
    changed_refs = sorted(
        name
        for name in set(before_refs) | set(refs)
        if before_refs.get(name) != refs.get(name)
    )
    controlled_patterns = [
        item.removeprefix(".git:")
        for item in snapshot.get("controlled_refs_namespace", [])
        if isinstance(item, str) and item.startswith(".git:refs/")
    ]
    outside_refs = [
        name for name in changed_refs if not any(fnmatch.fnmatch(name, pattern) for pattern in controlled_patterns)
    ]
    checks: dict[str, bool] = {
        "remote_target_unchanged": current_target == snapshot.get("preflight_target_oid"),
        "refs_within_contract": not outside_refs,
    }
    if operation == "git_fetch":
        index_result = git_command(target, "ls-files", "-s", "-z")
        checks.update(
            {
                "index_readable": index_result.returncode == 0,
                "head_unchanged": head == snapshot.get("head"),
                "index_unchanged": sha256_text(index_result.stdout) == snapshot.get("index_tree"),
                "worktree_unchanged": current_workspace_fingerprint == snapshot.get("worktree_fingerprint"),
            }
        )
    else:
        controlled_ref = str(snapshot.get("controlled_ref", ""))
        checks.update(
            {
                "head_matches_preflight_target": head == snapshot.get("preflight_target_oid"),
                "controlled_ref_matches_target": refs.get(controlled_ref) == snapshot.get("preflight_target_oid"),
            }
        )
        if checks["controlled_ref_matches_target"]:
            divergence = git_command(target, "rev-list", "--left-right", "--count", f"HEAD...{controlled_ref}")
            checks["branch_not_diverged"] = divergence.returncode == 0 and divergence.stdout.strip() == "0\t0"
        else:
            checks["branch_not_diverged"] = False
        if snapshot.get("uses_lfs"):
            checks["lfs_available"] = git_command(target, "lfs", "version").returncode == 0
            checks["lfs_objects_valid"] = git_command(target, "lfs", "fsck").returncode == 0
        if snapshot.get("uses_submodules"):
            submodule = git_command(target, "submodule", "status")
            checks["submodule_state_valid"] = (
                submodule.returncode == 0
                and all(not line.startswith(("-", "+", "U")) for line in submodule.stdout.splitlines() if line)
            )
    reason_code = "git_remote_drift" if not checks["remote_target_unchanged"] else (
        "git_ref_scope_violation" if not checks["refs_within_contract"] else "git_postcheck_failed"
    )
    return {
        "passed": all(checks.values()),
        "reason_code": None if all(checks.values()) else reason_code,
        "operation": operation,
        "checks": checks,
        "changed_refs": changed_refs,
        "outside_refs": outside_refs,
        "remote_refs": remote_refs,
    }


def git_ignored_install_paths(target: Path, relative_paths: Sequence[str]) -> list[str]:
    root = git_root(target)
    if root is None:
        return []
    ignored: list[str] = []
    for relative in relative_paths:
        path = (target / relative).resolve()
        try:
            git_relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", git_relative],
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0:
            continue
        checked = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--no-index", "-q", "--", git_relative],
            capture_output=True,
            check=False,
        )
        if checked.returncode == 0:
            ignored.append(relative)
    return ignored


def runtime_root(target: Path) -> Path:
    root = git_dir(target)
    return (root / "docs-harness" / "runs") if root else (target / ".docs-harness" / "runs")


def quality_ledger_root(target: Path) -> Path:
    return runtime_root(target).parent / "quality-ledger"


def quality_records_root(target: Path) -> Path:
    return quality_ledger_root(target) / "records"


def task_state_dir(target: Path, task_id: str) -> Path:
    validate_task_id(task_id)
    return runtime_root(target) / task_id


def harness_command_argv(command: str, target: Path, *arguments: str) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        command,
        "--target",
        str(target),
        *arguments,
        "--json",
    ]


def next_step_payload(
    target: Path,
    state: Path,
    package: dict[str, Any],
    next_action: str,
    *,
    reason_code: str | None = None,
    artifact_ref: Path | None = None,
    work_package: str | None = None,
) -> dict[str, Any]:
    task_id = package["task_id"]
    artifact = artifact_ref
    command: list[str] = []
    if next_action == "load_plan_context":
        artifact = artifact or (state / "plan.json")
        command = harness_command_argv(
            "context", target, "--task-id", task_id, "--stage", "plan"
        )
    elif next_action in {"submit_plan", "complete_plan"}:
        artifact = artifact or (state / "plan.json")
        command = harness_command_argv(
            "run", target, "--task-id", task_id, "--plan", str(artifact)
        )
    elif next_action == "complete_plan_delta":
        artifact = artifact or (state / "plan-delta.json")
        command = harness_command_argv(
            "run", target, "--task-id", task_id, "--plan", str(artifact)
        )
    elif next_action == "load_action_context":
        command = harness_command_argv(
            "context", target, "--task-id", task_id, "--stage", "action"
        )
    elif next_action == "load_context_delta":
        command = harness_command_argv(
            "context", target, "--task-id", task_id, "--stage", "action"
        )
    elif next_action == "obtain_authorization":
        artifact = artifact or (state / "authorization.json")
        command = harness_command_argv(
            "run", target, "--task-id", task_id, "--authorization", str(artifact)
        )
    elif next_action in {"provide_evidence", "refresh_evidence"}:
        artifact = artifact or (state / "evidence.json")
        command = harness_command_argv(
            "verify", target, "--task-id", task_id, "--evidence", str(artifact)
        )
    elif next_action in {"verify", "retry_verification"}:
        command = harness_command_argv("verify", target, "--task-id", task_id)
    elif next_action == "rerun_harness_for_readmission":
        command = harness_command_argv("run", target, "--task-id", task_id)
    elif next_action == "load_work_package_context" and work_package:
        command = harness_command_argv(
            "context", target, "--task-id", task_id, "--work-package", work_package
        )
    elif next_action == "begin_work_package" and work_package:
        command = harness_command_argv(
            "progress",
            target,
            "begin",
            "--task-id",
            task_id,
            "--work-package",
            work_package,
        )
    return {
        "reason_code": reason_code or next_action,
        "next_action": next_action,
        "next_command_argv": command,
        "artifact_ref": str(artifact) if artifact else None,
        "contract_snapshot": {
            "allowed_scope": package.get("allowed_scope", []),
            "read_scope": package.get("read_scope", []),
            "write_scope": package.get("write_scope", []),
            "plan_fields": package.get("plan_fields", []),
            "evidence_types": (package.get("completion_manifest") or {}).get("required_evidence_types", []),
            "functional_confirmation_required": bool(
                any(item.get("required", False) for item in package.get("functional_confirmation_features", []))
            ),
            "functional_confirmation_features": [
                {
                    "feature_id": item.get("feature_id"),
                    "name": item.get("name"),
                    "tier": item.get("tier", ""),
                    "mode": item.get("mode", ""),
                    "assertions": item.get("assertions", []),
                    "testing_ref": item.get("testing_ref", ""),
                    "required": item.get("required", False),
                    "skip_reason": item.get("skip_reason", ""),
                }
                for item in package.get("functional_confirmation_features", [])
                if isinstance(item, dict)
            ],
        },
    }


@contextlib.contextmanager
def state_lock(state: Path) -> Iterator[None]:
    state.mkdir(parents=True, exist_ok=True)
    lock = state / ".lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        try:
            age = time.time() - lock.stat().st_mtime
        except FileNotFoundError:
            age = 0
        if age > 300:
            raise HarnessError("检测到超过 5 分钟的状态锁；需人工确认后清理", code="stale_lock") from exc
        raise HarnessError("同一任务正在被另一个进程更新", code="state_locked") from exc
    try:
        os.write(fd, f"pid={os.getpid()} at={utc_now()}\n".encode("utf-8"))
        os.close(fd)
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()


def append_task_event(
    state: Path,
    package: dict[str, Any],
    *,
    event: str,
    phase: str,
    reason_code: str,
    duration_ms: int = 0,
    context_cache_hit: bool = False,
    **fields: Any,
) -> None:
    prior = read_jsonl(state / "events.jsonl")
    evidence_index = read_json(state / "evidence-index.json") if (state / "evidence-index.json").is_file() else {"evidence": []}
    payload = {
        "schema_version": EVENT_SCHEMA,
        "event": event,
        "task_id": package["task_id"],
        "phase": phase,
        "started_at": utc_now(),
        "duration_ms": max(0, int(duration_ms)),
        "reason_code": reason_code,
        "package_revision": package["package_revision"],
        "context_cache_hit": bool(context_cache_hit),
        "context_load_count": sum(1 for item in prior if item.get("phase") == "context" and not item.get("context_cache_hit")),
        "readmission_count": sum(
            1
            for item in prior
            if item.get("event") in {"readmission", "scope_bound_readmission", "incremental_gate_readmission", "scope_extension_readmission"}
        ),
        "evidence_round_count": sum(1 for item in prior if item.get("phase") == "verification"),
        "host_receipt_count": (
            len(read_jsonl(state / "context-receipts.jsonl"))
            + len(read_jsonl(state / "authorization-receipts.jsonl"))
            + len(evidence_index.get("evidence", []))
        ),
        "business_action_count": sum(1 for item in prior if item.get("event") in {"begin", "submit"}),
        "at": utc_now(),
    }
    payload.update(fields)
    append_jsonl(state / "events.jsonl", payload)


def excluded_workspace_path(relative: str) -> bool:
    parts = Path(relative).parts
    if not parts:
        return False
    if parts[0] in {".git", "node_modules", ".venv"}:
        return True
    return (
        len(parts) >= 2
        and parts[0] == ".docs-harness"
        and parts[1] in {"runs", "quality-ledger", "knowledge", "knowledge-jobs", "background"}
    )


def git_workspace_paths(target: Path) -> list[Path] | None:
    probe = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    try:
        git_root = Path(probe.stdout.strip()).resolve()
    except (OSError, RuntimeError):
        return None
    if git_root != target.resolve():
        return None
    listed = subprocess.run(
        ["git", "-C", str(target), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        check=False,
    )
    if listed.returncode != 0:
        return None
    relatives = [item.decode("utf-8", errors="surrogateescape") for item in listed.stdout.split(b"\0") if item]
    return [target / relative for relative in sorted(set(relatives))]


_LAYER_REUSE_LIMIT = 64
_LAYER_REUSE_STATS = {"snapshot_hits": 0, "snapshot_misses": 0, "file_hash_hits": 0, "file_hash_misses": 0}
_WORKSPACE_SNAPSHOT_CACHE: dict[tuple[str, str, str], tuple[str, dict[str, str]]] = {}
_FILE_FINGERPRINT_CACHE: dict[tuple[str, int, int], str] = {}


def layer_reuse_stats() -> dict[str, int]:
    """单次 CLI 会话内验收层中间产物复用的有界遥测（只含计数，不含路径以外信息）。"""
    return dict(_LAYER_REUSE_STATS)


def reset_layer_reuse_cache() -> None:
    _WORKSPACE_SNAPSHOT_CACHE.clear()
    _FILE_FINGERPRINT_CACHE.clear()
    for key in _LAYER_REUSE_STATS:
        _LAYER_REUSE_STATS[key] = 0


def cached_file_fingerprint(path: Path) -> str:
    """按 (路径, 大小, mtime_ns) 复用进程内文件 SHA-256；文件变化即失效。"""
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    cached = _FILE_FINGERPRINT_CACHE.get(key)
    if cached is not None:
        _LAYER_REUSE_STATS["file_hash_hits"] += 1
        return cached
    _LAYER_REUSE_STATS["file_hash_misses"] += 1
    digest = file_fingerprint(path)
    if len(_FILE_FINGERPRINT_CACHE) >= _LAYER_REUSE_LIMIT * 16:
        _FILE_FINGERPRINT_CACHE.clear()
    _FILE_FINGERPRINT_CACHE[key] = digest
    return digest


def cached_workspace_snapshot(target: Path, *, contract_version: str, target_id: str) -> dict[str, str]:
    """按 (路径, 清单摘要, 合同版本, target_identity) 复用进程内工作区快照。

    清单摘要是全部受跟踪文件 (相对路径, 大小, mtime_ns) 的 SHA-256：任何文件新建、
    删除或内容变化都会改变摘要并触发重算；合同版本或目标变化同样失效。只复用确定性
    中间产物，各验收层的判定结论仍各自独立产出。
    """
    git_paths = git_workspace_paths(target)
    paths = git_paths if git_paths is not None else sorted(target.rglob("*"))
    listing: list[list[Any]] = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(target).as_posix()
        if excluded_workspace_path(relative):
            continue
        stat = path.stat()
        listing.append([relative, stat.st_size, stat.st_mtime_ns])
    digest = sha256_text(canonical_json(listing))
    key = (str(target.resolve()), contract_version, target_id)
    cached = _WORKSPACE_SNAPSHOT_CACHE.get(key)
    if cached is not None and cached[0] == digest:
        _LAYER_REUSE_STATS["snapshot_hits"] += 1
        return dict(cached[1])
    _LAYER_REUSE_STATS["snapshot_misses"] += 1
    snapshot = workspace_snapshot(target)
    if len(_WORKSPACE_SNAPSHOT_CACHE) >= _LAYER_REUSE_LIMIT:
        _WORKSPACE_SNAPSHOT_CACHE.clear()
    _WORKSPACE_SNAPSHOT_CACHE[key] = (digest, dict(snapshot))
    return snapshot


def workspace_snapshot(target: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    git_paths = git_workspace_paths(target)
    count = 0
    paths = git_paths if git_paths is not None else sorted(target.rglob("*"))
    for path in paths:
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(target).as_posix()
        if excluded_workspace_path(relative):
            continue
        if git_paths is None and count >= FALLBACK_SNAPSHOT_FILE_LIMIT:
            raise HarnessError(
                f"非 Git 工作区快照超过 {FALLBACK_SNAPSHOT_FILE_LIMIT} 个文件，拒绝使用截断基线",
                code="workspace_snapshot_truncated",
                exit_code=3,
            )
        stat = path.stat()
        if stat.st_size <= 2 * 1024 * 1024:
            snapshot[relative] = cached_file_fingerprint(path)
        else:
            snapshot[relative] = sha256_text(f"{stat.st_size}:{stat.st_mtime_ns}")
        count += 1
    return snapshot


def snapshot_changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


VOLATILE_VERIFICATION_DIR_PARTS = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".pytype",
    ".tox", ".nox", ".hypothesis", ".cache", ".nyc_output", "htmlcov",
}
VOLATILE_VERIFICATION_SUFFIXES = {".pyc", ".pyo", ".tmp", ".temp", ".swp", ".bak", ".log"}
VOLATILE_VERIFICATION_FILENAMES = {".coverage", ".ds_store", "thumbs.db", ".eslintcache"}


def validate_volatile_verification_paths(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise HarnessError("verification.volatile_paths 必须是非空字符串数组", code="invalid_project_config")
    patterns: list[str] = []
    for raw in value:
        pattern = raw.strip()
        parts = pattern.split("/")
        if (
            len(pattern) > 256
            or "\\" in pattern
            or ":" in pattern
            or pattern.startswith("/")
            or len(parts) < 2
            or any(part in {"", ".", ".."} for part in parts)
            or any(char in parts[0] for char in "*?[")
            or parts[0].casefold() in {".git", ".docs-harness"}
            or any(ord(char) < 32 or ord(char) == 127 for char in pattern)
        ):
            raise HarnessError(
                f"verification.volatile_paths 必须是工作区内带固定根目录的 glob：{pattern}",
                code="invalid_project_config",
            )
        patterns.append(pattern)
    return list(dict.fromkeys(patterns))


def configured_volatile_verification_patterns(target: Path) -> list[str]:
    config = project_config(target) or {}
    verification = config.get("verification")
    if verification is None:
        return []
    if not isinstance(verification, dict):
        raise HarnessError("项目配置 verification 必须是对象", code="invalid_project_config")
    return validate_volatile_verification_paths(verification.get("volatile_paths"))


def verification_command_cache_enabled(target: Path) -> bool:
    """验证命令逐项缓存默认开启，可通过项目配置 verification.command_cache_enabled 整体关闭。"""
    config = project_config(target) or {}
    verification = config.get("verification")
    if verification is None:
        return True
    if not isinstance(verification, dict):
        raise HarnessError("项目配置 verification 必须是对象", code="invalid_project_config")
    enabled = verification.get("command_cache_enabled", True)
    if not isinstance(enabled, bool):
        raise HarnessError("项目配置 verification.command_cache_enabled 必须是布尔值", code="invalid_project_config")
    return enabled


def auto_attribute_in_scope(target: Path) -> bool:
    """write_scope 内未归因写入默认由控制器自动归因，可通过 verification.auto_attribute_in_scope 关闭。"""
    config = project_config(target) or {}
    verification = config.get("verification")
    if verification is None:
        return True
    if not isinstance(verification, dict):
        raise HarnessError("项目配置 verification 必须是对象", code="invalid_project_config")
    enabled = verification.get("auto_attribute_in_scope", True)
    if not isinstance(enabled, bool):
        raise HarnessError("项目配置 verification.auto_attribute_in_scope 必须是布尔值", code="invalid_project_config")
    return enabled


def volatile_verification_path(relative: str, extra_patterns: Sequence[str] = ()) -> bool:
    parts = Path(relative).parts
    if not parts:
        return False
    if any(part.casefold() in VOLATILE_VERIFICATION_DIR_PARTS for part in parts):
        return True
    name = parts[-1]
    if Path(name).suffix.casefold() in VOLATILE_VERIFICATION_SUFFIXES:
        return True
    lowered = name.casefold()
    if lowered in VOLATILE_VERIFICATION_FILENAMES or lowered.startswith(".coverage."):
        return True
    if name.startswith((".~", ".#")) or name.endswith("~"):
        return True
    return any(
        fnmatch.fnmatchcase(relative, pattern) or fnmatch.fnmatchcase(name, pattern)
        for pattern in extra_patterns
    )


def environment_fingerprint() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "executable": str(Path(sys.executable).resolve()),
    }


def load_facts(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    _, value = load_json_object_file(
        path,
        argument="--facts",
        max_bytes=1024 * 1024,
        error_code="invalid_facts",
    )
    return value


def normalize_string_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise HarnessError(f"{name} 必须是非空字符串数组", code="invalid_facts")
    return list(dict.fromkeys(item.strip() for item in value))


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    metadata: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    return metadata, text[end + 5 :]


def project_config(target: Path) -> dict[str, Any] | None:
    path = target / ".docs-harness" / "config.json"
    if not path.is_file():
        return None
    value = read_json(path)
    return value if isinstance(value, dict) else None


def document_route_config(target: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """读取并完整校验显式文档路由；配置存在但非法时绝不回退。"""
    config = project_config(target) or {}
    governance = config.get("background_governance", {})
    if not isinstance(governance, dict):
        return {}, [{"reason_code": "invalid_document_route_config", "kind": "background_governance"}]
    raw = governance.get("document_routes")
    if raw is None:
        return {}, []
    if not isinstance(raw, dict):
        return {}, [{"reason_code": "invalid_document_route_config", "kind": "document_routes"}]
    errors: list[dict[str, Any]] = []
    routes: dict[str, str] = {}
    unknown = sorted(str(key) for key in raw if key not in DOCUMENT_ROUTE_KINDS)
    for key in unknown:
        errors.append({"reason_code": "invalid_document_route_config", "kind": key})
    for kind in DOCUMENT_ROUTE_KINDS:
        if kind not in raw:
            continue
        value = raw[kind]
        if not isinstance(value, str) or not value or len(value) > 512:
            errors.append({"reason_code": "invalid_document_route_config", "kind": kind})
            continue
        if (
            value != value.strip()
            or value.startswith("/")
            or "\\" in value
            or ":" in value
            or any(char in value for char in "*?[]")
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            errors.append({"reason_code": "invalid_document_route_config", "kind": kind})
            continue
        relative = Path(value)
        if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
            errors.append({"reason_code": "invalid_document_route_config", "kind": kind})
            continue
        if relative.parts[0] in {".git", ".docs-harness"}:
            errors.append({"reason_code": "invalid_document_route_config", "kind": kind})
            continue
        path = target / relative
        unsafe = False
        current = target
        for part in relative.parts:
            current = current / part
            if current.exists() or current.is_symlink():
                if current.is_symlink():
                    unsafe = True
                    break
        try:
            path.resolve().relative_to(target.resolve())
        except ValueError:
            unsafe = True
        expected = path.is_file() if kind in DOCUMENT_ROUTE_FILE_KINDS else path.is_dir()
        if unsafe or not expected:
            errors.append({"reason_code": "invalid_document_route_config", "kind": kind})
            continue
        routes[kind] = relative.as_posix()
    return routes, errors


def document_route_candidates(target: Path, kind: str) -> tuple[list[str], list[dict[str, str]]]:
    names = {
        "architecture": "architecture.md",
        "changelog": "changelog.md",
        "todo": "todo.md",
        "adr_root": "adr",
        "reviews_root": "reviews",
    }
    expected_name = names[kind].casefold()
    parents = (target, target / "docs") if kind in DOCUMENT_ROUTE_FILE_KINDS else (target / "docs",)
    trusted: list[tuple[str, tuple[int, int]]] = []
    rejected: list[dict[str, str]] = []
    for parent in parents:
        if not parent.is_dir() or parent.is_symlink():
            continue
        for path in sorted(parent.iterdir(), key=lambda item: item.name):
            if path.name.casefold() != expected_name:
                continue
            relative = path.relative_to(target).as_posix()
            if path.is_symlink():
                rejected.append({"path": relative, "reason_code": "document_route_unsafe"})
                continue
            valid_type = path.is_file() if kind in DOCUMENT_ROUTE_FILE_KINDS else path.is_dir()
            if not valid_type:
                rejected.append({"path": relative, "reason_code": "document_route_wrong_type"})
                continue
            try:
                path.resolve().relative_to(target.resolve())
                stat = path.stat()
            except (ValueError, OSError):
                rejected.append({"path": relative, "reason_code": "document_route_unsafe"})
                continue
            trusted.append((relative, (int(stat.st_dev), int(stat.st_ino))))
    # 同一实际文件身份只保留一个表示；不同大小写但不同 inode 仍保持多候选。
    by_identity: dict[tuple[int, int], str] = {}
    for relative, identity in trusted:
        by_identity.setdefault(identity, relative)
    return sorted(by_identity.values()), rejected[:20]


def document_route_fingerprint(contract: dict[str, Any]) -> str:
    routes = contract.get("routes", {})
    return sha256_text(canonical_json({
        "schema_version": DOCUMENT_ROUTE_SCHEMA,
        "required_kinds": sorted(contract.get("required_kinds", [])),
        "routes": [
            {"kind": kind, **routes[kind]}
            for kind in sorted(routes)
        ],
    }))


def resolve_document_routes(target: Path, *, required_kinds: Sequence[str]) -> dict[str, Any]:
    required = sorted(set(required_kinds))
    if any(kind not in DOCUMENT_ROUTE_KINDS for kind in required):
        raise HarnessError("治理交付物包含未知文档类别", code="invalid_background_candidate")
    explicit, config_errors = document_route_config(target)
    if config_errors:
        return {
            "schema_version": DOCUMENT_ROUTE_SCHEMA,
            "status": "invalid_config",
            "required_kinds": required,
            "routes": {},
            "reason_code": "invalid_document_route_config",
            "errors": config_errors[:20],
        }
    routes: dict[str, dict[str, str]] = {}
    errors: list[dict[str, Any]] = []
    for kind in required:
        if kind in explicit:
            routes[kind] = {
                "path": explicit[kind],
                "source": "explicit",
                "type": "file" if kind in DOCUMENT_ROUTE_FILE_KINDS else "directory",
            }
            continue
        candidates, rejected = document_route_candidates(target, kind)
        if rejected:
            errors.append({"kind": kind, "reason_code": "document_route_unsafe", "rejected": rejected})
        if len(candidates) == 1 and not rejected:
            routes[kind] = {
                "path": candidates[0],
                "source": "auto",
                "type": "file" if kind in DOCUMENT_ROUTE_FILE_KINDS else "directory",
            }
        else:
            errors.append({
                "kind": kind,
                "reason_code": "document_route_ambiguous" if len(candidates) > 1 else "document_route_missing",
                "candidates": candidates[:20],
            })
    if errors:
        primary = next((item["reason_code"] for item in errors if item["reason_code"] != "document_route_unsafe"), "document_route_missing")
        return {
            "schema_version": DOCUMENT_ROUTE_SCHEMA,
            "status": "unresolved",
            "required_kinds": required,
            "routes": {},
            "reason_code": primary,
            "errors": errors[:20],
        }
    contract = {
        "schema_version": DOCUMENT_ROUTE_SCHEMA,
        "status": "resolved",
        "required_kinds": required,
        "routes": routes,
    }
    contract["fingerprint"] = document_route_fingerprint(contract)
    return contract


def governance_required_kinds(deliverables: Sequence[str]) -> list[str]:
    kinds: list[str] = []
    for deliverable in deliverables:
        kinds.extend(GOVERNANCE_DELIVERABLE_ROUTES.get(deliverable, ()))
    return sorted(set(kinds))


def governance_route_scopes(contract: dict[str, Any]) -> tuple[list[str], list[str]]:
    writes: list[str] = []
    for route in contract.get("routes", {}).values():
        path = str(route["path"])
        writes.append(path if route["type"] == "file" else f"{path}/**")
    writes = sorted(set(writes))
    reads = sorted(set(str(route["path"]) + ("/**" if route["type"] == "directory" else "") for route in contract.get("routes", {}).values()))
    return reads, writes


def knowledge_runtime_root(target: Path) -> Path:
    return runtime_root(target).parent / "knowledge"


def knowledge_jobs_root(target: Path) -> Path:
    """v1.3 兼容入口；v1.4 的真源位于 background/jobs。"""
    return runtime_root(target).parent / "knowledge-jobs"


def background_runtime_root(target: Path) -> Path:
    return runtime_root(target).parent / "background"


def background_jobs_root(target: Path) -> Path:
    return background_runtime_root(target) / "jobs"


def background_estimates_root(target: Path) -> Path:
    return background_runtime_root(target) / "estimates"


def knowledge_map_path(target: Path) -> Path:
    return target / KNOWLEDGE_MAP_RELATIVE


def empty_knowledge_map() -> dict[str, Any]:
    return {
        "schema_version": KNOWLEDGE_MAP_SCHEMA,
        "knowledge_level": "L2",
        "reviewed_revision": None,
        "features": [],
    }


def safe_project_relative(target: Path, raw: str, *, field: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise HarnessError(f"{field} 必须是非空项目内相对路径", code="invalid_knowledge_map")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise HarnessError(f"{field} 不能越出项目", code="invalid_knowledge_map")
    resolved = (target / relative).resolve()
    try:
        resolved.relative_to(target.resolve())
    except ValueError as exc:
        raise HarnessError(f"{field} 不能越出项目", code="invalid_knowledge_map") from exc
    if resolved.is_symlink():
        raise HarnessError(f"{field} 不允许符号链接", code="invalid_knowledge_map")
    return relative.as_posix()


def normalize_knowledge_map(target: Path, value: Any, *, require_files: bool = True) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != KNOWLEDGE_MAP_SCHEMA:
        raise HarnessError("功能知识地图 schema 无效", code="invalid_knowledge_map")
    if value.get("knowledge_level") != "L2":
        raise HarnessError("功能知识地图必须声明 L2 目标", code="invalid_knowledge_map")
    raw_features = value.get("features")
    if not isinstance(raw_features, list) or len(raw_features) > 500:
        raise HarnessError("features 必须是有界数组", code="invalid_knowledge_map")
    features: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in raw_features:
        if not isinstance(raw, dict):
            raise HarnessError("功能记录必须是对象", code="invalid_knowledge_map")
        feature_id = raw.get("feature_id")
        name = raw.get("name")
        if not isinstance(feature_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", feature_id):
            raise HarnessError("功能 ID 必须是稳定 kebab-case", code="invalid_knowledge_map")
        if feature_id in seen_ids:
            raise HarnessError(f"功能 ID 重复：{feature_id}", code="invalid_knowledge_map")
        seen_ids.add(feature_id)
        if not isinstance(name, str) or not name.strip():
            raise HarnessError(f"功能 {feature_id} 缺少名称", code="invalid_knowledge_map")
        documents = raw.get("documents")
        if not isinstance(documents, dict) or set(documents) != set(KNOWLEDGE_CATEGORIES):
            raise HarnessError(f"功能 {feature_id} 必须具备产品、研发、测试、设计四类文档", code="invalid_knowledge_map")
        normalized_docs = {
            category: safe_project_relative(target, str(documents[category]), field=f"{feature_id}.{category}")
            for category in KNOWLEDGE_CATEGORIES
        }
        expected_prefix = f"docs/features/{feature_id}/"
        if any(not path.startswith(expected_prefix) for path in normalized_docs.values()):
            raise HarnessError(f"功能 {feature_id} 的四类文档必须位于独立功能目录", code="invalid_knowledge_map")
        if require_files:
            missing = [path for path in normalized_docs.values() if not (target / path).is_file()]
            if missing:
                raise HarnessError("功能知识文档缺失：" + ", ".join(missing), code="missing_feature_knowledge")
        aliases = normalize_string_list(raw.get("aliases"), f"{feature_id}.aliases")
        scopes = [safe_project_relative(target, item, field=f"{feature_id}.scope_patterns") for item in normalize_string_list(raw.get("scope_patterns"), f"{feature_id}.scope_patterns")]
        shared = [safe_project_relative(target, item, field=f"{feature_id}.shared_refs") for item in normalize_string_list(raw.get("shared_refs"), f"{feature_id}.shared_refs")]
        dependencies = normalize_string_list(raw.get("dependencies"), f"{feature_id}.dependencies")
        functional_confirmation = raw.get("functional_confirmation")
        if functional_confirmation is not None and not isinstance(functional_confirmation, dict):
            raise HarnessError(f"功能 {feature_id} 的 functional_confirmation 必须是对象", code="invalid_knowledge_map")
        features.append(
            {
                "feature_id": feature_id,
                "name": name.strip(),
                "aliases": aliases,
                "feature_type": str(raw.get("feature_type") or "user_capability"),
                "status": str(raw.get("status") or "implemented"),
                "scope_patterns": scopes,
                "documents": normalized_docs,
                "shared_refs": shared,
                "dependencies": dependencies,
                "known_gaps": normalize_string_list(raw.get("known_gaps"), f"{feature_id}.known_gaps"),
                "functional_confirmation": (
                    {key: value for key, value in functional_confirmation.items() if value is not None}
                    if isinstance(functional_confirmation, dict)
                    else {}
                ),
            }
        )
    unknown_dependencies = sorted({item for feature in features for item in feature["dependencies"] if item not in seen_ids})
    if unknown_dependencies:
        raise HarnessError("功能依赖不存在：" + ", ".join(unknown_dependencies), code="invalid_knowledge_map")
    return {
        "schema_version": KNOWLEDGE_MAP_SCHEMA,
        "knowledge_level": "L2",
        "reviewed_revision": value.get("reviewed_revision"),
        "features": features,
    }


def read_knowledge_map(target: Path, *, require_files: bool = True) -> dict[str, Any] | None:
    path = knowledge_map_path(target)
    if not path.is_file():
        return None
    return normalize_knowledge_map(target, read_json(path), require_files=require_files)


def repowiki_card_limit() -> int:
    """知识卡枚举上限：默认 1000，可用 DOCS_HARNESS_REPOWIKI_CARD_LIMIT 覆盖为正整数。"""
    raw = os.environ.get("DOCS_HARNESS_REPOWIKI_CARD_LIMIT", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return REPOWIKI_CARD_LIMIT


def repowiki_knowledge_root(target: Path) -> Path | None:
    """返回 .qoder/repowiki 的知识卡根目录（knowledge/<locale>/），不存在时返回 None。"""
    base = target / REPOWIKI_RELATIVE / "knowledge"
    if not base.is_dir():
        return None
    locales = sorted(path for path in base.iterdir() if path.is_dir())
    ordered = [path for path in locales if path.name == "zh"] + [path for path in locales if path.name != "zh"]
    for candidate in ordered:
        if any(candidate.rglob("*.md")):
            return candidate
    return None


def parse_repowiki_frontmatter(path: Path) -> dict[str, Any]:
    """定向解析知识卡 frontmatter 的标量与列表字段（纯标准库，仅支持机器生成的简单形态）。"""
    try:
        with path.open("r", encoding="utf-8") as handle:
            text = handle.read(4096)
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    result: dict[str, Any] = {}
    current_key: str | None = None
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            result[current_key].append(stripped[2:].strip().strip("'\""))
        elif not line[0].isspace() and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip("'\"")
            if value:
                result[key] = value
                current_key = None
            else:
                result[key] = []
                current_key = key
    return result


def repowiki_cards(target: Path) -> tuple[list[dict[str, Any]], bool, int]:
    """枚举 repowiki 知识卡：返回（有界卡片列表, 是否截断, 磁盘卡片总数）。"""
    root = repowiki_knowledge_root(target)
    if root is None:
        return [], False, 0
    cards: list[dict[str, Any]] = []
    paths = sorted(root.rglob("*.md"))
    total = len(paths)
    limit = repowiki_card_limit()
    truncated = total > limit
    for path in paths[:limit]:
        meta = parse_repowiki_frontmatter(path)
        scope = meta.get("scope")
        cards.append(
            {
                "ref": path.relative_to(target).as_posix(),
                "name": str(meta.get("name") or path.stem),
                "scope": [str(item) for item in scope] if isinstance(scope, list) else [],
                "category": str(meta.get("category") or ""),
            }
        )
    return cards, truncated, total


def meaningful_knowledge_doc(target: Path, relative: str) -> bool:
    path = target / relative
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        return False
    text = path.read_text(encoding="utf-8")
    body = "\n".join(line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
    placeholders = ("待项目遍历后补全", "待确认", "TODO", "TBD")
    for item in placeholders:
        body = body.replace(item, "")
    return len(body.strip()) >= 20


def active_knowledge_bootstrap(target: Path) -> dict[str, Any] | None:
    """返回最后一个非终态 bootstrap；所有调用点共享同一判定。"""
    bootstraps = [
        job
        for job in list_background_jobs(target)
        if job.get("task_kind") == "knowledge_bootstrap"
        and job.get("status") not in BACKGROUND_TERMINAL_STATES
    ]
    return bootstraps[-1] if bootstraps else None


def evaluate_candidate_knowledge(target: Path, normalized_map: dict[str, Any]) -> dict[str, Any]:
    """不写知识地图，依据候选地图和当前功能文档复算知识状态。"""
    gaps: list[str] = []
    for feature in normalized_map.get("features", []):
        for category, relative in feature.get("documents", {}).items():
            if not meaningful_knowledge_doc(target, relative):
                gaps.append(f"{feature.get('feature_id')}.{category}")
    features = len(normalized_map.get("features", []))
    if not features:
        gaps.append("尚未建立功能清单")
    return {
        "status": "ready" if features and not gaps else "partial",
        "features": features,
        "gaps": gaps,
    }


def knowledge_ready_for_incremental(target: Path) -> bool:
    return knowledge_status(target).get("status") == "ready"


def knowledge_dependency_outcome(bootstrap_job: dict[str, Any], target: Path) -> str:
    status = str(bootstrap_job.get("status"))
    if status in {"updated", "no_change"}:
        return "success" if knowledge_ready_for_incremental(target) else "blocked"
    if status in {"failed", "cancelled", "completed_with_finding", "needs_user_input", "needs_rebase"}:
        return "blocked"
    if status in BACKGROUND_KNOWN_STATES:
        return "pending"
    return "unknown"


def knowledge_status(target: Path) -> dict[str, Any]:
    if repowiki_knowledge_root(target) is not None:
        cards, truncated, total_cards = repowiki_cards(target)
        return {
            "status": "ready",
            "source": "repowiki",
            "features": len(cards),
            "total_cards": total_cards,
            "truncated": truncated,
            "gaps": [],
            "knowledge_root": REPOWIKI_RELATIVE,
        }
    docs = target / KNOWLEDGE_ROOT_RELATIVE
    if not docs.is_dir():
        return {"status": "absent", "features": 0, "gaps": ["docs/ 不存在"]}
    try:
        knowledge = read_knowledge_map(target)
    except HarnessError as exc:
        return {"status": "quarantined", "features": 0, "gaps": [str(exc)], "reason_code": exc.code}
    if knowledge is None:
        return {"status": "needs_audit", "features": 0, "gaps": ["缺少 docs/knowledge-map.json"]}
    if not knowledge["features"]:
        bootstraps = [job for job in list_background_jobs(target) if job.get("task_kind") == "knowledge_bootstrap"]
        active = active_knowledge_bootstrap(target)
        failed = next((job for job in reversed(bootstraps) if job.get("status") == "failed"), None)
        return {
            "status": "building" if active else ("failed" if failed else "needs_bootstrap"),
            "features": 0,
            "gaps": ["尚未建立功能清单"],
            "active_job_id": active.get("job_id") if active else (failed.get("job_id") if failed else None),
        }
    gaps: list[str] = []
    for feature in knowledge["features"]:
        for category, relative in feature["documents"].items():
            if not meaningful_knowledge_doc(target, relative):
                gaps.append(f"{feature['feature_id']}.{category}")
    return {
        "status": "ready" if not gaps else "partial",
        "features": len(knowledge["features"]),
        "gaps": gaps,
        "map_fingerprint": file_fingerprint(knowledge_map_path(target)),
        "reviewed_revision": knowledge.get("reviewed_revision"),
    }


def knowledge_handoff(target: Path, operation: str, docs_preexisted: bool) -> dict[str, Any]:
    """统一生成 init/upgrade 与后台路由使用的知识交接合同。"""
    status = knowledge_status(target)
    if status.get("source") == "repowiki":
        return {
            "mode": "external_consume_only",
            "operation": operation,
            "knowledge_status": status,
            "requires_user_consent_before_update": False,
            "job_id": None,
            "dispatch_required": False,
            "dispatch_status": "not_required",
            "knowledge_next_action": "none",
            "knowledge_next_command_argv": [],
            "assessment_artifact_ref": str(knowledge_runtime_root(target) / "assessment.json"),
        }
    active = active_knowledge_bootstrap(target)
    current = str(status.get("status"))
    configured = project_config(target) or {}
    knowledge_config = configured.get("knowledge", {}) if isinstance(configured.get("knowledge"), dict) else {}
    preexisting_at_install = bool(knowledge_config.get("docs_preexisting_at_install", docs_preexisted))
    if current == "ready":
        mode = "already_ready"
    elif current == "building" or active:
        mode = "bootstrap_in_progress"
    elif current == "absent" and not docs_preexisted:
        mode = "bootstrap_new"
    elif current == "needs_bootstrap" and not preexisting_at_install:
        mode = "bootstrap_new"
    else:
        mode = "audit_existing"
    requires_consent = mode == "audit_existing"
    next_argv = [] if mode in {"already_ready", "bootstrap_in_progress", "bootstrap_new"} else harness_command_argv("knowledge", target, "audit")
    return {
        "mode": mode,
        "operation": operation,
        "knowledge_status": status,
        "requires_user_consent_before_update": requires_consent,
        "job_id": active.get("job_id") if active else None,
        "dispatch_required": mode == "bootstrap_new",
        "dispatch_status": (
            "not_required" if mode == "already_ready"
            else "in_progress" if mode == "bootstrap_in_progress"
            else "awaiting_user_consent" if mode == "audit_existing"
            else "dispatch_required"
        ),
        "knowledge_next_action": (
            "none" if mode == "already_ready"
            else "continue_bootstrap" if mode == "bootstrap_in_progress"
            else "bootstrap_knowledge_base" if mode == "bootstrap_new"
            else "audit_existing_docs"
        ),
        "knowledge_next_command_argv": next_argv,
        "assessment_artifact_ref": str(knowledge_runtime_root(target) / "assessment.json"),
    }


def knowledge_delivery_paths(target: Path) -> list[str]:
    paths = list(KNOWLEDGE_SCAFFOLD)
    if knowledge_map_path(target).is_file():
        paths.append(KNOWLEDGE_MAP_RELATIVE)
    with contextlib.suppress(HarnessError):
        knowledge = read_knowledge_map(target, require_files=False)
        if knowledge:
            for feature in knowledge["features"]:
                paths.extend(feature["documents"].values())
                paths.extend(feature["shared_refs"])
    return sorted(set(path for path in paths if (target / path).is_file()))


def knowledge_categories_for_gates(gates: Sequence[str]) -> list[str]:
    categories: list[str] = []
    for gate in gates:
        categories.extend(GATE_KNOWLEDGE_CATEGORIES.get(gate, ()))
    return list(dict.fromkeys(categories))


def pending_knowledge_jobs(target: Path, feature_ids: Sequence[str]) -> list[dict[str, Any]]:
    selected = set(feature_ids)
    pending: list[dict[str, Any]] = []
    paths: list[Path] = []
    for root in (background_jobs_root(target), knowledge_jobs_root(target)):
        if root.is_dir():
            paths.extend(root.glob("*/job.json"))
    seen: set[str] = set()
    for path in sorted(paths):
        try:
            value = read_json(path)
        except HarnessError:
            continue
        job_id = value.get("job_id") if isinstance(value, dict) else None
        if not isinstance(job_id, str) or job_id in seen or value.get("status") in BACKGROUND_TERMINAL_STATES:
            continue
        seen.add(job_id)
        job_features = set(item for item in value.get("feature_ids", []) if isinstance(item, str))
        if selected and not selected.intersection(job_features):
            continue
        pending.append(
            {
                "job_id": value.get("job_id"),
                "parent_task_id": value.get("parent_task_id"),
                "status": value.get("status"),
                "feature_ids": sorted(job_features),
                "candidate_categories": list(value.get("candidate_categories", [])),
                "changed_paths": list(value.get("changed_paths", []))[:100],
            }
        )
    return pending


def resolve_repowiki_knowledge(
    target: Path,
    task: str,
    scope: Sequence[str],
    categories: list[str],
    requested: Sequence[str],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """repowiki 只消费知识源：按任务文本与 scope 命中知识卡，绝不产生写动作。"""
    cards, truncated, total_cards = repowiki_cards(target)
    selected: list[dict[str, Any]] = []
    if requested:
        for feature_id in requested:
            match = next(
                (card for card in cards if card["name"] == feature_id or feature_id.casefold() in card["name"].casefold()),
                None,
            )
            if match is None:
                raise HarnessError(f"未知功能 ID：{feature_id}", code="unknown_feature")
            selected.append(match)
    else:
        lowered = task.casefold()
        for card in cards:
            text_match = bool(card["name"]) and card["name"].casefold() in lowered
            scope_match = any(
                fnmatch.fnmatch(path, pattern) or scope_covers(path, [pattern])
                for path in scope
                for pattern in card["scope"]
            )
            if text_match or scope_match:
                selected.append(card)
    selected = list({card["ref"]: card for card in selected}.values())
    if not selected and len(cards) == 1:
        selected = list(cards)
    meaningful = [card for card in selected if meaningful_knowledge_doc(target, card["ref"])]
    if not meaningful:
        return {
            "status": "unresolved",
            "source": "repowiki",
            "context_quality": "degraded",
            "coverage": "partial",
            "selected_features": [],
            "loaded_categories": [],
            "missing_categories": categories,
            "category_refs": {},
            "shared_refs": [],
            "fallback_required": True,
            "truncated": truncated,
            "total_cards": total_cards,
        }, [], []
    refs = [card["ref"] for card in meaningful]
    return {
        "status": "ready",
        "source": "repowiki",
        "context_quality": "complete",
        "coverage": "complete",
        "selected_features": [card["name"] for card in meaningful],
        "categories": categories,
        "loaded_categories": list(categories),
        "missing_categories": [],
        "category_refs": {category: list(refs) for category in categories},
        "shared_refs": [],
        "pending_update_jobs": [],
        "fallback_required": False,
        "fallback_fact_refs": [],
        "truncated": truncated,
        "total_cards": total_cards,
    }, refs, []


def resolve_feature_knowledge(
    target: Path,
    task: str,
    scope: Sequence[str],
    gates: Sequence[str],
    requested: Sequence[str],
) -> tuple[dict[str, Any], list[str], list[str]]:
    categories = knowledge_categories_for_gates(gates)
    if not categories:
        return {"status": "not_required", "selected_features": [], "category_refs": {}, "shared_refs": []}, [], []
    if repowiki_knowledge_root(target) is not None:
        return resolve_repowiki_knowledge(target, task, scope, categories, requested)
    status = knowledge_status(target)
    if status["status"] not in {"ready", "partial"}:
        if any(term in task.casefold() for term in ("新增功能", "创建功能", "new feature")):
            return {
                "status": "new_feature",
                "context_quality": "degraded",
                "coverage": "partial",
                "selected_features": [],
                "loaded_categories": [],
                "missing_categories": categories,
                "category_refs": {},
                "shared_refs": [],
                "fallback_required": True,
            }, [], []
        jobs = pending_knowledge_jobs(target, [])
        return {
            "status": "quarantined" if status["status"] in {"invalid", "quarantined"} else status["status"],
            "context_quality": "degraded",
            "coverage": "absent" if status["status"] == "absent" else "partial",
            "selected_features": [],
            "loaded_categories": [],
            "missing_categories": categories,
            "active_job_id": jobs[0]["job_id"] if jobs else None,
            "category_refs": {},
            "shared_refs": [],
            "fallback_required": True,
            "fallback_fact_refs": [],
        }, [], []
    knowledge = read_knowledge_map(target)
    assert knowledge is not None
    by_id = {item["feature_id"]: item for item in knowledge["features"]}
    selected_ids: list[str] = []
    for feature_id in requested:
        if feature_id not in by_id:
            raise HarnessError(f"未知功能 ID：{feature_id}", code="unknown_feature")
        selected_ids.append(feature_id)
    lowered = task.casefold()
    if not selected_ids:
        for feature in knowledge["features"]:
            terms = [feature["feature_id"], feature["name"], *feature["aliases"]]
            text_match = any(term.casefold() in lowered for term in terms if term)
            scope_match = any(fnmatch.fnmatch(path, pattern) or scope_covers(path, [pattern]) for path in scope for pattern in feature["scope_patterns"])
            if text_match or scope_match:
                selected_ids.append(feature["feature_id"])
    selected_ids = list(dict.fromkeys(selected_ids))
    if not selected_ids and len(by_id) == 1:
        selected_ids = list(by_id)
    if not selected_ids:
        return {
            "status": "unresolved",
            "context_quality": "degraded",
            "coverage": "partial",
            "selected_features": [],
            "loaded_categories": [],
            "missing_categories": categories,
            "category_refs": {},
            "shared_refs": [],
            "fallback_required": True,
        }, [], []
    refs: list[str] = []
    category_refs: dict[str, list[str]] = {category: [] for category in categories}
    shared_refs: list[str] = []
    gaps: list[str] = []
    for feature_id in selected_ids:
        feature = by_id[feature_id]
        for category in categories:
            relative = feature["documents"][category]
            if meaningful_knowledge_doc(target, relative):
                refs.append(relative)
                category_refs[category].append(relative)
            else:
                gaps.append(f"{feature_id}.{category}")
        for relative in feature["shared_refs"]:
            if meaningful_knowledge_doc(target, relative):
                refs.append(relative)
                shared_refs.append(relative)
    return {
        "status": "partial" if gaps else "ready",
        "context_quality": "degraded" if gaps else "complete",
        "coverage": "partial" if gaps else "complete",
        "knowledge_map_fingerprint": file_fingerprint(knowledge_map_path(target)),
        "selected_features": selected_ids,
        "categories": categories,
        "loaded_categories": [category for category in categories if category_refs[category]],
        "missing_categories": sorted({item.split(".", 1)[1] for item in gaps}),
        "category_refs": category_refs,
        "shared_refs": list(dict.fromkeys(shared_refs)),
        "reviewed_revision": knowledge.get("reviewed_revision"),
        "pending_update_jobs": pending_knowledge_jobs(target, selected_ids),
        "fallback_required": bool(gaps),
        "fallback_fact_refs": [],
    }, list(dict.fromkeys(refs)), []


def resolve_functional_confirmation(
    target: Path,
    knowledge_context: dict[str, Any],
    write_scope: Sequence[str],
) -> list[dict[str, Any]]:
    """检查 matched 功能是否要求 functional_confirmation，返回功能级确认配置。"""
    selected = knowledge_context.get("selected_features", [])
    if not selected:
        return []

    skip_suffixes = (".md", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", "_test.go", ".test.js", ".test.jsx")
    skip_prefixes = ("docs/",)
    normalized_scope = [
        Path(path).as_posix().strip().removeprefix("./").removesuffix("/")
        for path in (write_scope or [])
        if isinstance(path, str)
    ]
    if write_scope and normalized_scope:
        if all(
            any(path.endswith(suffix) for suffix in skip_suffixes)
            or any(path.lower().startswith(prefix) for prefix in skip_prefixes)
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
    for feature_id in selected:
        feature = by_id.get(feature_id)
        if not feature:
            continue
        fc = feature.get("functional_confirmation")
        if not isinstance(fc, dict):
            continue
        result.append({
            "feature_id": feature_id,
            "name": feature.get("name", feature_id),
            "tier": fc.get("tier", ""),
            "mode": fc.get("mode", ""),
            "assertions": fc.get("assertions", []),
            "testing_ref": feature.get("documents", {}).get("testing", ""),
            "required": bool(fc.get("required", False)),
            "skip_reason": fc.get("skip_reason", ""),
        })
    return result


def source_root_for(target: Path) -> Path:
    return SCRIPT_ROOT


def rules_root_for(target: Path) -> Path:
    config = project_config(target)
    if config:
        raw = config.get("rules_root")
        if not isinstance(raw, str) or not raw.strip():
            raise HarnessError("项目配置缺少 rules_root", code="invalid_config")
        relative = Path(raw)
        if relative.is_absolute():
            raise HarnessError("rules_root 必须是项目内相对路径", code="invalid_config")
        resolved = (target / relative).resolve()
        try:
            resolved.relative_to(target)
        except ValueError as exc:
            raise HarnessError("rules_root 不能越出项目目录", code="invalid_config") from exc
        return resolved
    return source_root_for(target) / "harness-home" / "rules"


def rule_file_fingerprints(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {path.name: file_fingerprint(path) for path in sorted(root.glob("*.md"))}


def portable_install_paths(rule_names: Sequence[str]) -> list[str]:
    paths = ["scripts/harness.py", "AGENTS.md", "CLAUDE.md", ".docs-harness/config.json"]
    paths.extend(f"{PROJECT_RULES_RELATIVE}/{Path(name).name}" for name in sorted(set(rule_names)))
    return paths


def installed_rule_names(config: dict[str, Any] | None, rules_root: Path) -> list[str]:
    names = {path.name for path in rules_root.glob("*.md")} if rules_root.is_dir() else set()
    configured = config.get("installed_rule_fingerprints", {}) if config else {}
    if isinstance(configured, dict):
        names.update(str(name) for name in configured)
    return sorted(names)


def project_portable_install_paths(target: Path) -> list[str]:
    config = project_config(target)
    rules_root = target / PROJECT_RULES_RELATIVE
    raw = config.get("rules_root") if config else None
    if isinstance(raw, str) and raw.strip() and not Path(raw).is_absolute():
        candidate = (target / raw).resolve()
        with contextlib.suppress(ValueError):
            candidate.relative_to(target.resolve())
            rules_root = candidate
    return sorted(set(portable_install_paths(installed_rule_names(config, rules_root)) + knowledge_delivery_paths(target)))


def git_head_blob(root: Path, relative: str) -> bytes | None:
    shown = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative}"],
        capture_output=True,
        check=False,
    )
    return shown.stdout if shown.returncode == 0 else None


def install_delivery_status(target: Path, relative_paths: Sequence[str]) -> dict[str, Any]:
    root = git_root(target)
    if root is None:
        return {
            "delivery_status": "not_applicable",
            "clone_ready": False,
            "required_commit_paths": [],
            "ignored_paths": [],
        }
    ignored = git_ignored_install_paths(target, relative_paths)
    pending: list[str] = []
    for relative in relative_paths:
        path = target / relative
        try:
            git_relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            pending.append(relative)
            continue
        blob = git_head_blob(root, git_relative)
        if blob is None:
            pending.append(relative)
            continue
        if relative == "AGENTS.md":
            text = blob.decode("utf-8", errors="replace")
            expected = replace_managed_block(
                text, MANAGED_BEGIN, MANAGED_END, managed_agent_block()
            )
            if text != expected:
                pending.append(relative)
            continue
        if relative == "CLAUDE.md":
            text = blob.decode("utf-8", errors="replace")
            expected = replace_managed_block(
                text, CLAUDE_BEGIN, CLAUDE_END, claude_block()
            )
            if text != expected:
                pending.append(relative)
            continue
        if not path.is_file():
            pending.append(relative)
            continue
        # 用 git 自身判定工作区与 HEAD 是否一致，尊重 autocrlf/.gitattributes 的行尾转换；
        # 字节级指纹对比会把仅行尾差异误判为未交付。
        diff = git_command(root, "diff", "--quiet", "HEAD", "--", git_relative)
        if diff.returncode != 0:
            pending.append(relative)
    if ignored:
        status = "blocked"
    elif pending:
        status = "pending_commit"
    else:
        status = "in_head"
    return {
        "delivery_status": status,
        "clone_ready": status == "in_head",
        "required_commit_paths": sorted(set(pending)),
        "ignored_paths": ignored,
    }


def project_delivery_summary(target: Path, controller_paths: Sequence[str]) -> dict[str, Any]:
    controller = install_delivery_status(target, controller_paths)
    current_knowledge = knowledge_status(target)
    if current_knowledge.get("source") == "repowiki":
        # 外部只消费知识源不参与交付判定：.qoder 常被 gitignore，纳入会误报 blocked
        knowledge_delivery = {
            "delivery_status": "external_repowiki",
            "clone_ready": True,
            "required_commit_paths": [],
            "ignored_paths": [],
        }
    else:
        knowledge_paths = knowledge_delivery_paths(target)
        knowledge_delivery = install_delivery_status(target, knowledge_paths) if knowledge_paths else {
            "delivery_status": "not_ready",
            "clone_ready": False,
            "required_commit_paths": [],
            "ignored_paths": [],
        }
    clone_ready = bool(
        controller["clone_ready"]
        and current_knowledge["status"] == "ready"
        and knowledge_delivery["clone_ready"]
    )
    required = sorted(set(controller["required_commit_paths"] + knowledge_delivery["required_commit_paths"]))
    ignored = sorted(set(controller["ignored_paths"] + knowledge_delivery["ignored_paths"]))
    if ignored:
        overall = "blocked"
    elif controller["delivery_status"] == "pending_commit" or knowledge_delivery["delivery_status"] == "pending_commit":
        overall = "pending_commit"
    elif current_knowledge["status"] != "ready":
        overall = "knowledge_pending"
    elif clone_ready:
        overall = "in_head"
    else:
        overall = "not_applicable"
    questioned_jobs = [
        str(job.get("job_id"))
        for job in list_background_jobs(target)
        if job.get("status") == "completed_with_finding" or job.get("task_kind") == "critical_followup"
    ]
    return {
        "delivery_status": overall,
        "clone_ready": clone_ready,
        "controller_clone_ready": controller["clone_ready"],
        "controller_delivery_status": controller["delivery_status"],
        "knowledge_delivery_status": knowledge_delivery["delivery_status"],
        "knowledge_status": current_knowledge["status"],
        "delivery_confidence": "questioned" if questioned_jobs else "normal",
        "critical_followup_job_ids": questioned_jobs,
        "required_commit_paths": required,
        "ignored_paths": ignored,
    }


def load_active_rules(
    target: Path,
    gates: Sequence[str],
    task: str,
    *,
    match_all: bool = False,
    mutation_profile: str = "workspace_write",
) -> tuple[list[dict[str, Any]], list[str]]:
    root = rules_root_for(target)
    if not root.is_dir():
        return [], [f"Harness Home 规则目录不存在：{root}"]
    matched: list[dict[str, Any]] = []
    errors: list[str] = []
    lowered_task = task.casefold()
    seen_rule_ids: set[str] = set()
    valid_active_count = 0
    for path in sorted(root.glob("*.md")):
        metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if metadata.get("status") != "active":
            continue
        rule_id = metadata.get("rule_id", "")
        declared = metadata.get("content_fingerprint", "")
        actual = sha256_text(body)
        if not rule_id or not declared:
            errors.append(f"{path.name}: active 规则缺少 rule_id 或 content_fingerprint")
            continue
        if declared != actual:
            errors.append(f"{path.name}: content_fingerprint 与正文不匹配")
            continue
        if rule_id in seen_rule_ids:
            errors.append(f"{path.name}: rule_id 重复：{rule_id}")
            continue
        seen_rule_ids.add(rule_id)
        gate_terms = {item.strip() for item in metadata.get("gates", "").split(",") if item.strip()}
        keywords = {item.strip().casefold() for item in metadata.get("keywords", "").split(",") if item.strip()}
        plan_fields = [item.strip() for item in metadata.get("plan_fields", "").split(",") if item.strip()]
        evidence_types = [item.strip() for item in metadata.get("evidence_types", "").split(",") if item.strip()]
        failure_mode = metadata.get("failure_mode", "").strip()
        required_headings = ("## 适用条件", "## 必需的方案字段", "## 验收条件", "## 失败处理方式")
        if not gate_terms and not keywords:
            errors.append(f"{path.name}: active 规则缺少 gates 或 keywords 适用条件")
            continue
        if not plan_fields or not evidence_types or not failure_mode:
            errors.append(f"{path.name}: active 规则缺少 plan_fields、evidence_types 或 failure_mode")
            continue
        if any(heading not in body for heading in required_headings):
            errors.append(f"{path.name}: active 规则正文结构不完整")
            continue
        valid_active_count += 1
        keyword_match_allowed = not (
            mutation_profile in {"read_only", "git_metadata_write"}
            and gate_terms.intersection({"code-edit", "document-edit"})
        )
        if match_all or (gate_terms and gate_terms.intersection(gates)) or (keyword_match_allowed and keywords and any(word in lowered_task for word in keywords)):
            matched.append(
                {
                    "rule_id": rule_id,
                    "content_fingerprint": actual,
                    "path": str(path),
                    "plan_fields": plan_fields,
                    "evidence_types": evidence_types,
                    "failure_mode": failure_mode,
                }
            )
    if valid_active_count == 0 and not errors:
        errors.append("Harness Home 没有可执行的 active 规则")
    return matched, errors


def phrase_matches(text: str, term: str) -> bool:
    lowered = text.casefold()
    needle = term.casefold()
    if re.search(r"[a-z0-9]", needle):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered))
    return needle in lowered


def floor_term_matches(text: str, term: str) -> bool:
    """带否定守卫的底线词匹配：命中词前紧邻否定标记（「不要」「无需」等）时视为未命中。"""
    lowered = text.casefold()
    needle = term.casefold()
    if re.search(r"[a-z0-9]", needle):
        pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
    else:
        pattern = re.escape(needle)
    for match in re.finditer(pattern, lowered):
        prefix = lowered[max(0, match.start() - 8):match.start()]
        if not any(marker in prefix for marker in NEGATION_MARKERS):
            return True
    return False


def infer_floor_gates(task: str) -> set[str]:
    """安全底线 gate 的确定性触发：只使用 FLOOR_TERMS 精确词表，与 GATE_DEFS 宽泛词表解耦。"""
    return {gate for gate, terms in FLOOR_TERMS.items() if any(floor_term_matches(task, term) for term in terms)}


def classify_task_intents(
    task: str,
    facts: dict[str, Any],
    *,
    has_declared_scope: bool,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    lowered = task.casefold()
    detected: list[tuple[int, str]] = []
    deferred: list[tuple[int, str]] = []
    reason_codes: list[str] = []
    future_markers = tuple(marker.casefold() for marker in ("后续", "以后", "后面", "另行", "单独", "另开任务", "下一任务"))
    completed_markers = tuple(marker.casefold() for marker in ("已经", "此前", "上次", "曾经", "已完成"))
    for intent, patterns in INTENT_PATTERNS.items():
        positions: list[int] = []
        for pattern in patterns:
            needle = pattern.casefold()
            start = 0
            while True:
                position = lowered.find(needle, start)
                if position < 0:
                    break
                if re.search(r"[a-z0-9]", needle):
                    before = lowered[position - 1] if position else ""
                    after_index = position + len(needle)
                    after = lowered[after_index] if after_index < len(lowered) else ""
                    if (before and before.isalnum()) or (after and after.isalnum()):
                        start = position + len(needle)
                        continue
                prefix = lowered[max(0, position - 8) : position]
                negated = re.search(r"(?:不|不要|禁止|不会|无需|不得|不进行|不执行|不允许|do not|don't)\s*$", prefix)
                clause_start = max(lowered.rfind(mark, 0, position) for mark in ("。", "！", "？", ";", "；", "\n")) + 1
                clause_prefix = lowered[clause_start:position]
                is_deferred = intent in {"modify", "external_write", "git_sync"} and any(marker in clause_prefix for marker in future_markers)
                is_completed = intent in {"modify", "external_write", "git_sync"} and any(marker in clause_prefix for marker in completed_markers)
                if is_deferred:
                    deferred.append((position, intent))
                    reason_codes.append("future_clause_deferred")
                elif is_completed:
                    reason_codes.append("completed_action_is_context")
                elif not negated:
                    positions.append(position)
                start = position + len(needle)
        if positions:
            detected.append((min(positions), intent))
    read_only_question = re.search(r"(?:是否|能否|可否|要不要|有没有必要).{0,12}(?:删除|修改|修复|合并)", task)
    explicit_followup_write = re.search(r"(?:并|然后|随后|直接|请|帮我|如需|需要时|必要时).{0,8}(?:删除|修改|修复|合并)", task)
    if read_only_question and not explicit_followup_write:
        detected = [item for item in detected if item[1] != "modify"]

    explicit_candidates = facts.get("candidate_intents")
    explicit: list[str] = []
    if explicit_candidates is not None:
        if not isinstance(explicit_candidates, list):
            raise HarnessError("candidate_intents 必须是数组", code="invalid_task_intent")
        for item in explicit_candidates:
            intent = item.get("intent") if isinstance(item, dict) else item
            if not isinstance(intent, str) or intent not in TASK_INTENTS:
                raise HarnessError(f"未知任务意图：{intent}", code="invalid_task_intent")
            explicit.append(intent)
    primary = facts.get("task_intent")
    if primary is not None:
        if not isinstance(primary, str) or primary not in TASK_INTENTS:
            raise HarnessError(f"未知任务意图：{primary}", code="invalid_task_intent")
        explicit.insert(0, primary)

    ordered = explicit + [intent for _, intent in sorted(detected)]
    if not ordered:
        ordered = ["modify" if has_declared_scope else "query"]
    unique = list(dict.fromkeys(ordered))
    current = [{"intent": intent, "mutation_profile": INTENT_MUTATION[intent]} for intent in unique]
    deferred_contract = [
        {"intent": intent, "mutation_profile": INTENT_MUTATION[intent]}
        for intent in dict.fromkeys(intent for _, intent in sorted(deferred))
    ]
    return current, deferred_contract, list(dict.fromkeys(reason_codes))


def infer_task_intents(task: str, facts: dict[str, Any], *, has_declared_scope: bool) -> list[dict[str, str]]:
    current, _, _ = classify_task_intents(task, facts, has_declared_scope=has_declared_scope)
    return current


def compile_mutation_profile(candidates: Sequence[dict[str, str]], declared: Any) -> str:
    inferred = max((item["mutation_profile"] for item in candidates), key=MUTATION_RANK.get)
    if declared is None:
        return inferred
    if not isinstance(declared, str) or declared not in MUTATION_RANK:
        raise HarnessError("mutation_profile 无效", code="invalid_mutation_profile")
    return max((inferred, declared), key=MUTATION_RANK.get)


def infer_gates(task: str, declared: Sequence[str] = (), *, mutation_profile: str = "workspace_write") -> list[str]:
    gate_text = re.sub(r"\b(?:claude|vs|visual studio)\s+code\b", "", task, flags=re.IGNORECASE)
    gates = set(declared)
    unknown = gates - set(GATE_DEFS)
    if unknown:
        raise HarnessError(f"未知 Gate：{', '.join(sorted(unknown))}", code="invalid_gate")
    for gate, spec in GATE_DEFS.items():
        if any(phrase_matches(gate_text, term) for term in spec["terms"]):
            gates.add(gate)
    if mutation_profile == "read_only":
        gates.difference_update({"code-edit", "document-edit"})
    if mutation_profile == "git_metadata_write":
        gates.difference_update({"code-edit", "document-edit"})
    return [gate for gate in GATE_ORDER if gate in gates]


def infer_gates_from_paths(paths: Sequence[str], *, mutation_profile: str = "workspace_write") -> list[str]:
    gates: set[str] = set()
    for path in paths:
        lowered = path.casefold().replace("\\", "/")
        suffix = Path(lowered).suffix
        parts = tuple(part for part in lowered.split("/") if part)
        stems = {Path(part).stem for part in parts}
        filename = parts[-1] if parts else ""
        if mutation_profile in {"workspace_write", "external_write"} and (lowered.endswith(".md") or lowered.startswith("docs/") or lowered in {"agents.md", "claude.md"}):
            gates.add("document-edit")
        if mutation_profile in {"workspace_write", "external_write"}:
            if ({"security", "auth", "secret", "permission"} & (set(parts) | stems)):
                gates.add("security-sensitive")
            if ({"api", "schema", "migration", "database"} & (set(parts) | stems)):
                gates.add("architecture-contract")
            if suffix in {".tsx", ".jsx", ".css", ".scss", ".swift"} or {"ui", "views", "components"} & set(parts):
                gates.add("frontend-design")
        if mutation_profile in {"workspace_write", "external_write"} and suffix in {".py", ".js", ".ts", ".go", ".rs", ".swift", ".java", ".kt"}:
            gates.add("code-edit")
        if mutation_profile in {"workspace_write", "external_write"} and (
            any(stem == "spec" or stem.startswith("test") or stem.endswith("_test") for stem in stems)
            or re.search(r"(?:^|[._-])(?:test|spec)(?:[._-]|$)", filename) is not None
            or any("测试" in part for part in parts)
        ):
            gates.add("testing-acceptance")
    return [gate for gate in GATE_ORDER if gate in gates]


def expand_scope_paths_for_inference(paths: Sequence[str], target: Path) -> list[str]:
    """将目录型 scope 路径展开为实际文件路径，供 Gate 推断使用。

    若路径以 '/' 结尾或在磁盘上是目录，尝试遍历其下文件（有界）；
    非目录路径原样保留。目录不存在或不可读时保留原路径。
    """
    expanded: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        candidate = target / normalized.rstrip("/")
        if normalized.endswith("/") or candidate.is_dir():
            try:
                files = [p.relative_to(target).as_posix() for p in candidate.rglob("*") if p.is_file()]
                if files:
                    expanded.extend(files[:200])  # 有界，避免巨型目录
                else:
                    expanded.append(path)
            except (OSError, PermissionError):
                expanded.append(path)
        else:
            expanded.append(path)
    return expanded


def extract_task_paths(task: str, target: Path) -> list[str]:
    candidates = re.findall(r"`([^`]+)`", task)
    paths: list[str] = []
    for raw in candidates:
        if not ("/" in raw or "\\" in raw or Path(raw).suffix):
            continue
        path = Path(raw).expanduser()
        if path.is_absolute():
            try:
                raw = path.resolve().relative_to(target).as_posix()
            except ValueError:
                continue
        else:
            raw = path.as_posix()
            while raw.startswith("./"):
                raw = raw[2:]
        if raw and ".." not in Path(raw).parts:
            paths.append(raw)
    return list(dict.fromkeys(paths))


def validate_scope(scope: Sequence[str], *, field: str = "scope", allow_git_resources: bool = False) -> list[str]:
    result: list[str] = []
    for item in scope:
        if looks_like_inline_input(item):
            raise HarnessError(
                f"{field} 不接受 JSON 或内联结构：{item}",
                code="invalid_scope_json",
                actual_vs_expected={"actual": item, "expected": "单个项目内相对路径"},
                suggested_fix="--scope 是可重复单值参数，一次只传一个路径；facts 中 scope 字段必须是字符串数组，不要把 JSON 数组整体作为单个字符串传入",
            )
        if allow_git_resources and CONTROLLED_GIT_SCOPE_RE.fullmatch(item):
            result.append(item)
            continue
        normalized = item.replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        looks_descriptive = (
            any(marker in normalized for marker in SCOPE_DESCRIPTION_MARKERS)
            or normalized.rstrip().endswith(("。", "；", "，", ".", "!", "?"))
            or (" " in normalized and "/" not in normalized and not Path(normalized).suffix)
        )
        if looks_descriptive:
            raise HarnessError(f"{field} 只能包含结构化路径或受控资源：{item}", code="invalid_scope_description")
        if re.search(r"[;|,\t]", normalized) or re.search(r"\s{2,}", normalized):
            raise HarnessError(
                f"{field} 条目疑似多路径拼接：{item}",
                code="invalid_scope_concatenated",
                suggested_fix="每个路径必须是独立条目——用数组传入或分行书写，不要用 ;/,/| 等符号拼接在同一条目中",
            )
        if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts or ":" in normalized:
            raise HarnessError(f"{field} 不是项目内相对路径：{item}", code="invalid_scope")
        result.append(normalized)
    return list(dict.fromkeys(result))


def scope_covers(path: str, scope: Sequence[str]) -> bool:
    return any(
        pattern in {"*", "**"}
        or fnmatch.fnmatch(path, pattern)
        or path == pattern.rstrip("/")
        or path.startswith(pattern.rstrip("/") + "/")
        for pattern in scope
    )


def validate_external_scope(scope: Sequence[str]) -> list[str]:
    result: list[str] = []
    for item in scope:
        normalized = item.strip()
        if (
            not normalized
            or len(normalized) > 128
            or any(char.isspace() for char in normalized)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", normalized)
            or "@" in normalized
            or "?" in normalized
        ):
            raise HarnessError(f"external_scope 不是受控目标标识：{item}", code="invalid_external_scope")
        result.append(normalized)
    return list(dict.fromkeys(result))


def normalize_work_packages(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise HarnessError("work_packages 必须是数组", code="invalid_work_packages")
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise HarnessError("每个工作包必须是对象", code="invalid_work_packages")
        work_id = str(item.get("work_package_id") or item.get("id") or f"wp-{index}")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", work_id) or work_id in ids:
            raise HarnessError(f"工作包 ID 无效或重复：{work_id}", code="invalid_work_packages")
        ids.add(work_id)
        scope = validate_scope(normalize_string_list(item.get("scope"), f"{work_id}.scope"))
        result.append(
            {
                "work_package_id": work_id,
                "goal": str(item.get("goal", "")).strip(),
                "scope": scope,
                "dependencies": normalize_string_list(item.get("dependencies"), f"{work_id}.dependencies"),
                "owner": str(item.get("owner") or "main").strip(),
                "success_criteria": normalize_string_list(item.get("success_criteria"), f"{work_id}.success_criteria"),
                "acceptance": normalize_string_list(item.get("acceptance"), f"{work_id}.acceptance"),
                "required_fact_refs": normalize_string_list(item.get("required_fact_refs"), f"{work_id}.required_fact_refs"),
            }
        )
    for item in result:
        missing = set(item["dependencies"]) - ids
        if missing:
            raise HarnessError(f"{item['work_package_id']} 依赖不存在：{', '.join(sorted(missing))}", code="invalid_work_packages")
        if not item["goal"] or not item["scope"] or not item["success_criteria"] or not item["acceptance"]:
            raise HarnessError(f"{item['work_package_id']} 缺少 goal/scope/success_criteria/acceptance", code="invalid_work_packages")
    pending = {item["work_package_id"]: set(item["dependencies"]) for item in result}
    resolved: set[str] = set()
    while pending:
        ready = {item for item, deps in pending.items() if deps <= resolved}
        if not ready:
            raise HarnessError("工作包依赖存在环", code="invalid_work_packages")
        resolved.update(ready)
        for item in ready:
            pending.pop(item)
    return result


def decide_topology(work_packages: Sequence[dict[str, Any]], requested: str | None) -> str:
    allowed = {"single_owner", "single_owner_with_verifier", "multi_owner"}
    if requested and requested not in allowed:
        raise HarnessError("execution_topology 无效", code="invalid_topology")
    owners = {item["owner"] for item in work_packages}
    def patterns_overlap(left: str, right: str) -> bool:
        if left in {"*", "**"} or right in {"*", "**"} or left == right:
            return True
        left_prefix = left.split("*", 1)[0].rstrip("/")
        right_prefix = right.split("*", 1)[0].rstrip("/")
        return bool(left_prefix and right_prefix and (left_prefix.startswith(right_prefix + "/") or right_prefix.startswith(left_prefix + "/")))

    overlap = False
    for index, left in enumerate(work_packages):
        for right in work_packages[index + 1 :]:
            if any(patterns_overlap(left_scope, right_scope) for left_scope in left["scope"] for right_scope in right["scope"]):
                overlap = True
    if requested == "multi_owner" and (len(work_packages) < 2 or len(owners) < 2 or overlap):
        raise HarnessError("multi_owner 不满足独立交付、Owner 或范围隔离条件", code="unsafe_topology")
    if requested:
        return requested
    return "multi_owner" if len(work_packages) >= 2 and len(owners) >= 2 and not overlap else "single_owner"


def build_dispatch_contracts(
    topology: str,
    work_packages: Sequence[dict[str, Any]],
    task_id: str,
    allowed_scope: Sequence[str],
    success_criteria: Sequence[str],
) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    if topology == "multi_owner":
        for work in work_packages:
            contracts.append(
                {
                    "role": "implementation_owner",
                    "owner": work["owner"],
                    "goal": work["goal"],
                    "scope": work["scope"],
                    "input_refs": [f"task:{task_id}"] + work["required_fact_refs"],
                    "acceptance": work["acceptance"],
                    "stop_condition": "交付结构化证据，或报告真实阻塞和范围变化",
                }
            )
    elif topology == "single_owner_with_verifier":
        contracts.append(
            {
                "role": "independent_verifier",
                "owner": "independent_verifier",
                "goal": "独立验证任务包成功标准，不参与实现",
                "scope": list(allowed_scope),
                "input_refs": [f"task:{task_id}", "evidence-index.json", "actual-workspace-diff"],
                "acceptance": list(success_criteria),
                "stop_condition": "返回通过、补证或重新准入结论",
            }
        )
    return contracts


def meaningful_project_fact(target: Path, ref: str) -> bool:
    path_part = ref.split("#", 1)[0]
    path = (target / path_part).resolve()
    try:
        path.relative_to(target)
    except ValueError:
        return False
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        return False
    text = path.read_text(encoding="utf-8")
    body = "\n".join(line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
    return bool(body.strip())


def required_fact_refs(gates: Sequence[str], declared: Sequence[str]) -> list[str]:
    refs = list(declared)
    for gate in gates:
        refs.extend(GATE_DEFS[gate]["facts"])
    return list(dict.fromkeys(refs))


def compile_plan_contract(
    gates: Sequence[str],
    matched_rules: Sequence[dict[str, Any]],
    scope: Sequence[str],
    *,
    scope_required: bool,
) -> tuple[list[str], dict[str, Any]]:
    fields = list(PLAN_FIELDS)
    for gate in gates:
        fields.extend(GATE_DEFS[gate]["plan_fields"])
    for rule in matched_rules:
        fields.extend(rule["plan_fields"])
    if scope_required and not scope:
        fields.append("执行范围")
    fields = list(dict.fromkeys(fields))
    return fields, {field: None for field in fields}


def plan_contract_payload(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_fields": package["plan_fields"],
        "plan_skeleton": package["plan_skeleton"],
        "scope_required": (
            package["mutation_profile"] in {"workspace_write", "external_write"}
            and package["task_intent"] != "git_sync"
            and not bool(package["write_scope"])
        ),
        "allowed_scope": package["allowed_scope"],
        "read_scope": package["read_scope"],
        "write_scope": package["write_scope"],
        "git_scope": package["git_scope"],
        "external_scope": package["external_scope"],
        "allowed_actions": package["allowed_actions"],
    }


def build_completion_manifest(
    *,
    task_intent: str,
    mutation_profile: str,
    gates: Sequence[str],
    evidence_types: Sequence[str],
    verification_commands: Sequence[Any],
    evidence_profile: str = "standard",
) -> dict[str, Any]:
    if evidence_profile not in {"standard", "fast_track"}:
        raise HarnessError("evidence_profile 无效", code="invalid_evidence_profile")
    required_receipts = ["read_set"] if mutation_profile == "read_only" else ["write_set"]
    if task_intent in {"git_fetch", "git_sync"}:
        required_receipts.append("git_state_snapshot")
    conditional_reviews: list[dict[str, str]] = []
    if "security-sensitive" in gates:
        conditional_reviews.append(
            {
                "review_type": "security_acceptance",
                "trigger": "security_sensitive_gate_active",
                "reason_code": "security_sensitive_task",
            }
        )
    conditional_evidence: list[dict[str, str]] = []
    if evidence_profile == "standard" and mutation_profile in {"workspace_write", "external_write"}:
        conditional_evidence.append(
            {
                "evidence_type": "test_result",
                "trigger": "verification_command_declared_and_workspace_write",
                "reason_code": "workspace_write_requires_verification",
            }
        )
    manifest: dict[str, Any] = {
        "schema_version": COMPLETION_MANIFEST_SCHEMA,
        "evidence_profile": evidence_profile,
        "required_evidence_types": list(dict.fromkeys(evidence_types)),
        "required_receipts": list(dict.fromkeys(required_receipts)),
        "conditional_reviews": conditional_reviews,
        "conditional_evidence": conditional_evidence,
        "verification_commands": list(verification_commands),
        "completion_blockers": [],
        "completion_protocol": "incremental_receipts_single_final",
    }
    manifest["manifest_fingerprint"] = sha256_text(canonical_json(manifest))
    return manifest


RECEIPT_CONDITION_TEXT = {
    "write_set": "仅在任务产生实际写入时要求；无写入时不要求",
    "read_set": "read_only 任务要求记录读取集",
    "git_state_snapshot": "git_fetch/git_sync 任务要求记录 Git 状态快照",
}


def evidence_skeleton_path(state: Path, evidence_type: str) -> Path:
    return state / "templates" / f"evidence-{evidence_type.replace('_', '-')}-skeleton.json"


def ensure_evidence_skeletons(state: Path, evidence_types: Sequence[str]) -> list[str]:
    """为缺失证据类型生成/刷新声明骨架；准入与验收共用同一助手，保证两处文件一致。"""
    refs: list[str] = []
    if not evidence_types:
        return refs
    templates_dir = state / "templates"
    templates_dir.mkdir(exist_ok=True)
    for etype in evidence_types:
        skeleton = {
            "schema_version": EVIDENCE_DECLARATION_SCHEMA,
            "type": etype,
            "write_set": [],
            "read_set": [],
            "concurrent_drift": [],
            "conclusion": "",
            "_instructions": "填充 write_set/read_set/concurrent_drift/conclusion 后提交；write_set 只写 git status/diff 中实际变化的路径，不要写入未变化路径",
        }
        skeleton_path = evidence_skeleton_path(state, etype)
        atomic_write_json(skeleton_path, skeleton)
        refs.append(str(skeleton_path))
    return refs


def evidence_checklist_payload(state: Path, package: dict[str, Any]) -> dict[str, Any]:
    """把完成清单转成一次性备齐的证据清单，消灭首轮补证往返。"""
    manifest = package["completion_manifest"]
    required = list(manifest.get("required_evidence_types", []))
    return {
        "required": required,
        "conditional": list(manifest.get("conditional_evidence", [])),
        "required_receipts": [
            {
                "receipt": str(name),
                "condition": RECEIPT_CONDITION_TEXT.get(str(name), "按完成清单要求"),
            }
            for name in manifest.get("required_receipts", [])
        ],
        "skeletons": [str(evidence_skeleton_path(state, etype)) for etype in required],
    }


def pending_context_receipts(
    state: Path,
    package: dict[str, Any],
    target: Path,
    compiled: dict[str, Any] | None = None,
) -> list[str]:
    """列出尚未加载或已失效的上下文阶段与工作包，避免执行后才暴露缺上下文。"""
    pending: list[str] = []
    for stage in ("plan", "action"):
        schedule = package.get("context_schedule", {}).get(stage) or {}
        if not (schedule.get("rule_ids") or schedule.get("project_fact_refs")):
            continue
        if not context_receipt_valid(state, package, target, stage=stage):
            pending.append(stage)
    work_states = (compiled or {}).get("work_package_states", {})
    for work_id, schedule in (package.get("context_schedule", {}).get("work_packages") or {}).items():
        if not (schedule.get("rule_ids") or schedule.get("project_fact_refs")):
            continue
        if work_states.get(work_id) == "verified":
            continue
        if not context_receipt_valid(state, package, target, work_package=str(work_id)):
            pending.append(f"work_package:{work_id}")
    return pending


def completion_manifest_valid(manifest: Any) -> bool:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != COMPLETION_MANIFEST_SCHEMA:
        return False
    expected = manifest.get("manifest_fingerprint")
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_fingerprint"}
    return isinstance(expected, str) and expected == sha256_text(canonical_json(unsigned))


def parse_gate_assessment(facts: dict[str, Any]) -> tuple[list[str], str] | None:
    """解析宿主权威 gate 声明；返回 (声明 gates, rationale)，未声明时返回 None。"""
    raw = facts.get("gate_assessment")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise HarnessError("gate_assessment 必须是 JSON 对象", code="invalid_gate_assessment")
    gates = normalize_string_list(raw.get("gates"), "gate_assessment.gates")
    unknown = set(gates) - set(GATE_DEFS)
    if unknown:
        raise HarnessError(f"未知 Gate：{', '.join(sorted(unknown))}", code="invalid_gate")
    rationale = raw.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 500:
        raise HarnessError("gate_assessment.rationale 必须是 500 字符内的非空字符串", code="invalid_gate_assessment")
    return list(dict.fromkeys(gates)), rationale.strip()


PLATFORM_SPECIFIC_EXTENSIONS: dict[str, str] = {
    ".ps1": "windows",
    ".bat": "windows",
    ".cmd": "windows",
    ".sh": "unix",
    ".bash": "unix",
    ".zsh": "unix",
}


def current_platform() -> str:
    if sys.platform == "win32":
        return "windows"
    return "unix"


def detect_platform_scope(paths: list[str]) -> dict[str, Any]:
    detected: set[str] = set()
    for path in paths:
        suffix = Path(path).suffix.lower()
        if suffix in PLATFORM_SPECIFIC_EXTENSIONS:
            detected.add(PLATFORM_SPECIFIC_EXTENSIONS[suffix])
    current = current_platform()
    cross_platform = bool(detected) and (detected != {current} or len(detected) > 1)
    return {
        "detected_platforms": sorted(detected),
        "current_platform": current,
        "cross_platform": cross_platform,
        "verification_layers": build_verification_layers(detected, current),
    }


def build_verification_layers(detected: set[str], current: str) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    if not detected:
        return layers
    for platform in sorted(detected):
        status = "executable" if platform == current else "pending_verification"
        layers.append({
            "layer": f"{'current' if platform == current else 'target'}_platform",
            "platform": platform,
            "status": status,
        })
    return layers


# fast_track 只允许文档/规则/测试类路径：分类完全复用 infer_gates_from_paths，不引入新真源。
FAST_TRACK_DOC_LIKE_GATES = {"document-edit", "testing-acceptance", "code-edit"}


def fast_track_scope_doc_like(write_scope: Sequence[str], mutation_profile: str, target: Path) -> bool:
    """write_scope 全部落在文档/规则/测试路径才允许 fast_track。

    纯 code-edit（非测试代码）或任何高风险/其他 Gate 命中都不算 doc-like；
    空 write_scope 不允许（直接路线写任务必须显式声明范围）。
    """
    if not write_scope:
        return False
    for path in expand_scope_paths_for_inference(write_scope, target):
        gates = set(infer_gates_from_paths([path], mutation_profile=mutation_profile))
        if not gates or not gates <= FAST_TRACK_DOC_LIKE_GATES or gates == {"code-edit"}:
            return False
    return True


def build_package(target: Path, task: str, facts: dict[str, Any], cli: argparse.Namespace, task_id: str) -> tuple[dict[str, Any], list[str]]:
    declared_gates = normalize_string_list(facts.get("gates"), "gates")
    gate_assessment = parse_gate_assessment(facts)
    work_packages = normalize_work_packages(facts.get("work_packages"))
    fast_track_declared = facts.get("fast_track", False)
    if not isinstance(fast_track_declared, bool):
        raise HarnessError("fast_track 必须是布尔值", code="invalid_facts")
    inline_note = facts.get("inline_note")
    if inline_note is not None:
        if not isinstance(inline_note, str) or not inline_note.strip() or len(inline_note.strip()) > 200:
            raise HarnessError("inline_note 必须是 200 字符内的非空字符串", code="invalid_facts")
        inline_note = inline_note.strip()
    cli_scope = list(cli.scope or [])
    legacy_scope_raw = facts.get("allowed_scope", facts.get("target_paths"))
    has_declared_scope = any(
        value is not None
        for value in (
            legacy_scope_raw,
            facts.get("read_scope"),
            facts.get("write_scope"),
            facts.get("git_scope"),
            facts.get("external_scope"),
        )
    ) or bool(cli_scope)
    candidate_intents, deferred_intents, intent_boundary_reason_codes = classify_task_intents(
        task,
        facts,
        has_declared_scope=has_declared_scope,
    )
    task_intent = str(facts.get("task_intent") or candidate_intents[0]["intent"])
    mutation_profile = compile_mutation_profile(candidate_intents, facts.get("mutation_profile"))
    requested_actions = normalize_string_list(facts.get("allowed_actions"), "allowed_actions") + list(cli.action or [])
    if any(action == "external_write" for action in requested_actions):
        mutation_profile = max((mutation_profile, "external_write"), key=MUTATION_RANK.get)
    elif any(action in {"write", "git_sync"} for action in requested_actions):
        mutation_profile = max((mutation_profile, "workspace_write"), key=MUTATION_RANK.get)
    elif any(action == "git_fetch" for action in requested_actions):
        mutation_profile = max((mutation_profile, "git_metadata_write"), key=MUTATION_RANK.get)
    if work_packages:
        mutation_profile = max((mutation_profile, "workspace_write"), key=MUTATION_RANK.get)

    legacy_scope = normalize_string_list(legacy_scope_raw, "allowed_scope") + cli_scope
    read_scope = validate_scope(
        normalize_string_list(facts.get("read_scope"), "read_scope"), field="read_scope", allow_git_resources=True
    )
    write_scope = validate_scope(
        normalize_string_list(facts.get("write_scope"), "write_scope"), field="write_scope"
    )
    git_scope = validate_scope(
        normalize_string_list(facts.get("git_scope"), "git_scope"), field="git_scope", allow_git_resources=True
    )
    external_scope = validate_external_scope(normalize_string_list(facts.get("external_scope"), "external_scope"))
    if legacy_scope:
        if mutation_profile == "read_only":
            read_scope = validate_scope([*read_scope, *legacy_scope], field="read_scope", allow_git_resources=True)
        else:
            write_scope = validate_scope([*write_scope, *legacy_scope], field="write_scope")
    extracted_scope = extract_task_paths(task, target)
    if not read_scope and not write_scope and extracted_scope:
        if mutation_profile == "read_only":
            read_scope = validate_scope(extracted_scope, field="read_scope", allow_git_resources=True)
        else:
            write_scope = validate_scope(extracted_scope, field="write_scope")
    if write_scope:
        mutation_profile = max((mutation_profile, "workspace_write"), key=MUTATION_RANK.get)
    if external_scope:
        mutation_profile = "external_write"
    if not any(item["mutation_profile"] == mutation_profile for item in candidate_intents):
        profile_intent = {
            "read_only": "query",
            "git_metadata_write": "git_fetch",
            "workspace_write": "modify",
            "external_write": "external_write",
        }[mutation_profile]
        candidate_intents.append({"intent": profile_intent, "mutation_profile": mutation_profile})
    candidate_names = {item["intent"] for item in candidate_intents}
    git_operation = "git_sync" if "git_sync" in candidate_names else ("git_fetch" if "git_fetch" in candidate_names else None)
    git_state, git_sync_scope, git_preflight_blockers = git_preflight_contract(
        target,
        git_operation,
        git_scope,
    )
    if git_operation == "git_sync" and git_sync_scope:
        if write_scope and set(write_scope) != set(git_sync_scope):
            git_preflight_blockers.append("手工 write_scope 与 Git 预检变化清单不一致")
        write_scope = validate_scope(git_sync_scope, field="write_scope")
    scope = write_scope if write_scope else read_scope
    path_gates = infer_gates_from_paths(expand_scope_paths_for_inference([*read_scope, *write_scope], target), mutation_profile=mutation_profile)
    floor_added: list[str] = []
    if gate_assessment is not None:
        # 权威模式：以宿主声明为准，代码只对安全底线 gate 做确定性兜底。
        assessment_gates, assessment_rationale = gate_assessment
        floor_from_text = [gate for gate in GATE_ORDER if gate in infer_floor_gates(task)]
        floor_from_paths = [gate for gate in path_gates if gate in SAFETY_FLOOR_GATES]
        floor_added = [
            gate
            for gate in GATE_ORDER
            if gate in set(floor_from_text) | set(floor_from_paths)
            and gate not in assessment_gates
            and gate not in declared_gates
        ]
        gates = [
            gate
            for gate in GATE_ORDER
            if gate in set(assessment_gates) | set(declared_gates) | set(floor_from_text) | set(floor_from_paths)
        ]
        if mutation_profile in {"read_only", "git_metadata_write"}:
            gates = [gate for gate in gates if gate not in {"code-edit", "document-edit"}]
        gate_decision: dict[str, Any] = {
            "mode": "host_declared",
            "declared_gates": assessment_gates,
            "rationale": assessment_rationale,
            "floor_added": floor_added,
        }
    else:
        gates = infer_gates(
            task,
            list(dict.fromkeys(declared_gates + path_gates)),
            mutation_profile=mutation_profile,
        )
        gate_decision = {"mode": "keyword_inferred", "declared_gates": [], "rationale": None, "floor_added": []}
    requested_route = facts.get("execution_route")
    if requested_route is not None and requested_route not in {"direct", "planned", "extended"}:
        raise HarnessError("execution_route 无效", code="invalid_route")
    high_gates = {"product-change", "architecture-contract", "security-sensitive", "destructive-data", "release-external", "frontend-design"}
    inferred_route = "extended" if work_packages else (
        "planned" if git_operation == "git_sync" or set(gates) & high_gates else "direct"
    )
    route_rank = {"direct": 0, "planned": 1, "extended": 2}
    route = max((inferred_route, requested_route or "direct"), key=route_rank.get)
    if route == "extended" and not work_packages:
        route = "planned"
    if route == "direct" and mutation_profile in {"workspace_write", "external_write"} and not write_scope:
        route = "planned"

    fast_track = False
    fast_track_denied_reason: str | None = None
    if fast_track_declared:
        if work_packages:
            fast_track_denied_reason = "has_work_packages"
        elif set(gates) & (high_gates | SAFETY_FLOOR_GATES):
            fast_track_denied_reason = "high_gate_present"
        elif route != "direct":
            fast_track_denied_reason = "route_not_direct"
        elif not fast_track_scope_doc_like(write_scope, mutation_profile, target):
            fast_track_denied_reason = "scope_not_doc_like"
        else:
            fast_track = True

    default_actions = {
        "read_only": ["read"],
        "git_metadata_write": ["read", "git_fetch"],
        "workspace_write": ["read", "write", "local_verify"],
        "external_write": ["read", "write", "local_verify", "external_write"],
    }
    intent_actions = {
        "git_inspect": ["git_inspect"],
        "git_fetch": ["git_fetch"],
        "git_sync": ["git_fetch", "git_sync"],
    }.get(task_intent, [])
    actions = list(dict.fromkeys([*default_actions[mutation_profile], *intent_actions, *requested_actions]))
    criteria = normalize_string_list(facts.get("success_criteria"), "success_criteria") + list(cli.success or [])
    criteria = list(dict.fromkeys(criteria or [task.strip()]))
    declared_refs = normalize_string_list(facts.get("required_fact_refs"), "required_fact_refs")
    requested_features = normalize_string_list(facts.get("feature_ids"), "feature_ids") + list(getattr(cli, "feature", None) or [])
    config = project_config(target)
    if config and config.get("schema_version") == CONFIG_SCHEMA:
        knowledge_context, knowledge_refs, knowledge_blockers = resolve_feature_knowledge(
            target,
            task,
            scope,
            gates,
            list(dict.fromkeys(requested_features)),
        )
        fact_refs = list(dict.fromkeys(declared_refs + knowledge_refs))
    else:
        knowledge_context = {"status": "legacy", "selected_features": [], "category_refs": {}, "shared_refs": []}
        knowledge_blockers = []
        fact_refs = required_fact_refs(gates, declared_refs)
    missing_facts = [ref for ref in fact_refs if not meaningful_project_fact(target, ref)]

    auth_requirements: list[str] = normalize_string_list(facts.get("authorization_requirements"), "authorization_requirements")
    semantic_evidence = normalize_string_list(facts.get("semantic_evidence_requirements"), "semantic_evidence_requirements")
    fc_features: list[dict[str, Any]] = []
    if mutation_profile in {"workspace_write", "external_write"}:
        fc_features = resolve_functional_confirmation(target, knowledge_context, write_scope)
    if any(item.get("required", False) for item in fc_features):
        semantic_evidence.append("functional_confirmation")
    for gate in gates:
        auth_requirements.extend(GATE_DEFS[gate].get("authorization", ()))
        semantic_evidence.extend(GATE_DEFS[gate]["evidence"])
    intent_evidence = {
        "query": ["source_trace"],
        "audit": ["source_trace"],
        "git_inspect": ["git_inspection_result"],
        "git_fetch": ["git_fetch_result"],
        "git_sync": ["git_sync_result"],
        "modify": [],
        "external_write": [],
    }
    semantic_evidence.extend(intent_evidence[task_intent])
    auth_requirements = list(dict.fromkeys(auth_requirements))
    semantic_evidence = list(dict.fromkeys(semantic_evidence))
    verification_commands = facts.get("verification_commands", [])
    if not isinstance(verification_commands, list):
        raise HarnessError("verification_commands 必须是数组", code="invalid_facts")
    normalized_verification_commands: list[dict[str, Any]] = []
    for raw_command in verification_commands:
        argv, produces = normalize_verification_spec(raw_command)
        normalized_verification_commands.append({"argv": argv, "produces": produces})
    verification_commands = normalized_verification_commands
    topology = decide_topology(work_packages, facts.get("execution_topology"))
    dispatch_contracts = build_dispatch_contracts(topology, work_packages, task_id, scope, criteria)
    matched_rules, rule_errors = load_active_rules(
        target,
        gates,
        task,
        mutation_profile=mutation_profile,
    )
    for rule in matched_rules:
        semantic_evidence.extend(rule["evidence_types"])
    plan_fields, plan_skeleton = compile_plan_contract(
        gates,
        matched_rules,
        write_scope,
        scope_required=mutation_profile in {"workspace_write", "external_write"} and task_intent != "git_sync",
    )
    semantic_evidence = list(dict.fromkeys(semantic_evidence))
    blocking_deliverables, background_deliverables = classify_document_deliverables(
        task,
        facts,
        gates,
        scope,
        mutation_profile=mutation_profile,
        target=target,
    )
    evidence_profile = "fast_track" if fast_track else "standard"
    manifest_evidence = semantic_evidence
    if fast_track:
        # 最小证据集：code_diff + 声明了验证命令时的 test_run；语义规则累加不叠加。
        manifest_evidence = ["code_diff"] + (["test_run"] if verification_commands else [])
    completion_manifest = build_completion_manifest(
        task_intent=task_intent,
        mutation_profile=mutation_profile,
        gates=gates,
        evidence_types=manifest_evidence,
        verification_commands=verification_commands,
        evidence_profile=evidence_profile,
    )

    blockers = list(rule_errors) + knowledge_blockers + git_preflight_blockers
    if missing_facts:
        blockers.append("缺少必要项目事实：" + ", ".join(missing_facts))
    context_schedule: dict[str, Any] = {
        "plan": {"rule_ids": [item["rule_id"] for item in matched_rules], "project_fact_refs": fact_refs},
        "action": {"rule_ids": [item["rule_id"] for item in matched_rules], "project_fact_refs": fact_refs},
        "acceptance": {"rule_ids": [], "project_fact_refs": []},
        "work_packages": {
            item["work_package_id"]: {
                "rule_ids": [rule["rule_id"] for rule in matched_rules],
                "project_fact_refs": list(dict.fromkeys(fact_refs + item["required_fact_refs"])),
            }
            for item in work_packages
        },
    }
    admission = "blocked" if blockers else ("ready_direct" if route == "direct" else "needs_plan")
    platform_scope = detect_platform_scope(write_scope + read_scope)
    package = {
        "schema_version": TASK_SCHEMA,
        "package_revision": 1,
        "task_id": task_id,
        "created_at": utc_now(),
        "task_snapshot_ref": sha256_text(task),
        "original_task": task,
        "task_type": str(facts.get("task_type") or (gates[0] if gates else "general")),
        "task_intent": task_intent,
        "candidate_intents": candidate_intents,
        "deferred_intents": deferred_intents,
        "intent_boundary_reason_codes": intent_boundary_reason_codes,
        "mutation_profile": mutation_profile,
        "execution_route": route,
        "execution_topology": topology,
        "matched_gates": gates,
        "gate_assessment": (
            {"gates": gate_assessment[0], "rationale": gate_assessment[1]}
            if gate_assessment is not None
            else None
        ),
        "gate_decision": gate_decision,
        "matched_rules": matched_rules,
        "knowledge_context": knowledge_context,
        "context_quality": knowledge_context.get("context_quality", "complete"),
        "feature_ids": knowledge_context.get("selected_features", []),
        "functional_confirmation_features": fc_features,
        "fallback_fact_refs": normalize_string_list(facts.get("fallback_fact_refs"), "fallback_fact_refs"),
        "blocking_deliverables": blocking_deliverables,
        "background_deliverables": background_deliverables,
        "post_completion_dispatch_policy": (
            "suppressed" if facts.get("suppress_post_completion_dispatch", False)
            else "declared_deliverables_only"
        ),
        "required_fact_refs": fact_refs,
        "loaded_project_facts": [ref for ref in fact_refs if ref not in missing_facts],
        "allowed_scope": scope,
        "read_scope": read_scope,
        "write_scope": write_scope,
        "git_scope": git_scope,
        "external_scope": external_scope,
        "git_operation": git_operation,
        "git_state_snapshot": git_state,
        "git_sync_scope": git_sync_scope,
        "allowed_actions": actions,
        "success_criteria": criteria,
        "authorization_requirements": auth_requirements,
        "stop_conditions": list(
            dict.fromkeys(
                ["范围、目标、准备动作、授权或 Gate 发生变化时重新准入", "出现真实阻塞时停止"]
                + [rule["failure_mode"] for rule in matched_rules]
            )
        ),
        "plan_fields": plan_fields,
        "plan_skeleton": plan_skeleton,
        "acceptance_requirements": criteria,
        "verification_commands": verification_commands,
        "semantic_evidence_requirements": semantic_evidence,
        "completion_manifest": completion_manifest,
        "context_schedule": context_schedule,
        "work_packages": work_packages,
        "dispatch_contracts": dispatch_contracts,
        "admission_status": admission,
        "platform_scope": platform_scope,
        "fast_track": fast_track,
    }
    if fast_track_declared and fast_track_denied_reason is not None:
        package["fast_track_denied_reason"] = fast_track_denied_reason
    if fast_track and inline_note is not None:
        package["inline_note"] = inline_note
    elif inline_note is not None:
        package["inline_note_ignored"] = True
    return package, blockers


def package_fingerprint(package: dict[str, Any]) -> str:
    return sha256_text(canonical_json(package))


def scope_contract_fingerprint(package: dict[str, Any]) -> str:
    """读写、Git、外部范围、动作、路线与工作包组成的范围合同指纹。"""
    return sha256_text(
        canonical_json(
            {
                "allowed_scope": package.get("allowed_scope", []),
                "read_scope": package.get("read_scope", []),
                "write_scope": package.get("write_scope", []),
                "git_scope": package.get("git_scope", []),
                "external_scope": package.get("external_scope", []),
                "allowed_actions": package.get("allowed_actions", []),
                "execution_route": package.get("execution_route"),
                "execution_topology": package.get("execution_topology"),
                "work_packages": package.get("work_packages", []),
            }
        )
    )


def plan_contract_fingerprint(package: dict[str, Any]) -> str:
    """正式方案必须满足的字段、Gate、阻断交付物与成功标准指纹。"""
    return sha256_text(
        canonical_json(
            {
                "plan_fields": package.get("plan_fields", []),
                "matched_gates": package.get("matched_gates", []),
                "blocking_deliverables": package.get("blocking_deliverables", []),
                "success_criteria": package.get("success_criteria", []),
            }
        )
    )


def authorization_contract_fingerprint(package: dict[str, Any]) -> str:
    """授权动作与全部授权范围组成的授权合同指纹。"""
    return sha256_text(
        canonical_json(
            {
                "authorization_requirements": package.get("authorization_requirements", []),
                "allowed_scope": package.get("allowed_scope", []),
                "write_scope": package.get("write_scope", []),
                "git_scope": package.get("git_scope", []),
                "external_scope": package.get("external_scope", []),
            }
        )
    )


def context_schedule_refs(package: dict[str, Any]) -> list[str]:
    schedule = package.get("context_schedule", {})
    refs: list[str] = []
    stages: list[dict[str, Any]] = []
    for key in ("plan", "action", "acceptance"):
        value = schedule.get(key)
        if isinstance(value, dict):
            stages.append(value)
    for value in (schedule.get("work_packages") or {}).values():
        if isinstance(value, dict):
            stages.append(value)
    for value in stages:
        refs.extend(f"rule:{item}" for item in value.get("rule_ids", []))
        refs.extend(str(item) for item in value.get("project_fact_refs", []))
    return list(dict.fromkeys(refs))


def required_evidence_types(package: dict[str, Any]) -> list[str]:
    manifest = package.get("completion_manifest", {})
    types = list(manifest.get("required_evidence_types", []))
    types.extend(str(item.get("evidence_type")) for item in manifest.get("conditional_evidence", []))
    return list(dict.fromkeys(types))


def contract_disposition(previous: dict[str, Any], current: dict[str, Any]) -> str:
    """只由控制器判定的合同分段处置结论。"""
    if package_fingerprint(previous) == package_fingerprint(current):
        return "no_change"
    if (
        scope_contract_fingerprint(previous) != scope_contract_fingerprint(current)
        or authorization_contract_fingerprint(previous) != authorization_contract_fingerprint(current)
        or previous.get("blocking_deliverables", []) != current.get("blocking_deliverables", [])
    ):
        return "full_readmission"
    if set(current.get("plan_fields", [])) - set(previous.get("plan_fields", [])):
        return "plan_amendment"
    if set(current.get("matched_gates", [])) - set(previous.get("matched_gates", [])):
        return "incremental_admission"
    if set(required_evidence_types(current)) - set(required_evidence_types(previous)):
        return "evidence_only"
    if set(context_schedule_refs(current)) - set(context_schedule_refs(previous)):
        return "context_only"
    return "no_change"


def build_contract_delta(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    prior_refs = set(context_schedule_refs(previous))
    prior_types = set(required_evidence_types(previous))
    return {
        "schema_version": CONTRACT_DELTA_SCHEMA,
        "from_package_fingerprint": package_fingerprint(previous),
        "to_package_fingerprint": package_fingerprint(current),
        "from_package_revision": previous.get("package_revision"),
        "to_package_revision": current.get("package_revision"),
        "added_gates": [item for item in current.get("matched_gates", []) if item not in previous.get("matched_gates", [])],
        "added_plan_fields": [item for item in current.get("plan_fields", []) if item not in previous.get("plan_fields", [])],
        "added_context_refs": [item for item in context_schedule_refs(current) if item not in prior_refs],
        "added_evidence_types": [item for item in required_evidence_types(current) if item not in prior_types],
        "scope_changed": scope_contract_fingerprint(previous) != scope_contract_fingerprint(current),
        "route_changed": previous.get("execution_route") != current.get("execution_route"),
        "authorization_contract_changed": authorization_contract_fingerprint(previous)
        != authorization_contract_fingerprint(current),
        "work_packages_changed": previous.get("work_packages", []) != current.get("work_packages", []),
        "blocking_deliverables_changed": previous.get("blocking_deliverables", [])
        != current.get("blocking_deliverables", []),
        "plan_contract_changed": plan_contract_fingerprint(previous) != plan_contract_fingerprint(current),
        "disposition": contract_disposition(previous, current),
    }


def initial_compiled(package: dict[str, Any], blockers: Sequence[str]) -> dict[str, Any]:
    states = {item["work_package_id"]: "pending" for item in package["work_packages"]}
    action_schedule = package["context_schedule"]["action"]
    direct_next = "load_action_context" if action_schedule["rule_ids"] or action_schedule["project_fact_refs"] else "execute"
    return {
        "schema_version": COMPILED_SCHEMA,
        "task_id": package["task_id"],
        "package_revision": package["package_revision"],
        "package_fingerprint": package_fingerprint(package),
        "control_status": package["admission_status"],
        "execution_route": package["execution_route"],
        "execution_topology": package["execution_topology"],
        "work_package_states": states,
        "current_work_package": None,
        "next_action": "resolve_blocker" if blockers else (direct_next if package["execution_route"] == "direct" else "load_plan_context"),
        "blockers": list(blockers),
        "evidence_refs": [],
        "scope_changed": False,
        "plan_ref": None,
        "plan_fingerprint": None,
        "plan_artifact": None,
        "plan_delta_contract": None,
        "authorization_status": "not_required" if not package["authorization_requirements"] else "missing",
        "authorization_receipt_ref": None,
        "verification_status": "not_started",
        "updated_at": utc_now(),
    }


def create_task_state(
    target: Path,
    package: dict[str, Any],
    blockers: Sequence[str],
    *,
    timing_started: float | None = None,
) -> Path:
    state = task_state_dir(target, package["task_id"])
    if state.exists():
        raise HarnessError("task-id 已存在", code="task_exists")
    snapshot = workspace_snapshot(target)
    state.mkdir(parents=True)
    atomic_write_json(state / "task-package.json", package)
    atomic_write_json(state / "compiled-task.json", initial_compiled(package, blockers))
    atomic_write_json(state / "evidence-index.json", {"schema_version": EVIDENCE_SCHEMA, "evidence": []})
    atomic_write_json(
        state / "freeze.json",
        {
            "schema_version": FREEZE_SCHEMA,
            "task_id": package["task_id"],
            "package_revision": package["package_revision"],
            "package_fingerprint": package_fingerprint(package),
            "task_snapshot_ref": package["task_snapshot_ref"],
            "workspace_snapshot": snapshot,
            "workspace_fingerprint": sha256_text(canonical_json(snapshot)),
            "git_state_snapshot": package.get("git_state_snapshot"),
            "environment": environment_fingerprint(),
            "created_at": utc_now(),
        },
    )
    for name in ("events.jsonl", "context-receipts.jsonl", "authorization-receipts.jsonl"):
        atomic_write_text(state / name, "")
    ensure_evidence_skeletons(
        state,
        list((package.get("completion_manifest") or {}).get("required_evidence_types", [])),
    )
    append_task_event(
        state,
        package,
        event="created",
        phase="admission",
        reason_code=package["admission_status"],
        duration_ms=int((time.monotonic() - timing_started) * 1000) if timing_started is not None else 0,
    )
    return state


def load_state(target: Path, task_id: str) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    state = task_state_dir(target, task_id)
    package = read_json(state / "task-package.json")
    compiled = read_json(state / "compiled-task.json")
    freeze = read_json(state / "freeze.json")
    if isinstance(package, dict) and package.get("schema_version") == LEGACY_TASK_SCHEMA:
        raise HarnessError(
            "v1 在途任务仅允许只读 status；继续执行前必须显式 task migrate --apply",
            code="legacy_task_requires_migration",
            exit_code=3,
        )
    if not isinstance(package, dict) or package.get("schema_version") != TASK_SCHEMA:
        raise HarnessError("任务包 schema 无效", code="invalid_state")
    if package_fingerprint(package) != compiled.get("package_fingerprint") or compiled.get("package_fingerprint") != freeze.get("package_fingerprint"):
        raise HarnessError("任务包与编译状态指纹不一致", code="stale_state")
    return state, package, compiled, freeze


def migrate_v1_package(target: Path, package: dict[str, Any]) -> dict[str, Any]:
    if package.get("schema_version") != LEGACY_TASK_SCHEMA:
        raise HarnessError("只允许迁移 task-package/v1", code="migration_not_required")
    task = str(package.get("original_task", ""))
    legacy_scope = validate_scope(
        normalize_string_list(package.get("allowed_scope"), "allowed_scope"),
        field="allowed_scope",
    )
    candidates = infer_task_intents(task, {}, has_declared_scope=bool(legacy_scope))
    task_intent = candidates[0]["intent"]
    mutation_profile = compile_mutation_profile(candidates, None)
    if legacy_scope and mutation_profile == "read_only":
        read_scope = legacy_scope
        write_scope: list[str] = []
    else:
        read_scope = []
        write_scope = legacy_scope
        if write_scope:
            mutation_profile = max((mutation_profile, "workspace_write"), key=MUTATION_RANK.get)
    actions = {
        "read_only": ["read"],
        "git_metadata_write": ["read", "git_fetch"],
        "workspace_write": ["read", "write", "local_verify"],
        "external_write": ["read", "write", "local_verify", "external_write"],
    }[mutation_profile]
    migrated = dict(package)
    migrated.update(
        {
            "schema_version": TASK_SCHEMA,
            "package_revision": int(package.get("package_revision", 1)) + 1,
            "migrated_from_schema": LEGACY_TASK_SCHEMA,
            "migrated_at": utc_now(),
            "task_intent": task_intent,
            "candidate_intents": candidates,
            "deferred_intents": [],
            "intent_boundary_reason_codes": [],
            "mutation_profile": mutation_profile,
            "read_scope": read_scope,
            "write_scope": write_scope,
            "git_scope": [],
            "external_scope": [],
            "git_operation": None,
            "git_state_snapshot": None,
            "git_sync_scope": [],
            "allowed_scope": write_scope if write_scope else read_scope,
            "allowed_actions": actions,
            "post_completion_dispatch_policy": "declared_deliverables_only",
        }
    )
    migrated["completion_manifest"] = build_completion_manifest(
        task_intent=task_intent,
        mutation_profile=mutation_profile,
        gates=migrated.get("matched_gates", []),
        evidence_types=migrated.get("semantic_evidence_requirements", []),
        verification_commands=migrated.get("verification_commands", []),
    )
    return migrated


def recover_incomplete_task_migration(state: Path) -> bool:
    root = state / "migration-v1-v2"
    journal_path = root / "journal.json"
    if not journal_path.is_file():
        return False
    journal = read_json(journal_path)
    if journal.get("status") != "applying":
        return False
    backup = root / "backup"
    for name in journal.get("objects", []):
        source = backup / name
        if source.is_file():
            shutil.copy2(source, state / name)
    journal["status"] = "recovered"
    journal["recovered_at"] = utc_now()
    atomic_write_json(journal_path, journal)
    return True


def migrate_v1_task_state(
    target: Path,
    task_id: str,
    *,
    apply: bool,
    fail_after: int | None = None,
) -> dict[str, Any]:
    validate_task_id(task_id)
    state = task_state_dir(target, task_id)
    recovered = recover_incomplete_task_migration(state)
    package = read_json(state / "task-package.json")
    if package.get("schema_version") == TASK_SCHEMA:
        return {"task_id": task_id, "status": "already_migrated", "schema_version": TASK_SCHEMA, "recovered": recovered}
    if package.get("schema_version") != LEGACY_TASK_SCHEMA:
        raise HarnessError("任务包不是可迁移的 v1 对象", code="invalid_state")
    objects = [
        "task-package.json",
        "compiled-task.json",
        "freeze.json",
        "evidence-index.json",
        "context-receipts.jsonl",
        "authorization-receipts.jsonl",
    ]
    if not apply:
        return {
            "task_id": task_id,
            "status": "migration_preview",
            "from_schema": LEGACY_TASK_SCHEMA,
            "to_schema": TASK_SCHEMA,
            "objects": objects,
            "requires_apply": True,
            "recovered": recovered,
        }
    migrated = migrate_v1_package(target, package)
    fingerprint = package_fingerprint(migrated)
    old_compiled = read_json(state / "compiled-task.json")
    compiled = dict(old_compiled)
    compiled.update(
        {
            "schema_version": COMPILED_SCHEMA,
            "package_revision": migrated["package_revision"],
            "package_fingerprint": fingerprint,
            "control_status": "blocked",
            "verification_status": "needs_readmission",
            "next_action": "rerun_harness_for_readmission",
            "blockers": ["v1→v2 显式迁移完成，必须按 v2 合同重新准入"],
            "updated_at": utc_now(),
        }
    )
    old_freeze = read_json(state / "freeze.json")
    freeze = dict(old_freeze)
    freeze.update(
        {
            "schema_version": FREEZE_SCHEMA,
            "package_revision": migrated["package_revision"],
            "package_fingerprint": fingerprint,
            "git_state_snapshot": None,
            "migrated_at": utc_now(),
        }
    )
    old_evidence = read_json(state / "evidence-index.json")
    evidence_index = {
        "schema_version": EVIDENCE_SCHEMA,
        "evidence": [],
        "legacy_evidence": old_evidence.get("evidence", []),
        "legacy_evidence_read_only": True,
    }
    root = state / "migration-v1-v2"
    staging = root / "staging"
    backup = root / "backup"
    staging.mkdir(parents=True, exist_ok=True)
    backup.mkdir(parents=True, exist_ok=True)
    staged_values: dict[str, Any] = {
        "task-package.json": migrated,
        "compiled-task.json": compiled,
        "freeze.json": freeze,
        "evidence-index.json": evidence_index,
        "context-receipts.jsonl": "",
        "authorization-receipts.jsonl": "",
    }
    manifest_objects: dict[str, str] = {}
    for name, value in staged_values.items():
        destination = staging / name
        if isinstance(value, str):
            atomic_write_text(destination, value)
        else:
            atomic_write_json(destination, value)
        manifest_objects[name] = file_fingerprint(destination)
        shutil.copy2(state / name, backup / name)
    manifest = {
        "schema_version": "docs-harness/migration-manifest/v1",
        "task_id": task_id,
        "from_schema": LEGACY_TASK_SCHEMA,
        "to_schema": TASK_SCHEMA,
        "objects": manifest_objects,
        "created_at": utc_now(),
    }
    manifest["manifest_fingerprint"] = sha256_text(canonical_json(manifest))
    atomic_write_json(root / "manifest.json", manifest)
    journal = {"status": "applying", "objects": objects, "started_at": utc_now()}
    atomic_write_json(root / "journal.json", journal)
    replaced = 0
    try:
        for name in objects:
            os.replace(staging / name, state / name)
            replaced += 1
            if fail_after is not None and replaced >= fail_after:
                raise OSError("injected migration interruption")
    except OSError as exc:
        for name in objects:
            source = backup / name
            if source.is_file():
                shutil.copy2(source, state / name)
        journal["status"] = "rolled_back"
        journal["rolled_back_at"] = utc_now()
        atomic_write_json(root / "journal.json", journal)
        raise HarnessError("v1→v2 迁移中断，已按全对象备份回滚", code="migration_interrupted", exit_code=3) from exc
    history = state / "package-history"
    history.mkdir(exist_ok=True)
    atomic_write_json(history / f"task-package.v{package.get('package_revision', 1)}.json", package)
    journal["status"] = "completed"
    journal["completed_at"] = utc_now()
    atomic_write_json(root / "journal.json", journal)
    return {
        "task_id": task_id,
        "status": "migrated_needs_readmission",
        "from_schema": LEGACY_TASK_SCHEMA,
        "to_schema": TASK_SCHEMA,
        "package_revision": migrated["package_revision"],
        "manifest_fingerprint": manifest["manifest_fingerprint"],
        "objects": objects,
        "recovered": recovered,
        "next_action": "rerun_harness_for_readmission",
    }


def task_disposition_index_path(target: Path) -> Path:
    return runtime_root(target) / "task-dispositions.json"


@contextlib.contextmanager
def disposition_index_lock(target: Path) -> Iterator[None]:
    root = runtime_root(target)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "task-dispositions.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise HarnessError("任务处置索引正在被另一个进程更新", code="disposition_index_locked") from exc
    try:
        os.write(fd, f"pid={os.getpid()} at={utc_now()}\n".encode("utf-8"))
        os.close(fd)
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()


def read_task_disposition_index(target: Path) -> dict[str, Any]:
    path = task_disposition_index_path(target)
    if not path.is_file():
        return {"schema_version": TASK_DISPOSITION_INDEX_SCHEMA, "dispositions": []}
    value = read_json(path)
    if not isinstance(value, dict) or value.get("schema_version") != TASK_DISPOSITION_INDEX_SCHEMA or not isinstance(value.get("dispositions"), list):
        raise HarnessError("任务处置索引无效", code="invalid_disposition_index", exit_code=1)
    return value


def write_task_disposition_index(target: Path, index: dict[str, Any]) -> None:
    task_disposition_index_path(target).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(task_disposition_index_path(target), index)


def archived_dispositions(target: Path) -> dict[str, dict[str, Any]]:
    """已归档 v1 处置索引；源对象漂移或缺失时失败关闭。"""
    result: dict[str, dict[str, Any]] = {}
    for entry in read_task_disposition_index(target)["dispositions"]:
        if not isinstance(entry, dict) or entry.get("disposition") != "archived":
            continue
        task_id = str(entry.get("task_id", ""))
        validate_task_id(task_id)
        package_path = runtime_root(target) / task_id / "task-package.json"
        if not package_path.is_file() or file_fingerprint(package_path) != entry.get("source_object_fingerprint"):
            raise HarnessError("归档源对象指纹已变化，归档失效", code="archive_source_drift", exit_code=1)
        result[task_id] = entry
    return result


def task_lock_error(state: Path) -> HarnessError | None:
    """取消/归档预检：区分活动锁与超过 5 分钟的陈旧锁，与 state_lock 语义一致。"""
    lock = state / ".lock"
    if not lock.exists():
        return None
    try:
        age = time.time() - lock.stat().st_mtime
    except FileNotFoundError:
        return None
    if age > 300:
        return HarnessError("检测到超过 5 分钟的状态锁；需人工确认后清理", code="stale_lock")
    return HarnessError("同一任务正在被另一个进程更新", code="state_locked")


def task_cancel(target: Path, state: Path, task_id: str, reason_code: str | None, *, apply: bool) -> tuple[int, dict[str, Any]]:
    if not reason_code:
        raise HarnessError("task cancel 必须提供 --reason-code", code="missing_reason_code")
    if reason_code not in TASK_DISPOSITION_REASON_CODES:
        raise HarnessError("取消原因码不受支持", code="invalid_cancel_reason")
    package = read_json(state / "task-package.json")
    compiled = read_json(state / "compiled-task.json")
    freeze = read_json(state / "freeze.json")
    if isinstance(package, dict) and package.get("schema_version") == LEGACY_TASK_SCHEMA:
        raise HarnessError("v1 任务不能取消，只能只读归档", code="legacy_task_not_cancellable")
    if not isinstance(package, dict) or package.get("schema_version") != TASK_SCHEMA:
        raise HarnessError("任务包 schema 无效", code="invalid_state")
    if package_fingerprint(package) != compiled.get("package_fingerprint") or compiled.get("package_fingerprint") != freeze.get("package_fingerprint"):
        raise HarnessError("任务包与编译状态指纹不一致", code="stale_state")
    status = str(compiled.get("control_status"))
    fingerprint = package_fingerprint(package)
    if status == "cancelled":
        if compiled.get("cancellation_reason_code") != reason_code:
            raise HarnessError("任务已按其他原因取消，不得覆盖首次处置事实", code="task_cancel_conflict")
        return 0, {
            "action": "cancel",
            "task_id": task_id,
            "mode": "apply",
            "previous_status": compiled.get("cancellation_previous_status", "cancelled"),
            "new_status": "cancelled",
            "reason_code": reason_code,
            "task_fingerprint": fingerprint,
            "event_ref": compiled.get("cancellation_event_ref"),
            "idempotent": True,
        }
    if status in {"complete", "failed"}:
        raise HarnessError("终态任务不能取消", code="task_already_terminal")
    lock_error = task_lock_error(state)
    if lock_error is not None:
        raise lock_error
    if not apply:
        return 0, {
            "action": "cancel",
            "task_id": task_id,
            "mode": "preview",
            "previous_status": status,
            "new_status": "cancelled",
            "reason_code": reason_code,
            "task_fingerprint": fingerprint,
            "event_ref": None,
            "idempotent": False,
        }
    with state_lock(state):
        current = read_json(state / "compiled-task.json")
        if current.get("control_status") != status:
            raise HarnessError("取消期间任务状态已变化，拒绝覆盖", code="task_state_changed")
        if current.get("package_fingerprint") != fingerprint:
            raise HarnessError("任务包与编译状态指纹不一致", code="stale_state")
        events = read_jsonl(state / "events.jsonl")
        recorded = next(
            (
                index + 1
                for index, item in enumerate(events)
                if item.get("event") == "task_cancelled" and item.get("reason_code") == reason_code
            ),
            None,
        )
        if recorded is not None:
            event_ref = f"events.jsonl#{recorded}"
        else:
            event_ref = f"events.jsonl#{len(events) + 1}"
            append_task_event(
                state,
                package,
                event="task_cancelled",
                phase="lifecycle",
                reason_code=reason_code,
                previous_status=status,
            )
        cancelled_at = utc_now()
        current.update(
            {
                "control_status": "cancelled",
                "next_action": "none",
                "cancelled_at": cancelled_at,
                "cancellation_reason_code": reason_code,
                "cancellation_previous_status": status,
                "cancellation_event_ref": event_ref,
                "updated_at": cancelled_at,
            }
        )
        atomic_write_json(state / "compiled-task.json", current)
    return 0, {
        "action": "cancel",
        "task_id": task_id,
        "mode": "apply",
        "previous_status": status,
        "new_status": "cancelled",
        "reason_code": reason_code,
        "task_fingerprint": fingerprint,
        "event_ref": event_ref,
        "idempotent": False,
    }


def task_archive(target: Path, state: Path, task_id: str, reason_code: str | None, *, apply: bool) -> tuple[int, dict[str, Any]]:
    if not reason_code:
        raise HarnessError("task archive 必须提供 --reason-code", code="missing_reason_code")
    if reason_code not in TASK_DISPOSITION_REASON_CODES:
        raise HarnessError("归档原因码不受支持", code="invalid_archive_reason")
    package = read_json(state / "task-package.json")
    if not isinstance(package, dict) or package.get("schema_version") != LEGACY_TASK_SCHEMA:
        raise HarnessError("只有 v1 只读任务可以归档；v2 任务使用 task cancel", code="invalid_archive_target")
    source_fingerprint = file_fingerprint(state / "task-package.json")
    if not apply:
        index = read_task_disposition_index(target)
        existing = next(
            (item for item in index["dispositions"] if isinstance(item, dict) and item.get("task_id") == task_id),
            None,
        )
        if existing is not None:
            if existing.get("source_object_fingerprint") != source_fingerprint:
                raise HarnessError("归档源对象指纹已变化，归档失效", code="archive_source_drift", exit_code=1)
            if existing.get("reason_code") != reason_code:
                raise HarnessError("任务已按其他原因归档，不得覆盖首次处置事实", code="task_archive_conflict")
            return 0, {**existing, "action": "archive", "mode": "apply", "idempotent": True}
        entry = {
            "task_id": task_id,
            "source_schema": package["schema_version"],
            "source_object_fingerprint": source_fingerprint,
            "disposition": "archived",
            "reason_code": reason_code,
            "recorded_at": utc_now(),
        }
        return 0, {**entry, "action": "archive", "mode": "preview", "idempotent": False}
    with disposition_index_lock(target):
        index = read_task_disposition_index(target)
        existing = next(
            (item for item in index["dispositions"] if isinstance(item, dict) and item.get("task_id") == task_id),
            None,
        )
        if existing is not None:
            if existing.get("source_object_fingerprint") != source_fingerprint:
                raise HarnessError("归档源对象指纹已变化，归档失效", code="archive_source_drift", exit_code=1)
            if existing.get("reason_code") != reason_code:
                raise HarnessError("任务已按其他原因归档，不得覆盖首次处置事实", code="task_archive_conflict")
            return 0, {**existing, "action": "archive", "mode": "apply", "idempotent": True}
        entry = {
            "task_id": task_id,
            "source_schema": package["schema_version"],
            "source_object_fingerprint": source_fingerprint,
            "disposition": "archived",
            "reason_code": reason_code,
            "recorded_at": utc_now(),
        }
        index["dispositions"].append(entry)
        write_task_disposition_index(target, index)
    return 0, {**entry, "action": "archive", "mode": "apply", "idempotent": False}


def task_list(target: Path, *, include_archived: bool) -> tuple[int, dict[str, Any]]:
    archived = archived_dispositions(target)
    tasks: list[dict[str, Any]] = []
    root = runtime_root(target)
    for state in sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []:
        package_path = state / "task-package.json"
        compiled_path = state / "compiled-task.json"
        if not package_path.is_file() or not compiled_path.is_file():
            continue
        with contextlib.suppress(HarnessError):
            package = read_json(package_path)
            compiled = read_json(compiled_path)
            task_id = str(package.get("task_id") or state.name)
            if task_id in archived and not include_archived:
                continue
            tasks.append(
                {
                    "task_id": task_id,
                    "schema_version": package.get("schema_version"),
                    "control_status": compiled.get("control_status"),
                    "disposition": "archived" if task_id in archived else None,
                }
            )
    return 0, {"action": "list", "tasks": tasks, "count": len(tasks), "archived_count": len(archived)}


def task_state_fingerprint(state: Path) -> str:
    parts: list[str] = []
    for path in sorted(state.rglob("*")):
        if path.is_file() and path.name != ".lock":
            parts.append(f"{path.relative_to(state)}:{file_fingerprint(path)}")
    return sha256_text("\n".join(parts))


def task_prune_candidates_path(target: Path) -> Path:
    return runtime_root(target) / "task-prune-candidates.json"


def task_prune_candidate_for_state(
    target: Path,
    state: Path,
    cutoff: dt.datetime,
    archived: dict[str, dict[str, Any]],
    jobs: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    if (state / ".lock").exists():
        return None
    package_path = state / "task-package.json"
    compiled_path = state / "compiled-task.json"
    if not package_path.is_file() or not compiled_path.is_file():
        return None
    try:
        package = read_json(package_path)
        compiled = read_json(compiled_path)
    except HarnessError:
        return None
    task_id = str(package.get("task_id") or state.name)
    if any(
        str(job.get("parent_task_id")) == task_id
        and (
            job.get("status") not in BACKGROUND_TERMINAL_STATES
            or job.get("status") == "completed_with_finding"
            or job.get("task_kind") == "critical_followup"
        )
        for job in jobs
    ):
        return None
    schema = package.get("schema_version")
    terminal_at: Any = None
    disposition: str | None = None
    control_status: Any = compiled.get("control_status")
    if schema == TASK_SCHEMA:
        if control_status not in ACTIVE_TASK_TERMINAL_STATUSES:
            return None
        try:
            freeze = read_json(state / "freeze.json")
        except HarnessError:
            return None
        if (
            package_fingerprint(package) != compiled.get("package_fingerprint")
            or compiled.get("package_fingerprint") != freeze.get("package_fingerprint")
        ):
            return None
        if not read_jsonl(state / "events.jsonl"):
            return None
        terminal_at = compiled.get("cancelled_at") or compiled.get("completed_at") or compiled.get("failed_at")
    elif schema == LEGACY_TASK_SCHEMA:
        entry = archived.get(task_id)
        if entry is None:
            return None
        disposition = "archived"
        terminal_at = entry.get("recorded_at")
    else:
        return None
    if not terminal_at:
        return None
    try:
        when = dt.datetime.fromisoformat(str(terminal_at).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if when > cutoff:
        return None
    return {
        "task_id": task_id,
        "schema_version": schema,
        "control_status": control_status,
        "disposition": disposition,
        "terminal_at": terminal_at,
        "state_fingerprint": task_state_fingerprint(state),
    }


def task_prune(target: Path, *, older_than: int | None, apply: bool, dry_run: bool) -> tuple[int, dict[str, Any]]:
    if apply and dry_run:
        raise HarnessError("--apply 与 --dry-run 不能同时使用", code="invalid_prune_request")
    if older_than is None or older_than < 0:
        raise HarnessError("--older-than 必须是非负天数", code="invalid_prune_request")
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=older_than)
    archived = archived_dispositions(target)
    jobs = list_background_jobs(target)
    root = runtime_root(target)
    states = sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []
    if not apply:
        candidates = [
            candidate
            for state in states
            if (candidate := task_prune_candidate_for_state(target, state, cutoff, archived, jobs)) is not None
        ]
        atomic_write_json(
            task_prune_candidates_path(target),
            {
                "schema_version": "docs-harness/task-prune-candidates/v1",
                "older_than": older_than,
                "generated_at": utc_now(),
                "candidates": candidates,
            },
        )
        return 0, {"action": "prune", "mode": "dry_run", "candidates": candidates, "removed": []}
    frozen_path = task_prune_candidates_path(target)
    if not frozen_path.is_file():
        raise HarnessError("task prune --apply 需要先执行 dry-run 冻结候选清单", code="prune_candidates_missing", exit_code=3)
    frozen = read_json(frozen_path)
    if not isinstance(frozen, dict) or frozen.get("schema_version") != "docs-harness/task-prune-candidates/v1" or not isinstance(frozen.get("candidates"), list):
        raise HarnessError("任务 prune 候选清单无效", code="invalid_prune_candidates", exit_code=1)
    removed: list[str] = []
    with disposition_index_lock(target):
        index = read_task_disposition_index(target)
        index_changed = False
        for item in frozen["candidates"]:
            state = root / str(item.get("task_id", ""))
            if not state.is_dir() or state.parent != root:
                continue
            current = task_prune_candidate_for_state(target, state, cutoff, archived, jobs)
            if current is None or current["state_fingerprint"] != item.get("state_fingerprint"):
                continue
            if (state / ".lock").exists():
                continue
            shutil.rmtree(state)
            if current["disposition"] == "archived":
                index["dispositions"] = [entry for entry in index["dispositions"] if entry.get("task_id") != current["task_id"]]
                index_changed = True
            removed.append(current["task_id"])
        if index_changed:
            write_task_disposition_index(target, index)
    return 0, {"action": "prune", "mode": "apply", "candidates": frozen["candidates"], "removed": removed}


def task_adopt(
    target: Path,
    state: Path,
    task_id: str,
    outcome: str | None,
    external_evidence: str | None,
    bypass_reason: str | None,
) -> tuple[int, dict[str, Any]]:
    package_path = state / "task-package.json"
    compiled_path = state / "compiled-task.json"
    if not package_path.is_file() or not compiled_path.is_file():
        raise HarnessError(f"任务状态不完整：{task_id}", code="missing_task_state")
    package = read_json(package_path)
    compiled = read_json(compiled_path)
    terminal_statuses = {"complete", "cancelled", "failed"}
    if compiled.get("control_status") in terminal_statuses:
        raise HarnessError(
            f"任务已处于终态({compiled.get('control_status')})，不可补录",
            code="task_already_terminal",
            suggested_fix=f"harness task status --target . --task-id {task_id} 查看当前状态",
        )
    if not outcome or not outcome.strip():
        raise HarnessError(
            "task adopt 必须提供 --outcome 描述外部完成结果",
            code="missing_outcome",
            suggested_fix="harness task adopt --target . --task-id <id> --outcome '完成结果摘要'",
        )
    evidence_refs: list[str] = []
    if external_evidence:
        evidence_path = Path(external_evidence).expanduser().resolve()
        if not evidence_path.is_file():
            raise HarnessError(f"外部证据文件不存在：{evidence_path}", code="missing_evidence_file")
        managed = store_managed_artifact(
            state,
            "evidence",
            f"adoption-evidence.{utc_now().replace(':', '-')}.json",
            evidence_path.read_text(encoding="utf-8"),
        )
        evidence_refs.append(str(managed))
    adoption_record = {
        "schema_version": "docs-harness/task-adoption/v1",
        "task_id": task_id,
        "adopted_at": utc_now(),
        "adopted_by": "user",
        "original_package_fingerprint": package_fingerprint(package),
        "bypass_reason": bypass_reason or "not_specified",
        "outcome_summary": outcome.strip(),
        "external_evidence_refs": evidence_refs,
        "verification_status": "adopted_external",
    }
    with state_lock(state):
        compiled["control_status"] = "complete"
        compiled["verification_status"] = "adopted_external"
        compiled["adopted_externally"] = True
        compiled["adoption_record"] = adoption_record
        atomic_write_json(compiled_path, compiled)
        append_task_event(
            state,
            package,
            event="task_adopted",
            phase="completion",
            reason_code="external_adoption",
            adoption_record=adoption_record,
        )
    return 0, {
        "action": "adopt",
        "task_id": task_id,
        "status": "adopted",
        "adoption_record": adoption_record,
        "next_action": "ledger_add",
        "message": f"任务已补录。建议将本次经验添加到质量账本：harness ledger add --target . --task-id {task_id} --review <review-file>",
    }


def task_overhead_summary(state: Path) -> dict[str, Any]:
    """harness 自身耗时复算口径：各阶段 duration_ms 求和 vs 首末事件墙钟。"""
    events_path = state / "events.jsonl"
    events = read_jsonl(events_path) if events_path.is_file() else []
    harness_total_ms = sum(int(item.get("duration_ms", 0)) for item in events)
    timestamps: list[dt.datetime] = []
    for item in events:
        raw = item.get("at") or item.get("started_at")
        if not isinstance(raw, str):
            continue
        try:
            timestamps.append(dt.datetime.fromisoformat(raw.replace("Z", "+00:00")))
        except ValueError:
            continue
    wall_clock_ms = 0
    if len(timestamps) >= 2:
        wall_clock_ms = max(0, int((max(timestamps) - min(timestamps)).total_seconds() * 1000))
    return {
        "harness_total_ms": harness_total_ms,
        "wall_clock_ms": wall_clock_ms,
        "harness_share": (harness_total_ms / wall_clock_ms) if wall_clock_ms > 0 else None,
    }


def task_changes_preview(target: Path, state: Path, task_id: str) -> tuple[int, dict[str, Any]]:
    """只读预览当前工作区相对冻结基线的变化，供证据 write_set 零试探对齐。"""
    package = read_json(state / "task-package.json")
    if package.get("schema_version") == LEGACY_TASK_SCHEMA:
        raise HarnessError("v1 任务不支持 changes-preview，需先迁移", code="legacy_task_requires_migration")
    freeze = read_json(state / "freeze.json")
    if not isinstance(freeze.get("workspace_snapshot"), dict):
        raise HarnessError("冻结基线缺少 workspace_snapshot，无法预览变化", code="invalid_freeze_snapshot")
    changed = snapshot_changes(freeze["workspace_snapshot"], workspace_snapshot(target))
    write_scope = package.get("write_scope", package.get("allowed_scope", []))
    read_scope = package.get("read_scope", [])
    in_scope = sorted(path for path in changed if scope_covers(path, write_scope))
    outside_scope = sorted(path for path in changed if not scope_covers(path, write_scope))
    read_set_drift = sorted(
        path for path in changed if path not in in_scope and scope_covers(path, read_scope)
    )
    return 0, {
        "action": "changes-preview",
        "task_id": task_id,
        "changed_paths": changed,
        "in_scope": in_scope,
        "outside_scope": outside_scope,
        "read_set_drift": read_set_drift,
        "next_action": "按 changed_paths 对齐证据 write_set 后 verify",
    }


def command_task(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    if args.action == "list":
        return task_list(target, include_archived=bool(args.include_archived))
    if args.action == "prune":
        return task_prune(target, older_than=args.older_than, apply=bool(args.apply), dry_run=bool(args.dry_run))
    if not args.task_id:
        raise HarnessError(f"task {args.action} 必须提供 --task-id", code="missing_task_id")
    validate_task_id(args.task_id)
    state = task_state_dir(target, args.task_id)
    if args.action == "status":
        package = read_json(state / "task-package.json")
        compiled = read_json(state / "compiled-task.json")
        legacy = package.get("schema_version") == LEGACY_TASK_SCHEMA
        status_payload: dict[str, Any] = {
            "task_id": args.task_id,
            "schema_version": package.get("schema_version"),
            "package_revision": package.get("package_revision"),
            "control_status": compiled.get("control_status"),
            "compatibility_mode": "v1_read_only" if legacy else "v2",
            "migration_required": legacy,
            "overhead_summary": task_overhead_summary(state),
        }
        if completion_manifest_valid(package.get("completion_manifest")):
            status_payload["evidence_checklist"] = evidence_checklist_payload(state, package)
            status_payload["pending_context_receipts"] = pending_context_receipts(state, package, target, compiled)
        return 0, status_payload
    if args.action == "changes-preview":
        return task_changes_preview(target, state, args.task_id)
    if args.action == "cancel":
        return task_cancel(target, state, args.task_id, args.reason_code, apply=bool(args.apply))
    if args.action == "archive":
        return task_archive(target, state, args.task_id, args.reason_code, apply=bool(args.apply))
    if args.action == "adopt":
        return task_adopt(target, state, args.task_id, args.outcome, args.external_evidence, args.bypass_reason)
    return 0, migrate_v1_task_state(target, args.task_id, apply=bool(args.apply))


def generate_task_id() -> str:
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"dh-{stamp}-{uuid.uuid4().hex[:10]}"


def normalize_task_text(task: str) -> str:
    return " ".join(task.split())


def active_task_key(target: Path, task: str, facts: dict[str, Any]) -> str:
    """活动任务幂等键：相同 target、任务、facts 与初始工作区返回同一任务。"""
    return sha256_text(
        canonical_json(
            {
                "target_identity": target_identity(target),
                "task": normalize_task_text(task),
                "facts_fingerprint": sha256_text(canonical_json(facts or {})),
                "workspace_snapshot_fingerprint": sha256_text(canonical_json(workspace_snapshot(target))),
            }
        )
    )


ACTIVE_TASK_TERMINAL_STATUSES = {"complete", "cancelled", "failed"}
# blocked 任务不参与幂等复用：重新 run 时必须重新校验规则与合同，不得返回陈旧阻断原因。
ACTIVE_TASK_NO_REUSE_STATUSES = ACTIVE_TASK_TERMINAL_STATUSES | {"blocked"}


def find_existing_active_task(target: Path, key: str) -> Path | None:
    """查找相同 active task key 的可复用任务；终态与 blocked 任务不复用。"""
    root = runtime_root(target)
    if not root.is_dir():
        return None
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        package_path = entry / "task-package.json"
        compiled_path = entry / "compiled-task.json"
        if not package_path.is_file() or not compiled_path.is_file():
            continue
        package = read_json(package_path)
        if package.get("active_task_key") != key:
            continue
        compiled = read_json(compiled_path)
        if compiled.get("control_status") in ACTIVE_TASK_NO_REUSE_STATUSES:
            continue
        return entry
    return None


def extract_markdown_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1).strip().casefold()] = text[start:end].strip()
    return result


def plan_value(plan: Any, field: str) -> Any:
    aliases = PLAN_FIELD_ALIASES.get(field, (field,))
    if isinstance(plan, dict):
        normalized = {str(key).casefold().replace("_", " "): value for key, value in plan.items()}
        for alias in aliases:
            for key, value in normalized.items():
                if alias.casefold() == key or alias.casefold() in key:
                    return value
        return None
    sections = extract_markdown_sections(str(plan))
    for alias in aliases:
        for key, value in sections.items():
            if alias.casefold() == key or alias.casefold() in key:
                return value
    return None


def load_plan(path: str) -> tuple[Path, Any]:
    plan_path, text = load_input_file(
        path,
        argument="--plan",
        max_bytes=2 * 1024 * 1024,
        error_code="invalid_plan",
    )
    if plan_path.suffix.casefold() == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HarnessError("方案 JSON 无效", code="invalid_plan") from exc
        if not isinstance(value, dict):
            raise HarnessError("方案 JSON 必须是对象", code="invalid_plan")
        return plan_path, value
    return plan_path, text


def validate_plan(plan: Any, fields: Sequence[str]) -> list[str]:
    missing: list[str] = []
    for field in fields:
        value = plan_value(plan, field)
        if value is None or (isinstance(value, str) and not value.strip()) or value == []:
            missing.append(field)
    return missing


ARTIFACT_KINDS = ("plans", "authorizations", "evidence", "verification")
PLAN_SCOPE_FIELD = "执行范围"


def artifact_store_dir(state: Path, kind: str) -> Path:
    """控制器所有的受管工件目录；调用者临时文件清理后仍然有效。"""
    if kind not in ARTIFACT_KINDS:
        raise HarnessError("受管工件类别无效", code="invalid_artifact_kind")
    path = state / "artifacts" / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_managed_artifact(state: Path, kind: str, name: str, content: str) -> Path:
    path = artifact_store_dir(state, kind) / name
    atomic_write_text(path, content)
    return path


def ingest_managed_plan(
    state: Path,
    package: dict[str, Any],
    plan_path: Path,
    *,
    kind: str,
    content: str | None = None,
) -> dict[str, Any]:
    """把计划正文摄取为不可变受管副本，并记录调用者来源。"""
    body = plan_path.read_text(encoding="utf-8") if content is None else content
    suffix = plan_path.suffix.casefold() or ".txt"
    stored = store_managed_artifact(state, "plans", f"{kind}.v{package['package_revision']}{suffix}", body)
    return {
        "schema_version": MANAGED_PLAN_SCHEMA,
        "artifact_ref": str(stored),
        "artifact_fingerprint": file_fingerprint(stored),
        "source_ref": str(plan_path),
        "source_fingerprint": file_fingerprint(plan_path),
        "ingested_at": utc_now(),
    }


def load_managed_plan(ref: Any, fingerprint: Any) -> Any:
    path = Path(str(ref or ""))
    if not path.is_file() or file_fingerprint(path) != fingerprint:
        raise HarnessError("受管计划副本不可用，必须重新提交完整方案", code="managed_plan_unavailable")
    _, plan = load_plan(str(path))
    return plan


def validate_plan_delta_binding(patch: Any, package: dict[str, Any], contract: dict[str, Any]) -> None:
    """计划补丁必须绑定当前任务、原计划工件与目标计划合同。"""
    if not isinstance(patch, dict):
        return
    bindings = (
        ("task_id", package["task_id"]),
        ("base_plan_fingerprint", contract.get("base_plan_fingerprint")),
        ("plan_contract_fingerprint", contract.get("plan_contract_fingerprint")),
    )
    for key, expected in bindings:
        declared = patch.get(key)
        if declared is not None and str(declared) != str(expected):
            raise HarnessError(f"计划补丁绑定的 {key} 与当前任务不一致", code="plan_delta_conflict")


def merge_plan_delta(
    base: Any,
    patch: Any,
    *,
    missing_fields: Sequence[str],
    frozen_fields: Sequence[str],
) -> Any:
    """补丁只能补齐控制器列出的缺失字段；已冻结字段不得被改写。"""
    for field in frozen_fields:
        if field == PLAN_SCOPE_FIELD:
            continue
        patched = plan_value(patch, field)
        if patched is None:
            continue
        if canonical_json(patched) != canonical_json(plan_value(base, field)):
            raise HarnessError(f"计划补丁不得改写已冻结字段：{field}", code="plan_delta_conflict")
    fillable = list(dict.fromkeys(list(missing_fields) + [PLAN_SCOPE_FIELD]))
    if isinstance(base, dict):
        merged = dict(base)
        for field in fillable:
            value = plan_value(patch, field)
            if value is not None:
                merged[field] = value
        return merged
    additions: list[str] = []
    for field in fillable:
        value = plan_value(patch, field)
        if value is None:
            continue
        body = value if isinstance(value, str) else canonical_json(value)
        additions.append(f"## {field}\n\n{body}\n")
    if not additions:
        return base
    return str(base).rstrip("\n") + "\n\n" + "\n".join(additions)


def plan_delta_contract(
    package: dict[str, Any],
    managed: dict[str, Any],
    delta: dict[str, Any],
    missing_fields: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": PLAN_DELTA_SCHEMA,
        "task_id": package["task_id"],
        "package_revision": package["package_revision"],
        "plan_contract_fingerprint": plan_contract_fingerprint(package),
        "base_plan_ref": managed["artifact_ref"],
        "base_plan_fingerprint": managed["artifact_fingerprint"],
        "base_plan_source_ref": managed["source_ref"],
        "frozen_plan_fields": [item for item in package["plan_fields"] if item not in set(missing_fields)],
        "missing_plan_fields": list(missing_fields),
        "added_gates": list(delta.get("added_gates", [])),
        "added_plan_fields": list(delta.get("added_plan_fields", [])),
        "added_evidence_types": list(delta.get("added_evidence_types", [])),
        "frozen_scope": list(package["allowed_scope"]),
        "created_at": utc_now(),
    }


def freeze_managed_plan(
    state: Path,
    package: dict[str, Any],
    compiled: dict[str, Any],
    plan_path: Path,
    *,
    plan: Any = None,
) -> dict[str, Any]:
    """正式计划一次冻结：引用受管副本，不再依赖调用者临时文件。"""
    content = None
    if plan is not None:
        content = json.dumps(plan, ensure_ascii=False, indent=2) + "\n" if isinstance(plan, dict) else str(plan)
    managed = ingest_managed_plan(state, package, plan_path, kind="plan", content=content)
    compiled["plan_ref"] = managed["artifact_ref"]
    compiled["plan_fingerprint"] = managed["artifact_fingerprint"]
    compiled["plan_artifact"] = managed
    compiled["plan_delta_contract"] = None
    compiled["blockers"] = []
    return managed


def read_ref(target: Path, ref: str) -> dict[str, str]:
    path_part, _, anchor = ref.partition("#")
    path = (target / path_part).resolve()
    try:
        path.relative_to(target)
    except ValueError as exc:
        raise HarnessError(f"项目事实引用越界：{ref}", code="invalid_fact_ref") from exc
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise HarnessError(f"项目事实不可用：{ref}", code="missing_fact")
    content = path.read_text(encoding="utf-8")
    if anchor:
        sections = extract_markdown_sections(content)
        match = next((value for heading, value in sections.items() if anchor.casefold() in heading), None)
        if match is None:
            raise HarnessError(f"项目事实章节不存在：{ref}", code="missing_fact")
        content = match
    return {"ref": ref, "fingerprint": sha256_text(content), "content": content}


def rule_content(package: dict[str, Any], rule_id: str) -> dict[str, str]:
    rule = next((item for item in package["matched_rules"] if item["rule_id"] == rule_id), None)
    if not rule:
        raise HarnessError(f"任务包未命中规则：{rule_id}", code="invalid_rule_ref")
    path = Path(rule["path"])
    if not path.is_file():
        raise HarnessError(f"规则文件不存在：{rule_id}", code="missing_rule")
    metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    fingerprint = sha256_text(body)
    if metadata.get("status") != "active" or fingerprint != rule["content_fingerprint"]:
        raise HarnessError(f"规则已变化：{rule_id}", code="stale_rule")
    return {"ref": f"rule:{rule_id}", "fingerprint": fingerprint, "content": body}


def context_set_fingerprint(
    package: dict[str, Any],
    target: Path,
    rule_ids: Sequence[str],
    project_fact_refs: Sequence[str],
) -> tuple[str, list[str]]:
    entries: list[dict[str, str]] = []
    for rule_id in rule_ids:
        item = rule_content(package, rule_id)
        entries.append({"ref": item["ref"], "fingerprint": item["fingerprint"]})
    for ref in project_fact_refs:
        item = read_ref(target, ref)
        entries.append({"ref": item["ref"], "fingerprint": item["fingerprint"]})
    entries = sorted(entries, key=lambda item: (item["ref"], item["fingerprint"]))
    return sha256_text(canonical_json(entries)), list(dict.fromkeys(item["fingerprint"] for item in entries))


def find_context_receipt(
    state: Path,
    package: dict[str, Any],
    target: Path,
    *,
    stage: str | None = None,
    work_package: str | None = None,
) -> dict[str, Any] | None:
    receipts = read_jsonl(state / "context-receipts.jsonl")
    if work_package is not None:
        schedule = package["context_schedule"]["work_packages"].get(work_package)
        expected_stage = "work_package"
    else:
        expected_stage = stage
        schedule = package["context_schedule"].get(str(stage)) if stage is not None else None
    if schedule is None:
        return None
    try:
        content_set, _ = context_set_fingerprint(
            package,
            target,
            schedule.get("rule_ids", []),
            schedule.get("project_fact_refs", []),
        )
    except HarnessError:
        return None
    for receipt in reversed(receipts):
        if receipt.get("schema_version") != RECEIPT_SCHEMA:
            continue
        if receipt.get("task_id") != package["task_id"]:
            continue
        if receipt.get("target_identity") != target_identity(target):
            continue
        if receipt.get("compiler_contract") != COMPILER_CONTRACT:
            continue
        if expected_stage is not None and receipt.get("stage") != expected_stage:
            continue
        if work_package is not None and receipt.get("work_package_id") != work_package:
            continue
        if receipt.get("content_set_fingerprint") == content_set:
            return receipt
    return None


def prior_context_content_fingerprints(
    state: Path,
    package: dict[str, Any],
    target: Path,
) -> set[str]:
    """已在同一 task/target/compiler contract 下交付过的内容正文指纹；跨 stage 不重复交付。"""
    fingerprints: set[str] = set()
    identity = target_identity(target)
    for receipt in read_jsonl(state / "context-receipts.jsonl"):
        if receipt.get("schema_version") != RECEIPT_SCHEMA:
            continue
        if receipt.get("task_id") != package["task_id"] or receipt.get("target_identity") != identity:
            continue
        if receipt.get("compiler_contract") != COMPILER_CONTRACT:
            continue
        fingerprints.update(
            item
            for item in receipt.get("delivered_content_fingerprints", receipt.get("content_fingerprints", []))
            if isinstance(item, str) and item.startswith("sha256:")
        )
    return fingerprints


def context_receipt_valid(
    state: Path,
    package: dict[str, Any],
    target: Path,
    *,
    stage: str | None = None,
    work_package: str | None = None,
) -> bool:
    return find_context_receipt(
        state,
        package,
        target,
        stage=stage,
        work_package=work_package,
    ) is not None


def command_context(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    started = time.monotonic()
    target = safe_target(args.target)
    state, package, compiled, _ = load_state(target, args.task_id)
    if args.work_package:
        work = next((item for item in package["work_packages"] if item["work_package_id"] == args.work_package), None)
        if not work:
            raise HarnessError("工作包不存在", code="missing_work_package")
        schedule = package["context_schedule"]["work_packages"][args.work_package]
        stage = "work_package"
    else:
        stage = args.stage
        schedule = package["context_schedule"].get(stage)
        if schedule is None:
            raise HarnessError("上下文阶段无效", code="invalid_context_stage")
    contents: list[dict[str, str]] = []
    seen: set[str] = set()
    for rule_id in schedule.get("rule_ids", []):
        item = rule_content(package, rule_id)
        if item["fingerprint"] not in seen:
            contents.append(item)
            seen.add(item["fingerprint"])
    for ref in schedule.get("project_fact_refs", []):
        item = read_ref(target, ref)
        if item["fingerprint"] not in seen:
            contents.append(item)
            seen.add(item["fingerprint"])
    content_set, content_fingerprints = context_set_fingerprint(
        package,
        target,
        schedule.get("rule_ids", []),
        schedule.get("project_fact_refs", []),
    )
    cached_receipt = find_context_receipt(
        state,
        package,
        target,
        stage=stage if stage != "work_package" else None,
        work_package=args.work_package,
    )
    prior_fingerprints = prior_context_content_fingerprints(state, package, target)
    delivered_contents = (
        []
        if cached_receipt is not None
        else [item for item in contents if item["fingerprint"] not in prior_fingerprints]
    )
    context_delta = cached_receipt is None and bool(prior_fingerprints)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "task_id": package["task_id"],
        "package_revision": package["package_revision"],
        "package_fingerprint": package_fingerprint(package),
        "target_identity": target_identity(target),
        "compiler_contract": COMPILER_CONTRACT,
        "stage": stage,
        "work_package_id": args.work_package,
        "rule_ids": schedule.get("rule_ids", []),
        "project_fact_refs": schedule.get("project_fact_refs", []),
        "content_fingerprints": content_fingerprints,
        "delivered_content_fingerprints": [item["fingerprint"] for item in delivered_contents],
        "reused_content_fingerprints": [
            item["fingerprint"] for item in contents if item["fingerprint"] in prior_fingerprints
        ],
        "content_set_fingerprint": content_set,
        "loaded_at": utc_now(),
    }
    if cached_receipt is None:
        with state_lock(state):
            append_jsonl(state / "context-receipts.jsonl", receipt)
    else:
        receipt = cached_receipt
    append_task_event(
        state,
        package,
        event=("context_reused" if cached_receipt is not None else ("context_delta_loaded" if context_delta else "context_loaded")),
        phase="context",
        reason_code=("context_cache_hit" if cached_receipt is not None else ("context_delta_loaded" if context_delta else "context_content_loaded")),
        duration_ms=int((time.monotonic() - started) * 1000),
        context_cache_hit=cached_receipt is not None,
        context_delta=context_delta,
        loaded_content_count=len(delivered_contents),
        reused_content_count=max(0, len(contents) - len(delivered_contents)),
        stage=stage,
    )
    payload = {
        "task_id": package["task_id"],
        "stage": stage,
        "work_package_id": args.work_package,
        "control_status": compiled["control_status"],
        "context_cache_hit": cached_receipt is not None,
        "context_delta": context_delta,
        "loaded_content_count": len(delivered_contents),
        "reused_content_count": max(0, len(contents) - len(delivered_contents)),
        "rules": [item for item in delivered_contents if item["ref"].startswith("rule:")],
        "project_facts": [item for item in delivered_contents if not item["ref"].startswith("rule:")],
        "knowledge_context": package.get("knowledge_context", {}),
        "receipt": receipt,
    }
    if stage == "plan":
        payload["plan_contract"] = plan_contract_payload(package)
        payload.update(
            next_step_payload(
                target,
                state,
                package,
                "submit_plan",
                reason_code="plan_submission_required",
            )
        )
    elif stage == "action":
        followup = (
            "verify"
            if compiled.get("verification_status") == "needs_evidence"
            and compiled.get("next_action") == "load_action_context"
            else "execute"
        )
        payload.update(
            next_step_payload(
                target,
                state,
                package,
                followup,
                reason_code=("incremental_action_context_loaded" if followup == "verify" else "action_context_loaded"),
            )
        )
    elif stage == "work_package":
        payload.update(
            next_step_payload(
                target,
                state,
                package,
                "begin_work_package",
                reason_code="work_package_context_loaded",
                work_package=args.work_package,
            )
        )
    else:
        payload.update(
            next_step_payload(
                target,
                state,
                package,
                "verify",
                reason_code="acceptance_context_loaded",
            )
        )
    return 0, payload


def authorization_receipt(path: str, package: dict[str, Any]) -> dict[str, Any]:
    auth_path, value = load_json_object_file(
        path,
        argument="--authorization",
        max_bytes=1024 * 1024,
        error_code="invalid_authorization",
    )
    if value.get("approved") is not True:
        raise HarnessError("授权必须是 approved=true 的 JSON 对象", code="invalid_authorization")
    actions = normalize_string_list(value.get("authorized_actions"), "authorized_actions")
    scope = validate_scope(normalize_string_list(value.get("authorized_scope"), "authorized_scope"))
    external_values = normalize_string_list(value.get("authorized_external_scope"), "authorized_external_scope")
    if not external_values and isinstance(value.get("external_target"), str):
        external_values = [str(value["external_target"])]
    authorized_external_scope = validate_external_scope(external_values)
    authorized_git_scope = validate_scope(
        normalize_string_list(value.get("authorized_git_scope"), "authorized_git_scope"),
        field="authorized_git_scope",
        allow_git_resources=True,
    )
    missing_actions = set(package["authorization_requirements"]) - set(actions)
    uncovered_scope = [item for item in package["allowed_scope"] if not scope_covers(item, scope)]
    uncovered_external = [item for item in package.get("external_scope", []) if item not in authorized_external_scope]
    uncovered_git = [item for item in package.get("git_scope", []) if item not in authorized_git_scope] if package.get("authorization_requirements") and package.get("git_scope") else []
    if missing_actions or uncovered_scope or uncovered_external or uncovered_git:
        missing_items: list[dict[str, Any]] = []
        for action in sorted(missing_actions):
            missing_items.append({
                "scope_type": "authorized_actions",
                "required": action,
                "authorized": sorted(actions),
                "hint": "authorized_actions 必须包含任务包要求的全部授权动作",
            })
        for item in uncovered_scope:
            missing_items.append({
                "scope_type": "write_scope",
                "required": item,
                "authorized": scope,
                "hint": "write_scope 必须与任务包 allowed_scope 的路径形式逐字一致（含 glob）",
            })
        for item in uncovered_external:
            missing_items.append({
                "scope_type": "external_scope",
                "required": item,
                "authorized": authorized_external_scope,
                "hint": "external_scope 格式为 <remote>，不是 git-remote:<remote>",
            })
        for item in uncovered_git:
            missing_items.append({
                "scope_type": "git_scope",
                "required": item,
                "authorized": authorized_git_scope,
                "hint": "git_scope 格式为 .git:refs/remotes/<remote>/<branch>",
            })
        raise HarnessError(
            "授权动作或范围未覆盖任务包",
            code="authorization_mismatch",
            missing_items=missing_items,
            suggested_fix=(
                f"harness authorization template --target . --task-id {package['task_id']} --output auth.json "
                f"&& 编辑 auth.json 填充 authorized_by/expires_at "
                f"&& harness run --authorization auth.json"
            ),
        )
    expires = value.get("expires_at")
    if expires:
        try:
            expiry = dt.datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        except ValueError as exc:
            raise HarnessError("授权 expires_at 无效", code="invalid_authorization") from exc
        if expiry <= dt.datetime.now(dt.timezone.utc):
            raise HarnessError("授权已过期", code="authorization_expired")
    return {
        "schema_version": AUTH_SCHEMA,
        "task_id": package["task_id"],
        "package_revision": package["package_revision"],
        "package_fingerprint": package_fingerprint(package),
        "authorized_actions": actions,
        "authorized_scope": scope,
        "authorized_git_scope": authorized_git_scope,
        "authorized_external_scope": authorized_external_scope,
        "external_target": value.get("external_target"),
        "expires_at": expires,
        "source_fingerprint": file_fingerprint(auth_path),
        "source_ref": str(auth_path),
        "trust_level": "reported",
        "recorded_at": utc_now(),
    }


def archive_and_rewrite_package(state: Path, package: dict[str, Any], compiled: dict[str, Any], freeze: dict[str, Any], target: Path) -> dict[str, Any]:
    current_package = read_json(state / "task-package.json")
    current_freeze = read_json(state / "freeze.json")
    revision = current_package["package_revision"]
    delta = build_contract_delta(current_package, package)
    history = state / "package-history"
    history.mkdir(exist_ok=True)
    atomic_write_json(history / f"task-package.v{revision}.json", current_package)
    atomic_write_json(history / f"freeze.v{revision}.json", current_freeze)
    atomic_write_json(history / f"contract-delta.v{revision}.json", delta)
    atomic_write_json(state / "task-package.json", package)
    atomic_write_json(state / "compiled-task.json", compiled)
    freeze.update(
        {
            "package_revision": package["package_revision"],
            "package_fingerprint": package_fingerprint(package),
            "package_updated_at": utc_now(),
            "git_state_snapshot": package.get("git_state_snapshot"),
        }
    )
    atomic_write_json(state / "freeze.json", freeze)
    return delta


def plan_scope(plan: Any) -> list[str] | None:
    value = plan_value(plan, "执行范围")
    if value is None:
        return None
    if isinstance(value, list):
        return validate_scope([str(item) for item in value])
    if isinstance(value, str):
        entries = [line.lstrip("-* ").strip(" `") for line in value.splitlines() if line.strip()]
        return validate_scope(entries)
    raise HarnessError("正式方案的执行范围必须是路径数组或分行路径", code="invalid_plan")


def recompile_package_from_plan_scope(
    state: Path,
    package: dict[str, Any],
    freeze: dict[str, Any],
    target: Path,
    requested_scope: Sequence[str],
    cli: argparse.Namespace,
    supplied_facts: dict[str, Any],
    *,
    timing_started: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str], dict[str, Any]]:
    recompile_facts = merge_recompile_facts(package, supplied_facts)
    recompile_facts["allowed_scope"] = list(requested_scope)
    new_package, blockers = build_package(
        target,
        package["original_task"],
        recompile_facts,
        cli,
        package["task_id"],
    )
    new_package["package_revision"] = package["package_revision"] + 1
    new_package["created_at"] = package["created_at"]
    new_package["recompiled_at"] = utc_now()
    new_compiled = initial_compiled(new_package, blockers)
    new_freeze = dict(freeze)
    with state_lock(state):
        delta = archive_and_rewrite_package(
            state,
            new_package,
            new_compiled,
            new_freeze,
            target,
        )
        append_task_event(
            state,
            new_package,
            event="scope_bound_readmission",
            phase="admission",
            reason_code="scope_bound_context_reload",
            duration_ms=int((time.monotonic() - timing_started) * 1000) if timing_started is not None else 0,
            disposition=delta["disposition"],
            added_gates=delta["added_gates"],
            added_plan_fields=delta["added_plan_fields"],
        )
    return new_package, new_compiled, new_freeze, blockers, delta


def facts_from_package(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_type": package["task_type"],
        "task_intent": package["task_intent"],
        "candidate_intents": package["candidate_intents"],
        "deferred_intents": package.get("deferred_intents", []),
        "intent_boundary_reason_codes": package.get("intent_boundary_reason_codes", []),
        "mutation_profile": package["mutation_profile"],
        "gates": package["matched_gates"],
        "gate_assessment": package.get("gate_assessment"),
        "execution_route": package["execution_route"],
        "execution_topology": package["execution_topology"],
        "allowed_scope": package["allowed_scope"],
        "read_scope": package["read_scope"],
        "write_scope": package["write_scope"],
        "git_scope": package["git_scope"],
        "external_scope": package["external_scope"],
        "allowed_actions": package["allowed_actions"],
        "success_criteria": package["success_criteria"],
        "authorization_requirements": package["authorization_requirements"],
        "required_fact_refs": package["required_fact_refs"],
        "verification_commands": package["verification_commands"],
        "semantic_evidence_requirements": package["semantic_evidence_requirements"],
        "work_packages": package["work_packages"],
        "feature_ids": package.get("feature_ids", []),
        "fallback_fact_refs": package.get("fallback_fact_refs", []),
        "blocking_deliverables": [item["deliverable"] for item in package.get("blocking_deliverables", [])],
        "background_deliverables": [item["deliverable"] for item in package.get("background_deliverables", [])],
        # fast_track 是声明制：重编译只继承任务包记录的生效值；运行期降级为 false 后不可反向升级。
        "fast_track": bool(package.get("fast_track", False)),
        "inline_note": package.get("inline_note"),
    }


def merge_recompile_facts(package: dict[str, Any], supplied: dict[str, Any]) -> dict[str, Any]:
    merged = facts_from_package(package)
    if not supplied:
        return merged
    for key, value in supplied.items():
        merged[key] = value
    for key in (
        "gates",
        "allowed_actions",
        "success_criteria",
        "authorization_requirements",
        "required_fact_refs",
        "semantic_evidence_requirements",
    ):
        old_values = normalize_string_list(facts_from_package(package).get(key), key)
        new_values = normalize_string_list(supplied.get(key), key) if key in supplied else []
        merged[key] = list(dict.fromkeys(old_values + new_values))
    rank = {"direct": 0, "planned": 1, "extended": 2}
    old_route = package["execution_route"]
    new_route = supplied.get("execution_route", old_route)
    if new_route not in rank:
        raise HarnessError("execution_route 无效", code="invalid_route")
    merged["execution_route"] = max((old_route, new_route), key=rank.get)
    return merged


def first_run_payload(
    target: Path,
    state: Path,
    package: dict[str, Any],
    compiled: dict[str, Any],
    *,
    reused: bool = False,
) -> tuple[int, dict[str, Any]]:
    payload = {
        "task_id": package["task_id"],
        "task_package_ref": str(state / "task-package.json"),
        "progress_state_ref": str(state / "compiled-task.json"),
        "execution_route": package["execution_route"],
        "execution_topology": package["execution_topology"],
        "task_intent": package["task_intent"],
        "candidate_intents": package["candidate_intents"],
        "deferred_intents": package.get("deferred_intents", []),
        "intent_boundary_reason_codes": package.get("intent_boundary_reason_codes", []),
        "mutation_profile": package["mutation_profile"],
        "matched_gates": package["matched_gates"],
        "gate_decision": package.get("gate_decision"),
        "matched_rules": package["matched_rules"],
        "rules": [item["rule_id"] for item in package["matched_rules"]],
        "allowed_scope": package["allowed_scope"],
        "read_scope": package["read_scope"],
        "write_scope": package["write_scope"],
        "git_scope": package["git_scope"],
        "external_scope": package["external_scope"],
        "allowed_actions": package["allowed_actions"],
        "success_criteria": package["success_criteria"],
        "authorization_requirements": package["authorization_requirements"],
        "stop_conditions": package["stop_conditions"],
        "plan_fields": package["plan_fields"],
        "plan_skeleton": package["plan_skeleton"],
        "context_schedule": package["context_schedule"],
        "knowledge_context": package.get("knowledge_context", {}),
        "context_quality": package.get("context_quality", "complete"),
        "blocking_deliverables": package.get("blocking_deliverables", []),
        "background_deliverables": package.get("background_deliverables", []),
        "completion_manifest": package.get("completion_manifest"),
        "admission_status": compiled["control_status"],
        "blockers": compiled["blockers"],
        "next_action": compiled["next_action"],
    }
    if package.get("fast_track"):
        payload["fast_track"] = True
        payload["evidence_profile"] = "fast_track"
        if package.get("inline_note"):
            payload["inline_note"] = package["inline_note"]
    elif package.get("fast_track_denied_reason"):
        payload["fast_track"] = False
        payload["fast_track_denied_reason"] = package["fast_track_denied_reason"]
    if package.get("inline_note_ignored"):
        payload["inline_note_ignored"] = True
        payload["inline_note_effective_condition"] = "inline_note 仅 fast_track 任务生效；本次未生效，已按普通流程处理"
    if reused:
        payload["active_task_reused"] = True
    platform_scope = package.get("platform_scope", {})
    if platform_scope.get("cross_platform"):
        target_platforms = [p for p in platform_scope.get("detected_platforms", []) if p != platform_scope.get("current_platform")]
        payload["cross_platform_notice"] = {
            "detected": True,
            "target_platforms": target_platforms,
            "current_platform": platform_scope.get("current_platform"),
            "message": f"检测到跨平台专属文件({', '.join(target_platforms)})，当前平台({platform_scope.get('current_platform')})可能无法执行完整验证。建议在目标平台补验。",
            "verification_layers": platform_scope.get("verification_layers", []),
        }
    payload["plan_contract"] = plan_contract_payload(package)
    if completion_manifest_valid(package.get("completion_manifest")):
        payload["evidence_checklist"] = evidence_checklist_payload(state, package)
        payload["pending_context_receipts"] = pending_context_receipts(state, package, target, compiled)
    reason_code = (
        "active_task_reused"
        if reused
        else (
            "scope_required"
            if compiled["control_status"] == "needs_plan" and not package["allowed_scope"]
            else (
                "plan_required"
                if compiled["control_status"] == "needs_plan"
                else compiled["control_status"]
            )
        )
    )
    payload.update(
        next_step_payload(
            target,
            state,
            package,
            compiled["next_action"],
            reason_code=reason_code,
        )
    )
    return (3 if compiled["control_status"] == "blocked" else 0), payload


def command_run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    started = time.monotonic()
    target = safe_target(args.target)
    facts = load_facts(args.facts)
    if not args.task_id:
        if not args.task or not args.task.strip():
            raise HarnessError("首次 run 必须提供原始任务", code="missing_task")
        task_text = args.task.strip()
        # 幂等键包含全工作区快照，仅当存在历史任务目录时才值得计算；
        # 无历史任务时延迟到落盘前再算（此时快照可被后续 create_task_state 复用）。
        key: str | None = None
        if not getattr(args, "new_task", False) and runtime_root(target).is_dir():
            key = active_task_key(target, task_text, facts)
            existing = find_existing_active_task(target, key)
            if existing is not None:
                package = read_json(existing / "task-package.json")
                compiled = read_json(existing / "compiled-task.json")
                return first_run_payload(target, existing, package, compiled, reused=True)
        task_id = generate_task_id()
        package, blockers = build_package(target, task_text, facts, args, task_id)
        package["active_task_key"] = key if key is not None else active_task_key(target, task_text, facts)
        state = create_task_state(target, package, blockers, timing_started=started)
        compiled = read_json(state / "compiled-task.json")
        return first_run_payload(target, state, package, compiled)

    state, package, compiled, freeze = load_state(target, args.task_id)
    should_recompile = bool(compiled.get("scope_changed")) or (
        compiled.get("control_status") == "blocked" and not args.plan and not args.authorization
    )
    if should_recompile:
        task = args.task or package["original_task"]
        recompile_facts = merge_recompile_facts(package, facts)
        git_sync_readmission = package.get("git_operation") == "git_sync"
        if git_sync_readmission:
            # 预检会按当前 HEAD 与远端目标重新生成 write_scope；清空继承值避免“手工 write_scope 与预检清单不一致”误报
            # （allowed_scope 会经 legacy_scope 重新并入 write_scope，必须一并清空）
            recompile_facts["write_scope"] = []
            recompile_facts["allowed_scope"] = []
        new_package, blockers = build_package(target, task, recompile_facts, args, package["task_id"])
        new_package["package_revision"] = package["package_revision"] + 1
        new_package["created_at"] = package["created_at"]
        new_package["recompiled_at"] = utc_now()
        if git_sync_readmission:
            old_head = str((package.get("git_state_snapshot") or {}).get("head") or "unborn")
            new_head = str((new_package.get("git_state_snapshot") or {}).get("head") or "unborn")
            landed: list[str] = []
            if old_head != new_head and new_head != "unborn":
                diff_base = EMPTY_TREE_HASH if old_head == "unborn" else old_head
                diff_result = git_command(target, "diff", "--name-status", "-M", diff_base, new_head)
                if diff_result.returncode == 0:
                    landed = git_name_status_paths(diff_result.stdout)
            new_package["git_sync_landed_scope"] = sorted(
                set(package.get("git_sync_landed_scope", [])) | set(landed)
            )
            new_package["write_scope"] = sorted(
                set(new_package["write_scope"]) | set(new_package["git_sync_landed_scope"])
            )
        new_compiled = initial_compiled(new_package, blockers)
        if git_sync_readmission and plan_is_current(compiled):
            old_contract = plan_contract_payload(package)
            new_contract = plan_contract_payload(new_package)
            # git_sync 方案从不绑定范围；预检范围随远端漂移变化，不参与方案复用比较
            for key in ("write_scope", "allowed_scope"):
                old_contract.pop(key, None)
                new_contract.pop(key, None)
            if old_contract == new_contract:
                new_compiled["plan_ref"] = compiled["plan_ref"]
                new_compiled["plan_fingerprint"] = compiled["plan_fingerprint"]
                new_compiled["plan_artifact"] = compiled.get("plan_artifact")
        elif plan_is_current(compiled):
            # 普通任务方案继承：合同除范围外未变时复用已冻结方案，避免重交 plan
            old_contract = plan_contract_payload(package)
            new_contract = plan_contract_payload(new_package)
            for key in ("write_scope", "allowed_scope", "read_scope"):
                old_contract.pop(key, None)
                new_contract.pop(key, None)
            if old_contract == new_contract:
                new_compiled["plan_ref"] = compiled["plan_ref"]
                new_compiled["plan_fingerprint"] = compiled["plan_fingerprint"]
                new_compiled["plan_artifact"] = compiled.get("plan_artifact")
        new_freeze = dict(freeze)
        with state_lock(state):
            archive_and_rewrite_package(state, new_package, new_compiled, new_freeze, target)
            append_task_event(
                state,
                new_package,
                event="readmission",
                phase="admission",
                reason_code="task_contract_recompiled",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        package, compiled, freeze = new_package, new_compiled, new_freeze

    if args.plan:
        if not context_receipt_valid(state, package, target, stage="plan"):
            compiled["control_status"] = "blocked"
            compiled["blockers"] = ["正式方案前必须先运行 harness context --stage plan"]
            compiled["next_action"] = "load_plan_context"
            atomic_write_json(state / "compiled-task.json", compiled)
            payload = {
                "task_id": args.task_id,
                "admission_status": "blocked",
                "blockers": compiled["blockers"],
            }
            payload.update(
                next_step_payload(
                    target,
                    state,
                    package,
                    compiled["next_action"],
                    reason_code="plan_context_required",
                )
            )
            return 3, payload
        plan_path, plan = load_plan(args.plan)
        pending_delta = compiled.get("plan_delta_contract")
        if not isinstance(pending_delta, dict) or pending_delta.get("plan_contract_fingerprint") != plan_contract_fingerprint(package):
            pending_delta = None
            compiled["plan_delta_contract"] = None
        if pending_delta is not None:
            validate_plan_delta_binding(plan, package, pending_delta)
            plan = merge_plan_delta(
                load_managed_plan(pending_delta.get("base_plan_ref"), pending_delta.get("base_plan_fingerprint")),
                plan,
                missing_fields=pending_delta.get("missing_plan_fields", []),
                frozen_fields=pending_delta.get("frozen_plan_fields", []),
            )
        missing = validate_plan(plan, package["plan_fields"])
        if missing:
            compiled["control_status"] = "needs_plan"
            compiled["blockers"] = ["方案缺少字段：" + ", ".join(missing)]
            compiled["next_action"] = "complete_plan_delta" if pending_delta else "complete_plan"
            atomic_write_json(state / "compiled-task.json", compiled)
            payload = {
                "task_id": args.task_id,
                "admission_status": "needs_plan",
                "missing_plan_fields": missing,
                "plan_contract": plan_contract_payload(package),
            }
            if pending_delta is not None:
                payload["plan_delta_contract"] = pending_delta
                payload["plan_regeneration_required"] = False
            payload.update(
                next_step_payload(
                    target,
                    state,
                    package,
                    compiled["next_action"],
                    reason_code="plan_delta_required" if pending_delta else "plan_incomplete",
                    artifact_ref=plan_path,
                )
            )
            return 3, payload
        requested_scope = plan_scope(plan)
        if requested_scope is not None and package["allowed_scope"] and set(requested_scope) != set(package["allowed_scope"]):
            if set(requested_scope) >= set(package["allowed_scope"]):
                # 严格超集：自动重编译而非要求全量重准入
                package, compiled, freeze, blockers, scope_delta = recompile_package_from_plan_scope(
                    state,
                    package,
                    freeze,
                    target,
                    requested_scope,
                    args,
                    facts,
                    timing_started=started,
                )
                if blockers:
                    compiled["blockers"] = blockers
                    atomic_write_json(state / "compiled-task.json", compiled)
                    payload = {
                        "task_id": args.task_id,
                        "admission_status": compiled["control_status"],
                        "package_revision": package["package_revision"],
                        "matched_gates": package["matched_gates"],
                        "blockers": blockers,
                        "plan_contract": plan_contract_payload(package),
                    }
                    payload.update(
                        next_step_payload(
                            target,
                            state,
                            package,
                            compiled["next_action"],
                            reason_code="scope_superset_recompile_blocked",
                        )
                    )
                    return 3, payload
                missing_after_superset = validate_plan(plan, package["plan_fields"])
                if missing_after_superset:
                    managed = ingest_managed_plan(state, package, plan_path, kind="plan-draft")
                    contract = plan_delta_contract(package, managed, scope_delta, missing_after_superset)
                    compiled["control_status"] = "needs_plan"
                    compiled["next_action"] = "complete_plan_delta"
                    compiled["plan_delta_contract"] = contract
                    compiled["blockers"] = ["范围扩展新增 Gate 只需补充计划字段：" + ", ".join(missing_after_superset)]
                    atomic_write_json(state / "compiled-task.json", compiled)
                    payload = {
                        "task_id": args.task_id,
                        "result": "补充计划",
                        "missing_plan_fields": missing_after_superset,
                        "plan_delta_contract": contract,
                        "plan_regeneration_required": False,
                    }
                    payload.update(
                        next_step_payload(
                            target,
                            state,
                            package,
                            compiled["next_action"],
                            reason_code="scope_superset_plan_amendment",
                            artifact_ref=plan_path,
                        )
                    )
                    return 3, payload
            else:
                compiled["scope_changed"] = True
                compiled["control_status"] = "blocked"
                compiled["verification_status"] = "needs_readmission"
                compiled["blockers"] = ["正式方案执行范围与当前任务包不一致，必须重新准入"]
                compiled["next_action"] = "rerun_harness_for_readmission"
                atomic_write_json(state / "compiled-task.json", compiled)
                scope_diff = {
                    "only_in_task": sorted(set(package["allowed_scope"]) - set(requested_scope)),
                    "only_in_plan": sorted(set(requested_scope) - set(package["allowed_scope"])),
                }
                payload = {
                    "task_id": args.task_id,
                    "result": "重新准入",
                    "task_scope": package["allowed_scope"],
                    "plan_scope": requested_scope,
                    "scope_diff": scope_diff,
                    "blockers": compiled["blockers"],
                }
                payload.update(
                    next_step_payload(
                        target,
                        state,
                        package,
                        compiled["next_action"],
                        reason_code="plan_scope_mismatch",
                        artifact_ref=plan_path,
                    )
                )
                return 4, payload
        freeze_reason = "plan_delta_merged" if pending_delta is not None else "plan_submitted"
        if not package["allowed_scope"] and plan_contract_payload(package)["scope_required"]:
            if requested_scope is None:
                raise HarnessError("正式方案仍未给出执行范围", code="missing_plan_scope")
            package, compiled, freeze, blockers, scope_delta = recompile_package_from_plan_scope(
                state,
                package,
                freeze,
                target,
                requested_scope,
                args,
                facts,
                timing_started=started,
            )
            if blockers:
                compiled["blockers"] = blockers
                atomic_write_json(state / "compiled-task.json", compiled)
                payload = {
                    "task_id": args.task_id,
                    "admission_status": compiled["control_status"],
                    "package_revision": package["package_revision"],
                    "matched_gates": package["matched_gates"],
                    "blockers": blockers,
                    "plan_contract": plan_contract_payload(package),
                }
                payload.update(
                    next_step_payload(
                        target,
                        state,
                        package,
                        compiled["next_action"],
                        reason_code="scope_recompile_blocked",
                    )
                )
                return 3, payload
            missing_after_scope = validate_plan(plan, package["plan_fields"])
            if missing_after_scope:
                managed = ingest_managed_plan(state, package, plan_path, kind="plan-draft")
                contract = plan_delta_contract(package, managed, scope_delta, missing_after_scope)
                compiled["control_status"] = "needs_plan"
                compiled["next_action"] = "complete_plan_delta"
                compiled["plan_delta_contract"] = contract
                compiled["blockers"] = ["范围绑定新增 Gate 只需补充计划字段：" + ", ".join(missing_after_scope)]
                atomic_write_json(state / "compiled-task.json", compiled)
                append_task_event(
                    state,
                    package,
                    event="plan_amendment_required",
                    phase="planning",
                    reason_code="scope_gate_plan_amendment_required",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    added_gates=scope_delta["added_gates"],
                    added_plan_fields=scope_delta["added_plan_fields"],
                    missing_plan_field_count=len(missing_after_scope),
                    plan_regeneration_required=False,
                )
                payload = {
                    "task_id": args.task_id,
                    "result": "补充计划",
                    "admission_status": "needs_plan",
                    "package_revision": package["package_revision"],
                    "matched_gates": package["matched_gates"],
                    "added_gates": scope_delta["added_gates"],
                    "added_plan_fields": scope_delta["added_plan_fields"],
                    "added_context_refs": scope_delta["added_context_refs"],
                    "added_evidence_types": scope_delta["added_evidence_types"],
                    "missing_plan_fields": missing_after_scope,
                    "plan_regeneration_required": False,
                    "source_execution_allowed": False,
                    "plan_delta_contract": contract,
                    "blockers": compiled["blockers"],
                    "plan_contract": plan_contract_payload(package),
                }
                payload.update(
                    next_step_payload(
                        target,
                        state,
                        package,
                        "complete_plan_delta",
                        reason_code="scope_gate_plan_amendment_required",
                    )
                )
                return 3, payload
            freeze_reason = "scope_bound_plan_adopted"
        managed_plan = freeze_managed_plan(state, package, compiled, plan_path, plan=plan)
        append_task_event(
            state,
            package,
            event="plan_frozen",
            phase="planning",
            reason_code=freeze_reason,
            duration_ms=int((time.monotonic() - started) * 1000),
            plan_artifact_fingerprint=managed_plan["artifact_fingerprint"],
            plan_regeneration_required=False,
        )

    if package["execution_route"] == "direct":
        compiled["control_status"] = "ready_direct"
        schedule = package["context_schedule"]["action"]
        compiled["next_action"] = "load_action_context" if schedule["rule_ids"] or schedule["project_fact_refs"] else "execute"
    elif not compiled.get("plan_ref"):
        compiled["control_status"] = "needs_plan"
        compiled["next_action"] = "load_plan_context"
    elif package["authorization_requirements"]:
        if not args.authorization:
            compiled["control_status"] = "needs_authorization"
            compiled["authorization_status"] = "missing"
            compiled["next_action"] = "obtain_authorization"
        else:
            receipt = authorization_receipt(args.authorization, package)
            source = Path(str(receipt.get("source_ref", "")))
            managed_auth = store_managed_artifact(
                state,
                "authorizations",
                f"authorization.v{package['package_revision']}.json",
                source.read_text(encoding="utf-8"),
            )
            receipt["artifact_ref"] = str(managed_auth)
            receipt["artifact_fingerprint"] = file_fingerprint(managed_auth)
            receipt["authorization_contract_fingerprint"] = authorization_contract_fingerprint(package)
            with state_lock(state):
                append_jsonl(state / "authorization-receipts.jsonl", receipt)
            compiled["authorization_status"] = "reported"
            compiled["authorization_receipt_ref"] = str(state / "authorization-receipts.jsonl")
            compiled["control_status"] = "ready_extended" if package["execution_route"] == "extended" else "ready_planned"
            schedule = package["context_schedule"]["action"]
            compiled["next_action"] = "load_work_package_context" if package["execution_route"] == "extended" else ("load_action_context" if schedule["rule_ids"] or schedule["project_fact_refs"] else "execute")
    else:
        compiled["control_status"] = "ready_extended" if package["execution_route"] == "extended" else "ready_planned"
        schedule = package["context_schedule"]["action"]
        compiled["next_action"] = "load_work_package_context" if package["execution_route"] == "extended" else ("load_action_context" if schedule["rule_ids"] or schedule["project_fact_refs"] else "execute")
    compiled["updated_at"] = utc_now()
    atomic_write_json(state / "compiled-task.json", compiled)
    exit_code = 0 if compiled["control_status"].startswith("ready_") else 3
    payload = {
        "task_id": args.task_id,
        "execution_route": package["execution_route"],
        "execution_topology": package["execution_topology"],
        "admission_status": compiled["control_status"],
        "authorization_status": compiled["authorization_status"],
        "work_packages": package["work_packages"],
        "dispatch_contracts": package["dispatch_contracts"],
        "blockers": compiled["blockers"],
    }
    if completion_manifest_valid(package.get("completion_manifest")):
        payload["evidence_checklist"] = evidence_checklist_payload(state, package)
        payload["pending_context_receipts"] = pending_context_receipts(state, package, target, compiled)
    facts_ignored = bool(facts) and not should_recompile and not args.plan and not args.authorization
    if facts_ignored:
        payload["facts_ignored"] = True
        payload["facts_effective_condition"] = "--facts 仅在 blocked 或 scope_changed 的重准入时生效；当前任务状态已忽略本次 facts"
    if package.get("fast_track"):
        payload["fast_track"] = True
        payload["evidence_profile"] = "fast_track"
        if package.get("inline_note"):
            payload["inline_note"] = package["inline_note"]
    elif package.get("fast_track_denied_reason"):
        payload["fast_track"] = False
        payload["fast_track_denied_reason"] = package["fast_track_denied_reason"]
    if package.get("inline_note_ignored"):
        payload["inline_note_ignored"] = True
        payload["inline_note_effective_condition"] = "inline_note 仅 fast_track 任务生效；本次未生效，已按普通流程处理"
    work_package = None
    if compiled["next_action"] == "load_work_package_context":
        work_package = next(
            (
                item["work_package_id"]
                for item in package["work_packages"]
                if compiled["work_package_states"].get(item["work_package_id"]) == "pending"
            ),
            None,
        )
    payload.update(
        next_step_payload(
            target,
            state,
            package,
            compiled["next_action"],
            reason_code=compiled["control_status"],
            work_package=work_package,
        )
    )
    return exit_code, payload


def replay_progress(package: dict[str, Any], events: Sequence[dict[str, Any]]) -> tuple[dict[str, str], dict[str, Any]]:
    revision = package["package_revision"]
    states = {item["work_package_id"]: "pending" for item in package["work_packages"]}
    blockers: dict[str, str] = {}
    evidence_refs: list[str] = []
    for event in events:
        if event.get("package_revision") != revision:
            continue
        work_id = event.get("work_package_id")
        if work_id not in states:
            continue
        kind = event.get("event")
        if kind == "begin":
            if states[work_id] != "pending":
                raise HarnessError(f"事件重放发现非法 begin：{work_id}", code="invalid_state")
            states[work_id] = "in_progress"
        elif kind == "submit":
            if states[work_id] != "in_progress" or event.get("accepted") is not True:
                raise HarnessError(f"事件重放发现非法 submit：{work_id}", code="invalid_state")
            states[work_id] = "verified"
            evidence_refs.extend(event.get("evidence_refs", []))
        elif kind == "block":
            if states[work_id] not in {"pending", "in_progress"}:
                raise HarnessError(f"事件重放发现非法 block：{work_id}", code="invalid_state")
            states[work_id] = "blocked"
            blockers[work_id] = str(event.get("reason", "blocked"))
    current = next((work_id for work_id, status in states.items() if status == "in_progress"), None)
    return states, {"current": current, "blockers": blockers, "evidence_refs": list(dict.fromkeys(evidence_refs))}


def next_progress_action(package: dict[str, Any], states: dict[str, str], state: Path, target: Path) -> str:
    if any(status == "blocked" for status in states.values()):
        return "rerun_harness_for_readmission"
    for work in package["work_packages"]:
        work_id = work["work_package_id"]
        if states[work_id] == "in_progress":
            return f"submit_or_block:{work_id}"
        if states[work_id] == "pending" and all(states[dep] == "verified" for dep in work["dependencies"]):
            if not context_receipt_valid(state, package, target, work_package=work_id):
                return f"load_context:{work_id}"
            return f"begin:{work_id}"
    return "verify" if states and all(status == "verified" for status in states.values()) else "none"


def refresh_compiled_progress(state: Path, package: dict[str, Any], compiled: dict[str, Any], target: Path) -> dict[str, Any]:
    states, replay = replay_progress(package, read_jsonl(state / "events.jsonl"))
    compiled["work_package_states"] = states
    compiled["current_work_package"] = replay["current"]
    compiled["evidence_refs"] = replay["evidence_refs"]
    compiled["blockers"] = list(replay["blockers"].values())
    compiled["next_action"] = next_progress_action(package, states, state, target)
    compiled["updated_at"] = utc_now()
    atomic_write_json(state / "compiled-task.json", compiled)
    return compiled


def parse_utc_timestamp(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise HarnessError(f"{field} 必须是 ISO 时间", code="invalid_evidence_receipt")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HarnessError(f"{field} 必须是 ISO 时间", code="invalid_evidence_receipt") from exc
    if parsed.tzinfo is None:
        raise HarnessError(f"{field} 必须包含时区", code="invalid_evidence_receipt")
    return parsed.astimezone(dt.timezone.utc)


def known_evidence_types() -> set[str]:
    result = {
        "workspace_attribution",
        "source_trace",
        "document_trace",
        "code_diff",
        "test_run",
        "git_inspection_result",
        "git_fetch_result",
        "git_sync_result",
        "review_result",
        "document_review",
        "security_acceptance",
        "external_state",
        "test_result",
        "contract_acceptance",
        "product_acceptance",
        "ui_acceptance",
        "diagnostic_replay",
        "recovery_acceptance",
        "remote_delivery",
        "fresh_clone_verification",
        "release_acceptance",
        "functional_confirmation",
    }
    for spec in GATE_DEFS.values():
        result.update(str(item) for item in spec.get("evidence", ()))
    return result


def mint_evidence_receipt(
    target: Path,
    package: dict[str, Any],
    declaration: dict[str, Any],
    *,
    producer: dict[str, str],
) -> dict[str, Any]:
    """控制器代铸：把证据声明正文装订成完整 evidence-receipt/v2，装订字段一律由控制器计算。"""
    snapshot = workspace_snapshot(target)
    now = utc_now()
    read_set: list[dict[str, str | None]] = []
    for item in declaration.get("read_set", []):
        path = str(item.get("path") if isinstance(item, dict) else item)
        read_set.append({"path": path, "fingerprint": snapshot.get(path)})
    digest = sha256_text(canonical_json(declaration))
    return {
        "schema_version": EVIDENCE_RECEIPT_SCHEMA,
        "type": declaration.get("type"),
        "result": "passed",
        "covers": [package["task_id"]],
        "task_id": package["task_id"],
        "conclusion": declaration.get("conclusion", ""),
        "changed_paths": list(declaration.get("changed_paths", [])),
        "write_set": list(declaration.get("write_set", [])),
        "read_set": read_set,
        "concurrent_drift": list(declaration.get("concurrent_drift", [])),
        "producer": producer,
        "target_identity": target_identity(target),
        "package_fingerprint": package_fingerprint(package),
        "content_set_fingerprint": None,
        "cwd": str(target.resolve()),
        "started_at": now,
        "ended_at": now,
        "ttl": 3600,
        "exit_code": 0,
        "command_argv_digest": digest,
        "output_or_artifact_digest": digest,
    }


def load_evidence(
    path_value: str,
    *,
    expected_cover: str | None = None,
    package: dict[str, Any] | None = None,
    target: Path | None = None,
    binding_package_fingerprint: str | None = None,
    binding_target_identity: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    path, value = load_json_object_file(
        path_value,
        argument="--evidence",
        max_bytes=1024 * 1024,
        error_code="invalid_evidence",
    )
    if value.get("schema_version") == EVIDENCE_DECLARATION_SCHEMA:
        if package is None or target is None:
            raise HarnessError("证据声明草案缺少任务验证上下文", code="invalid_evidence_receipt")
        value = mint_evidence_receipt(
            target,
            package,
            value,
            producer={"adapter": "docs-harness", "capability": "host_declaration"},
        )
    is_v2 = value.get("schema_version") == EVIDENCE_RECEIPT_SCHEMA
    if package is not None and package.get("schema_version") == TASK_SCHEMA and not is_v2:
        raise HarnessError(
            "v2 任务只接受 evidence-receipt/v2；旧证据仅作只读历史",
            code="legacy_evidence_not_accepted",
        )
    if value.get("result") != "passed" and not (is_v2 and value.get("exit_code") == 0):
        raise HarnessError("证据 result 必须为 passed", code="evidence_not_passed")
    covers = normalize_string_list(value.get("covers"), "evidence.covers")
    if is_v2 and not covers and isinstance(value.get("task_id"), str):
        covers = [str(value["task_id"])]
    if expected_cover and expected_cover not in covers:
        raise HarnessError(f"证据未覆盖 {expected_cover}", code="evidence_mismatch")
    evidence_type = value.get("type")
    if not isinstance(evidence_type, str) or not evidence_type.strip():
        raise HarnessError("证据缺少 type", code="invalid_evidence")
    if evidence_type not in known_evidence_types():
        raise HarnessError("证据 type 不在白名单", code="invalid_evidence_type")
    changed_paths = validate_scope(
        normalize_string_list(value.get("changed_paths"), "evidence.changed_paths"),
        field="evidence.changed_paths",
    )
    write_set = validate_scope(
        normalize_string_list(value.get("write_set"), "evidence.write_set"),
        field="evidence.write_set",
    )
    if not write_set:
        write_set = changed_paths
    raw_read_set = value.get("read_set", [])
    if not isinstance(raw_read_set, list):
        raise HarnessError("evidence.read_set 必须是数组", code="invalid_evidence")
    read_set: list[dict[str, str | None]] = []
    for item in raw_read_set:
        if isinstance(item, str):
            normalized = validate_scope([item], field="evidence.read_set", allow_git_resources=True)[0]
            read_set.append({"path": normalized, "fingerprint": None})
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            normalized = validate_scope([str(item["path"])], field="evidence.read_set", allow_git_resources=True)[0]
            fingerprint = item.get("fingerprint")
            if fingerprint is not None and (not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:")):
                raise HarnessError("evidence.read_set fingerprint 无效", code="invalid_evidence")
            read_set.append({"path": normalized, "fingerprint": fingerprint})
        else:
            raise HarnessError("evidence.read_set 条目无效", code="invalid_evidence")
    concurrent_drift = validate_scope(
        normalize_string_list(value.get("concurrent_drift"), "evidence.concurrent_drift"),
        field="evidence.concurrent_drift",
    )
    attribution_quality = str(value.get("attribution_quality") or "reported")
    if attribution_quality not in {"verified", "reported", "partial", "unknown"}:
        raise HarnessError("evidence.attribution_quality 无效", code="invalid_evidence")
    producer = value.get("producer") if isinstance(value.get("producer"), dict) else {}
    trust_level = "reported"
    if is_v2:
        if package is None or target is None:
            raise HarnessError("v2 证据收据缺少任务验证上下文", code="invalid_evidence_receipt")
        required = {
            "task_id",
            "target_identity",
            "package_fingerprint",
            "producer",
            "command_argv_digest",
            "cwd",
            "started_at",
            "ended_at",
            "ttl",
            "exit_code",
            "output_or_artifact_digest",
            "read_set",
            "write_set",
        }
        missing = sorted(key for key in required if key not in value)
        if missing:
            raise HarnessError("v2 证据收据缺少字段：" + ", ".join(missing), code="invalid_evidence_receipt")
        if binding_package_fingerprint is None:
            binding_package_fingerprint = package_fingerprint(package)
        if binding_target_identity is None:
            binding_target_identity = target_identity(target)
        if value.get("task_id") != package["task_id"] or value.get("package_fingerprint") != binding_package_fingerprint:
            raise HarnessError("v2 证据收据未绑定当前任务包", code="evidence_binding_mismatch")
        if value.get("target_identity") != binding_target_identity:
            raise HarnessError("v2 证据收据目标不匹配", code="evidence_binding_mismatch")
        adapter = producer.get("adapter")
        capability = producer.get("capability")
        if (adapter, capability) not in TRUSTED_EVIDENCE_PRODUCERS:
            raise HarnessError("v2 证据生产者不可信", code="untrusted_evidence_producer")
        started = parse_utc_timestamp(value.get("started_at"), "started_at")
        ended = parse_utc_timestamp(value.get("ended_at"), "ended_at")
        ttl = value.get("ttl")
        if not isinstance(ttl, int) or ttl <= 0 or ttl > 604800 or ended < started:
            raise HarnessError("v2 证据收据时效字段无效", code="invalid_evidence_receipt")
        if dt.datetime.now(dt.timezone.utc) > ended + dt.timedelta(seconds=ttl):
            raise HarnessError("v2 证据收据已过期", code="evidence_expired", exit_code=3)
        digest_fields = (value.get("command_argv_digest"), value.get("output_or_artifact_digest"))
        if any(not isinstance(item, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", item) for item in digest_fields):
            raise HarnessError("v2 证据收据摘要无效", code="invalid_evidence_receipt")
        if value.get("exit_code") != 0 or str(value.get("cwd")) != str(target.resolve()):
            raise HarnessError("v2 证据收据执行结果或 cwd 不匹配", code="evidence_binding_mismatch")
        content_set = value.get("content_set_fingerprint")
        if content_set is not None and (not isinstance(content_set, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", content_set)):
            raise HarnessError("content_set_fingerprint 无效", code="invalid_evidence_receipt")
        attribution_quality = "verified"
        trust_level = "verified"
    return path, {
        "schema_version": EVIDENCE_RECEIPT_SCHEMA if is_v2 else "docs-harness/evidence/v1",
        "id": str(value.get("id") or sha256_text(canonical_json(value))[7:23]),
        "type": evidence_type.strip(),
        "result": "passed",
        "covers": covers,
        "conclusion": str(value.get("conclusion", "")).strip(),
        "changed_paths": changed_paths,
        "read_set": read_set,
        "write_set": write_set,
        "concurrent_drift": concurrent_drift,
        "attribution_quality": attribution_quality,
        "producer": producer,
        "trust_level": trust_level,
        "target_identity": value.get("target_identity"),
        "package_fingerprint": value.get("package_fingerprint"),
        "content_set_fingerprint": value.get("content_set_fingerprint"),
        "expires_at": (
            (parse_utc_timestamp(value.get("ended_at"), "ended_at") + dt.timedelta(seconds=int(value.get("ttl")))).isoformat()
            if is_v2
            else None
        ),
        "source_ref": str(path),
        "source_fingerprint": file_fingerprint(path),
        "recorded_at": utc_now(),
    }


def actual_scope_change(target: Path, package: dict[str, Any], freeze: dict[str, Any], scope: Sequence[str]) -> tuple[list[str], list[str], list[str]]:
    changed = snapshot_changes(freeze["workspace_snapshot"], workspace_snapshot(target))
    outside = [path for path in changed if not scope_covers(path, scope)]
    new_gates = [gate for gate in infer_gates_from_paths(changed) if gate not in package["matched_gates"]]
    return changed, outside, new_gates


def workspace_change_attribution(
    target: Path,
    package: dict[str, Any],
    freeze: dict[str, Any],
    evidence: Sequence[dict[str, Any]],
    *,
    git_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_snapshot = cached_workspace_snapshot(target, contract_version=VERSION, target_id=target_identity(target))
    changed = snapshot_changes(freeze["workspace_snapshot"], current_snapshot)
    changed_set = set(changed)
    reported_writes = {
        path
        for item in evidence
        for path in item.get("write_set", item.get("changed_paths", []))
        if path in changed_set
    }
    if git_result is not None and git_result.get("passed") and package.get("git_operation") == "git_sync":
        reported_writes.update(path for path in package.get("git_sync_scope", []) if path in changed_set)
        reported_writes.update(path for path in package.get("git_sync_landed_scope", []) if path in changed_set)
    concurrent = {
        path
        for item in evidence
        if item.get("attribution_quality") == "verified"
        for path in item.get("concurrent_drift", [])
        if path in changed_set and path not in reported_writes
    }
    unattributed = changed_set - reported_writes - concurrent
    read_items = [entry for item in evidence for entry in item.get("read_set", [])]
    read_paths = {str(item.get("path")) for item in read_items if isinstance(item, dict)}
    write_scope = package.get("write_scope", package.get("allowed_scope", []))
    read_scope = package.get("read_scope", [])
    read_set_drift: list[str] = []
    refreshed_reads: set[str] = set()
    for item in read_items:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path"))
        fingerprint = item.get("fingerprint")
        if not fingerprint:
            continue
        if current_snapshot.get(path) != fingerprint:
            read_set_drift.append(path)
        else:
            refreshed_reads.add(path)
    unattributed -= refreshed_reads
    task_outside = sorted(path for path in reported_writes if not scope_covers(path, write_scope))
    concurrent_overlap = sorted(
        path for path in concurrent if scope_covers(path, write_scope) or scope_covers(path, read_scope) or path in read_paths
    )
    drift_set = set(read_set_drift)
    unattributed_overlap = sorted(
        path
        for path in unattributed
        if path not in drift_set
        and (scope_covers(path, write_scope) or scope_covers(path, read_scope) or path in read_paths)
    )
    risk_gates = SAFETY_FLOOR_GATES
    risky_concurrent = sorted(
        path
        for path in concurrent | unattributed
        if set(infer_gates_from_paths([path], mutation_profile="workspace_write")) & risk_gates
    )
    new_gates = [
        gate
        for gate in infer_gates_from_paths(sorted(reported_writes), mutation_profile=package.get("mutation_profile", "workspace_write"))
        if gate not in package["matched_gates"]
    ]
    blockers: list[dict[str, Any]] = []
    if task_outside:
        blockers.append({"reason_code": "write_scope_violation", "paths": task_outside})
    if read_set_drift:
        blockers.append({"reason_code": "read_set_drift", "paths": sorted(set(read_set_drift))})
    if concurrent_overlap:
        blockers.append({"reason_code": "concurrent_drift_overlap", "paths": concurrent_overlap})
    if unattributed_overlap:
        blockers.append({"reason_code": "unattributed_drift_overlap", "paths": unattributed_overlap})
    if risky_concurrent:
        blockers.append({"reason_code": "high_risk_drift", "paths": risky_concurrent})
    if new_gates:
        blockers.append({"reason_code": "new_risk_gate", "gates": new_gates})
    warnings: list[dict[str, Any]] = []
    unrelated_concurrent = sorted(concurrent - set(concurrent_overlap) - set(risky_concurrent))
    unrelated_unattributed = sorted(unattributed - set(unattributed_overlap) - set(risky_concurrent))
    if unrelated_concurrent:
        warnings.append({"reason_code": "concurrent_drift_unrelated", "paths": unrelated_concurrent})
    if unrelated_unattributed:
        warnings.append({"reason_code": "unattributed_drift_unrelated", "paths": unrelated_unattributed})
    quality = "verified" if evidence and all(item.get("attribution_quality") == "verified" for item in evidence) else (
        "reported" if evidence else "unknown"
    )
    return {
        "changed_paths": changed,
        "task_write_set": sorted(reported_writes),
        "read_set": read_items,
        "concurrent_drift": sorted(concurrent),
        "unattributed_drift": sorted(unattributed),
        "attribution_quality": quality,
        "outside_scope": task_outside,
        "new_gates": new_gates,
        "blockers": blockers,
        "warnings": warnings,
    }


def index_evidence(state: Path, evidence: dict[str, Any]) -> None:
    index = read_json(state / "evidence-index.json")
    items = index.setdefault("evidence", [])
    if not any(item.get("source_fingerprint") == evidence["source_fingerprint"] for item in items):
        items.append(evidence)
    atomic_write_json(state / "evidence-index.json", index)


def discard_evidence_referencing_paths(state: Path, paths: set[str]) -> list[str]:
    """read-set 漂移时只失效引用这些路径的证据，返回被失效的证据 id。"""
    index_path = state / "evidence-index.json"
    index = read_json(index_path)
    items = index.get("evidence", [])
    if not items:
        return []
    kept: list[dict[str, Any]] = []
    discarded: list[str] = []
    for item in items:
        refs = {str(entry.get("path")) for entry in item.get("read_set", []) if isinstance(entry, dict)}
        if refs & paths:
            discarded.append(str(item.get("id", "unknown")))
        else:
            kept.append(item)
    if discarded:
        index["evidence"] = kept
        atomic_write_json(index_path, index)
    return discarded


def incrementally_recompile_new_gates(
    state: Path,
    target: Path,
    package: dict[str, Any],
    compiled: dict[str, Any],
    freeze: dict[str, Any],
    new_gates: Sequence[str],
    evidence: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], bool] | None:
    """对不改变执行/授权/方案合同的新增 Gate 原子增量准入并继承同轮证据。"""
    additions = [gate for gate in GATE_ORDER if gate in new_gates and gate not in package["matched_gates"]]
    full_readmission_gates = {
        "product-change",
        "architecture-contract",
        "security-sensitive",
        "destructive-data",
        "release-external",
        "frontend-design",
    }
    if not additions or set(additions) & full_readmission_gates or package["execution_route"] == "extended":
        return None
    recompile_facts = merge_recompile_facts(package, {"gates": additions})
    neutral_cli = argparse.Namespace(scope=[], action=[], success=[], feature=[])
    candidate, blockers = build_package(
        target,
        package["original_task"],
        recompile_facts,
        neutral_cli,
        package["task_id"],
    )
    candidate["package_revision"] = package["package_revision"] + 1
    candidate["created_at"] = package["created_at"]
    candidate["recompiled_at"] = utc_now()
    stable_fields = (
        "task_id",
        "task_snapshot_ref",
        "original_task",
        "task_intent",
        "candidate_intents",
        "mutation_profile",
        "execution_route",
        "execution_topology",
        "allowed_scope",
        "read_scope",
        "write_scope",
        "git_scope",
        "external_scope",
        "git_operation",
        "git_sync_scope",
        "allowed_actions",
        "success_criteria",
        "authorization_requirements",
        "verification_commands",
        "work_packages",
        "dispatch_contracts",
        "blocking_deliverables",
    )
    if blockers or any(candidate.get(field) != package.get(field) for field in stable_fields):
        return None
    if package["execution_route"] != "direct" and candidate["plan_fields"] != package["plan_fields"]:
        return None

    action_schedule = candidate["context_schedule"]["action"]
    needs_context = bool(action_schedule["rule_ids"] or action_schedule["project_fact_refs"]) and not context_receipt_valid(
        state,
        candidate,
        target,
        stage="action",
    )
    candidate_compiled = initial_compiled(candidate, [])
    for field in (
        "plan_ref",
        "plan_fingerprint",
        "plan_artifact",
        "authorization_status",
        "authorization_receipt_ref",
        "work_package_states",
        "current_work_package",
    ):
        candidate_compiled[field] = compiled.get(field)
    candidate_compiled.update(
        {
            "control_status": compiled["control_status"],
            "verification_status": "needs_evidence" if needs_context else "not_started",
            "next_action": "load_action_context" if needs_context else "verify",
            "blockers": [],
            "scope_changed": False,
            "updated_at": utc_now(),
        }
    )
    candidate_freeze = dict(freeze)
    old_fingerprint = package_fingerprint(package)
    new_fingerprint = package_fingerprint(candidate)
    adoption = authorization_adoption_record(state, package, candidate)
    if candidate.get("authorization_requirements") and adoption is None:
        return None
    adopted: list[dict[str, Any]] = []
    for item in evidence:
        if item.get("schema_version") != EVIDENCE_RECEIPT_SCHEMA:
            continue
        value = dict(item)
        value["origin_package_fingerprint"] = value.get("origin_package_fingerprint") or value.get("package_fingerprint")
        value["adopted_from_package_fingerprint"] = value.get("package_fingerprint")
        value["package_fingerprint"] = new_fingerprint
        value["adoption_reason"] = "additive_gate_only"
        value["adopted_at"] = utc_now()
        adopted.append(value)

    with state_lock(state):
        delta = archive_and_rewrite_package(
            state,
            candidate,
            candidate_compiled,
            candidate_freeze,
            target,
        )
        if adoption is not None:
            append_jsonl(state / "authorization-receipts.jsonl", adoption)
        if adopted:
            index = read_json(state / "evidence-index.json")
            fingerprints = {item.get("source_fingerprint") for item in adopted}
            retained = [
                item
                for item in index.setdefault("evidence", [])
                if item.get("source_fingerprint") not in fingerprints
            ]
            index["evidence"] = [*retained, *adopted]
            atomic_write_json(state / "evidence-index.json", index)
        append_task_event(
            state,
            candidate,
            event="incremental_gate_readmission",
            phase="admission",
            reason_code="additive_gate_only",
            added_gates=additions,
            prior_package_fingerprint=old_fingerprint,
            adopted_evidence_ids=[str(item.get("id", "unknown")) for item in adopted],
            authorization_adopted=adoption is not None,
            disposition=delta["disposition"],
        )
    return candidate, candidate_compiled, candidate_freeze, adopted, needs_context


SCOPE_EXTENSION_LIMIT = 3

# 与增量重编译相同的稳定字段清单，但去掉 allowed_scope/write_scope：扩围本身就是对这两个字段的受控变更。
STABLE_FIELDS_MINUS_SCOPE = (
    "task_id",
    "task_snapshot_ref",
    "original_task",
    "task_intent",
    "candidate_intents",
    "mutation_profile",
    "execution_route",
    "execution_topology",
    "read_scope",
    "git_scope",
    "external_scope",
    "git_operation",
    "git_sync_scope",
    "allowed_actions",
    "success_criteria",
    "authorization_requirements",
    "verification_commands",
    "work_packages",
    "dispatch_contracts",
    "blocking_deliverables",
)


def scope_extension_count(state: Path) -> int:
    return sum(
        1
        for item in read_jsonl(state / "events.jsonl")
        if item.get("event") == "scope_extension_readmission"
    )


def enforce_supplied_write_sets_changed(supplied: Sequence[dict[str, Any]], changed: Sequence[str]) -> None:
    """硬校验 supplied 证据 write_set ⊆ 实际变化路径；虚报即失败关闭，防止 stale 证据借扩围入索引。"""
    for evidence in supplied:
        stale_write_paths = [path for path in evidence.get("write_set", []) if path not in changed]
        if stale_write_paths:
            raise HarnessError(
                "任务证据 write_set 包含实际未变化路径",
                code="stale_evidence",
                missing_items=[
                    {
                        "path": path,
                        "reason": "git_untracked_or_unchanged",
                        "hint": "write_set 只写 git 可跟踪的源码路径，构建产物路径不要写入",
                    }
                    for path in stale_write_paths
                ],
                suggested_fix="先运行 task changes-preview 或 git status --short && git diff --name-only 核对实际变更，从 write_set 中移除未变化路径",
                extra_payload={
                    "stale_write_paths": stale_write_paths,
                    "actual_changed_paths": list(changed),
                },
            )


def incrementally_extend_write_scope(
    state: Path,
    target: Path,
    package: dict[str, Any],
    compiled: dict[str, Any],
    freeze: dict[str, Any],
    outside_paths: Sequence[str],
    reusable: Sequence[dict[str, Any]],
    supplied: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[str]] | None:
    """在执行/授权/方案合同不变的前提下，把已声明的越界写入并入 write_scope 并继承同轮证据。"""
    target = Path(target).resolve()
    if package.get("execution_route") not in {"direct", "planned"}:
        return None
    if package.get("git_operation") == "git_sync":
        return None
    write_scope = list(package.get("write_scope", []))
    if not write_scope or not outside_paths:
        return None
    additions = [path for path in outside_paths if not scope_covers(path, write_scope)]
    if not additions:
        return None
    extended = list(dict.fromkeys([*write_scope, *additions]))
    recompile_facts = merge_recompile_facts(package, {"write_scope": extended})
    neutral_cli = argparse.Namespace(scope=[], action=[], success=[], feature=[])
    candidate, blockers = build_package(
        target,
        package["original_task"],
        recompile_facts,
        neutral_cli,
        package["task_id"],
    )
    candidate["package_revision"] = package["package_revision"] + 1
    candidate["created_at"] = package["created_at"]
    candidate["recompiled_at"] = utc_now()
    if blockers:
        return None
    # 硬断言：候选包必须是原范围与越界路径的超集，任何包覆写都失败关闭。
    if not set(candidate.get("write_scope", [])) >= set(write_scope) | set(outside_paths):
        return None
    if any(candidate.get(field) != package.get(field) for field in STABLE_FIELDS_MINUS_SCOPE):
        return None
    if set(candidate.get("matched_gates", [])) != set(package.get("matched_gates", [])):
        return None
    if candidate["plan_fields"] != package["plan_fields"]:
        return None
    adoption = authorization_adoption_record(state, package, candidate)
    if candidate.get("authorization_requirements") and adoption is None:
        return None
    supplied_sources = {str(item.get("source_fingerprint") or "") for item in supplied if item.get("source_fingerprint")}
    old_fingerprint = package_fingerprint(package)
    new_fingerprint = package_fingerprint(candidate)
    adopted: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for item in [*reusable, *supplied]:
        if item.get("schema_version") != EVIDENCE_RECEIPT_SCHEMA:
            continue
        source_fp = str(item.get("source_fingerprint") or "")
        if source_fp and source_fp in seen_sources:
            continue
        if source_fp:
            seen_sources.add(source_fp)
        value = dict(item)
        value["origin_package_fingerprint"] = value.get("origin_package_fingerprint") or value.get("package_fingerprint")
        value["adopted_from_package_fingerprint"] = value.get("package_fingerprint")
        value["package_fingerprint"] = new_fingerprint
        value["adoption_reason"] = "scope_superset_extension"
        value["adopted_at"] = utc_now()
        if source_fp and source_fp in supplied_sources:
            # supplied 来源：与常规 verify 路径一致，补齐受管 artifact 审计字段，避免扩展轮收据缺 artifact_ref。
            source_path = Path(str(value.get("source_ref", "")))
            if source_path.is_file() and not value.get("artifact_ref"):
                managed_evidence = store_managed_artifact(
                    state,
                    "evidence",
                    f"evidence.{value.get('id', 'item')}.v{candidate['package_revision']}.json",
                    source_path.read_text(encoding="utf-8"),
                )
                value["artifact_ref"] = str(managed_evidence)
                value["artifact_fingerprint"] = file_fingerprint(managed_evidence)
        adopted.append(value)
    candidate_compiled = initial_compiled(candidate, [])
    for field in (
        "plan_ref",
        "plan_fingerprint",
        "plan_artifact",
        "authorization_status",
        "authorization_receipt_ref",
        "work_package_states",
        "current_work_package",
    ):
        candidate_compiled[field] = compiled.get(field)
    candidate_compiled.update(
        {
            "control_status": compiled["control_status"],
            "verification_status": compiled.get("verification_status", "not_started"),
            "next_action": compiled.get("next_action", "verify"),
            "blockers": [],
            "scope_changed": False,
            "updated_at": utc_now(),
        }
    )
    candidate_freeze = dict(freeze)
    extended_paths = sorted(set(candidate["write_scope"]) - set(write_scope))
    with state_lock(state):
        delta = archive_and_rewrite_package(
            state,
            candidate,
            candidate_compiled,
            candidate_freeze,
            target,
        )
        if adoption is not None:
            append_jsonl(state / "authorization-receipts.jsonl", adoption)
        if adopted:
            index = read_json(state / "evidence-index.json")
            fingerprints = {item.get("source_fingerprint") for item in adopted}
            retained = [
                item
                for item in index.setdefault("evidence", [])
                if item.get("source_fingerprint") not in fingerprints
            ]
            index["evidence"] = [*retained, *adopted]
            atomic_write_json(state / "evidence-index.json", index)
        append_task_event(
            state,
            candidate,
            event="scope_extension_readmission",
            phase="admission",
            reason_code="scope_superset_extension",
            extended_paths=extended_paths,
            prior_package_fingerprint=old_fingerprint,
            adopted_evidence_ids=[str(item.get("id", "unknown")) for item in adopted],
            authorization_adopted=adoption is not None,
            disposition=delta["disposition"],
        )
    return candidate, candidate_compiled, candidate_freeze, adopted, extended_paths


def command_progress(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    started = time.monotonic()
    target = safe_target(args.target)
    state, package, compiled, freeze = load_state(target, args.task_id)
    if package["execution_route"] != "extended":
        raise HarnessError("只有 extended 路线使用 progress", code="progress_not_required")
    compiled = refresh_compiled_progress(state, package, compiled, target)
    if args.action == "status":
        payload = {
            "task_id": package["task_id"],
            "status": compiled["control_status"],
            "current_work_package": compiled["current_work_package"],
            "work_package_states": compiled["work_package_states"],
            "next_action": compiled["next_action"],
            "blockers": compiled["blockers"],
            "evidence_refs": compiled["evidence_refs"],
            "scope_changed": compiled["scope_changed"],
        }
        if args.handoff:
            payload["handoff"] = {
                "task_id": package["task_id"],
                "route": package["execution_route"],
                "scope": package["allowed_scope"],
                "states": compiled["work_package_states"],
                "blockers": compiled["blockers"],
                "next_action": compiled["next_action"],
            }
        return 0, payload

    if compiled["control_status"] != "ready_extended":
        raise HarnessError("任务尚未获得 ready_extended 准入", code="not_admitted", exit_code=3)
    work = next((item for item in package["work_packages"] if item["work_package_id"] == args.work_package), None)
    if not work:
        raise HarnessError("工作包不存在", code="missing_work_package")
    work_id = work["work_package_id"]
    states = compiled["work_package_states"]
    if args.action == "begin":
        if states[work_id] != "pending":
            raise HarnessError("工作包不是 pending", code="invalid_transition")
        if any(states[dep] != "verified" for dep in work["dependencies"]):
            raise HarnessError("工作包依赖尚未 verified", code="dependency_blocked", exit_code=3)
        if not context_receipt_valid(state, package, target, work_package=work_id):
            raise HarnessError("工作包上下文尚未通过 harness context 加载", code="context_not_loaded", exit_code=3)
        active_owners = {
            item["owner"]
            for item in package["work_packages"]
            if states[item["work_package_id"]] == "in_progress"
        }
        if work["owner"] in active_owners:
            raise HarnessError("同一 Owner 已有 in_progress 工作包", code="owner_busy", exit_code=3)
        event = {"schema_version": EVENT_SCHEMA, "event": "begin", "task_id": package["task_id"], "package_revision": package["package_revision"], "work_package_id": work_id, "owner": work["owner"], "workspace_snapshot": workspace_snapshot(target), "at": utc_now()}
        with state_lock(state):
            locked_states, _ = replay_progress(package, read_jsonl(state / "events.jsonl"))
            if locked_states[work_id] != "pending" or any(locked_states[dep] != "verified" for dep in work["dependencies"]):
                raise HarnessError("并发更新后工作包不再满足 begin 条件", code="concurrent_transition", exit_code=3)
            locked_active_owners = {
                item["owner"]
                for item in package["work_packages"]
                if locked_states[item["work_package_id"]] == "in_progress"
            }
            if work["owner"] in locked_active_owners:
                raise HarnessError("并发更新后同一 Owner 已有工作包", code="owner_busy", exit_code=3)
            append_task_event(
                state,
                package,
                event="begin",
                phase="business_action",
                reason_code="work_package_started",
                duration_ms=int((time.monotonic() - started) * 1000),
                work_package_id=work_id,
                owner=work["owner"],
                workspace_snapshot=event["workspace_snapshot"],
            )
        compiled = refresh_compiled_progress(state, package, compiled, target)
        return 0, {"task_id": package["task_id"], "work_package_id": work_id, "state": "in_progress", "allowed_scope": work["scope"], "next_action": compiled["next_action"]}

    if args.action == "block":
        if states[work_id] not in {"pending", "in_progress"}:
            raise HarnessError("工作包不能进入 blocked", code="invalid_transition")
        if not args.reason:
            raise HarnessError("block 必须提供 reason", code="missing_reason")
        event = {"schema_version": EVENT_SCHEMA, "event": "block", "task_id": package["task_id"], "package_revision": package["package_revision"], "work_package_id": work_id, "reason": args.reason, "scope_changed": bool(args.scope_changed), "at": utc_now()}
        with state_lock(state):
            locked_states, _ = replay_progress(package, read_jsonl(state / "events.jsonl"))
            if locked_states[work_id] not in {"pending", "in_progress"}:
                raise HarnessError("并发更新后工作包不能进入 blocked", code="concurrent_transition", exit_code=3)
            append_task_event(
                state,
                package,
                event="block",
                phase="business_action",
                reason_code="scope_changed" if args.scope_changed else "reported_blocker",
                duration_ms=int((time.monotonic() - started) * 1000),
                work_package_id=work_id,
                scope_changed=bool(args.scope_changed),
            )
        if args.scope_changed:
            compiled["scope_changed"] = True
            compiled["control_status"] = "blocked"
        compiled = refresh_compiled_progress(state, package, compiled, target)
        return 3, {"task_id": package["task_id"], "work_package_id": work_id, "state": "blocked", "scope_changed": compiled["scope_changed"], "next_action": compiled["next_action"]}

    if states[work_id] != "in_progress":
        raise HarnessError("submit 只接受 in_progress 工作包", code="invalid_transition")
    evidence_path, evidence = load_evidence(
        args.evidence,
        expected_cover=work_id,
        package=package,
        target=target,
    )
    begin_event = next(
        (
            event
            for event in reversed(read_jsonl(state / "events.jsonl"))
            if event.get("package_revision") == package["package_revision"]
            and event.get("event") == "begin"
            and event.get("work_package_id") == work_id
        ),
        None,
    )
    if not begin_event or not isinstance(begin_event.get("workspace_snapshot"), dict):
        raise HarnessError("缺少工作包 begin 快照", code="invalid_state")
    work_freeze = dict(freeze)
    work_freeze["workspace_snapshot"] = begin_event["workspace_snapshot"]
    changed, outside, new_gates = actual_scope_change(target, package, work_freeze, work["scope"])
    declared_changed = evidence.get("changed_paths", [])
    if declared_changed and sorted(declared_changed) != sorted(changed):
        extra_paths = sorted(set(declared_changed) - set(changed))
        missing_paths = sorted(set(changed) - set(declared_changed))
        raise HarnessError(
            "证据 changed_paths 与实际工作区变化不一致",
            code="stale_evidence",
            missing_items=[
                {
                    "path": path,
                    "reason": "declared_but_not_changed",
                    "hint": "write_set 只写 git 可跟踪的源码路径，构建产物路径不要写入",
                }
                for path in extra_paths
            ] + [
                {
                    "path": path,
                    "reason": "changed_but_not_declared",
                    "hint": "实际工作区变化必须全部声明在 changed_paths 中",
                }
                for path in missing_paths
            ],
            suggested_fix="git status --short && git diff --name-only 核对实际变更，从 write_set 中移除未变化路径",
        )
    if outside or new_gates:
        event = {"schema_version": EVENT_SCHEMA, "event": "block", "task_id": package["task_id"], "package_revision": package["package_revision"], "work_package_id": work_id, "reason": "范围或 Gate 变化，需要重新准入", "scope_changed": True, "changed_paths": changed, "outside_scope": outside, "new_gates": new_gates, "at": utc_now()}
        with state_lock(state):
            locked_states, _ = replay_progress(package, read_jsonl(state / "events.jsonl"))
            if locked_states[work_id] != "in_progress":
                raise HarnessError("并发更新后工作包不再是 in_progress", code="concurrent_transition", exit_code=3)
            append_task_event(
                state,
                package,
                event="block",
                phase="business_action",
                reason_code="write_scope_violation",
                duration_ms=int((time.monotonic() - started) * 1000),
                work_package_id=work_id,
                scope_changed=True,
                changed_paths=changed,
                outside_scope=outside,
                new_gates=new_gates,
            )
        compiled["scope_changed"] = True
        compiled["control_status"] = "blocked"
        compiled = refresh_compiled_progress(state, package, compiled, target)
        compiled["scope_changed"] = True
        compiled["control_status"] = "blocked"
        atomic_write_json(state / "compiled-task.json", compiled)
        return 4, {"task_id": package["task_id"], "result": "重新准入", "changed_paths": changed, "outside_scope": outside, "new_gates": new_gates, "next_action": "rerun_harness_for_readmission"}
    event = {"schema_version": EVENT_SCHEMA, "event": "submit", "task_id": package["task_id"], "package_revision": package["package_revision"], "work_package_id": work_id, "accepted": True, "evidence_refs": [str(evidence_path)], "at": utc_now()}
    with state_lock(state):
        locked_states, _ = replay_progress(package, read_jsonl(state / "events.jsonl"))
        if locked_states[work_id] != "in_progress":
            raise HarnessError("并发更新后工作包不再是 in_progress", code="concurrent_transition", exit_code=3)
        index_evidence(state, evidence)
        append_task_event(
            state,
            package,
            event="submit",
            phase="business_action",
            reason_code="work_package_evidence_accepted",
            duration_ms=int((time.monotonic() - started) * 1000),
            work_package_id=work_id,
            accepted=True,
            evidence_refs=[str(evidence_path)],
        )
    compiled = refresh_compiled_progress(state, package, compiled, target)
    return 0, {"task_id": package["task_id"], "work_package_id": work_id, "state": "verified", "changed_paths": changed, "next_action": compiled["next_action"]}


SAFE_COMMANDS = {"python", "python3", "pytest", "npm", "node", "bun", "swift", "go", "cargo", "make", "git"}
FORBIDDEN_ARGS = {"push", "publish", "deploy", "release", "reset", "clean", "checkout", "rm", "uninstall"}


def normalize_verification_command(raw: Any) -> list[str]:
    if isinstance(raw, str):
        command = shlex.split(raw)
    elif isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        command = list(raw)
    else:
        raise HarnessError("验证命令必须是字符串或字符串数组", code="invalid_verification_command")
    if not command:
        raise HarnessError("验证命令为空", code="invalid_verification_command")
    executable = Path(command[0]).name
    lowered_args = [arg.casefold() for arg in command[1:]]
    if executable not in SAFE_COMMANDS or any(arg in FORBIDDEN_ARGS for arg in lowered_args):
        raise HarnessError(f"验证命令不在安全本地检查白名单：{command}", code="unsafe_verification_command")
    if executable == "git" and (len(command) < 2 or command[1] not in {"diff", "status"}):
        raise HarnessError("verify 只允许 git diff/status", code="unsafe_verification_command")
    if executable in {"python", "python3"}:
        if "-c" in command or ("-m" in command and command[command.index("-m") + 1 : command.index("-m") + 2] not in [["unittest"], ["pytest"], ["compileall"], ["py_compile"]]):
            raise HarnessError("verify 不允许 Python 内联代码或非测试/检查模块", code="unsafe_verification_command")
    if executable == "node" and any(arg in {"-e", "--eval"} for arg in lowered_args):
        raise HarnessError("verify 不允许 Node 内联代码", code="unsafe_verification_command")
    if executable == "npm":
        if not lowered_args or lowered_args[0] not in {"test", "run"}:
            raise HarnessError("verify 只允许 npm test 或 npm run <检查脚本>", code="unsafe_verification_command")
        if lowered_args[0] == "run" and (len(lowered_args) < 2 or not any(token in lowered_args[1] for token in ("test", "check", "lint", "type", "build"))):
            raise HarnessError("npm run 仅允许测试、检查、lint、type 或 build 脚本", code="unsafe_verification_command")
    if executable == "bun" and (not lowered_args or lowered_args[0] not in {"test", "run"}):
        raise HarnessError("verify 只允许 bun test/run", code="unsafe_verification_command")
    if executable in {"swift", "go", "cargo", "make"} and (not lowered_args or not any(token in lowered_args[0] for token in ("test", "check", "build"))):
        raise HarnessError("verify 只允许本地 test/check/build", code="unsafe_verification_command")
    return command


def normalize_verification_spec(raw: Any) -> tuple[list[str], list[str]]:
    if isinstance(raw, dict):
        command = normalize_verification_command(raw.get("argv"))
        produces = normalize_string_list(raw.get("produces"), "verification_command.produces")
        unknown = set(produces) - known_evidence_types()
        if unknown:
            raise HarnessError(
                "verification_command.produces 包含未知证据类型：" + ", ".join(sorted(unknown)),
                code="invalid_verification_command",
            )
        return command, list(dict.fromkeys(produces))
    return normalize_verification_command(raw), []


def verification_input_fingerprint(target: Path, volatile_patterns: Sequence[str]) -> str:
    """排除 Harness Runtime 与允许 volatile 项后的完整工作区快照指纹，作为验证命令输入缓存键。"""
    snapshot = cached_workspace_snapshot(target, contract_version=VERSION, target_id=target_identity(target))
    filtered = {
        path: digest
        for path, digest in snapshot.items()
        if not volatile_verification_path(path, volatile_patterns)
    }
    return sha256_text(canonical_json(filtered))


def verification_command_cache_key(
    *,
    task_id: str,
    target_identity: str,
    command_argv_digest: str,
    cwd: str,
    input_fingerprint: str,
    contract_digest: str,
) -> str:
    return sha256_text(
        canonical_json(
            {
                "task_id": task_id,
                "target_identity": target_identity,
                "command_argv_digest": command_argv_digest,
                "cwd": cwd,
                "verification_input_fingerprint": input_fingerprint,
                "contract_digest": contract_digest,
            }
        )
    )


def load_verification_command_receipts(state: Path) -> dict[str, dict[str, Any]]:
    """读取验证命令收据缓存；同一 cache_key 以最后一条为准。"""
    path = state / "artifacts" / "verification" / "command-receipts.jsonl"
    index: dict[str, dict[str, Any]] = {}
    for item in read_jsonl(path):
        key = item.get("cache_key")
        if isinstance(key, str):
            index[key] = item
    return index


def verification_command_receipt_usable(receipt: dict[str, Any]) -> bool:
    if receipt.get("result") != "passed":
        return False
    ttl = receipt.get("ttl")
    cached_at = receipt.get("cached_at")
    if ttl and cached_at:
        try:
            age = (dt.datetime.now(dt.timezone.utc) - parse_utc_timestamp(cached_at, "cached_at")).total_seconds()
        except HarnessError:
            return False
        if age > float(ttl):
            return False
    return True


def run_verification_commands_cached(
    state: Path,
    target: Path,
    package: dict[str, Any],
    volatile_patterns: Sequence[str],
    *,
    cache_enabled: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """逐条执行验证命令：命中可复用通过收据则跳过；否则命令前快照→执行→命令后快照→分类写入。

    cache_enabled=False 时不读不写缓存，逐条真实执行（配置整体关闭开关）。
    返回 (results, 待持久化的缓存条目, 输入指纹)。
    """
    input_fp = verification_input_fingerprint(target, volatile_patterns)
    cache = load_verification_command_receipts(state)
    cwd = str(target.resolve())
    target_id = target_identity(target)
    results: list[dict[str, Any]] = []
    cache_entries: list[dict[str, Any]] = []
    for raw in package.get("verification_commands", []):
        command, produces = normalize_verification_spec(raw)
        argv_digest = sha256_text(canonical_json(command))
        contract_digest = sha256_text(canonical_json(raw))
        cache_key = verification_command_cache_key(
            task_id=package["task_id"],
            target_identity=target_id,
            command_argv_digest=argv_digest,
            cwd=cwd,
            input_fingerprint=input_fp,
            contract_digest=contract_digest,
        )
        cached = cache.get(cache_key) if cache_enabled else None
        if cached is not None and verification_command_receipt_usable(cached):
            results.append(
                {
                    "command": command,
                    "command_argv_digest": argv_digest,
                    "exit_code": cached.get("exit_code", 0),
                    "duration_ms": 0,
                    "started_at": cached.get("started_at"),
                    "ended_at": cached.get("ended_at"),
                    "output_or_artifact_digest": cached.get("output_or_artifact_digest"),
                    "produces": cached.get("produces", produces),
                    "result": "passed",
                    "cache_hit": True,
                }
            )
            continue
        pre = workspace_snapshot(target)
        started = time.monotonic()
        started_at = utc_now()
        command_unavailable = False
        try:
            completed = subprocess.run(command, cwd=target, capture_output=True, text=True, timeout=120, check=False)
            output_digest = sha256_text(completed.stdout + "\0" + completed.stderr)
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            output_digest = sha256_text("timeout")
            exit_code = None
        except OSError as exc:
            output_digest = sha256_text(f"unavailable:{exc}")
            exit_code = None
            command_unavailable = True
        ended_at = utc_now()
        duration_ms = int((time.monotonic() - started) * 1000)
        post = workspace_snapshot(target)
        write_set = snapshot_changes(pre, post)
        volatile_write_set = [
            path
            for path in write_set
            if path not in pre and path in post and volatile_verification_path(path, volatile_patterns)
        ]
        blocking_write_set = [path for path in write_set if path not in set(volatile_write_set)]
        result: dict[str, Any] = {
            "command": command,
            "command_argv_digest": argv_digest,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "started_at": started_at,
            "ended_at": ended_at,
            "output_or_artifact_digest": output_digest,
            "produces": produces if exit_code == 0 else [],
            "result": "passed" if exit_code == 0 else "failed",
            "cache_hit": False,
        }
        if exit_code == 0 and blocking_write_set:
            result["result"] = "failed"
            result["reason_code"] = "verification_command_workspace_write"
            result["unexpected_write_set"] = blocking_write_set
            result["produces"] = []
        if command_unavailable and result["result"] == "failed":
            result["reason_code"] = "verification_command_unavailable"
        if volatile_write_set:
            result["volatile_write_set"] = volatile_write_set
        results.append(result)
        if cache_enabled and result["result"] == "passed":
            cache_entries.append(
                {
                    "schema_version": VERIFICATION_RECEIPT_SCHEMA,
                    "cache_key": cache_key,
                    "task_id": package["task_id"],
                    "target_identity": target_id,
                    "command_argv_digest": argv_digest,
                    "cwd": cwd,
                    "verification_input_fingerprint": input_fp,
                    "contract_digest": contract_digest,
                    "produces": produces,
                    "exit_code": exit_code,
                    "output_or_artifact_digest": output_digest,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "ttl": 3600,
                    "result": "passed",
                    "cached_at": utc_now(),
                }
            )
    return results, cache_entries, input_fp


def persist_verification_command_cache(state: Path, entries: Sequence[dict[str, Any]]) -> None:
    """把本次新产生的通过收据合并进验证命令缓存；写入失败不改变既有索引。"""
    if not entries:
        return
    index = load_verification_command_receipts(state)
    for entry in entries:
        index[entry["cache_key"]] = entry
    path = artifact_store_dir(state, "verification") / "command-receipts.jsonl"
    atomic_write_text(path, "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in index.values()))


def persist_verification_receipts(
    state: Path,
    target: Path,
    package: dict[str, Any],
    results: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    root = state / "generated-evidence"
    root.mkdir(exist_ok=True)
    persisted: list[dict[str, Any]] = []
    for result in results:
        if result.get("result") != "passed":
            continue
        for evidence_type in result.get("produces", []):
            receipt_id = sha256_text(canonical_json({"task": package["task_id"], "command": result["command_argv_digest"], "type": evidence_type}))[7:23]
            path = root / f"{receipt_id}.json"
            value = {
                "schema_version": EVIDENCE_RECEIPT_SCHEMA,
                "id": receipt_id,
                "type": evidence_type,
                "result": "passed",
                "covers": [package["task_id"]],
                "task_id": package["task_id"],
                "target_identity": target_identity(target),
                "package_fingerprint": package_fingerprint(package),
                "content_set_fingerprint": None,
                "producer": {"adapter": "docs-harness", "capability": "verification_command"},
                "command_argv_digest": result["command_argv_digest"],
                "cwd": str(target.resolve()),
                "started_at": result["started_at"],
                "ended_at": result["ended_at"],
                "ttl": 3600,
                "exit_code": 0,
                "output_or_artifact_digest": result["output_or_artifact_digest"],
                "read_set": [],
                "write_set": [],
                "changed_paths": [],
                "conclusion": "声明的本地验证命令通过",
            }
            atomic_write_json(path, value)
            _, normalized = load_evidence(
                str(path),
                expected_cover=package["task_id"],
                package=package,
                target=target,
            )
            index_evidence(state, normalized)
            persisted.append(normalized)
    return persisted


def plan_is_current(compiled: dict[str, Any]) -> bool:
    raw = compiled.get("plan_ref")
    expected = compiled.get("plan_fingerprint")
    if not raw or not expected:
        return False
    path = Path(raw)
    return path.is_file() and file_fingerprint(path) == expected


def authorization_receipt_usable(receipt: dict[str, Any]) -> bool:
    artifact_ref = receipt.get("artifact_ref")
    if artifact_ref:
        managed = Path(str(artifact_ref))
        if not managed.is_file() or file_fingerprint(managed) != receipt.get("artifact_fingerprint"):
            return False
    else:
        source = Path(str(receipt.get("source_ref", "")))
        if not source.is_file() or file_fingerprint(source) != receipt.get("source_fingerprint"):
            return False
    expires = receipt.get("expires_at")
    if expires:
        try:
            expiry = dt.datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        except ValueError:
            return False
        if expiry <= dt.datetime.now(dt.timezone.utc):
            return False
    return True


def find_authorization_receipt(state: Path, fingerprint: str) -> dict[str, Any] | None:
    """返回绑定给定 package fingerprint 且仍然有效的授权收据或采用记录。"""
    for receipt in reversed(read_jsonl(state / "authorization-receipts.jsonl")):
        if receipt.get("schema_version") not in {AUTH_SCHEMA, AUTH_ADOPTION_SCHEMA}:
            continue
        if receipt.get("package_fingerprint") != fingerprint:
            continue
        return receipt if authorization_receipt_usable(receipt) else None
    return None


def authorization_is_current(state: Path, package: dict[str, Any]) -> bool:
    if not package["authorization_requirements"]:
        return True
    return find_authorization_receipt(state, package_fingerprint(package)) is not None


def evidence_source_current(item: dict[str, Any]) -> bool:
    """已摄取证据是否仍然有效：优先读受管副本，其次来源文件（兼容未摄取的历史收据）。"""
    artifact_ref = item.get("artifact_ref")
    if artifact_ref:
        managed = Path(str(artifact_ref))
        return managed.is_file() and file_fingerprint(managed) == item.get("artifact_fingerprint")
    source = Path(str(item.get("source_ref", "")))
    return source.is_file() and file_fingerprint(source) == item.get("source_fingerprint")


def authorization_adoption_record(
    state: Path,
    previous: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    """授权合同完全相同时，为新 package fingerprint 生成可审计的授权继承记录。"""
    if not candidate.get("authorization_requirements"):
        return None
    if authorization_contract_fingerprint(previous) != authorization_contract_fingerprint(candidate):
        return None
    origin = find_authorization_receipt(state, package_fingerprint(previous))
    if origin is None:
        return None
    return {
        "schema_version": AUTH_ADOPTION_SCHEMA,
        "task_id": candidate["task_id"],
        "package_revision": candidate["package_revision"],
        "package_fingerprint": package_fingerprint(candidate),
        "origin_package_fingerprint": origin.get("origin_package_fingerprint") or origin.get("package_fingerprint"),
        "adopted_from_package_fingerprint": origin.get("package_fingerprint"),
        "authorization_contract_fingerprint": authorization_contract_fingerprint(candidate),
        "authorized_actions": list(origin.get("authorized_actions", [])),
        "authorized_scope": list(origin.get("authorized_scope", [])),
        "authorized_git_scope": list(origin.get("authorized_git_scope", [])),
        "authorized_external_scope": list(origin.get("authorized_external_scope", [])),
        "external_target": origin.get("external_target"),
        "expires_at": origin.get("expires_at"),
        "source_ref": origin.get("source_ref"),
        "source_fingerprint": origin.get("source_fingerprint"),
        "artifact_ref": origin.get("artifact_ref"),
        "artifact_fingerprint": origin.get("artifact_fingerprint"),
        "trust_level": origin.get("trust_level", "reported"),
        "adoption_reason": "authorization_contract_unchanged",
        "adopted_at": utc_now(),
    }


def delivery_layer_entry(expectation: str, verified: bool, evidence_refs: Sequence[str]) -> dict[str, Any]:
    return {
        "expectation": expectation,
        "status": "verified" if verified else "not_verified",
        "evidence_refs": sorted(str(item) for item in evidence_refs),
    }


def build_delivery_layers(package: dict[str, Any], evidence_types: Sequence[str]) -> dict[str, Any]:
    """按任务意图与成功标准推导每层交付适用性，只把已验证证据绑定到对应层。"""
    intent = str(package.get("task_intent") or "")
    read_only = intent in DELIVERY_READ_ONLY_INTENTS
    git_operation = package.get("git_operation")
    criteria = " ".join(str(item) for item in package.get("success_criteria", []))
    types = {str(item) for item in evidence_types}
    manifest = package.get("completion_manifest") if isinstance(package.get("completion_manifest"), dict) else {}
    required_types = {str(item) for item in manifest.get("required_evidence_types", [])}

    layers: dict[str, Any] = {
        "source": delivery_layer_entry("required", bool(types), sorted(types)),
    }
    if read_only:
        local_expectation = "not_applicable"
    elif "test_result" in required_types or package.get("verification_commands"):
        local_expectation = "required"
    else:
        local_expectation = "not_requested"
    layers["local_verification"] = delivery_layer_entry(
        local_expectation, "test_result" in types, ["test_result"] if "test_result" in types else []
    )
    if git_operation in {"git_fetch", "git_sync"}:
        git_result_type = f"{git_operation}_result"
        layers["git_head"] = delivery_layer_entry(
            "required", git_result_type in types, [git_result_type] if git_result_type in types else []
        )
    else:
        layers["git_head"] = delivery_layer_entry("not_applicable", False, [])
    if read_only:
        remote_expectation = "not_applicable"
    elif intent in {"git_sync", "external_write"} or DELIVERY_REMOTE_REQUIRE_RE.search(criteria):
        remote_expectation = "required"
    else:
        remote_expectation = "not_requested"
    layers["remote_delivery"] = delivery_layer_entry(
        remote_expectation, "remote_delivery" in types, ["remote_delivery"] if "remote_delivery" in types else []
    )
    if read_only:
        fresh_clone_expectation = "not_applicable"
    elif DELIVERY_FRESH_CLONE_RE.search(criteria):
        fresh_clone_expectation = "required"
    else:
        fresh_clone_expectation = "not_requested"
    layers["fresh_clone"] = delivery_layer_entry(
        fresh_clone_expectation,
        "fresh_clone_verification" in types,
        ["fresh_clone_verification"] if "fresh_clone_verification" in types else [],
    )
    if read_only:
        release_expectation = "not_applicable"
    elif DELIVERY_RELEASE_RE.search(criteria):
        release_expectation = "required"
    else:
        release_expectation = "not_requested"
    layers["release_artifact"] = delivery_layer_entry(
        release_expectation,
        "release_acceptance" in types,
        ["release_acceptance"] if "release_acceptance" in types else [],
    )
    ui_expectation = "required" if "frontend-design" in package.get("matched_gates", []) else "not_applicable"
    layers["ui"] = delivery_layer_entry(
        ui_expectation, "ui_acceptance" in types, ["ui_acceptance"] if "ui_acceptance" in types else []
    )
    if intent == "external_write" or DELIVERY_INSTALL_RE.search(criteria):
        external_expectation = "required"
    elif read_only:
        external_expectation = "not_applicable"
    else:
        external_expectation = "not_requested"
    layers["external_state"] = delivery_layer_entry(
        external_expectation, "external_state" in types, ["external_state"] if "external_state" in types else []
    )
    return layers


def minimum_delivery_receipt(
    package: dict[str, Any],
    changed_paths: Sequence[str],
    evidence_types: Sequence[str],
    jobs: Sequence[dict[str, Any]],
    background_status: str,
) -> dict[str, Any]:
    layers = build_delivery_layers(package, evidence_types)
    limit_codes = [
        DELIVERY_LAYER_LIMIT_CODES[name]
        for name in DELIVERY_LAYER_ORDER
        if name in DELIVERY_LAYER_LIMIT_CODES
        and layers[name]["expectation"] == "required"
        and layers[name]["status"] != "verified"
    ]
    limit_details = [DELIVERY_LIMIT_DETAILS[code] for code in limit_codes]
    return {
        "result": "完成",
        "control_status": "complete",
        "delivered_value": list(package.get("success_criteria", [])),
        "changed_paths": list(changed_paths),
        "acceptance_layers": [name for name in DELIVERY_LAYER_ORDER if layers[name]["status"] == "verified"],
        "delivery_layers": layers,
        "minimum_evidence": [f"{item}:passed" for item in sorted(set(evidence_types))],
        "context_quality": package.get("context_quality", "complete"),
        "fallback_fact_refs": list(package.get("fallback_fact_refs", [])) or (list(changed_paths) if package.get("context_quality") == "degraded" else []),
        "known_limit_codes": limit_codes,
        "known_limit_details": limit_details,
        "background": {
            "status": background_status,
            "jobs": [str(job["job_id"]) for job in jobs],
            "job_created_at": {str(job["job_id"]): job.get("created_at") for job in jobs},
        },
    }


RETRY_VERIFICATION_REASON_CODES = {
    "verification_command_failed",
    "git_tool_unavailable",
    "git_probe_failed",
    "git_remote_unreachable",
}
REFRESH_EVIDENCE_REASON_CODES = {"read_set_drift", "stale_evidence"}
INCREMENTAL_ADMISSION_REASON_CODES = {"incremental_gate_context_required"}


def verification_reason_codes(payload: dict[str, Any]) -> list[str]:
    """从 verify 返回载荷提取受控原因码，不包含自由文本或命令输出。"""
    codes: list[str] = []
    declared = payload.get("reason_code")
    if isinstance(declared, str) and declared:
        codes.append(declared)
    commands = payload.get("verification_commands")
    if isinstance(commands, list) and any(
        isinstance(item, dict) and item.get("result") != "passed" for item in commands
    ):
        codes.append("verification_command_failed")
    for field, code in (
        ("missing_evidence_types", "missing_evidence_types"),
        ("missing_receipts", "missing_receipts"),
        ("missing_blocking_deliverables", "missing_blocking_deliverables"),
        ("stale_evidence", "stale_evidence"),
        ("incomplete_work_packages", "incomplete_work_packages"),
    ):
        if payload.get(field):
            codes.append(code)
    return list(dict.fromkeys(codes))[:VERIFICATION_REASON_CODE_LIMIT]


def classify_verification_outcome(exit_code: int, reason_codes: Sequence[str]) -> str:
    if exit_code == 0:
        return "complete"
    codes = set(reason_codes)
    if exit_code == 4:
        return "full_readmission"
    if codes & INCREMENTAL_ADMISSION_REASON_CODES:
        return "incremental_admission"
    if codes & RETRY_VERIFICATION_REASON_CODES:
        return "retry_verification"
    if codes & REFRESH_EVIDENCE_REASON_CODES:
        return "refresh_evidence"
    return "provide_evidence"


def context_load_counters(state: Path) -> tuple[int, int]:
    events = read_jsonl(state / "events.jsonl")
    full = sum(
        1
        for item in events
        if item.get("phase") == "context"
        and not item.get("context_cache_hit")
        and not item.get("context_delta")
    )
    delta = sum(1 for item in events if item.get("phase") == "context" and item.get("context_delta"))
    return full, delta


def record_verification_attempt(
    telemetry: dict[str, Any],
    *,
    exit_code: int,
    payload: dict[str, Any],
) -> None:
    """为每次 verify 入口写入一个有界遥测事件，不保存正文、输出或凭据。"""
    state = telemetry.get("state")
    package = telemetry.get("package")
    if not isinstance(state, Path) or not isinstance(package, dict):
        return
    reason_codes = verification_reason_codes(payload)
    outcome_class = classify_verification_outcome(exit_code, reason_codes)
    if not reason_codes:
        reason_codes = ["complete" if exit_code == 0 else "verification_incomplete"]
    full_loads, delta_loads = context_load_counters(state)
    with contextlib.suppress(OSError):
        append_task_event(
            state,
            package,
            event="verification_attempt",
            phase="verification",
            reason_code=reason_codes[0],
            duration_ms=int(telemetry.get("duration_ms", 0)),
            outcome_class=outcome_class,
            reason_codes=reason_codes,
            exit_code=int(exit_code),
            command_executed_count=int(telemetry.get("command_executed_count", 0)),
            command_cache_hit_count=int(telemetry.get("command_cache_hit_count", 0)),
            command_cache_enabled=bool(telemetry.get("command_cache_enabled", True)),
            context_full_load_count=full_loads,
            context_delta_load_count=delta_loads,
            evidence_regeneration_required=bool(
                outcome_class == "full_readmission" or payload.get("stale_evidence")
            ),
            changed_path_count=len(payload.get("changed_paths") or []),
        )


FAST_TRACK_DOWNGRADE_TRIGGERS = {"new_risk_gate", "high_risk_drift"}


def downgrade_fast_track_package(
    state: Path,
    target: Path,
    package: dict[str, Any],
    compiled: dict[str, Any],
    freeze: dict[str, Any],
    *,
    trigger: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """fast_track 运行期单向降级：写回普通证据集并留痕，不存在反向升级。"""
    new_package = dict(package)
    new_package["package_revision"] = package["package_revision"] + 1
    new_package["fast_track"] = False
    new_package["fast_track_downgraded"] = True
    new_package["fast_track_downgrade_reason"] = trigger
    new_package["completion_manifest"] = build_completion_manifest(
        task_intent=package["task_intent"],
        mutation_profile=package.get("mutation_profile", "workspace_write"),
        gates=package["matched_gates"],
        evidence_types=package.get("semantic_evidence_requirements", []),
        verification_commands=package.get("verification_commands", []),
        evidence_profile="standard",
    )
    new_compiled = dict(compiled)
    new_compiled["package_revision"] = new_package["package_revision"]
    new_compiled["package_fingerprint"] = package_fingerprint(new_package)
    new_compiled["updated_at"] = utc_now()
    with state_lock(state):
        delta = archive_and_rewrite_package(state, new_package, new_compiled, dict(freeze), target)
        append_task_event(
            state,
            new_package,
            event="fast_track_downgraded",
            phase="verification",
            reason_code=trigger,
            disposition=delta["disposition"],
        )
    return new_package, new_compiled, read_json(state / "freeze.json")


def command_verify(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    telemetry: dict[str, Any] = {"command_executed_count": 0, "command_cache_hit_count": 0}
    started = time.monotonic()
    try:
        exit_code, payload = verify_task(args, telemetry)
    except HarnessError as exc:
        telemetry["duration_ms"] = int((time.monotonic() - started) * 1000)
        if telemetry.get("input_accepted"):
            record_verification_attempt(
                telemetry,
                exit_code=exc.exit_code,
                payload={"reason_code": exc.code},
            )
        raise
    telemetry["duration_ms"] = int((time.monotonic() - started) * 1000)
    payload["layer_reuse"] = layer_reuse_stats()
    record_verification_attempt(telemetry, exit_code=exit_code, payload=payload)
    return exit_code, payload


def verify_task(args: argparse.Namespace, telemetry: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    state, package, compiled, freeze = load_state(target, args.task_id)
    telemetry["state"] = state
    telemetry["package"] = package
    manifest = package.get("completion_manifest")
    if not completion_manifest_valid(manifest):
        raise HarnessError("completion_manifest 缺失或指纹无效", code="invalid_completion_manifest")
    if compiled["control_status"] not in {"ready_direct", "ready_planned", "ready_extended"}:
        raise HarnessError("任务尚未获得执行准入", code="not_admitted", exit_code=3)
    if package["execution_route"] != "direct" and not plan_is_current(compiled):
        compiled["control_status"] = "blocked"
        compiled["verification_status"] = "needs_readmission"
        compiled["next_action"] = "rerun_harness_for_readmission"
        atomic_write_json(state / "compiled-task.json", compiled)
        return 4, {"task_id": package["task_id"], "result": "重新准入", "reason": "正式方案缺失或指纹已变化", "reason_code": "plan_contract_drift", "next_action": compiled["next_action"]}
    if not authorization_is_current(state, package):
        compiled["control_status"] = "blocked"
        compiled["verification_status"] = "needs_readmission"
        compiled["next_action"] = "rerun_harness_for_readmission"
        atomic_write_json(state / "compiled-task.json", compiled)
        return 4, {"task_id": package["task_id"], "result": "重新准入", "reason": "授权缺失、过期或指纹已变化", "reason_code": "authorization_contract_drift", "next_action": compiled["next_action"]}
    action_schedule = package["context_schedule"]["action"]
    if package["execution_route"] != "extended" and (action_schedule["rule_ids"] or action_schedule["project_fact_refs"]):
        if not context_receipt_valid(state, package, target, stage="action"):
            compiled["verification_status"] = "needs_evidence"
            compiled["next_action"] = "load_action_context"
            atomic_write_json(state / "compiled-task.json", compiled)
            return 3, {"task_id": package["task_id"], "result": "补充证据", "reason": "执行阶段上下文未加载或已失效", "reason_code": "action_context_missing", "pending_context_receipts": pending_context_receipts(state, package, target, compiled), "evidence_checklist": evidence_checklist_payload(state, package), "next_action": compiled["next_action"]}
    if package["execution_route"] == "extended":
        compiled = refresh_compiled_progress(state, package, compiled, target)
        incomplete = [work_id for work_id, status in compiled["work_package_states"].items() if status != "verified"]
        if incomplete:
            compiled["verification_status"] = "needs_evidence"
            atomic_write_json(state / "compiled-task.json", compiled)
            return 3, {"task_id": package["task_id"], "result": "补充证据", "reason_code": "work_package_incomplete", "incomplete_work_packages": incomplete, "next_action": compiled["next_action"]}
    git_result = git_postcheck(target, package)
    if git_result is not None and not git_result["passed"]:
        compiled["scope_changed"] = True
        compiled["control_status"] = "blocked"
        compiled["verification_status"] = "needs_readmission"
        compiled["next_action"] = "rerun_harness_for_readmission"
        atomic_write_json(state / "compiled-task.json", compiled)
        return 4, {
            "task_id": package["task_id"],
            "result": "重新准入",
            "reason_code": git_result["reason_code"],
            "git_postcheck": git_result,
            "next_action": compiled["next_action"],
        }
    binding_target_identity = target_identity(target)
    binding_package_fingerprint = package_fingerprint(package)
    supplied: list[dict[str, Any]] = []
    for raw in args.evidence or []:
        _, evidence = load_evidence(
            raw,
            expected_cover=package["task_id"],
            package=package,
            target=target,
            binding_package_fingerprint=binding_package_fingerprint,
            binding_target_identity=binding_target_identity,
        )
        supplied.append(evidence)
    telemetry["input_accepted"] = True
    reusable_evidence: list[dict[str, Any]] = []
    existing_index = read_json(state / "evidence-index.json")
    for item in existing_index.get("evidence", []):
        expires_at = item.get("expires_at")
        expired = False
        if expires_at:
            try:
                expired = parse_utc_timestamp(expires_at, "expires_at") <= dt.datetime.now(dt.timezone.utc)
            except HarnessError:
                expired = True
        binding_valid = (
            item.get("schema_version") != EVIDENCE_RECEIPT_SCHEMA
            or (
                item.get("package_fingerprint") == binding_package_fingerprint
                and item.get("target_identity") == binding_target_identity
            )
        )
        if evidence_source_current(item) and not expired and binding_valid:
            reusable_evidence.append(item)
    attribution = workspace_change_attribution(
        target,
        package,
        freeze,
        [*reusable_evidence, *supplied],
        git_result=git_result,
    )
    changed = attribution["changed_paths"]
    outside = attribution["outside_scope"]
    new_gates = attribution["new_gates"]
    blocker_codes = {str(item.get("reason_code")) for item in attribution["blockers"]}
    fast_track_downgraded_trigger: str | None = None
    if package.get("fast_track") and blocker_codes & FAST_TRACK_DOWNGRADE_TRIGGERS:
        trigger = "new_risk_gate" if "new_risk_gate" in blocker_codes else sorted(blocker_codes & FAST_TRACK_DOWNGRADE_TRIGGERS)[0]
        package, compiled, freeze = downgrade_fast_track_package(
            state,
            target,
            package,
            compiled,
            freeze,
            trigger=trigger,
        )
        telemetry["package"] = package
        manifest = package["completion_manifest"]
        fast_track_downgraded_trigger = trigger
        # 降级后 package fingerprint 已变，只有重新绑定通过的证据才能复用
        binding_package_fingerprint = package_fingerprint(package)
        reusable_evidence = [
            item
            for item in reusable_evidence
            if item.get("schema_version") != EVIDENCE_RECEIPT_SCHEMA
            or (
                item.get("package_fingerprint") == binding_package_fingerprint
                and item.get("target_identity") == binding_target_identity
            )
        ]
    if blocker_codes == {"new_risk_gate"}:
        detected_new_gates = list(new_gates)
        incremental = incrementally_recompile_new_gates(
            state,
            target,
            package,
            compiled,
            freeze,
            new_gates,
            [*reusable_evidence, *supplied],
        )
        if incremental is not None:
            package, compiled, freeze, adopted_evidence, needs_context = incremental
            telemetry["package"] = package
            reusable_evidence = adopted_evidence
            supplied = []
            attribution = workspace_change_attribution(
                target,
                package,
                freeze,
                reusable_evidence,
                git_result=git_result,
            )
            changed = attribution["changed_paths"]
            outside = attribution["outside_scope"]
            new_gates = attribution["new_gates"]
            if needs_context:
                return 3, {
                    "task_id": package["task_id"],
                    "result": "补充证据",
                    "reason_code": "incremental_gate_context_required",
                    "package_revision": package["package_revision"],
                    "added_gates": detected_new_gates,
                    "adopted_evidence_ids": [str(item.get("id", "unknown")) for item in adopted_evidence],
                    "evidence_regeneration_required": False,
                    "next_action": compiled["next_action"],
                }
    current_rules, rule_errors = load_active_rules(
        target,
        package["matched_gates"],
        package["original_task"],
        mutation_profile=package.get("mutation_profile", "workspace_write"),
    )
    frozen_rules = {(item["rule_id"], item["content_fingerprint"]) for item in package["matched_rules"]}
    active_rules = {(item["rule_id"], item["content_fingerprint"]) for item in current_rules}
    auto_attributed_paths: list[str] = []
    scope_extended_paths: list[str] = []
    if attribution["blockers"] or rule_errors or active_rules != frozen_rules:
        stable_contract = not rule_errors and active_rules == frozen_rules
        if stable_contract and blocker_codes == {"write_scope_violation"} and not new_gates:
            if scope_extension_count(state) >= SCOPE_EXTENSION_LIMIT:
                compiled["scope_changed"] = True
                compiled["control_status"] = "blocked"
                compiled["verification_status"] = "needs_readmission"
                compiled["next_action"] = "rerun_harness_for_readmission"
                atomic_write_json(state / "compiled-task.json", compiled)
                return 4, {
                    "task_id": package["task_id"],
                    "result": "重新准入",
                    "reason_code": "scope_extension_limit_exceeded",
                    "changed_paths": changed,
                    "outside_scope": outside,
                    "scope_extension_limit": SCOPE_EXTENSION_LIMIT,
                    "readmission_hint": {
                        "message": f"已达 {SCOPE_EXTENSION_LIMIT} 次增量扩围上限，需全量重准入并重新评估任务边界",
                        "facts_template": {"write_scope": list(dict.fromkeys([*package.get("write_scope", []), *outside]))},
                        "example_argv": harness_command_argv("run", target, "--task-id", package["task_id"], "--facts", "<facts.json>"),
                    },
                    "next_action": compiled["next_action"],
                }
            # 扩围前先硬校验 supplied 证据 write_set，虚报失败关闭、不扩围，与常规 verify 路径同一标准。
            enforce_supplied_write_sets_changed(supplied, changed)
            extension = incrementally_extend_write_scope(
                state,
                target,
                package,
                compiled,
                freeze,
                outside,
                reusable_evidence,
                supplied,
            )
            if extension is not None:
                package, compiled, freeze, adopted_evidence, scope_extended_paths = extension
                telemetry["package"] = package
                reusable_evidence = adopted_evidence
                supplied = []
                attribution = workspace_change_attribution(
                    target,
                    package,
                    freeze,
                    reusable_evidence,
                    git_result=git_result,
                )
                changed = attribution["changed_paths"]
                outside = attribution["outside_scope"]
                new_gates = attribution["new_gates"]
                blocker_codes = {str(item.get("reason_code")) for item in attribution["blockers"]}
        if stable_contract and "unattributed_drift_overlap" in blocker_codes and blocker_codes <= {"unattributed_drift_overlap", "new_risk_gate"}:
            write_scope = package.get("write_scope", package.get("allowed_scope", []))
            overlap_paths = sorted(
                {path for item in attribution["blockers"] if item.get("reason_code") == "unattributed_drift_overlap" for path in item.get("paths", [])}
            )
            if overlap_paths and all(scope_covers(path, write_scope) for path in overlap_paths):
                if not auto_attribute_in_scope(target):
                    compiled["verification_status"] = "needs_evidence"
                    compiled["next_action"] = "provide_evidence"
                    atomic_write_json(state / "compiled-task.json", compiled)
                    return 3, {"task_id": package["task_id"], "result": "补充证据", "reason_code": "unattributed_drift_overlap", "changed_paths": changed, "outside_scope": outside, "new_gates": new_gates, "missing_attribution_paths": overlap_paths, "auto_attributed_paths": [], "workspace_attribution": attribution, "next_action": compiled["next_action"]}
                receipt = mint_evidence_receipt(
                    target,
                    package,
                    {
                        "schema_version": EVIDENCE_DECLARATION_SCHEMA,
                        "type": "workspace_attribution",
                        "write_set": overlap_paths,
                        "conclusion": "write_scope 内未归因写入由控制器自动归因给当前任务",
                    },
                    producer={"adapter": "docs-harness", "capability": "auto_attribution"},
                )
                managed_receipt = store_managed_artifact(
                    state,
                    "evidence",
                    f"auto-attribution.v{package['package_revision']}.json",
                    json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                )
                _, auto_evidence = load_evidence(
                    str(managed_receipt),
                    expected_cover=package["task_id"],
                    package=package,
                    target=target,
                )
                supplied.append(auto_evidence)
                auto_attributed_paths = overlap_paths
                with state_lock(state):
                    append_task_event(
                        state,
                        package,
                        event="auto_attribution",
                        phase="verification",
                        reason_code="workspace_attribution",
                        paths=overlap_paths,
                        evidence_id=str(auto_evidence.get("id", "unknown")),
                    )
                attribution = workspace_change_attribution(
                    target,
                    package,
                    freeze,
                    [*reusable_evidence, *supplied],
                    git_result=git_result,
                )
                changed = attribution["changed_paths"]
                outside = attribution["outside_scope"]
                new_gates = attribution["new_gates"]
                blocker_codes = {str(item.get("reason_code")) for item in attribution["blockers"]}
                # 二次增量尝试：auto-attribution 消解 drift 后仅剩 new_risk_gate
                if stable_contract and blocker_codes == {"new_risk_gate"}:
                    incremental = incrementally_recompile_new_gates(
                        state,
                        target,
                        package,
                        compiled,
                        freeze,
                        new_gates,
                        [*reusable_evidence, *supplied],
                    )
                    if incremental is not None:
                        package, compiled, freeze, adopted_evidence, needs_context = incremental
                        telemetry["package"] = package
                        reusable_evidence = adopted_evidence
                        supplied = []
                        attribution = workspace_change_attribution(
                            target,
                            package,
                            freeze,
                            reusable_evidence,
                            git_result=git_result,
                        )
                        changed = attribution["changed_paths"]
                        outside = attribution["outside_scope"]
                        new_gates = attribution["new_gates"]
                        blocker_codes = {str(item.get("reason_code")) for item in attribution["blockers"]}
        if attribution["blockers"] or rule_errors or active_rules != frozen_rules:
            if stable_contract and blocker_codes == {"read_set_drift"}:
                drift_paths = {path for item in attribution["blockers"] for path in item.get("paths", [])}
                discarded_ids = discard_evidence_referencing_paths(state, drift_paths)
                compiled["verification_status"] = "needs_evidence"
                compiled["next_action"] = "refresh_evidence"
                atomic_write_json(state / "compiled-task.json", compiled)
                return 3, {"task_id": package["task_id"], "result": "补充证据", "reason_code": "read_set_drift", "changed_paths": changed, "outside_scope": outside, "new_gates": new_gates, "refresh_paths": sorted(drift_paths), "discarded_evidence_ids": discarded_ids, "auto_attributed_paths": auto_attributed_paths, "workspace_attribution": attribution, "next_action": compiled["next_action"]}
            compiled["scope_changed"] = True
            compiled["control_status"] = "blocked"
            compiled["verification_status"] = "needs_readmission"
            compiled["next_action"] = "rerun_harness_for_readmission"
            atomic_write_json(state / "compiled-task.json", compiled)
            reason_code = attribution["blockers"][0]["reason_code"] if attribution["blockers"] else "rule_drift"
            payload: dict[str, Any] = {"task_id": package["task_id"], "result": "重新准入", "reason_code": reason_code, "changed_paths": changed, "outside_scope": outside, "new_gates": new_gates, "rule_errors": rule_errors, "auto_attributed_paths": auto_attributed_paths, "workspace_attribution": attribution, "next_action": compiled["next_action"]}
            if fast_track_downgraded_trigger:
                payload["fast_track_downgraded"] = True
                payload["fast_track_downgrade_reason"] = fast_track_downgraded_trigger
            if "new_risk_gate" in blocker_codes and new_gates:
                payload["readmission_hint"] = {
                    "message": "可通过 --facts 声明 Gate 跳过关键词推断，避免反复循环",
                    "facts_template": {"gates": list(new_gates)},
                    "example_argv": harness_command_argv("run", target, "--task-id", package["task_id"], "--facts", "<facts.json>"),
                }
            elif "write_scope_violation" in blocker_codes and outside:
                payload["readmission_hint"] = {
                    "message": "实际写入超出 write_scope；将全部实际写入路径并入 write_scope 后一次性重准入，避免反复循环",
                    "facts_template": {"write_scope": list(dict.fromkeys([*package.get("write_scope", []), *outside]))},
                    "example_argv": harness_command_argv("run", target, "--task-id", package["task_id"], "--facts", "<facts.json>"),
                }
            elif "concurrent_drift_overlap" in blocker_codes:
                drift_paths = {
                    path
                    for item in attribution["blockers"]
                    if item.get("reason_code") == "concurrent_drift_overlap"
                    for path in item.get("paths", [])
                }
                base_scope = package.get("write_scope", package.get("allowed_scope", []))
                base_read_scope = package.get("read_scope", [])
                narrow_facts_template: dict[str, Any] = {"write_scope": [path for path in base_scope if path not in drift_paths]}
                narrowed_read_scope = [path for path in base_read_scope if path not in drift_paths]
                if narrowed_read_scope != base_read_scope:
                    # overlap 也可能来自 read_scope；read_paths 来自证据 read_set，只能走选项 2 刷新基线。
                    narrow_facts_template["read_scope"] = narrowed_read_scope
                payload["readmission_hint"] = {
                    "message": "并发写入与任务范围重叠：收窄任务范围或等待并发落定后刷新基线，二选一",
                    "options": [
                        {
                            "option": "narrow_scope",
                            "description": "将重叠路径移出任务范围（write_scope/read_scope）后重准入；若重叠来自证据 read_set，请改用选项 2",
                            "facts_template": narrow_facts_template,
                            "example_argv": harness_command_argv("run", target, "--task-id", package["task_id"], "--facts", "<facts.json>"),
                        },
                        {
                            "option": "wait_and_refresh",
                            "description": "等待并发变更落定后重新 run 刷新基线再验收",
                            "example_argv": harness_command_argv("run", target, "--task-id", package["task_id"]),
                        },
                    ],
                }
            return 4, payload

    with state_lock(state):
        enforce_supplied_write_sets_changed(supplied, changed)
        for evidence in supplied:
            source_path = Path(str(evidence.get("source_ref", "")))
            if source_path.is_file():
                managed_evidence = store_managed_artifact(
                    state,
                    "evidence",
                    f"evidence.{evidence.get('id', 'item')}.v{package['package_revision']}.json",
                    source_path.read_text(encoding="utf-8"),
                )
                evidence["artifact_ref"] = str(managed_evidence)
                evidence["artifact_fingerprint"] = file_fingerprint(managed_evidence)
            index_evidence(state, evidence)
    index = read_json(state / "evidence-index.json")
    all_evidence = index.get("evidence", [])
    fresh_evidence: list[dict[str, Any]] = []
    stale_evidence: list[str] = []
    # 增量重编译后 package 可能已替换，重新计算一次绑定指纹供循环复用
    binding_package_fingerprint = package_fingerprint(package)
    for item in all_evidence:
        evidence_writes = set(item.get("write_set", item.get("changed_paths", [])))
        task_paths_match = package["task_id"] not in item.get("covers", []) or evidence_writes <= set(changed)
        expires_at = item.get("expires_at")
        expired = False
        if expires_at:
            try:
                expired = parse_utc_timestamp(expires_at, "expires_at") <= dt.datetime.now(dt.timezone.utc)
            except HarnessError:
                expired = True
        binding_valid = (
            item.get("schema_version") != EVIDENCE_RECEIPT_SCHEMA
            or (
                item.get("package_fingerprint") == binding_package_fingerprint
                and item.get("target_identity") == binding_target_identity
            )
        )
        if evidence_source_current(item) and task_paths_match and not expired and binding_valid:
            fresh_evidence.append(item)
        else:
            stale_evidence.append(str(item.get("id", "unknown")))
    evidence_types = {
        item.get("type")
        for item in fresh_evidence
        if item.get("result") == "passed"
        and (item.get("type") not in HIGH_RISK_EVIDENCE_TYPES or item.get("trust_level") == "verified")
    }
    if git_result is not None and git_result["passed"]:
        evidence_types.add(f"{package['git_operation']}_result")
    volatile_patterns = configured_volatile_verification_patterns(target)
    cache_enabled = verification_command_cache_enabled(target)
    command_results, command_cache_entries, _verification_input_fp = run_verification_commands_cached(
        state, target, package, volatile_patterns, cache_enabled=cache_enabled
    )
    telemetry["command_executed_count"] = sum(
        1 for item in command_results if not item.get("cache_hit")
    )
    telemetry["command_cache_hit_count"] = sum(1 for item in command_results if item.get("cache_hit"))
    telemetry["command_cache_enabled"] = cache_enabled
    with state_lock(state):
        command_receipts = persist_verification_receipts(state, target, package, command_results)
        persist_verification_command_cache(state, command_cache_entries)
    command_failed = any(item["result"] != "passed" for item in command_results)
    evidence_types.update(item["type"] for item in command_receipts)
    activated_conditions: list[dict[str, str]] = []
    if package["verification_commands"] and attribution["task_write_set"]:
        activated_conditions.extend(manifest.get("conditional_evidence", []))
    required_types = list(manifest.get("required_evidence_types", []))
    required_types.extend(item["evidence_type"] for item in activated_conditions)
    missing_types = [item for item in dict.fromkeys(required_types) if item not in evidence_types]
    missing_receipts: list[str] = []
    if "read_set" in manifest.get("required_receipts", []) and not any(item.get("read_set") for item in fresh_evidence):
        missing_receipts.append("read_set")
    if "write_set" in manifest.get("required_receipts", []) and changed and not attribution["task_write_set"]:
        missing_receipts.append("write_set")
    if "git_state_snapshot" in manifest.get("required_receipts", []) and not package.get("git_state_snapshot"):
        missing_receipts.append("git_state_snapshot")
    missing_blocking_deliverables = [
        str(item["deliverable"])
        for item in package.get("blocking_deliverables", [])
        if (
            ("/" in str(item.get("deliverable", "")) or Path(str(item.get("deliverable", ""))).suffix)
            and not (target / str(item["deliverable"])).is_file()
        )
    ]
    no_evidence = not fresh_evidence and not command_results and git_result is None
    if command_failed or missing_types or missing_receipts or missing_blocking_deliverables or no_evidence:
        compiled["verification_status"] = "needs_evidence"
        compiled["next_action"] = "provide_evidence"
        atomic_write_json(state / "compiled-task.json", compiled)
        skeleton_refs = ensure_evidence_skeletons(state, missing_types)
        missing_payload: dict[str, Any] = {"task_id": package["task_id"], "result": "补充证据", "changed_paths": changed, "auto_attributed_paths": auto_attributed_paths, "workspace_attribution": attribution, "manifest_fingerprint": manifest["manifest_fingerprint"], "activated_conditions": activated_conditions, "missing_evidence_types": missing_types, "missing_receipts": missing_receipts, "missing_blocking_deliverables": missing_blocking_deliverables, "stale_evidence": stale_evidence, "verification_commands": command_results, "verification_receipts": command_receipts, "git_postcheck": git_result, "evidence_skeletons": skeleton_refs, "evidence_checklist": evidence_checklist_payload(state, package), "pending_context_receipts": pending_context_receipts(state, package, target, compiled), "next_action": compiled["next_action"]}
        if "functional_confirmation" in missing_types:
            fc_contract: list[dict[str, Any]] = []
            for item in package.get("functional_confirmation_features", []):
                if not isinstance(item, dict) or not item.get("required", False):
                    continue
                fc_contract.append(
                    {
                        "feature_id": item.get("feature_id"),
                        "name": item.get("name", item.get("feature_id")),
                        "tier": item.get("tier", ""),
                        "mode": item.get("mode", ""),
                        "assertions": item.get("assertions", []),
                        "testing_ref": item.get("testing_ref", ""),
                    }
                )
            missing_payload["functional_confirmation_contract"] = fc_contract
        if package.get("fast_track"):
            missing_payload["evidence_profile"] = "fast_track"
        if scope_extended_paths:
            missing_payload["scope_extended"] = True
            missing_payload["extended_paths"] = scope_extended_paths
        return 3, missing_payload
    if package.get("context_quality") == "degraded":
        fallback_refs = list(package.get("fallback_fact_refs", []))
        fallback_refs.extend(changed)
        for evidence in fresh_evidence:
            fallback_refs.extend(str(item) for item in evidence.get("changed_paths", []))
        compiled["fallback_fact_refs"] = list(dict.fromkeys(fallback_refs))
        compiled["context_quality"] = "degraded"
    compiled["verification_status"] = "passed"
    compiled["control_status"] = "complete"
    compiled["next_action"] = "none"
    compiled["completed_at"] = utc_now()
    fc_skipped: list[dict[str, Any]] = []
    for item in package.get("functional_confirmation_features", []):
        if (
            isinstance(item, dict)
            and not item.get("required", False)
            and str(item.get("tier", "")).upper() == "D"
        ):
            fc_skipped.append({
                "feature_id": item.get("feature_id"),
                "reason": item.get("skip_reason", "tier D，需真实账号/硬件"),
            })
    if fc_skipped:
        compiled["functional_confirmation_skipped"] = fc_skipped
    atomic_write_json(state / "compiled-task.json", compiled)
    background_jobs: list[dict[str, Any]] = []
    declared_deliverables = [
        str(item.get("deliverable"))
        for item in package.get("background_deliverables", [])
        if isinstance(item, dict) and item.get("deliverable")
    ]
    post_completion: dict[str, Any]
    knowledge_job: dict[str, Any] | None = None
    try:
        if not declared_deliverables:
            post_completion = {
                "action": "dispatch_declared_background_deliverables",
                "status": "not_required",
                "reason_code": "no_background_deliverables",
            }
        else:
            if not changed:
                post_completion = {
                    "action": "dispatch_declared_background_deliverables",
                    "status": "not_required",
                    "reason_code": "no_write_no_sync",
                }
            elif "feature_knowledge_incremental_sync" in declared_deliverables:
                knowledge_job = create_post_completion_knowledge_job(target, package, changed)
                if knowledge_job.get("created") is False:
                    post_completion = {
                        "action": "knowledge_handoff",
                        "status": "action_required",
                        "reason_code": knowledge_job.get("reason_code"),
                        "knowledge_handoff": knowledge_job.get("knowledge_handoff"),
                    }
                else:
                    background_jobs.append(knowledge_job)
                    post_completion = {
                        "action": "dispatch_declared_background_deliverables",
                        "status": "dispatch_required",
                        "job_id": knowledge_job["job_id"],
                    }
            else:
                post_completion = {
                    "action": "dispatch_declared_background_deliverables",
                    "status": "not_required",
                    "reason_code": "no_knowledge_incremental_deliverable",
                }
            governance_job = create_post_completion_governance_job(target, package, changed) if changed else None
            if governance_job:
                background_jobs.append(governance_job)
                route_contract = governance_job.get("document_route_contract", {})
                if route_contract.get("status") != "resolved":
                    post_completion = {
                        "action": "resolve_document_routes",
                        "status": "action_required",
                        "reason_code": route_contract.get("reason_code", "document_route_missing"),
                        "job_id": governance_job["job_id"],
                    }
                elif post_completion["status"] == "not_required":
                    post_completion = {
                        "action": "dispatch_declared_background_deliverables",
                        "status": "dispatch_required",
                        "job_id": governance_job["job_id"],
                    }
            if background_jobs:
                post_completion["background_job_ids"] = [job["job_id"] for job in background_jobs]
    except (HarnessError, OSError) as exc:
        reason_code = exc.code if isinstance(exc, HarnessError) else "knowledge_job_runtime_error"
        compiled["post_completion"] = {
            "action": "dispatch_knowledge_maintenance",
            "status": "dispatch_failed",
            "reason_code": reason_code,
        }
        atomic_write_json(state / "compiled-task.json", compiled)
        receipt = minimum_delivery_receipt(package, changed, sorted(str(item) for item in evidence_types), background_jobs, "dispatch_failed")
        if fc_skipped:
            receipt["functional_confirmation_skipped"] = fc_skipped
        return 0, {
            **receipt,
            "task_id": package["task_id"],
            "parent_completed_at": compiled["completed_at"],
            "evidence_types": sorted(str(item) for item in evidence_types),
            "verification_commands": command_results,
            "verification_receipts": command_receipts,
            "git_postcheck": git_result,
            "auto_attributed_paths": auto_attributed_paths,
            "workspace_attribution": attribution,
            "post_completion": {
                "action": "dispatch_knowledge_maintenance",
                "status": "dispatch_failed",
                "reason_code": reason_code,
            },
        }
    compiled["post_completion"] = post_completion
    atomic_write_json(state / "compiled-task.json", compiled)
    receipt = minimum_delivery_receipt(package, changed, sorted(str(item) for item in evidence_types), background_jobs, str(post_completion["status"]))
    success_payload: dict[str, Any] = {
        **receipt,
        "task_id": package["task_id"],
        "parent_completed_at": compiled["completed_at"],
        "evidence_types": sorted(str(item) for item in evidence_types),
        "verification_commands": command_results,
        "verification_receipts": command_receipts,
        "git_postcheck": git_result,
        "auto_attributed_paths": auto_attributed_paths,
        "workspace_attribution": attribution,
        "post_completion": {
            **post_completion,
            **({"dispatch_contract": knowledge_job} if knowledge_job and knowledge_job.get("created") is not False else {}),
        },
        "background_jobs": background_jobs,
    }
    if package.get("fast_track"):
        success_payload["evidence_profile"] = "fast_track"
    if scope_extended_paths:
        success_payload["scope_extended"] = True
        success_payload["extended_paths"] = scope_extended_paths
    if fc_skipped:
        success_payload["functional_confirmation_skipped"] = fc_skipped
    return 0, success_payload


def normalize_quality_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HarnessError(f"{field} 必须是非空字符串", code="invalid_quality_review")
    normalized = value.strip()
    if len(normalized) > QUALITY_TEXT_MAX_CHARS:
        raise HarnessError(f"{field} 超过长度限制", code="invalid_quality_review")
    if "```" in normalized or "\r" in normalized or normalized.count("\n") > 3:
        raise HarnessError(f"{field} 不能包含代码块或大段原始内容", code="invalid_quality_review")
    if any(ord(char) < 32 and char not in {"\n", "\t"} for char in normalized):
        raise HarnessError(f"{field} 包含非法控制字符", code="invalid_quality_review")
    if QUALITY_SECRET_PATTERN.search(normalized):
        raise HarnessError(f"{field} 疑似包含敏感凭据", code="invalid_quality_review")
    return normalized


def normalize_quality_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or len(value) > QUALITY_LIST_MAX_ITEMS:
        raise HarnessError(f"{field} 必须是至多 {QUALITY_LIST_MAX_ITEMS} 项的数组", code="invalid_quality_review")
    return [normalize_quality_text(item, f"{field}[]") for item in value]


def load_quality_review(path_value: str) -> dict[str, Any]:
    _, value = load_json_object_file(
        path_value,
        argument="--review",
        max_bytes=QUALITY_REVIEW_MAX_BYTES,
        error_code="invalid_quality_review",
    )
    return normalize_quality_review_value(value)


def quality_record_content_fingerprint(record: dict[str, Any]) -> str:
    value = dict(record)
    value.pop("content_fingerprint", None)
    return sha256_text(canonical_json(value))


def quality_record_snapshot_fingerprint(record: dict[str, Any]) -> str:
    value = dict(record)
    value.pop("recorded_at", None)
    value.pop("content_fingerprint", None)
    return sha256_text(canonical_json(value))


def validate_quality_record(value: Any, *, expected_task_id: str | None = None) -> dict[str, Any]:
    required = {
        "schema_version",
        "task_id",
        "recorded_at",
        "trigger_source",
        "package_revision",
        "package_fingerprint",
        "task_status_at_recording",
        "task_facts",
        "review",
        "content_fingerprint",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise HarnessError("质量记录合同无效", code="invalid_quality_record")
    if value.get("schema_version") != QUALITY_RECORD_SCHEMA:
        raise HarnessError("质量记录 schema 无效", code="invalid_quality_record")
    task_id = value.get("task_id")
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        raise HarnessError("质量记录 task-id 无效", code="invalid_quality_record")
    if expected_task_id and task_id != expected_task_id:
        raise HarnessError("质量记录 task-id 与文件名不一致", code="invalid_quality_record")
    if not isinstance(value.get("recorded_at"), str) or not value["recorded_at"]:
        raise HarnessError("质量记录缺少 recorded_at", code="invalid_quality_record")
    if value.get("trigger_source") != "reported_user_explicit":
        raise HarnessError("质量记录触发来源无效", code="invalid_quality_record")
    if not isinstance(value.get("package_revision"), int) or value["package_revision"] < 1:
        raise HarnessError("质量记录任务包版本无效", code="invalid_quality_record")
    if not isinstance(value.get("package_fingerprint"), str):
        raise HarnessError("质量记录任务包指纹无效", code="invalid_quality_record")
    if not isinstance(value.get("task_status_at_recording"), dict) or not isinstance(value.get("task_facts"), dict):
        raise HarnessError("质量记录任务事实无效", code="invalid_quality_record")
    review = value.get("review")
    if not isinstance(review, dict):
        raise HarnessError("质量记录复盘无效", code="invalid_quality_record")
    try:
        normalized_review = normalize_quality_review_value(
            {"schema_version": QUALITY_REVIEW_SCHEMA, **review}
        )
    except HarnessError as exc:
        raise HarnessError("质量记录复盘无效", code="invalid_quality_record") from exc
    if review != normalized_review:
        raise HarnessError("质量记录复盘未规范化", code="invalid_quality_record")
    if value.get("content_fingerprint") != quality_record_content_fingerprint(value):
        raise HarnessError("质量记录内容指纹不匹配", code="invalid_quality_record")
    return value


def normalize_quality_review_value(value: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(value) - QUALITY_REVIEW_FIELDS)
    missing = sorted(QUALITY_REVIEW_FIELDS - set(value))
    if unknown or missing:
        detail = []
        if missing:
            detail.append("缺少字段：" + ", ".join(missing))
        if unknown:
            detail.append("未知字段：" + ", ".join(unknown))
        raise HarnessError("；".join(detail), code="invalid_quality_review")
    if value.get("schema_version") != QUALITY_REVIEW_SCHEMA:
        raise HarnessError("质量复盘 schema 无效", code="invalid_quality_review")
    costs = value.get("cost_observations")
    if not isinstance(costs, list) or len(costs) > QUALITY_LIST_MAX_ITEMS:
        raise HarnessError("cost_observations 必须是有界数组", code="invalid_quality_review")
    normalized_costs: list[dict[str, str]] = []
    for item in costs:
        if not isinstance(item, dict) or set(item) != {"description", "source"}:
            raise HarnessError("cost_observations 项合同无效", code="invalid_quality_review")
        source = item.get("source")
        if source not in {"observed", "estimated", "unknown"}:
            raise HarnessError("cost_observations.source 无效", code="invalid_quality_review")
        normalized_costs.append(
            {
                "description": normalize_quality_text(item.get("description"), "cost_observations[].description"),
                "source": str(source),
            }
        )
    return {
        "task_summary": normalize_quality_text(value.get("task_summary"), "task_summary"),
        "record_reason": normalize_quality_text(value.get("record_reason"), "record_reason"),
        "outcome_summary": normalize_quality_text(value.get("outcome_summary"), "outcome_summary"),
        "delivered_value": normalize_quality_list(value.get("delivered_value"), "delivered_value"),
        "issues_and_rework": normalize_quality_list(value.get("issues_and_rework"), "issues_and_rework"),
        "cost_observations": normalized_costs,
        "lessons": normalize_quality_list(value.get("lessons"), "lessons"),
        "residual_risks": normalize_quality_list(value.get("residual_risks"), "residual_risks"),
        "next_actions": normalize_quality_list(value.get("next_actions"), "next_actions"),
    }


def task_quality_facts(state: Path, package: dict[str, Any], compiled: dict[str, Any]) -> dict[str, Any]:
    control_status = compiled.get("control_status")
    verification_status = compiled.get("verification_status")
    if not isinstance(control_status, str) or not isinstance(verification_status, str):
        raise HarnessError("任务控制状态无效", code="invalid_state")
    index = read_json(state / "evidence-index.json")
    if not isinstance(index, dict) or index.get("schema_version") != EVIDENCE_SCHEMA or not isinstance(index.get("evidence"), list):
        raise HarnessError("证据索引状态无效", code="invalid_state")
    evidence_types: list[str] = []
    changed_paths: list[str] = []
    for item in index["evidence"]:
        if not isinstance(item, dict):
            raise HarnessError("证据索引项目无效", code="invalid_state")
        evidence_type = item.get("type")
        if isinstance(evidence_type, str) and evidence_type:
            evidence_types.append(evidence_type)
        paths = item.get("changed_paths", [])
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            raise HarnessError("证据变更范围无效", code="invalid_state")
        changed_paths.extend(paths)
    for event in read_jsonl(state / "events.jsonl"):
        paths = event.get("changed_paths", [])
        if isinstance(paths, list):
            changed_paths.extend(path for path in paths if isinstance(path, str))
    rule_ids = [
        str(rule["rule_id"])
        for rule in package.get("matched_rules", [])
        if isinstance(rule, dict) and isinstance(rule.get("rule_id"), str)
    ]
    work_states = compiled.get("work_package_states", {})
    if not isinstance(work_states, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in work_states.items()):
        raise HarnessError("工作包状态无效", code="invalid_state")
    return {
        "status": {
            "control_status": control_status,
            "verification_status": verification_status,
        },
        "facts": {
            "task_type": str(package.get("task_type", "general")),
            "execution_route": str(package.get("execution_route", "direct")),
            "execution_topology": str(package.get("execution_topology", "single_owner")),
            "matched_gates": list(package.get("matched_gates", [])),
            "matched_rule_ids": list(dict.fromkeys(rule_ids)),
            "allowed_scope": list(package.get("allowed_scope", [])),
            "changed_paths": sorted(set(changed_paths)),
            "work_package_states": dict(sorted(work_states.items())),
            "evidence_types": sorted(set(evidence_types)),
        },
    }


def build_quality_record(state: Path, package: dict[str, Any], compiled: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    quality = task_quality_facts(state, package, compiled)
    record: dict[str, Any] = {
        "schema_version": QUALITY_RECORD_SCHEMA,
        "task_id": package["task_id"],
        "recorded_at": utc_now(),
        "trigger_source": "reported_user_explicit",
        "package_revision": package["package_revision"],
        "package_fingerprint": package_fingerprint(package),
        "task_status_at_recording": quality["status"],
        "task_facts": quality["facts"],
        "review": review,
    }
    record["content_fingerprint"] = quality_record_content_fingerprint(record)
    return record


def assert_safe_quality_paths(root: Path, records: Path, record: Path | None = None) -> None:
    for path in (root, records):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise HarnessError("质量账本目录不安全", code="unsafe_quality_path")
    if record is not None and (record.is_symlink() or (record.exists() and not record.is_file())):
        raise HarnessError("质量记录路径不安全", code="unsafe_quality_path")


def read_quality_record(path: Path, *, expected_task_id: str | None = None) -> dict[str, Any]:
    try:
        value = read_json(path)
        return validate_quality_record(value, expected_task_id=expected_task_id)
    except HarnessError:
        raise
    except (OSError, ValueError) as exc:
        raise HarnessError("质量记录不可读取", code="invalid_quality_record") from exc


def command_ledger(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    root = quality_ledger_root(target)
    records = quality_records_root(target)
    assert_safe_quality_paths(root, records)
    if args.action == "add":
        if not args.task_id or not args.review:
            raise HarnessError("ledger add 必须提供 --task-id 和 --review", code="missing_quality_input")
        if args.query is not None:
            raise HarnessError("ledger add 不接受 --query", code="invalid_quality_request")
        state, package, compiled, _ = load_state(target, args.task_id)
        review = load_quality_review(args.review)
        candidate = build_quality_record(state, package, compiled, review)
        record_path = records / f"{package['task_id']}.json"
        assert_safe_quality_paths(root, records, record_path)
        with state_lock(root):
            records.mkdir(parents=True, exist_ok=True)
            assert_safe_quality_paths(root, records, record_path)
            if record_path.exists():
                existing = read_quality_record(record_path, expected_task_id=package["task_id"])
                if quality_record_snapshot_fingerprint(existing) == quality_record_snapshot_fingerprint(candidate):
                    return 0, {
                        "status": "already_recorded",
                        "task_id": package["task_id"],
                        "record_ref": str(record_path),
                        "changed": False,
                    }
                return 2, {
                    "status": "error",
                    "code": "record_conflict",
                    "task_id": package["task_id"],
                    "record_ref": str(record_path),
                }
            atomic_write_json(record_path, candidate)
        return 0, {
            "status": "recorded",
            "task_id": package["task_id"],
            "record_ref": str(record_path),
            "task_status_at_recording": candidate["task_status_at_recording"],
            "content_fingerprint": candidate["content_fingerprint"],
            "changed": True,
        }

    if args.review is not None:
        raise HarnessError("ledger read 不接受 --review", code="invalid_quality_request")
    if args.task_id and args.query:
        raise HarnessError("ledger read 的 --task-id 与 --query 不能同时使用", code="invalid_quality_request")
    if args.limit < 1 or args.limit > QUALITY_READ_MAX_LIMIT:
        raise HarnessError(f"--limit 必须在 1 到 {QUALITY_READ_MAX_LIMIT} 之间", code="invalid_quality_request")
    if not records.exists():
        if args.task_id:
            raise HarnessError("质量记录不存在", code="missing_quality_record")
        return 0, {"status": "ok", "records": [], "invalid_records": [], "count": 0}
    assert_safe_quality_paths(root, records)
    if args.task_id:
        validate_task_id(args.task_id)
        candidates = [records / f"{args.task_id}.json"]
        if not candidates[0].is_file():
            raise HarnessError("质量记录不存在", code="missing_quality_record")
    else:
        candidates = sorted(records.glob("*.json"))
        if len(candidates) > QUALITY_RECORD_SCAN_LIMIT:
            raise HarnessError("质量记录数量超过无索引扫描上限", code="quality_scan_limit")
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    query = args.query.casefold() if isinstance(args.query, str) and args.query.strip() else None
    for path in candidates:
        try:
            if path.is_symlink():
                raise HarnessError("质量记录路径不安全", code="unsafe_quality_path")
            record = read_quality_record(path, expected_task_id=path.stem)
            if query and query not in canonical_json(record).casefold():
                continue
            valid.append(record)
        except HarnessError as exc:
            invalid.append({"task_id": path.stem, "reason_code": exc.code})
    valid.sort(key=lambda item: str(item.get("recorded_at", "")), reverse=True)
    selected = valid[: args.limit]
    return (1 if invalid else 0), {
        "status": "partial" if invalid else "ok",
        "records": selected,
        "invalid_records": invalid,
        "count": len(selected),
    }


def generate_knowledge_job_id(parent_task_id: str | None = None) -> str:
    if parent_task_id:
        validate_task_id(parent_task_id)
        return "bg" + parent_task_id[2:]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"bg-{stamp}-{uuid.uuid4().hex[:10]}"


def validate_knowledge_job_id(job_id: str) -> None:
    if not KNOWLEDGE_JOB_ID_RE.fullmatch(job_id):
        raise HarnessError("知识 Job ID 无效", code="invalid_knowledge_job")


def knowledge_job_dir(target: Path, job_id: str) -> Path:
    validate_knowledge_job_id(job_id)
    return background_jobs_root(target) / job_id


def legacy_knowledge_job_dir(target: Path, job_id: str) -> Path:
    validate_knowledge_job_id(job_id)
    return knowledge_jobs_root(target) / job_id


def write_background_job(target: Path, root: Path, job: dict[str, Any]) -> None:
    needs_legacy_mirror = job.get("task_kind") == "knowledge_incremental_sync"
    if needs_legacy_mirror and knowledge_jobs_root(target).exists() and not knowledge_jobs_root(target).is_dir():
        raise HarnessError("v1.3 兼容 Runtime 路径不可写", code="background_job_runtime_error")
    atomic_write_json(root / "job.json", job)
    if not needs_legacy_mirror:
        return
    legacy_root = legacy_knowledge_job_dir(target, str(job["job_id"]))
    atomic_write_json(legacy_root / "job.json", job)


def read_knowledge_job(target: Path, job_id: str) -> tuple[Path, dict[str, Any]]:
    root = knowledge_job_dir(target, job_id)
    if not (root / "job.json").is_file():
        legacy = legacy_knowledge_job_dir(target, job_id)
        if (legacy / "job.json").is_file():
            root = legacy
    value = read_json(root / "job.json")
    if not isinstance(value, dict) or value.get("schema_version") not in {KNOWLEDGE_JOB_SCHEMA, LEGACY_BACKGROUND_JOB_SCHEMA, "docs-harness/knowledge-job/v1"} or value.get("job_id") != job_id:
        raise HarnessError("知识 Job 合同无效", code="invalid_knowledge_job")
    if value.get("schema_version") in {LEGACY_BACKGROUND_JOB_SCHEMA, "docs-harness/knowledge-job/v1"}:
        value = {
            **value,
            "schema_version": BACKGROUND_JOB_SCHEMA,
            "task_kind": value.get("task_kind") or ("knowledge_incremental_sync" if value.get("parent_task_id") else "knowledge_bootstrap"),
            "parent_job_id": None,
            "may_mutate_parent": False,
            "may_spawn_child_jobs": False,
            "max_attempts": BACKGROUND_MAX_ATTEMPTS,
            "execution_route": value.get("execution_route", "background_direct"),
            "allowed_read_scope": value.get("allowed_read_scope", ["src/**", "tests/**", "docs/**"]),
            "forbidden_write_scope": value.get("forbidden_write_scope", ["src/**", "tests/**", ".git/**"]),
            "dependency_job_ids": value.get("dependency_job_ids", []),
        }
    return root, value


def knowledge_job_write_scope(knowledge_context: dict[str, Any]) -> list[str]:
    paths = ["docs/INDEX.md", "docs/features/INDEX.md", KNOWLEDGE_MAP_RELATIVE]
    if knowledge_context.get("status") == "new_feature":
        paths.append("docs/features/**")
    category_refs = knowledge_context.get("category_refs", {})
    if isinstance(category_refs, dict):
        for refs in category_refs.values():
            if isinstance(refs, list):
                paths.extend(str(item) for item in refs)
    paths.extend(str(item) for item in knowledge_context.get("shared_refs", []) if isinstance(item, str))
    return sorted(set(paths))


def knowledge_base_snapshot(target: Path) -> dict[str, str]:
    return {
        relative: fingerprint
        for relative, fingerprint in workspace_snapshot(target).items()
        if relative == "docs" or relative.startswith("docs/")
    }


def refresh_knowledge_job_baseline(target: Path, job: dict[str, Any]) -> None:
    allowed_scope = job.get("allowed_write_scope", [])
    if not isinstance(allowed_scope, list):
        raise HarnessError("知识 Job 写入范围无效", code="invalid_knowledge_job")
    job["base_fingerprints"] = {
        relative: file_fingerprint(target / relative)
        for relative in allowed_scope
        if "*" not in relative and (target / relative).is_file()
    }
    job["knowledge_base_snapshot"] = knowledge_base_snapshot(target)


def knowledge_job_scope_changes(target: Path, job: dict[str, Any]) -> tuple[list[str], list[str]]:
    before = job.get("knowledge_base_snapshot")
    if not isinstance(before, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in before.items()):
        raise HarnessError("知识 Job 缺少有效基线", code="invalid_knowledge_job")
    changed = snapshot_changes(before, knowledge_base_snapshot(target))
    allowed_scope = job.get("allowed_write_scope", [])
    if not isinstance(allowed_scope, list) or not all(isinstance(item, str) for item in allowed_scope):
        raise HarnessError("知识 Job 写入范围无效", code="invalid_knowledge_job")
    outside = [relative for relative in changed if not scope_covers(relative, allowed_scope)]
    return changed, outside


def mark_knowledge_job_needs_rebase(
    target: Path,
    root: Path,
    job: dict[str, Any],
    changed_paths: Sequence[str],
    reason_code: str,
) -> tuple[int, dict[str, Any]]:
    job["status"] = "needs_rebase"
    job["updated_at"] = utc_now()
    job["rebase_reason_code"] = reason_code
    job["rebase_changed_paths"] = list(changed_paths)
    write_background_job(target, root, job)
    release_knowledge_job_locks(target, job)
    append_background_event(root, job, "needs_rebase", status="needs_rebase", reason_code=reason_code)
    return 3, {
        "action": "verify",
        "job_id": job["job_id"],
        "status": "needs_rebase",
        "reason_code": reason_code,
        "changed_paths": list(changed_paths),
    }


def background_idempotency_key(
    task_kind: str,
    parent_task_id: str | None,
    feature_ids: Sequence[str],
    categories: Sequence[str],
    scope_fingerprint: str,
) -> str:
    return sha256_text(
        canonical_json(
            {
                "task_kind": task_kind,
                "parent_task_id": parent_task_id,
                "feature_ids": sorted(set(feature_ids)),
                "candidate_categories": sorted(set(categories)),
                "scope_fingerprint": scope_fingerprint,
            }
        )
    )


def governance_route_base_key(
    package: dict[str, Any], deliverables: Sequence[str]
) -> str:
    return sha256_text(canonical_json({
        "task_kind": "delivery_governance",
        "parent_task_id": package["task_id"],
        "parent_package_fingerprint": package_fingerprint(package),
        "deliverables": sorted(set(deliverables)),
    }))


def goal_contract_for_estimate(estimate: dict[str, Any], objective: str) -> dict[str, Any]:
    if estimate["execution_route"] == "background_direct":
        return {}
    return {
        "objective": objective,
        "success_criteria": [
            "合同范围内文档与当前项目事实一致",
            "知识地图、功能文档和公共知识层一致",
            "后台结果通过独立范围与基线验收",
        ],
        "plan_required": True,
        "progress_persistence": True,
        "stop_conditions": [
            "需要用户选择产品语义",
            "项目事实相互矛盾",
            "写入范围或基线发生变化",
        ],
    }


def normalized_background_work_packages(job: dict[str, Any]) -> list[dict[str, str]]:
    raw_packages = job.get("work_packages")
    if not isinstance(raw_packages, list) or not raw_packages:
        raise HarnessError("复杂后台 Job 缺少冻结工作包", code="invalid_background_job")
    packages: list[dict[str, str]] = []
    for index, raw in enumerate(raw_packages, 1):
        objective = raw.get("objective") if isinstance(raw, dict) else raw
        if not isinstance(objective, str) or not objective.strip():
            raise HarnessError("复杂后台 Job 工作包无效", code="invalid_background_job")
        packages.append({"id": f"wp-{index:02d}", "objective": objective.strip()})
    return packages


def background_goal_artifact_values(job: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    goal = job.get("goal_contract")
    if not isinstance(goal, dict) or not isinstance(goal.get("objective"), str) or not goal["objective"].strip():
        raise HarnessError("复杂后台 Job 缺少目标合同", code="invalid_background_job")
    packages = normalized_background_work_packages(job)
    common = {
        "artifact_revision": BACKGROUND_ARTIFACT_REVISION,
        "generated_by": "docs-harness",
        "job_id": str(job["job_id"]),
        "idempotency_key": str(job["idempotency_key"]),
    }
    plan = {
        "schema_version": BACKGROUND_PLAN_SCHEMA,
        **common,
        "objective": goal["objective"].strip(),
        "work_packages": packages,
    }
    states = [{"id": item["id"], "status": "pending"} for item in packages]
    progress = {
        "schema_version": BACKGROUND_PROGRESS_SCHEMA,
        **common,
        "attempt": int(job.get("attempt", 1)),
        "work_package_states": states,
        "completed_work_packages": [],
        "remaining_work_packages": [item["id"] for item in packages],
    }
    return plan, progress


def background_artifact_refs(root: Path) -> dict[str, Any]:
    plan_path = (root / "plan.json").resolve()
    progress_path = (root / "progress.json").resolve()
    return {
        "artifact_revision": BACKGROUND_ARTIFACT_REVISION,
        "attempt": None,
        "plan_ref": str(plan_path),
        "plan_fingerprint": file_fingerprint(plan_path),
        "progress_ref": str(progress_path),
        "progress_fingerprint": file_fingerprint(progress_path),
    }


def validate_background_goal_artifacts(
    root: Path,
    job: dict[str, Any],
    *,
    require_revision2: bool = True,
    require_recorded_fingerprints: bool = True,
) -> dict[str, Any]:
    """校验复杂 Job 的绑定、全集、attempt 与控制器记录的文件指纹。"""
    job_id = str(job.get("job_id", ""))
    idempotency_key = str(job.get("idempotency_key", ""))
    plan_path = root / "plan.json"
    progress_path = root / "progress.json"
    if not plan_path.is_file() or not progress_path.is_file():
        raise HarnessError("复杂后台 Job 必须先建立正式方案与持久化进度", code="missing_background_goal_artifacts", exit_code=3)
    plan = read_json(plan_path)
    progress = read_json(progress_path)
    if not isinstance(plan, dict) or plan.get("schema_version") != BACKGROUND_PLAN_SCHEMA:
        raise HarnessError("复杂后台 Job 方案合同无效", code="invalid_background_plan", exit_code=3)
    if not isinstance(progress, dict) or progress.get("schema_version") != BACKGROUND_PROGRESS_SCHEMA:
        raise HarnessError("复杂后台 Job 进度合同无效", code="invalid_background_progress", exit_code=3)
    if plan.get("job_id") != job_id or plan.get("idempotency_key") != idempotency_key:
        raise HarnessError("复杂后台 Job 方案未绑定当前 Job", code="background_plan_binding_mismatch", exit_code=3)
    if progress.get("job_id") != job_id or progress.get("idempotency_key") != idempotency_key:
        raise HarnessError("复杂后台 Job 进度未绑定当前 Job", code="background_progress_binding_mismatch", exit_code=3)
    revision2 = (
        plan.get("artifact_revision") == BACKGROUND_ARTIFACT_REVISION
        and progress.get("artifact_revision") == BACKGROUND_ARTIFACT_REVISION
        and plan.get("generated_by") == "docs-harness"
        and progress.get("generated_by") == "docs-harness"
    )
    if require_revision2 and not revision2:
        raise HarnessError("旧格式 Goal 工件不能用于新派发或新 attempt", code="legacy_background_goal_artifacts", exit_code=3)
    refs = background_artifact_refs(root)
    refs["artifact_revision"] = BACKGROUND_ARTIFACT_REVISION if revision2 else 1
    refs["attempt"] = int(job.get("attempt", 1))
    recorded = job.get("goal_artifacts")
    if require_recorded_fingerprints:
        if not isinstance(recorded, dict):
            raise HarnessError("Job 未记录 Goal 工件准备度", code="missing_background_goal_artifacts", exit_code=3)
        if any(recorded.get(key) != refs.get(key) for key in ("artifact_revision", "attempt", "plan_fingerprint", "progress_fingerprint")):
            raise HarnessError("Goal 工件指纹已漂移", code="background_goal_artifacts_tampered", exit_code=3)
    if revision2:
        expected_plan, _ = background_goal_artifact_values(job)
        packages = plan.get("work_packages")
        if plan != expected_plan or not isinstance(packages, list):
            raise HarnessError("复杂后台 Job 方案全集或冻结内容不一致", code="invalid_background_plan", exit_code=3)
        if progress.get("attempt") != int(job.get("attempt", 1)):
            raise HarnessError("复杂后台 Job 进度 attempt 不一致", code="background_progress_attempt_mismatch", exit_code=3)
        states = progress.get("work_package_states")
        if not isinstance(states, list) or any(not isinstance(item, dict) or set(item) != {"id", "status"} for item in states):
            raise HarnessError("复杂后台 Job 进度状态无效", code="invalid_background_progress", exit_code=3)
        expected_ids = [item["id"] for item in packages]
        state_ids = [item["id"] for item in states]
        if state_ids != expected_ids or len(set(state_ids)) != len(state_ids):
            raise HarnessError("复杂后台 Job 进度工作包全集不一致", code="invalid_background_progress", exit_code=3)
        if any(item["status"] not in BACKGROUND_PROGRESS_STATUSES for item in states):
            raise HarnessError("复杂后台 Job 进度状态无效", code="invalid_background_progress", exit_code=3)
        completed = [item["id"] for item in states if item["status"] == "completed"]
        remaining = [item["id"] for item in states if item["status"] != "completed"]
        if progress.get("completed_work_packages") != completed or progress.get("remaining_work_packages") != remaining:
            raise HarnessError("复杂后台 Job 进度派生列表不一致", code="invalid_background_progress", exit_code=3)
    else:
        if not isinstance(plan.get("objective"), str) or not isinstance(plan.get("work_packages"), list):
            raise HarnessError("旧格式复杂后台 Job 方案无效", code="invalid_background_plan", exit_code=3)
        if not isinstance(progress.get("completed_work_packages"), list) or not isinstance(progress.get("remaining_work_packages"), list):
            raise HarnessError("旧格式复杂后台 Job 进度无效", code="invalid_background_progress", exit_code=3)
    return refs


def append_background_event(root: Path, job: dict[str, Any], event: str, **fields: Any) -> bool:
    allowed = {
        "status", "from_status", "requested_status", "reason_code", "result",
        "work_package_id", "work_package_status", "artifact", "old_plan_fingerprint",
        "old_progress_fingerprint", "bootstrap_job_id",
    }
    value = {
        "event": event,
        "job_id": str(job.get("job_id", "")),
        "attempt": int(job.get("attempt", 1)),
        **{key: fields[key] for key in allowed if key in fields and fields[key] is not None},
        "at": utc_now(),
    }
    try:
        existing = read_jsonl(root / "events.jsonl")
        if event == "transition_rejected" and existing:
            comparable = {key: value.get(key) for key in ("event", "job_id", "attempt", "from_status", "requested_status", "reason_code")}
            previous = {key: existing[-1].get(key) for key in comparable}
            if previous == comparable:
                return True
        append_jsonl(root / "events.jsonl", value)
        return True
    except (HarnessError, OSError):
        return False


def host_dispatch_contract(target: Path, job_id: str, route: str) -> dict[str, Any]:
    complex_route = route in BACKGROUND_COMPLEX_ROUTES
    capabilities = ["background_agent"]
    if complex_route:
        capabilities.append("persistent_goal")
    if route == "background_goal_phased":
        capabilities.append("phased_work_packages")
    prepare_argv = harness_command_argv("background", target, "prepare", "--job-id", job_id)
    progress_argv = harness_command_argv(
        "background", target, "progress", "--job-id", job_id,
        "--work-package-id", "<wp-id>", "--work-package-status", "<status>",
    )
    resume = [harness_command_argv("background", target, "retry", "--job-id", job_id)]
    if complex_route:
        resume.append(prepare_argv)
    resume.extend([
        harness_command_argv("background", target, "dispatch", "--job-id", job_id, "--job-status", "dispatched"),
        harness_command_argv("background", target, "dispatch", "--job-id", job_id, "--job-status", "running"),
    ])
    return {
        "non_blocking": True,
        "required_capabilities": capabilities,
        "required_preparation": "background_goal_artifacts" if complex_route else None,
        "control_plane_write_policy": "harness_cli_only",
        "prepare_argv": prepare_argv if complex_route else None,
        "progress_argv_template": progress_argv if complex_route else None,
        "verify_argv_template": harness_command_argv(
            "background", target, "verify", "--job-id", job_id, "--result", "<result>"
        ),
        "dispatch_sequence": ["prepare", "create_host_goal", "dispatched", "running"] if complex_route else ["dispatched", "running"],
        "on_unsupported": "queued_manual",
        "silent_route_downgrade_allowed": False,
        "manual_command_argv": harness_command_argv(
            "background", target, "dispatch", "--job-id", job_id, "--job-status", "queued_manual"
        ),
        "manual_resume_argv": resume,
    }


def list_background_jobs(target: Path) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for parent in (background_jobs_root(target), knowledge_jobs_root(target)):
        if not parent.is_dir():
            continue
        for path in sorted(parent.glob("*/job.json")):
            with contextlib.suppress(HarnessError):
                value = read_json(path)
                job_id = value.get("job_id") if isinstance(value, dict) else None
                if isinstance(job_id, str) and job_id not in seen:
                    seen.add(job_id)
                    jobs.append(value)
    return sorted(jobs, key=lambda item: (str(item.get("created_at", "")), str(item.get("job_id", ""))))


def background_index_path(target: Path) -> Path:
    return background_runtime_root(target) / "index.jsonl"


def background_indexed_keys(target: Path) -> set[tuple[str, int, str]]:
    return {
        (str(item["job_id"]), int(item.get("attempt", 1)), str(item.get("status", "")))
        for item in read_jsonl(background_index_path(target))
        if isinstance(item.get("job_id"), str)
    }


def background_indexed_ids(target: Path) -> set[str]:
    return {job_id for job_id, _, _ in background_indexed_keys(target)}


def record_background_summary(target: Path, job: dict[str, Any]) -> None:
    job_id = str(job["job_id"])
    key = (job_id, int(job.get("attempt", 1)), str(job.get("status", "")))
    if key in background_indexed_keys(target):
        return
    append_jsonl(
        background_index_path(target),
        {
            "schema_version": "docs-harness/background-summary/v1",
            "job_id": job_id,
            "attempt": int(job.get("attempt", 1)),
            "task_kind": job.get("task_kind"),
            "parent_task_id": job.get("parent_task_id"),
            "status": job.get("status"),
            "execution_route": job.get("execution_route"),
            "completed_at": job.get("completed_at") or job.get("updated_at"),
        },
    )


def create_post_completion_knowledge_job(
    target: Path,
    package: dict[str, Any],
    changed_paths: Sequence[str],
) -> dict[str, Any]:
    job_id = generate_knowledge_job_id(package["task_id"])
    if repowiki_knowledge_root(target) is not None:
        return {
            "created": False,
            "task_kind": "knowledge_incremental_sync",
            "status": "not_required",
            "reason_code": "knowledge_external_consume_only",
        }
    root = knowledge_job_dir(target, job_id)
    path = root / "job.json"
    if path.is_file():
        existing_root, existing = read_knowledge_job(target, job_id)
        current_package_fingerprint = package_fingerprint(package)
        if existing.get("package_fingerprint") not in {None, current_package_fingerprint} or existing.get("changed_paths", []) != list(changed_paths):
            existing["status"] = "needs_rebase"
            existing["rebase_reason_code"] = "parent_package_changed"
            existing["updated_at"] = utc_now()
            write_background_job(target, existing_root, existing)
        return existing
    if knowledge_jobs_root(target).exists() and not knowledge_jobs_root(target).is_dir():
        raise HarnessError("v1.3 兼容 Runtime 路径不可写", code="background_job_runtime_error")
    context = package.get("knowledge_context", {})
    categories = context.get("categories") or knowledge_categories_for_gates(package.get("matched_gates", []))
    allowed_scope = knowledge_job_write_scope(context)
    if scope_claims_background_control_plane(target, allowed_scope):
        raise HarnessError("后台 Job 业务范围不得覆盖 Harness 控制面", code="invalid_background_scope")
    estimate = workload_estimate(
        target,
        candidate={
            "estimate_basis": "change_scoped",
            "changed_paths": list(changed_paths),
            "selected_features": list(context.get("selected_features", [])),
            "deliverables": ["feature_knowledge_incremental_sync"],
            "allowed_write_scope": allowed_scope,
            "requires_plan": False,
        },
    )
    estimate_path = persist_workload_estimate(target, estimate)
    ready_for_incremental = knowledge_ready_for_incremental(target)
    active_bootstrap = None if ready_for_incremental else active_knowledge_bootstrap(target)
    if not active_bootstrap and not ready_for_incremental:
        return {
            "created": False,
            "task_kind": "knowledge_incremental_sync",
            "status": "action_required",
            "reason_code": "knowledge_not_ready",
            "knowledge_handoff": knowledge_handoff(target, "post_completion", True),
        }
    initial_status = "waiting_for_bootstrap_merge" if active_bootstrap else "contract_ready"
    now = utc_now()
    job = {
        "schema_version": KNOWLEDGE_JOB_SCHEMA,
        "job_id": job_id,
        "task_kind": "knowledge_incremental_sync",
        "parent_task_id": package["task_id"],
        "parent_job_id": None,
        "may_mutate_parent": False,
        "may_spawn_child_jobs": False,
        "suppress_post_completion_dispatch": True,
        "status": initial_status,
        "execution_route": estimate["execution_route"],
        "workload_estimate_ref": str(estimate_path),
        "attempt": 1,
        "max_attempts": BACKGROUND_MAX_ATTEMPTS,
        "feature_ids": list(context.get("selected_features", [])),
        "new_feature_registration": context.get("status") == "new_feature",
        "changed_paths": list(changed_paths),
        "matched_gates": list(package.get("matched_gates", [])),
        "candidate_categories": list(categories),
        "allowed_read_scope": sorted(set([*package.get("allowed_scope", []), "docs/**", "tests/**"])),
        "allowed_write_scope": allowed_scope,
        "forbidden_write_scope": ["src/**", "tests/**", ".git/**"],
        "goal_contract": goal_contract_for_estimate(estimate, "同步本次业务变化对应的功能知识"),
        "host_dispatch_contract": host_dispatch_contract(target, job_id, estimate["execution_route"]),
        "work_packages": estimate["suggested_work_packages"] if estimate["requires_plan"] else [],
        "dependency_job_ids": [active_bootstrap["job_id"]] if active_bootstrap else [],
        "package_fingerprint": package_fingerprint(package),
        "idempotency_key": background_idempotency_key(
            "knowledge_incremental_sync",
            package["task_id"],
            context.get("selected_features", []),
            categories,
            estimate["source_fingerprint"],
        ),
        "created_at": now,
        "updated_at": now,
        "stale_after": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).replace(microsecond=0).isoformat(),
    }
    refresh_knowledge_job_baseline(target, job)
    root.mkdir(parents=True, exist_ok=True)
    write_background_job(target, root, job)
    atomic_write_text(root / "events.jsonl", "")
    append_background_event(root, job, "created", status=initial_status)
    return job


def create_post_completion_governance_job(
    target: Path,
    package: dict[str, Any],
    changed_paths: Sequence[str],
) -> dict[str, Any] | None:
    deliverables = [
        item["deliverable"]
        for item in package.get("background_deliverables", [])
        if item.get("deliverable") != "feature_knowledge_incremental_sync"
    ]
    if not deliverables:
        return None
    required_kinds = governance_required_kinds(deliverables)
    if not required_kinds:
        return None
    route_contract = resolve_document_routes(target, required_kinds=required_kinds)
    route_reads, route_writes = governance_route_scopes(route_contract)
    estimate = workload_estimate(
        target,
        candidate={
            "estimate_basis": "change_scoped",
            "changed_paths": list(changed_paths),
            "selected_features": list(package.get("knowledge_context", {}).get("selected_features", [])),
            "deliverables": deliverables,
            "allowed_write_scope": route_writes,
            "requires_plan": len(deliverables) > 2,
        },
    )
    job, _ = create_background_job(
        target,
        task_kind="delivery_governance",
        estimate=estimate,
        parent_task_id=package["task_id"],
        categories=deliverables,
        allowed_read_scope=sorted(set([*package.get("allowed_scope", []), *route_reads])),
        allowed_write_scope=route_writes,
        forbidden_write_scope=("src/**", "tests/**", ".git/**"),
        changed_paths=changed_paths,
        objective="完成不阻塞父任务的 ADR、Changelog、TODO 与证据整理",
        route_base_key=governance_route_base_key(package, deliverables),
        document_route_contract=route_contract,
    )
    return job


SOURCE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".dart", ".ex", ".exs", ".go", ".java", ".js",
    ".jsx", ".kt", ".kts", ".m", ".mm", ".php", ".py", ".rb", ".rs", ".scala",
    ".sh", ".swift", ".ts", ".tsx", ".vue",
}
TECH_STACK_BY_EXTENSION = {
    ".c": "c-cpp", ".cc": "c-cpp", ".cpp": "c-cpp", ".cs": "dotnet",
    ".dart": "dart", ".ex": "elixir", ".exs": "elixir", ".go": "go", ".java": "jvm",
    ".js": "javascript", ".jsx": "javascript", ".kt": "jvm", ".kts": "jvm",
    ".m": "apple", ".mm": "apple", ".php": "php", ".py": "python", ".rb": "ruby",
    ".rs": "rust", ".scala": "jvm", ".sh": "shell", ".swift": "apple",
    ".ts": "typescript", ".tsx": "typescript", ".vue": "vue",
}
WORKLOAD_EXCLUDED_PARTS = {
    ".git", ".docs-harness", "node_modules", "vendor", ".venv", "venv", "dist", "build",
    ".next", ".cache", "coverage", "target", "deriveddata", "pods", ".playwright-cli",
    "zbuddy-output",
}
BINARY_ASSET_EXTENSIONS = {
    ".7z", ".avi", ".bmp", ".dmg", ".doc", ".docx", ".gif", ".gz", ".heic",
    ".ico", ".jpeg", ".jpg", ".key", ".m4a", ".mov", ".mp3", ".mp4", ".numbers",
    ".pages", ".pdf", ".png", ".ppt", ".pptx", ".rar", ".tar", ".tiff", ".wav",
    ".webm", ".webp", ".xls", ".xlsx", ".zip",
}


def inventory_include_patterns(target: Path) -> list[str]:
    config = project_config(target) or {}
    knowledge = config.get("knowledge", {}) if isinstance(config.get("knowledge"), dict) else {}
    return validate_scope(
        normalize_string_list(knowledge.get("inventory_include"), "knowledge.inventory_include")
    ) if knowledge.get("inventory_include") is not None else []


def inventory_path_decision(target: Path, relative: str, *, include_patterns: Sequence[str]) -> tuple[bool, str | None]:
    lowered = relative.casefold()
    parts = tuple(part.casefold() for part in Path(relative).parts)
    explicitly_included = any(fnmatch.fnmatchcase(relative, pattern) for pattern in include_patterns)
    if relative in {"AGENTS.md", "CLAUDE.md", "scripts/harness.py", ".DS_Store"}:
        return False, "control_or_temporary"
    if any(part in {item.casefold() for item in WORKLOAD_EXCLUDED_PARTS} for part in parts):
        return (True, "explicit_include") if explicitly_included else (False, "generated_or_runtime")
    if any(term in lowered for term in (".env", "credential", "secret", "private", "token", "password", "keychain")):
        return False, "sensitive"
    suffix = Path(lowered).suffix
    if suffix in BINARY_ASSET_EXTENSIONS:
        return (True, "explicit_include") if explicitly_included else (False, "binary_or_packaged")
    if Path(relative).name.startswith((".~", ".#")) or Path(relative).name.endswith(("~", ".tmp", ".temp")):
        return False, "control_or_temporary"
    return True, "explicit_include" if explicitly_included else None


def knowledge_scan_inventory_details(target: Path) -> tuple[list[str], dict[str, int], list[str]]:
    items, _ = bounded_project_inventory(target)
    inventory = [item["path"] for item in items if not item["path"].startswith("docs/")]
    summary = dict(getattr(bounded_project_inventory, "last_excluded_summary", {}))
    return inventory, summary, inventory_include_patterns(target)


def knowledge_scan_inventory(target: Path) -> list[str]:
    inventory, _, _ = knowledge_scan_inventory_details(target)
    return inventory


def knowledge_inventory_fingerprint(target: Path) -> str:
    inventory, _, includes = knowledge_scan_inventory_details(target)
    return sha256_text(canonical_json({"inventory": inventory, "explicit_includes": includes}))


def docs_inventory_fingerprint(target: Path) -> str:
    """v1 名称兼容；v1.6 起绑定过滤后项目库存。"""
    return knowledge_inventory_fingerprint(target)


def bounded_project_inventory(target: Path) -> tuple[list[dict[str, Any]], bool]:
    """只收集路由所需元数据；超过上限时返回 truncated 而不是失败。"""
    paths: list[Path] = []
    excluded_summary: dict[str, int] = {}
    include_patterns = inventory_include_patterns(target)
    root = git_root(target)
    if root == target.resolve():
        result = subprocess.run(
            ["git", "-C", str(target), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            for raw in result.stdout.split(b"\0"):
                if not raw:
                    continue
                with contextlib.suppress(UnicodeDecodeError):
                    paths.append(target / raw.decode("utf-8"))
    if not paths:
        for current, dirs, files in os.walk(target):
            dirs[:] = [name for name in dirs if name.casefold() not in {item.casefold() for item in WORKLOAD_EXCLUDED_PARTS}]
            base = Path(current)
            for name in files:
                paths.append(base / name)
                if len(paths) > FALLBACK_SNAPSHOT_FILE_LIMIT:
                    break
            if len(paths) > FALLBACK_SNAPSHOT_FILE_LIMIT:
                break
    items: list[dict[str, Any]] = []
    truncated = len(paths) > FALLBACK_SNAPSHOT_FILE_LIMIT
    for path in paths[: FALLBACK_SNAPSHOT_FILE_LIMIT + 1]:
        with contextlib.suppress(OSError, ValueError):
            relative = path.resolve().relative_to(target.resolve()).as_posix()
            included, reason = inventory_path_decision(target, relative, include_patterns=include_patterns)
            if not included:
                excluded_summary[reason or "other"] = excluded_summary.get(reason or "other", 0) + 1
                continue
            stat = path.stat()
            if not path.is_file() or stat.st_size > 2 * 1024 * 1024:
                excluded_summary["oversized_or_unreadable"] = excluded_summary.get("oversized_or_unreadable", 0) + 1
                continue
            items.append({"path": relative, "size": stat.st_size, "extension": path.suffix.casefold()})
            if len(items) > FALLBACK_SNAPSHOT_FILE_LIMIT:
                truncated = True
                items = items[:FALLBACK_SNAPSHOT_FILE_LIMIT]
                break
    bounded_project_inventory.last_excluded_summary = excluded_summary
    return items, truncated


def score_bucket(value: int, boundaries: Sequence[tuple[int, int]], overflow: int) -> int:
    for maximum, score in boundaries:
        if value <= maximum:
            return score
    return overflow


def workload_estimate(target: Path, *, candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    inventory, truncated = bounded_project_inventory(target)
    candidate = candidate or {}
    estimate_basis = candidate.get("estimate_basis", "project_wide")
    if estimate_basis not in {"project_wide", "change_scoped"}:
        raise HarnessError("estimate_basis 必须是 project_wide 或 change_scoped", code="invalid_background_candidate")
    changed_paths: list[str] = []
    selected_features: list[str] = []
    deliverables: list[str] = []
    estimate_write_scope: list[str] = []
    if estimate_basis == "change_scoped":
        for field, limit in (("changed_paths", 512), ("selected_features", 100), ("deliverables", 100), ("allowed_write_scope", 256)):
            value = candidate.get(field, [])
            if not isinstance(value, list) or len(value) > limit or not all(isinstance(item, str) and 0 < len(item) <= 500 for item in value):
                raise HarnessError(f"{field} 必须是有界字符串数组", code="invalid_background_candidate")
        changed_paths = validate_scope(candidate.get("changed_paths", []), field="changed_paths")
        estimate_write_scope = validate_scope(candidate.get("allowed_write_scope", []), field="allowed_write_scope")
        selected_features = list(dict.fromkeys(candidate.get("selected_features", [])))
        deliverables = list(dict.fromkeys(candidate.get("deliverables", [])))
    source_items = [item for item in inventory if item["extension"] in SOURCE_EXTENSIONS]
    source_count = len(source_items)
    stacks = sorted({TECH_STACK_BY_EXTENSION[item["extension"]] for item in source_items})
    domain_markers = {"apps", "app", "services", "service", "packages", "runtime", "server", "client", "desktop", "mobile", "web"}
    domain_values: set[str] = set()
    for item in source_items:
        parts = Path(item["path"]).parts
        if not parts or parts[0].casefold() not in domain_markers:
            continue
        if parts[0].casefold() in {"apps", "services", "packages"} and len(parts) >= 2:
            domain_values.add("/".join(parts[:2]))
        else:
            domain_values.add(parts[0])
    domains = sorted(domain_values)
    if not domains and source_items:
        domains = ["project"]
    feature_roots: set[str] = set()
    for item in source_items:
        parts = Path(item["path"]).parts
        if len(parts) >= 2 and parts[0].casefold() in {"src", "lib", "app", "apps", "packages", "services", "modules", "features"}:
            feature_roots.add("/".join(parts[: min(3, len(parts) - 1)]))
        elif len(parts) >= 2:
            feature_roots.add("/".join(parts[:2]))
    feature_count = min(len(feature_roots), 500)
    status = knowledge_status(target)
    if status["status"] in {"absent", "needs_audit", "needs_bootstrap", "building", "invalid", "quarantined"}:
        doc_gap_score = 18
        coverage_label = "无地图"
    else:
        total = max(int(status.get("features", 0)) * 4, 1)
        gap_ratio = len(status.get("gaps", [])) / total
        if gap_ratio < 0.25:
            doc_gap_score, coverage_label = 0, "缺口低于 25%"
        elif gap_ratio <= 0.60:
            doc_gap_score, coverage_label = 8, "缺口 25%-60%"
        else:
            doc_gap_score, coverage_label = 14, "缺口高于 60%"
    dependency_score = 0
    dependency_label = "低"
    cyclic_dependencies = False
    with contextlib.suppress(HarnessError):
        knowledge = read_knowledge_map(target, require_files=False)
        if knowledge:
            edges = sum(len(feature["dependencies"]) for feature in knowledge["features"])
            if edges > max(10, len(knowledge["features"])):
                dependency_score, dependency_label = 9, "高"
            elif edges:
                dependency_score, dependency_label = 4, "中"
            graph = {feature["feature_id"]: list(feature["dependencies"]) for feature in knowledge["features"]}
            visiting: set[str] = set()
            visited: set[str] = set()
            def visit(node: str) -> bool:
                if node in visiting:
                    return True
                if node in visited:
                    return False
                visiting.add(node)
                found = any(visit(dep) for dep in graph.get(node, []))
                visiting.remove(node)
                visited.add(node)
                return found
            cyclic_dependencies = any(visit(node) for node in graph)
    scores = {
        "source_files": score_bucket(source_count, ((150, 0), (800, 8), (3000, 16)), 24),
        "feature_candidates": score_bucket(feature_count, ((5, 0), (15, 8), (40, 16)), 22),
        "architecture_domains": score_bucket(len(domains), ((1, 0), (2, 5), (4, 10)), 15),
        "technology_stacks": score_bucket(len(stacks), ((1, 0), (2, 4), (3, 8)), 12),
        "knowledge_gap": doc_gap_score,
        "cross_feature_dependencies": dependency_score,
    }
    raw_score = min(sum(scores.values()), 100)
    project_raw_score = raw_score
    project_context = {"raw_score": project_raw_score, "scan_truncated": truncated}
    effective_source_count = source_count
    effective_feature_count = feature_count
    effective_domains = domains
    effective_stacks = stacks
    change_scope_fingerprint: str | None = None
    if estimate_basis == "change_scoped":
        changed_source_paths = [path for path in changed_paths if Path(path).suffix.casefold() in SOURCE_EXTENSIONS]
        changed_stacks = sorted({TECH_STACK_BY_EXTENSION[Path(path).suffix.casefold()] for path in changed_source_paths})
        changed_domains = sorted({Path(path).parts[0] for path in changed_paths if Path(path).parts})
        scoped_features = selected_features or sorted({"/".join(Path(path).parts[:2]) for path in changed_paths if len(Path(path).parts) >= 2})
        effective_source_count = len(changed_source_paths)
        effective_feature_count = len(scoped_features)
        effective_domains = changed_domains
        effective_stacks = changed_stacks
        scores = {
            "source_files": score_bucket(effective_source_count, ((5, 0), (25, 5), (100, 10)), 16),
            "feature_candidates": score_bucket(effective_feature_count, ((1, 0), (3, 5), (8, 10)), 16),
            "architecture_domains": score_bucket(len(effective_domains), ((1, 0), (2, 4), (4, 8)), 12),
            "technology_stacks": score_bucket(len(effective_stacks), ((1, 0), (2, 4), (3, 8)), 12),
            "knowledge_gap": min(doc_gap_score, 8) if deliverables else 0,
            "cross_feature_dependencies": min(dependency_score, 6),
        }
        raw_score = min(sum(scores.values()), 100)
        change_scope_fingerprint = sha256_text(canonical_json({
            "changed_paths": changed_paths,
            "selected_features": selected_features,
            "deliverables": deliverables,
            "allowed_write_scope": estimate_write_scope,
        }))
    if raw_score <= 24:
        workload_class, score_route = "simple", "background_direct"
    elif raw_score <= 59:
        workload_class, score_route = "complex", "background_goal"
    else:
        workload_class, score_route = "oversized", "background_goal_phased"
    route_override_reason: str | None = None
    final_route = score_route
    existing_doc_count = sum(1 for item in inventory if item["path"].startswith("docs/") and item["extension"] in {".md", ".rst", ".txt"})
    if estimate_basis == "project_wide" and truncated:
        route_override_reason = "scan_file_limit_exceeded"
        final_route = "background_goal_phased"
        workload_class = "oversized"
    elif estimate_basis == "project_wide" and len(domains) >= 5 and final_route != "background_goal_phased":
        route_override_reason = "multiple_independent_domains"
        final_route = "background_goal_phased"
        workload_class = "oversized"
    elif estimate_basis == "project_wide" and cyclic_dependencies and final_route != "background_goal_phased":
        route_override_reason = "cyclic_or_unowned_dependencies"
        final_route = "background_goal_phased"
        workload_class = "oversized"
    elif estimate_basis == "project_wide" and existing_doc_count >= 50 and final_route != "background_goal_phased":
        route_override_reason = "large_existing_docs_preserve_and_merge"
        final_route = "background_goal_phased"
        workload_class = "oversized"
    elif estimate_basis == "project_wide" and existing_doc_count >= 10 and final_route == "background_direct":
        route_override_reason = "existing_docs_preserve_and_merge"
        final_route = "background_goal"
        workload_class = "complex"
    elif candidate and candidate.get("requires_plan") is True and final_route == "background_direct":
        route_override_reason = "candidate_requires_plan"
        final_route = "background_goal"
        workload_class = "complex"
    reasons = [
        f"识别到 {effective_source_count} 个估算范围内源码文件",
        f"识别到 {effective_feature_count} 个估算范围内功能候选",
        f"估算范围架构域 {len(effective_domains)} 个，技术栈 {len(effective_stacks)} 个",
        f"四类功能文档{coverage_label}，跨功能依赖{dependency_label}",
    ]
    fingerprint_input = [{"path": item["path"], "size": item["size"]} for item in inventory]
    if estimate_basis == "change_scoped":
        current = workspace_snapshot(target)
        scoped_files = {
            path: fingerprint
            for path, fingerprint in current.items()
            if path in set(changed_paths) or scope_covers(path, estimate_write_scope)
        }
        source_fingerprint = sha256_text(
            canonical_json(
                {
                    "change_scope_fingerprint": change_scope_fingerprint,
                    "scoped_files": scoped_files,
                }
            )
        )
    else:
        source_fingerprint = sha256_text(canonical_json(fingerprint_input))
    return {
        "schema_version": WORKLOAD_ESTIMATE_SCHEMA,
        "estimate_basis": estimate_basis,
        "project_scale_context": project_context,
        "change_scope_fingerprint": change_scope_fingerprint,
        "workload_class": workload_class,
        "raw_score": raw_score,
        "score_route": score_route,
        "route_override_reason": route_override_reason,
        "confidence": "low" if truncated else ("medium" if effective_source_count else "low"),
        "reasons": reasons,
        "score_dimensions": scores,
        "execution_route": final_route,
        "requires_plan": final_route != "background_direct",
        "blocking_main_task": False,
        "scan_file_count": len(inventory),
        "source_file_count": effective_source_count,
        "feature_candidate_count": effective_feature_count,
        "architecture_domain_count": len(effective_domains),
        "technology_stack_count": len(effective_stacks),
        "scan_truncated": truncated,
        "source_fingerprint": source_fingerprint,
        "suggested_work_packages": [
            "功能识别与知识地图",
            "功能文档补全",
            "公共知识层",
            "一致性与交付验收",
        ],
    }


def persist_workload_estimate(target: Path, estimate: dict[str, Any]) -> Path:
    root = background_estimates_root(target)
    estimate_id = sha256_text(canonical_json({
        key: estimate.get(key)
        for key in ("source_fingerprint", "execution_route", "raw_score", "estimate_basis", "change_scope_fingerprint")
    })).removeprefix("sha256:")[:16]
    path = root / f"{estimate_id}.json"
    if not path.is_file():
        atomic_write_json(path, estimate)
    return path


def classify_document_deliverables(
    task: str,
    facts: dict[str, Any],
    gates: Sequence[str],
    scope: Sequence[str],
    *,
    mutation_profile: str = "workspace_write",
    target: Path | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    blocking: list[dict[str, str]] = []
    background: list[dict[str, str]] = []
    for item in normalize_string_list(facts.get("blocking_deliverables"), "blocking_deliverables"):
        blocking.append({"deliverable": item, "reason_code": "user_or_gate_required"})
    for item in normalize_string_list(facts.get("background_deliverables"), "background_deliverables"):
        background.append({"deliverable": item, "reason_code": "explicit_background_candidate"})
    document_paths = [path for path in scope if path.casefold().endswith((".md", ".rst", ".txt"))]
    if "document-edit" in gates:
        for path in document_paths or ["current_task_document"]:
            blocking.append({"deliverable": path, "reason_code": "user_requested_document"})
    if set(gates) & {"architecture-contract", "destructive-data", "release-external", "security-sensitive"}:
        blocking.append({"deliverable": "required_contract_and_recovery_evidence", "reason_code": "control_or_acceptance_required"})
    business_write = mutation_profile in {"workspace_write", "external_write"} and any(
        not path.casefold().endswith((".md", ".rst", ".txt"))
        and not path.casefold().startswith("docs/")
        for path in scope
    )
    # repowiki 只消费项目不回流任何知识/文档治理交付物
    external_consume_only = target is not None and repowiki_knowledge_root(target) is not None
    if not external_consume_only and not facts.get("suppress_post_completion_dispatch", False) and business_write:
        background.append({"deliverable": "feature_knowledge_incremental_sync", "reason_code": "business_write_governance"})
        if set(gates) & {"product-change", "architecture-contract", "code-edit", "release-external"}:
            background.append({"deliverable": "adr_changelog_todo_review", "reason_code": "default_non_blocking_governance"})
    def dedupe(values: list[dict[str, str]]) -> list[dict[str, str]]:
        return list({item["deliverable"]: item for item in values}.values())
    return dedupe(blocking), dedupe(background)


def normalize_knowledge_assessment(target: Path, raw_path: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    path, value = load_json_object_file(
        raw_path,
        argument="--assessment",
        max_bytes=1024 * 1024,
        error_code="invalid_knowledge_assessment",
    )
    if value.get("schema_version") != KNOWLEDGE_ASSESSMENT_SCHEMA:
        raise HarnessError("知识审查报告 schema 无效", code="invalid_knowledge_assessment")
    status = value.get("status")
    if status not in {"ready", "partial"}:
        raise HarnessError("知识审查状态必须是 ready 或 partial", code="invalid_knowledge_assessment")
    gaps = normalize_string_list(value.get("gaps"), "gaps")
    if status == "ready" and gaps:
        raise HarnessError("ready 审查不能同时声明缺口", code="invalid_knowledge_assessment")
    map_value = {
        "schema_version": KNOWLEDGE_MAP_SCHEMA,
        "knowledge_level": "L2",
        "reviewed_revision": value.get("reviewed_revision"),
        "features": value.get("features", []),
    }
    normalized_map = normalize_knowledge_map(target, map_value, require_files=status == "ready")
    return path, {**value, "gaps": gaps}, normalized_map


def load_knowledge_consent(
    raw_path: str,
    allowed_scope: Sequence[str],
    *,
    assessment_fingerprint: str | None = None,
    inventory_fingerprint: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    path, value = load_json_object_file(
        raw_path,
        argument="--consent",
        max_bytes=64 * 1024,
        error_code="invalid_knowledge_consent",
    )
    if value.get("schema_version") != KNOWLEDGE_CONSENT_SCHEMA or not isinstance(value.get("approved"), bool):
        raise HarnessError("知识更新同意回执无效", code="invalid_knowledge_consent")
    requested = validate_scope(normalize_string_list(value.get("authorized_scope"), "authorized_scope"))
    uncovered = [item for item in allowed_scope if not scope_covers(item, requested)] if value["approved"] else []
    if uncovered:
        raise HarnessError("知识更新同意范围不完整", code="knowledge_consent_mismatch")
    if value.get("assessment_fingerprint") not in {None, assessment_fingerprint}:
        raise HarnessError("知识更新同意回执绑定的审查已失效", code="knowledge_consent_stale", exit_code=3)
    if value.get("inventory_fingerprint") not in {None, inventory_fingerprint}:
        raise HarnessError("知识更新同意回执绑定的文档盘点已失效", code="knowledge_consent_stale", exit_code=3)
    return path, value


def background_lock_names(job: dict[str, Any]) -> list[str]:
    if job.get("task_kind") == "delivery_governance":
        path_locks = [
            "path-" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
            for path in job.get("allowed_write_scope", [])
        ]
        kind_names = {
            "architecture": "architecture", "changelog": "changelog", "todo": "todo",
            "adr_root": "adr", "reviews_root": "reviews",
        }
        contract = job.get("document_route_contract", {})
        kind_locks = [
            f"document-kind-{kind_names[kind]}"
            for kind in contract.get("required_kinds", [])
            if contract.get("status") == "resolved" and kind in kind_names
        ]
        return sorted(set([*path_locks, *kind_locks]))
    names = [f"feature-{item}" for item in job.get("feature_ids", [])]
    if job.get("new_feature_registration") or not names or scope_covers(KNOWLEDGE_MAP_RELATIVE, job.get("allowed_write_scope", [])):
        names.append("catalog")
    if any("docs/shared/" in item for item in job.get("allowed_write_scope", [])):
        names.append("shared")
    return sorted(set(names))


def legacy_governance_route_job(job: dict[str, Any]) -> bool:
    return job.get("task_kind") == "delivery_governance" and not isinstance(
        job.get("document_route_contract"), dict
    )


def governance_route_contract_drift(target: Path, job: dict[str, Any]) -> dict[str, Any] | None:
    contract = job.get("document_route_contract")
    if not isinstance(contract, dict) or contract.get("status") != "resolved":
        return None
    current = resolve_document_routes(target, required_kinds=contract.get("required_kinds", []))
    if (
        current.get("status") != "resolved"
        or current.get("fingerprint") != job.get("route_contract_fingerprint")
    ):
        return current
    return None


def block_governance_route_drift(
    target: Path, root: Path, job: dict[str, Any], current: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    release_knowledge_job_locks(target, job)
    job["status"] = "needs_user_input" if current.get("status") != "resolved" else "needs_rebase"
    job["route_drift_contract"] = current
    job["updated_at"] = utc_now()
    write_background_job(target, root, job)
    append_background_event(root, job, "document_route_drift", status=job["status"], reason_code="document_route_drift")
    return 3, {
        "action": "document_route_recheck", "job_id": job["job_id"],
        "status": job["status"], "reason_code": "document_route_drift",
    }


def rebuild_governance_route_contract(
    target: Path, root: Path, job: dict[str, Any], *, legacy_repair: bool
) -> tuple[int, dict[str, Any]]:
    if legacy_repair:
        required = governance_required_kinds(job.get("candidate_categories", []))
        if not required:
            required = list(GOVERNANCE_DELIVERABLE_ROUTES["adr_changelog_todo_review"])
    else:
        required = list(job.get("document_route_contract", {}).get("required_kinds", []))
    contract = resolve_document_routes(target, required_kinds=required)
    route_reads, route_writes = governance_route_scopes(contract)
    old_contract = job.get("document_route_contract", {})
    old_reads, _ = governance_route_scopes(old_contract) if isinstance(old_contract, dict) else ([], [])
    base_reads = [item for item in job.get("allowed_read_scope", []) if item not in old_reads]
    archived = None
    if (root / "plan.json").exists() or (root / "progress.json").exists():
        archived = archive_background_goal_artifacts(
            root, job, "legacy_route_contract_repair" if legacy_repair else "document_route_retry"
        )
    release_knowledge_job_locks(target, job)
    attempt = int(job.get("attempt", 1))
    maximum = int(job.get("max_attempts", BACKGROUND_MAX_ATTEMPTS))
    if not legacy_repair and attempt >= maximum:
        job["status"] = "failed"
        job["updated_at"] = utc_now()
        job["completed_at"] = job["updated_at"]
        write_background_job(target, root, job)
        record_background_summary(target, job)
        return 3, {"action": "retry", "job_id": job["job_id"], "status": "failed", "reason_code": "max_attempts_reached", "attempt": attempt}
    job["attempt"] = attempt + 1
    if legacy_repair:
        job["max_attempts"] = maximum + 1
    job["document_route_contract"] = contract
    job["route_contract_fingerprint"] = contract.get("fingerprint") if contract.get("status") == "resolved" else None
    job["route_reason_code"] = contract.get("reason_code")
    job["allowed_read_scope"] = sorted(set([*base_reads, *route_reads]))
    job["allowed_write_scope"] = route_writes
    job["status"] = "contract_ready" if contract.get("status") == "resolved" else "needs_user_input"
    job["updated_at"] = utc_now()
    for key in ("completed_at", "goal_artifacts", "prepared_at", "route_drift_contract", "rebase_reason_code", "rebase_changed_paths"):
        job.pop(key, None)
    refresh_knowledge_job_baseline(target, job)
    write_background_job(target, root, job)
    event = "legacy_route_contract_repaired" if legacy_repair else "document_route_retry"
    append_background_event(
        root, job, event, status=job["status"], reason_code=contract.get("reason_code"),
        old_plan_fingerprint=archived.get("plan_fingerprint") if archived else None,
        old_progress_fingerprint=archived.get("progress_fingerprint") if archived else None,
    )
    return (0 if contract.get("status") == "resolved" else 3), {
        "action": "retry", "job_id": job["job_id"], "status": job["status"],
        "attempt": job["attempt"], "route_contract_status": contract.get("status"),
        "reason_code": contract.get("reason_code"),
        "requires_prepare": contract.get("status") == "resolved" and job.get("execution_route") in BACKGROUND_COMPLEX_ROUTES,
    }


def release_knowledge_job_locks(target: Path, job: dict[str, Any]) -> None:
    locks = background_runtime_root(target) / "locks"
    for name in background_lock_names(job):
        lock = locks / f"{name}.lock"
        if lock.is_file() and lock.read_text(encoding="utf-8").strip() == job["job_id"]:
            lock.unlink()


def acquire_knowledge_job_locks(target: Path, job: dict[str, Any]) -> None:
    locks = background_runtime_root(target) / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    acquired: list[Path] = []
    names = background_lock_names(job)
    try:
        for name in sorted(set(names)):
            path = locks / f"{name}.lock"
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as exc:
                owner = path.read_text(encoding="utf-8").strip() if path.is_file() else "unknown"
                raise HarnessError(f"功能知识正由 {owner} 更新", code="knowledge_feature_locked", exit_code=3) from exc
            os.write(fd, job["job_id"].encode("utf-8"))
            os.close(fd)
            acquired.append(path)
    except Exception:
        for path in acquired:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
        raise


BACKGROUND_TRANSITIONS = {
    "contract_ready": {"dispatched", "queued_manual", "cancelled"},
    "dispatched": {"running", "queued_manual", "failed", "cancelled"},
    "running": {
        "waiting_for_dependency", "waiting_for_bootstrap_merge", "updated", "no_change",
        "completed_with_finding", "needs_user_input", "needs_rebase", "failed", "cancelled",
    },
    "waiting_for_dependency": {"contract_ready", "failed", "cancelled"},
    "waiting_for_bootstrap_merge": {"contract_ready", "needs_user_input", "cancelled"},
    "needs_user_input": {"contract_ready", "cancelled"},
    "needs_rebase": {"contract_ready", "cancelled"},
    "queued_manual": {"contract_ready", "cancelled"},
}


def assert_background_control_root(target: Path, root: Path, job: dict[str, Any]) -> None:
    expected_roots = {
        knowledge_job_dir(target, str(job["job_id"])).resolve(),
        legacy_knowledge_job_dir(target, str(job["job_id"])).resolve(),
    }
    if root.resolve() not in expected_roots or root.is_symlink():
        raise HarnessError("后台控制面 Runtime 路径不安全", code="unsafe_background_runtime")
    for name in ("job.json", "plan.json", "progress.json", "events.jsonl"):
        path = root / name
        if path.is_symlink():
            raise HarnessError("后台控制面文件不允许符号链接", code="unsafe_background_runtime")


def archive_background_goal_artifacts(root: Path, job: dict[str, Any], reason_code: str) -> dict[str, str | None]:
    attempt_root = root / "attempts" / f"attempt-{int(job.get('attempt', 1)):03d}"
    attempt_root.mkdir(parents=True, exist_ok=True)
    index = 1
    while (attempt_root / f"archive-{index:03d}").exists():
        index += 1
    archive = attempt_root / f"archive-{index:03d}"
    archive.mkdir()
    fingerprints: dict[str, str | None] = {"plan": None, "progress": None}
    for name in ("plan", "progress"):
        source = root / f"{name}.json"
        if source.is_file() and not source.is_symlink():
            fingerprints[name] = file_fingerprint(source)
            shutil.copy2(source, archive / source.name)
            source.unlink()
    atomic_write_json(
        archive / "archive.json",
        {
            "schema_version": "docs-harness/background-artifact-archive/v1",
            "job_id": job["job_id"],
            "attempt": int(job.get("attempt", 1)),
            "reason_code": reason_code,
            "plan_fingerprint": fingerprints["plan"],
            "progress_fingerprint": fingerprints["progress"],
        },
    )
    return {"plan_fingerprint": fingerprints["plan"], "progress_fingerprint": fingerprints["progress"]}


def prepare_background_goal_artifacts(
    target: Path,
    root: Path,
    job: dict[str, Any],
    *,
    repair: bool,
) -> tuple[int, dict[str, Any]]:
    assert_background_control_root(target, root, job)
    if job.get("execution_route") == "background_direct":
        return 0, {"action": "prepare", "job_id": job["job_id"], "status": "not_required", "changed": False}
    if job.get("execution_route") not in BACKGROUND_COMPLEX_ROUTES:
        raise HarnessError("后台 Job 路线无效", code="invalid_background_job")
    if job.get("status") not in {"contract_ready", "dispatched"}:
        raise HarnessError("仅 contract_ready 或在途 dispatched Job 可以 prepare", code="invalid_background_job_transition", exit_code=3)
    plan_path = root / "plan.json"
    progress_path = root / "progress.json"
    existing_count = sum(path.exists() for path in (plan_path, progress_path))
    expected_plan, expected_progress = background_goal_artifact_values(job)
    archived: dict[str, str | None] | None = None
    if existing_count:
        valid = False
        try:
            refs = validate_background_goal_artifacts(
                root, job, require_revision2=True, require_recorded_fingerprints=False
            )
            valid = read_json(plan_path) == expected_plan and read_json(progress_path) == expected_progress
        except HarnessError:
            refs = None
        if existing_count == 2 and valid:
            recorded = job.get("goal_artifacts")
            if isinstance(recorded, dict) and all(
                recorded.get(key) == refs.get(key)
                for key in ("artifact_revision", "attempt", "plan_fingerprint", "progress_fingerprint")
            ):
                return 0, {
                    "action": "prepare", "job_id": job["job_id"], "status": "already_prepared",
                    "goal_artifacts": recorded, "changed": False,
                }
            if not repair:
                raise HarnessError("已存在工件未绑定当前准备记录", code="background_goal_artifacts_conflict", exit_code=3)
        elif not repair:
            code = "partial_background_goal_artifacts" if existing_count == 1 else "invalid_background_goal_artifacts"
            append_background_event(root, job, "prepare_rejected", reason_code=code)
            raise HarnessError("现有 Goal 工件不完整、无效或绑定冲突；需要显式 --repair", code=code, exit_code=3)
        archived = archive_background_goal_artifacts(root, job, "explicit_repair")
    atomic_write_json(plan_path, expected_plan)
    atomic_write_json(progress_path, expected_progress)
    refs = background_artifact_refs(root)
    refs["attempt"] = int(job.get("attempt", 1))
    job["goal_artifacts"] = refs
    job["prepared_at"] = utc_now()
    job["updated_at"] = job["prepared_at"]
    write_background_job(target, root, job)
    event = "repaired" if archived else "prepared"
    append_background_event(
        root, job, event,
        status=str(job.get("status")),
        old_plan_fingerprint=archived.get("plan_fingerprint") if archived else None,
        old_progress_fingerprint=archived.get("progress_fingerprint") if archived else None,
    )
    return 0, {
        "action": "prepare", "job_id": job["job_id"],
        "status": "repaired" if archived else "prepared",
        "job_status": job["status"], "goal_artifacts": refs, "changed": True,
    }


def update_background_goal_progress(
    target: Path,
    root: Path,
    job: dict[str, Any],
    work_package_id: str,
    requested_status: str,
    reason_code: str | None,
) -> tuple[int, dict[str, Any]]:
    assert_background_control_root(target, root, job)
    if job.get("execution_route") not in BACKGROUND_COMPLEX_ROUTES:
        raise HarnessError("direct 路线不使用 Goal 进度", code="background_progress_not_required")
    if job.get("status") != "running":
        raise HarnessError("只有 running Job 可以更新工作包进度", code="invalid_background_job_transition", exit_code=3)
    if requested_status not in {"in_progress", "completed", "blocked"}:
        raise HarnessError("工作包状态无效", code="invalid_background_progress")
    if reason_code is not None and not BACKGROUND_REASON_CODE_RE.fullmatch(reason_code):
        raise HarnessError("--reason-code 必须是长度有界的受控标识符", code="invalid_background_reason_code")
    validate_background_goal_artifacts(root, job)
    progress_path = root / "progress.json"
    progress = read_json(progress_path)
    states = progress["work_package_states"]
    state = next((item for item in states if item["id"] == work_package_id), None)
    if state is None:
        append_background_event(root, job, "progress_rejected", reason_code="unknown_work_package")
        raise HarnessError("工作包 ID 不在冻结方案中", code="unknown_background_work_package", exit_code=3)
    current = state["status"]
    if current == requested_status:
        return 0, {
            "action": "progress", "job_id": job["job_id"], "work_package_id": work_package_id,
            "work_package_status": requested_status, "idempotent": True,
        }
    allowed = {
        "pending": {"in_progress", "blocked"},
        "in_progress": {"completed", "blocked"},
        "completed": set(),
        "blocked": set(),
    }
    if requested_status not in allowed[current]:
        append_background_event(root, job, "progress_rejected", reason_code="invalid_background_progress_transition")
        raise HarnessError("工作包进度不允许倒退或跳过执行", code="invalid_background_progress_transition", exit_code=3)
    state["status"] = requested_status
    progress["completed_work_packages"] = [item["id"] for item in states if item["status"] == "completed"]
    progress["remaining_work_packages"] = [item["id"] for item in states if item["status"] != "completed"]
    atomic_write_json(progress_path, progress)
    job["goal_artifacts"] = background_artifact_refs(root)
    job["goal_artifacts"]["attempt"] = int(job.get("attempt", 1))
    job["updated_at"] = utc_now()
    write_background_job(target, root, job)
    append_background_event(
        root, job, "progress_updated", work_package_id=work_package_id,
        work_package_status=requested_status, reason_code=reason_code,
    )
    return 0, {
        "action": "progress", "job_id": job["job_id"], "work_package_id": work_package_id,
        "work_package_status": requested_status,
        "completed_work_packages": progress["completed_work_packages"],
        "remaining_work_packages": progress["remaining_work_packages"],
        "idempotent": False,
    }


def dispatch_background_job_status(
    target: Path,
    root: Path,
    job: dict[str, Any],
    requested: str,
    *,
    command_name: str | None,
) -> tuple[int, dict[str, Any]]:
    if requested not in set().union(*BACKGROUND_TRANSITIONS.values()):
        raise HarnessError("--job-status 无效", code="invalid_background_job_status")
    current = str(job.get("status"))
    if current == requested:
        return 0, {"action": "dispatch", "job_id": job["job_id"], "status": requested, "idempotent": True}
    complex_route = job.get("execution_route") in BACKGROUND_COMPLEX_ROUTES
    legacy_direct_start = (
        command_name == "knowledge"
        and job.get("execution_route") == "background_direct"
        and current == "contract_ready"
        and requested == "running"
    )
    if requested not in BACKGROUND_TRANSITIONS.get(current, set()) and not legacy_direct_start:
        event_persisted = append_background_event(
            root, job, "transition_rejected", from_status=current,
            requested_status=requested, reason_code="invalid_background_job_transition",
        )
        payload: dict[str, Any] = {
            "action": "dispatch", "job_id": job["job_id"], "status": current,
            "code": "invalid_background_job_transition", "reason_code": "invalid_background_job_transition",
            "event_persisted": event_persisted,
        }
        if complex_route and current == "contract_ready" and requested == "running":
            payload.update({
                "next_action": "prepare_background_goal",
                "next_command_argv": harness_command_argv("background", target, "prepare", "--job-id", str(job["job_id"])),
                "dispatch_sequence": ["prepare", "dispatched", "running"],
            })
        return 3, payload
    if current == "waiting_for_dependency" and requested == "contract_ready":
        dependency_states: dict[str, str] = {}
        for dependency_id in job.get("dependency_job_ids", []):
            _, dependency = read_knowledge_job(target, str(dependency_id))
            dependency_states[str(dependency_id)] = str(dependency.get("status"))
        if any(state in {"failed", "cancelled"} for state in dependency_states.values()):
            raise HarnessError("后台 Job 依赖已失败", code="background_dependency_failed", exit_code=3)
        if any(state not in {"updated", "no_change", "completed_with_finding"} for state in dependency_states.values()):
            raise HarnessError("后台 Job 依赖尚未完成", code="background_dependency_pending", exit_code=3)
    if requested in {"dispatched", "running"} and complex_route:
        if not job.get("goal_contract"):
            raise HarnessError("复杂后台 Job 缺少目标合同", code="invalid_background_job")
        try:
            validate_background_goal_artifacts(root, job)
        except HarnessError as exc:
            event_persisted = append_background_event(
                root, job, "transition_rejected", from_status=current,
                requested_status=requested, reason_code=exc.code,
            )
            return 3, {
                "action": "dispatch", "job_id": job["job_id"], "status": current,
                "code": exc.code, "reason_code": exc.code,
                "next_action": "prepare_background_goal",
                "next_command_argv": harness_command_argv("background", target, "prepare", "--job-id", str(job["job_id"])),
                "event_persisted": event_persisted,
            }
    if requested == "running":
        changed, _ = knowledge_job_scope_changes(target, job)
        if changed:
            reason = "knowledge_changed_before_dispatch" if command_name == "knowledge" else "background_changed_before_dispatch"
            return mark_knowledge_job_needs_rebase(target, root, job, changed, reason)
        acquire_knowledge_job_locks(target, job)
        job["started_at"] = utc_now()
    if requested == "dispatched":
        job["dispatched_at"] = utc_now()
    if requested in {"failed", "needs_user_input", "needs_rebase", "cancelled"}:
        release_knowledge_job_locks(target, job)
    job["status"] = requested
    job["updated_at"] = utc_now()
    write_background_job(target, root, job)
    append_background_event(root, job, requested, status=requested)
    if requested in BACKGROUND_TERMINAL_STATES:
        job["completed_at"] = job.get("completed_at") or job["updated_at"]
        write_background_job(target, root, job)
        record_background_summary(target, job)
    released = release_bootstrap_waiters(target, job) if job.get("task_kind") == "knowledge_bootstrap" and requested in {"failed", "cancelled", "needs_user_input", "needs_rebase"} else []
    return 0, {"action": "dispatch", "job_id": job["job_id"], "status": requested, "released_waiting_jobs": released}


def background_prepare_and_run_eligibility(target: Path, job: dict[str, Any]) -> str | None:
    """--prepare-and-run 资格判定：合格返回 None，否则返回受控原因码。"""
    route = str(job.get("execution_route"))
    if route == "background_goal_phased":
        return "route_phased_oversized"
    if route != "background_goal":
        return "route_not_complex_goal"
    estimate: Any = None
    estimate_ref = job.get("workload_estimate_ref")
    if isinstance(estimate_ref, str) and estimate_ref:
        with contextlib.suppress(HarnessError, OSError):
            estimate = read_json(Path(estimate_ref))
    if not isinstance(estimate, dict):
        return "workload_estimate_unavailable"
    if estimate.get("estimate_basis") != "change_scoped":
        return "estimate_not_change_scoped"
    raw_score = estimate.get("raw_score")
    if not isinstance(raw_score, int) or isinstance(raw_score, bool) or raw_score >= 60:
        return "score_not_below_60"
    return None


def background_prepare_and_run(
    target: Path,
    root: Path,
    job: dict[str, Any],
    requested: str | None,
    *,
    command_name: str | None,
) -> tuple[int, dict[str, Any]]:
    if requested != "running":
        raise HarnessError("--prepare-and-run 必须显式声明 --job-status running", code="invalid_background_job_status")
    current = str(job.get("status"))
    if current != "contract_ready":
        raise HarnessError(
            "--prepare-and-run 仅支持 contract_ready 起点的复杂路线 Job",
            code="invalid_background_job_transition", exit_code=3,
        )
    eligibility = background_prepare_and_run_eligibility(target, job)
    if eligibility is not None:
        event_persisted = append_background_event(
            root, job, "transition_rejected", from_status=current,
            requested_status="running", reason_code="background_prepare_and_run_not_eligible",
        )
        return 3, {
            "action": "dispatch", "job_id": job["job_id"], "status": current,
            "code": "background_prepare_and_run_not_eligible",
            "reason_code": "background_prepare_and_run_not_eligible",
            "eligibility_reason_code": eligibility,
            "prepare_and_run": False,
            "dispatch_sequence": ["prepare", "dispatched", "running"],
            "event_persisted": event_persisted,
        }
    _, prepared = prepare_background_goal_artifacts(target, root, job, repair=False)
    steps = ["prepare"]
    payload: dict[str, Any] = {}
    for step in ("dispatched", "running"):
        code, payload = dispatch_background_job_status(target, root, job, step, command_name=command_name)
        if code != 0:
            payload["prepare_and_run"] = True
            payload["completed_steps"] = steps
            return code, payload
        steps.append(step)
    return 0, {
        **payload,
        "prepare_and_run": True,
        "prepare_status": prepared["status"],
        "dispatch_sequence": ["prepare", "dispatched", "running"],
        "completed_steps": steps,
    }


def complete_all_background_work_packages(
    target: Path,
    root: Path,
    job: dict[str, Any],
    reason_code: str | None,
) -> tuple[int, dict[str, Any]]:
    assert_background_control_root(target, root, job)
    if job.get("execution_route") not in BACKGROUND_COMPLEX_ROUTES:
        raise HarnessError("direct 路线不使用 Goal 进度", code="background_progress_not_required")
    if job.get("status") != "running":
        raise HarnessError("只有 running Job 可以更新工作包进度", code="invalid_background_job_transition", exit_code=3)
    if reason_code is not None and not BACKGROUND_REASON_CODE_RE.fullmatch(reason_code):
        raise HarnessError("--reason-code 必须是长度有界的受控标识符", code="invalid_background_reason_code")
    validate_background_goal_artifacts(root, job)
    progress_path = root / "progress.json"
    progress = read_json(progress_path)
    states = progress["work_package_states"]
    blocking = [
        {"id": item["id"], "status": item["status"]}
        for item in states
        if item["status"] not in {"pending", "in_progress", "completed"}
    ]
    if blocking:
        event_persisted = append_background_event(
            root, job, "progress_rejected", reason_code="background_progress_all_blocked"
        )
        return 3, {
            "action": "progress", "job_id": job["job_id"], "all": "completed",
            "code": "background_progress_all_blocked",
            "reason_code": "background_progress_all_blocked",
            "blocking_work_packages": blocking,
            "completed_work_packages": progress["completed_work_packages"],
            "remaining_work_packages": progress["remaining_work_packages"],
            "partial_commit": False,
            "event_persisted": event_persisted,
        }
    updated: list[str] = []
    already_completed: list[str] = []
    for item in states:
        if item["status"] == "completed":
            already_completed.append(item["id"])
            continue
        if item["status"] == "pending":
            update_background_goal_progress(target, root, job, item["id"], "in_progress", reason_code)
        update_background_goal_progress(target, root, job, item["id"], "completed", reason_code)
        updated.append(item["id"])
    final = read_json(progress_path)
    return 0, {
        "action": "progress", "job_id": job["job_id"], "all": "completed",
        "updated_work_packages": updated,
        "already_completed_work_packages": already_completed,
        "completed_work_packages": final["completed_work_packages"],
        "remaining_work_packages": final["remaining_work_packages"],
        "partial_commit": False,
    }


def scope_claims_background_control_plane(target: Path, scope: Sequence[str]) -> bool:
    probes = [".git", ".git/docs-harness", ".docs-harness", ".docs-harness/background"]
    runtime = background_runtime_root(target)
    with contextlib.suppress(ValueError):
        probes.append(runtime.resolve().relative_to(target.resolve()).as_posix())
    return any(scope_covers(probe, scope) for probe in probes)


def create_background_job(
    target: Path,
    *,
    task_kind: str,
    estimate: dict[str, Any],
    parent_task_id: str | None,
    parent_job_id: str | None = None,
    feature_ids: Sequence[str] = (),
    categories: Sequence[str] = (),
    allowed_read_scope: Sequence[str] = ("src/**", "tests/**", "docs/**"),
    allowed_write_scope: Sequence[str] = ("docs/**",),
    forbidden_write_scope: Sequence[str] = ("src/**", "tests/**", ".git/**"),
    changed_paths: Sequence[str] = (),
    dependency_job_ids: Sequence[str] = (),
    objective: str = "完成非阻塞文档治理",
    authorization_basis: str = "task_contract",
    assessment_ref: str | None = None,
    consent_ref: str | None = None,
    route_base_key: str | None = None,
    document_route_contract: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    if task_kind not in BACKGROUND_TASK_KINDS:
        raise HarnessError("后台 Job 类型无效", code="invalid_background_job")
    if task_kind == "critical_followup" and (not parent_task_id or not parent_job_id):
        raise HarnessError("critical_followup 必须绑定父任务和父 Job", code="invalid_background_job")
    if route_base_key is not None or document_route_contract is not None:
        if (
            task_kind != "delivery_governance"
            or not isinstance(route_base_key, str)
            or not route_base_key.startswith("sha256:")
            or not isinstance(document_route_contract, dict)
            or document_route_contract.get("schema_version") != DOCUMENT_ROUTE_SCHEMA
        ):
            raise HarnessError("文档路由初始合同仅允许治理 Job 使用", code="invalid_background_job")
    normalized_reads = validate_scope(allowed_read_scope)
    normalized_writes = validate_scope(allowed_write_scope)
    normalized_forbidden = validate_scope(forbidden_write_scope)
    if any(scope_covers(path, normalized_forbidden) for path in normalized_writes):
        raise HarnessError("后台 Job 允许写入范围与禁止范围冲突", code="invalid_background_scope")
    if scope_claims_background_control_plane(target, normalized_writes):
        raise HarnessError("后台 Job 业务范围不得覆盖 Harness 控制面", code="invalid_background_scope")
    for relative in normalized_writes:
        if "*" in relative:
            continue
        path = target / relative
        if path.is_symlink():
            raise HarnessError("后台 Job 不允许写入符号链接", code="invalid_background_scope")
        try:
            path.resolve().relative_to(target.resolve())
        except ValueError as exc:
            raise HarnessError("后台 Job 写入范围越出项目", code="invalid_background_scope") from exc
    if task_kind == "delivery_governance" and document_route_contract is None:
        raise HarnessError(
            "新治理 Job 必须绑定文档路由合同",
            code="invalid_document_route_contract",
        )
    if task_kind == "knowledge_bootstrap":
        existing_bootstrap = active_knowledge_bootstrap(target)
        if existing_bootstrap:
            if existing_bootstrap.get("status") == "contract_ready":
                root, current = read_knowledge_job(target, str(existing_bootstrap["job_id"]))
                current["feature_ids"] = list(dict.fromkeys([*current.get("feature_ids", []), *feature_ids]))
                current["candidate_categories"] = list(dict.fromkeys([*current.get("candidate_categories", []), *categories]))
                current["allowed_read_scope"] = normalized_reads
                current["allowed_write_scope"] = normalized_writes
                current["assessment_ref"] = assessment_ref or current.get("assessment_ref")
                current["consent_ref"] = consent_ref or current.get("consent_ref")
                current["authorization_basis"] = authorization_basis
                current["updated_at"] = utc_now()
                refresh_knowledge_job_baseline(target, current)
                write_background_job(target, root, current)
                existing_bootstrap = current
            return existing_bootstrap, True
    estimate_path = persist_workload_estimate(target, estimate)
    idempotency_key = route_base_key or background_idempotency_key(
        task_kind, parent_task_id, feature_ids, categories,
        estimate["source_fingerprint"] + (f":{parent_job_id}" if parent_job_id else ""),
    )
    for existing in list_background_jobs(target):
        if existing.get("idempotency_key") != idempotency_key:
            continue
        if existing.get("status") not in {"failed", "cancelled"}:
            return existing, True
    if parent_task_id:
        validate_task_id(parent_task_id)
        base_job_id = generate_knowledge_job_id(parent_task_id)
        if task_kind != "knowledge_incremental_sync":
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
            job_id = f"bg-{stamp}-{hashlib.sha256(idempotency_key.encode()).hexdigest()[:10]}"
        else:
            job_id = base_job_id
    else:
        job_id = generate_knowledge_job_id()
    dependencies = list(dict.fromkeys(dependency_job_ids))
    if document_route_contract and document_route_contract.get("status") != "resolved":
        if normalized_writes:
            raise HarnessError("未解析治理 Job 必须保持零写权限", code="invalid_background_scope")
        initial_status = "needs_user_input"
    else:
        initial_status = (
            "waiting_for_bootstrap_merge"
            if task_kind == "knowledge_incremental_sync" and dependencies
            else "waiting_for_dependency" if dependencies else "contract_ready"
        )
    now = utc_now()
    job = {
        "schema_version": BACKGROUND_JOB_SCHEMA,
        "job_id": job_id,
        "task_kind": task_kind,
        "parent_task_id": parent_task_id,
        "parent_job_id": parent_job_id,
        "may_mutate_parent": False,
        "may_spawn_child_jobs": False,
        "suppress_post_completion_dispatch": True,
        "status": initial_status,
        "execution_route": estimate["execution_route"],
        "workload_estimate_ref": str(estimate_path),
        "feature_ids": list(dict.fromkeys(feature_ids)),
        "candidate_categories": list(dict.fromkeys(categories)),
        "allowed_read_scope": normalized_reads,
        "allowed_write_scope": normalized_writes,
        "forbidden_write_scope": normalized_forbidden,
        "base_fingerprints": {},
        "goal_contract": goal_contract_for_estimate(estimate, objective),
        "host_dispatch_contract": host_dispatch_contract(target, job_id, estimate["execution_route"]),
        "work_packages": estimate["suggested_work_packages"] if estimate["requires_plan"] else [],
        "dependency_job_ids": dependencies,
        "changed_paths": list(changed_paths),
        "attempt": 1,
        "max_attempts": BACKGROUND_MAX_ATTEMPTS,
        "idempotency_key": idempotency_key,
        "authorization_basis": authorization_basis,
        "assessment_ref": assessment_ref,
        "consent_ref": consent_ref,
        "created_at": now,
        "updated_at": now,
        "stale_after": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).replace(microsecond=0).isoformat(),
    }
    if document_route_contract is not None:
        job["route_base_key"] = route_base_key
        job["document_route_contract"] = document_route_contract
        job["route_contract_fingerprint"] = (
            document_route_contract.get("fingerprint")
            if document_route_contract.get("status") == "resolved"
            else None
        )
        job["route_reason_code"] = document_route_contract.get("reason_code")
    refresh_knowledge_job_baseline(target, job)
    root = knowledge_job_dir(target, job_id)
    root.mkdir(parents=True, exist_ok=True)
    write_background_job(target, root, job)
    atomic_write_text(root / "events.jsonl", "")
    append_background_event(root, job, "created", status=initial_status)
    return job, False


def background_manual_command(target: Path, job: dict[str, Any]) -> list[str]:
    return harness_command_argv(
        "background",
        target,
        "dispatch",
        "--job-id",
        str(job["job_id"]),
        "--job-status",
        "running",
    )


def complete_critical_followup(target: Path, job: dict[str, Any], finding: dict[str, Any]) -> dict[str, Any]:
    estimate = workload_estimate(target, candidate={"requires_plan": True})
    followup, _ = create_background_job(
        target,
        task_kind="critical_followup",
        estimate=estimate,
        parent_task_id=str(job.get("parent_task_id") or ""),
        parent_job_id=str(job["job_id"]),
        feature_ids=job.get("feature_ids", []),
        categories=["critical_finding"],
        allowed_read_scope=job.get("allowed_read_scope", []),
        allowed_write_scope=[],
        forbidden_write_scope=["**"],
        objective="核实后台治理发现的重大交付风险并形成独立修复任务",
    )
    followup["critical_finding"] = finding
    root = knowledge_job_dir(target, str(followup["job_id"]))
    write_background_job(target, root, followup)
    return followup


def release_bootstrap_waiters(target: Path, bootstrap_job: dict[str, Any]) -> list[str]:
    released: list[str] = []
    outcome = knowledge_dependency_outcome(bootstrap_job, target)
    if outcome == "pending":
        return released
    for waiter in list_background_jobs(target):
        if waiter.get("status") != "waiting_for_bootstrap_merge":
            continue
        if bootstrap_job.get("job_id") not in waiter.get("dependency_job_ids", []):
            continue
        waiter_root, current = read_knowledge_job(target, str(waiter["job_id"]))
        if outcome == "success":
            current["dependency_job_ids"] = [
                item for item in current.get("dependency_job_ids", []) if item != bootstrap_job.get("job_id")
            ]
            current["status"] = "contract_ready"
            current["baseline_rebuilt_after_bootstrap"] = True
            refresh_knowledge_job_baseline(target, current)
            event = "bootstrap_released"
        else:
            current["status"] = "needs_user_input"
            current["dependency_reason_code"] = (
                "unknown_bootstrap_outcome" if outcome == "unknown" else "bootstrap_dependency_not_ready"
            )
            event = "bootstrap_blocked"
        current["updated_at"] = utc_now()
        write_background_job(target, waiter_root, current)
        append_background_event(
            waiter_root, current, event,
            status=str(current.get("status")), bootstrap_job_id=bootstrap_job.get("job_id"),
        )
        released.append(str(current["job_id"]))
    return released


def command_background(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    if args.action in {"prepare", "progress", "dispatch", "retry", "verify"} and args.job_id:
        root, _ = read_knowledge_job(target, args.job_id)
        with state_lock(root):
            return command_background_unlocked(args)
    return command_background_unlocked(args)


def command_background_unlocked(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    action = args.action
    if action == "estimate":
        candidate: dict[str, Any] | None = None
        if args.candidate:
            _, candidate = load_json_object_file(
                args.candidate,
                argument="--candidate",
                max_bytes=256 * 1024,
                error_code="invalid_background_candidate",
            )
            if candidate.get("schema_version") not in {None, BACKGROUND_CANDIDATE_SCHEMA}:
                raise HarnessError("后台候选项 schema 无效", code="invalid_background_candidate")
        estimate = workload_estimate(target, candidate=candidate)
        path = persist_workload_estimate(target, estimate)
        return 0, {"action": "estimate", **estimate, "estimate_ref": str(path)}
    if action == "list":
        jobs = list_background_jobs(target)
        return 0, {
            "action": "list",
            "jobs": [
                {
                    key: job.get(key)
                    for key in (
                        "job_id", "task_kind", "parent_task_id", "status", "execution_route",
                        "attempt", "max_attempts", "created_at", "updated_at",
                    )
                }
                for job in jobs
            ],
            "count": len(jobs),
        }
    if action == "prune":
        if args.apply and args.dry_run:
            raise HarnessError("--apply 与 --dry-run 不能同时使用", code="invalid_prune_request")
        if args.older_than is None or args.older_than < 0:
            raise HarnessError("--older-than 必须是非负天数", code="invalid_prune_request")
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.older_than)
        candidates: list[dict[str, Any]] = []
        indexed_keys = background_indexed_keys(target)
        for job in list_background_jobs(target):
            if job.get("status") not in BACKGROUND_TERMINAL_STATES or job.get("status") == "completed_with_finding":
                continue
            summary_key = (str(job.get("job_id")), int(job.get("attempt", 1)), str(job.get("status", "")))
            if summary_key not in indexed_keys:
                continue
            raw_time = job.get("completed_at") or job.get("updated_at")
            with contextlib.suppress(ValueError, TypeError):
                when = dt.datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                if when <= cutoff:
                    candidates.append({"job_id": job["job_id"], "status": job["status"], "updated_at": raw_time})
        if not args.apply:
            return 0, {"action": "prune", "mode": "dry_run", "candidates": candidates, "removed": []}
        removed: list[str] = []
        for item in candidates:
            primary = knowledge_job_dir(target, item["job_id"])
            with state_lock(primary):
                _, current = read_knowledge_job(target, item["job_id"])
                current_key = (
                    str(current.get("job_id")), int(current.get("attempt", 1)), str(current.get("status", ""))
                )
                if current.get("status") not in BACKGROUND_TERMINAL_STATES or current_key not in background_indexed_keys(target):
                    continue
                for root in (primary, legacy_knowledge_job_dir(target, item["job_id"])):
                    if root.is_dir() and root.parent in {background_jobs_root(target), knowledge_jobs_root(target)}:
                        shutil.rmtree(root)
                removed.append(item["job_id"])
        return 0, {"action": "prune", "mode": "apply", "candidates": candidates, "removed": removed}
    if getattr(args, "prepare_and_run", False) and action != "dispatch":
        raise HarnessError("--prepare-and-run 只能配合 background dispatch 使用", code="invalid_prepare_and_run_usage")
    if getattr(args, "all_packages", None) and action != "progress":
        raise HarnessError("--all 只能配合 background progress 使用", code="invalid_background_progress")
    if not args.job_id:
        raise HarnessError(f"background {action} 必须提供 --job-id", code="missing_background_job")
    root, job = read_knowledge_job(target, args.job_id)
    if action == "status":
        return 0, {"action": "status", **job}
    if legacy_governance_route_job(job):
        cancellation = action == "dispatch" and args.job_status == "cancelled"
        if action == "retry":
            if job.get("status") != "cancelled":
                raise HarnessError(
                    "旧治理 Job 必须先由宿主停止并显式进入 cancelled",
                    code="legacy_governance_job_not_quiesced", exit_code=3,
                )
            return rebuild_governance_route_contract(target, root, job, legacy_repair=True)
        if not cancellation:
            raise HarnessError(
                "旧治理 Job 缺少文档路由合同，仅允许只读或显式取消后迁移",
                code="legacy_governance_route_contract", exit_code=3,
            )
    if (
        job.get("task_kind") == "delivery_governance"
        and action in {"prepare", "dispatch", "verify"}
        and not (action == "dispatch" and args.job_status == "cancelled")
    ):
        drift = governance_route_contract_drift(target, job)
        if drift is not None:
            return block_governance_route_drift(target, root, job, drift)
    if action == "prepare":
        return prepare_background_goal_artifacts(target, root, job, repair=bool(args.repair))
    if action == "progress":
        if getattr(args, "all_packages", None):
            if args.work_package_id or args.work_package_status:
                raise HarnessError("--all 不能与单包进度参数混用", code="invalid_background_progress")
            return complete_all_background_work_packages(target, root, job, args.reason_code)
        if not args.work_package_id or not args.work_package_status:
            raise HarnessError("background progress 必须提供工作包 ID 和状态", code="missing_background_progress")
        return update_background_goal_progress(
            target, root, job, args.work_package_id, args.work_package_status, args.reason_code
        )
    if action == "dispatch":
        command_name = getattr(args, "command", None)
        if getattr(args, "prepare_and_run", False):
            return background_prepare_and_run(target, root, job, args.job_status, command_name=command_name)
        return dispatch_background_job_status(target, root, job, args.job_status, command_name=command_name)
    if action == "retry":
        if (
            job.get("task_kind") == "delivery_governance"
            and isinstance(job.get("document_route_contract"), dict)
        ):
            if job.get("status") not in BACKGROUND_RETRYABLE_STATES | {"failed"}:
                raise HarnessError("当前治理 Job 不允许重试", code="invalid_background_retry")
            return rebuild_governance_route_contract(target, root, job, legacy_repair=False)
        if job.get("status") not in BACKGROUND_RETRYABLE_STATES | {"failed"}:
            raise HarnessError("当前后台 Job 不允许重试", code="invalid_background_retry")
        attempt = int(job.get("attempt", 1))
        maximum = int(job.get("max_attempts", BACKGROUND_MAX_ATTEMPTS))
        if attempt >= maximum:
            job["status"] = "failed"
            job["updated_at"] = utc_now()
            job["completed_at"] = job["updated_at"]
            write_background_job(target, root, job)
            record_background_summary(target, job)
            return 3, {"action": "retry", "job_id": job["job_id"], "status": "failed", "reason_code": "max_attempts_reached", "attempt": attempt}
        release_knowledge_job_locks(target, job)
        archived = None
        if (root / "plan.json").exists() or (root / "progress.json").exists():
            archived = archive_background_goal_artifacts(root, job, "retry")
        job["status"] = "contract_ready"
        job["attempt"] = attempt + 1
        job["updated_at"] = utc_now()
        for key in (
            "rebase_reason_code", "rebase_changed_paths", "completed_at", "goal_artifacts",
            "prepared_at", "legacy_goal_artifacts_accepted",
        ):
            job.pop(key, None)
        refresh_knowledge_job_baseline(target, job)
        write_background_job(target, root, job)
        append_background_event(
            root, job, "retry", status=job["status"],
            old_plan_fingerprint=archived.get("plan_fingerprint") if archived else None,
            old_progress_fingerprint=archived.get("progress_fingerprint") if archived else None,
        )
        return 0, {
            "action": "retry", "job_id": job["job_id"], "status": job["status"],
            "attempt": job["attempt"], "requires_prepare": job.get("execution_route") in BACKGROUND_COMPLEX_ROUTES,
        }
    if action == "verify":
        if job.get("status") != "running":
            raise HarnessError("只有 running Job 可以验收", code="invalid_background_job_transition")
        blocked_work_packages: list[str] = []
        if job.get("execution_route") in BACKGROUND_COMPLEX_ROUTES:
            try:
                refs = validate_background_goal_artifacts(root, job)
                progress = read_json(root / "progress.json")
                states = progress["work_package_states"]
                statuses = {item["status"] for item in states}
                blocked_work_packages = [item["id"] for item in states if item["status"] == "blocked"]
                if args.result in {"updated", "no_change"} and statuses != {"completed"}:
                    raise HarnessError("成功验收要求全部工作包 completed", code="incomplete_background_work_packages", exit_code=3)
                if args.result == "completed_with_finding" and statuses - {"completed", "blocked"}:
                    raise HarnessError("重大发现验收仍存在未终结工作包", code="incomplete_background_work_packages", exit_code=3)
            except HarnessError as exc:
                recorded = job.get("goal_artifacts")
                legacy_allowed = (
                    isinstance(recorded, dict)
                    and recorded.get("artifact_revision") in {None, 1}
                    and int(recorded.get("attempt", job.get("attempt", 1))) == int(job.get("attempt", 1))
                )
                if not legacy_allowed:
                    append_background_event(root, job, "verify_rejected", reason_code=exc.code)
                    return 3, {
                        "action": "verify", "job_id": job["job_id"], "status": "running",
                        "code": exc.code, "reason_code": exc.code,
                    }
                legacy_refs = validate_background_goal_artifacts(
                    root, job, require_revision2=False, require_recorded_fingerprints=False
                )
                if any(
                    recorded.get(key) != legacy_refs.get(key)
                    for key in ("plan_fingerprint", "progress_fingerprint")
                ):
                    append_background_event(root, job, "verify_rejected", reason_code="background_goal_artifacts_tampered")
                    return 3, {
                        "action": "verify", "job_id": job["job_id"], "status": "running",
                        "code": "background_goal_artifacts_tampered",
                        "reason_code": "background_goal_artifacts_tampered",
                    }
                job["legacy_goal_artifacts_accepted"] = True
                append_background_event(root, job, "legacy_goal_artifacts_accepted", status="running")
        changed, outside = knowledge_job_scope_changes(target, job)
        if outside:
            reason = "knowledge_write_outside_allowed_scope" if getattr(args, "command", None) == "knowledge" else "background_write_outside_allowed_scope"
            return mark_knowledge_job_needs_rebase(target, root, job, outside, reason)
        result = args.result
        if result == "no_change" and changed:
            reason = "no_change_but_knowledge_changed" if getattr(args, "command", None) == "knowledge" else "no_change_but_background_changed"
            return mark_knowledge_job_needs_rebase(target, root, job, changed, reason)
        if result == "no_change" and str(job.get("task_kind", "")).startswith("knowledge_") and not knowledge_ready_for_incremental(target):
            job["status"] = "needs_user_input"
            job["updated_at"] = utc_now()
            write_background_job(target, root, job)
            release_knowledge_job_locks(target, job)
            affected = release_bootstrap_waiters(target, job) if job.get("task_kind") == "knowledge_bootstrap" else []
            return 3, {
                "action": "verify",
                "job_id": job["job_id"],
                "status": "needs_user_input",
                "reason_code": "knowledge_no_change_without_ready_knowledge",
                "affected_waiting_jobs": affected,
            }
        if result == "completed_with_finding":
            if not args.assessment:
                raise HarnessError("重大发现必须提供 --assessment", code="missing_background_assessment")
            _, finding = load_json_object_file(args.assessment, argument="--assessment", max_bytes=256 * 1024, error_code="invalid_background_assessment")
            if finding.get("schema_version") not in {None, BACKGROUND_ASSESSMENT_SCHEMA} or not finding.get("critical_finding"):
                raise HarnessError("重大发现报告无效", code="invalid_background_assessment")
            followup = complete_critical_followup(target, job, finding)
            job["critical_followup_job_id"] = followup["job_id"]
            job["delivery_confidence"] = "questioned"
        elif result == "updated" and job.get("task_kind") in {"knowledge_bootstrap", "knowledge_incremental_sync"}:
            if not args.assessment:
                raise HarnessError("知识 Job 更新验收必须提供 --assessment", code="missing_knowledge_input")
            _, assessment, normalized_map = normalize_knowledge_assessment(target, args.assessment)
            if assessment["status"] != "ready":
                job["status"] = "needs_user_input"
                job["updated_at"] = utc_now()
                write_background_job(target, root, job)
                release_knowledge_job_locks(target, job)
                affected = release_bootstrap_waiters(target, job) if job.get("task_kind") == "knowledge_bootstrap" else []
                return 3, {"action": "verify", "job_id": job["job_id"], "status": "needs_user_input", "gaps": assessment["gaps"]}
            candidate_status = evaluate_candidate_knowledge(target, normalized_map)
            if candidate_status["status"] != "ready":
                job["status"] = "needs_user_input"
                job["updated_at"] = utc_now()
                job["candidate_knowledge_status"] = candidate_status
                write_background_job(target, root, job)
                release_knowledge_job_locks(target, job)
                affected = release_bootstrap_waiters(target, job) if job.get("task_kind") == "knowledge_bootstrap" else []
                return 3, {
                    "action": "verify",
                    "job_id": job["job_id"],
                    "status": "needs_user_input",
                    "reason_code": "candidate_knowledge_not_ready",
                    "gaps": candidate_status["gaps"],
                    "affected_waiting_jobs": affected,
                }
            if not scope_covers(KNOWLEDGE_MAP_RELATIVE, job.get("allowed_write_scope", [])):
                raise HarnessError("知识 Job 未授权写入知识地图", code="invalid_background_scope")
            atomic_write_json(knowledge_map_path(target), normalized_map)
            job["knowledge_map_fingerprint"] = file_fingerprint(knowledge_map_path(target))
        job["status"] = result
        job["completed_at"] = utc_now()
        job["updated_at"] = job["completed_at"]
        write_background_job(target, root, job)
        release_knowledge_job_locks(target, job)
        append_background_event(root, job, "verify", result=result)
        record_background_summary(target, job)
        released = release_bootstrap_waiters(target, job) if job.get("task_kind") == "knowledge_bootstrap" else []
        return 0, {
            "action": "verify",
            "job_id": job["job_id"],
            "result": result,
            "parent_control_status_unchanged": True,
            "critical_followup_job_id": job.get("critical_followup_job_id"),
            "blocked_work_package_ids": blocked_work_packages,
            "knowledge_status": knowledge_status(target) if job.get("task_kind", "").startswith("knowledge_") else None,
            "released_waiting_jobs": released,
        }
    raise HarnessError("未知 background 动作", code="invalid_background_action")


def command_knowledge(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    if args.action == "estimate":
        estimate = workload_estimate(target)
        path = persist_workload_estimate(target, estimate)
        return 0, {"action": "estimate", **estimate, "estimate_ref": str(path)}
    if args.action == "bootstrap":
        if repowiki_knowledge_root(target) is not None:
            raise HarnessError(
                "项目使用 .qoder/repowiki 外部知识源，知识库为只消费模式，禁止初始化或更新",
                code="knowledge_external_consume_only",
                exit_code=3,
            )
        estimate = workload_estimate(target)
        feature_ids: list[str] = []
        allowed_scope: list[str] = ["docs/**"]
        assessment_ref: str | None = None
        if args.assessment:
            assessment_path, _, normalized_map = normalize_knowledge_assessment(target, args.assessment)
            assessment_ref = str(assessment_path)
            feature_ids = [item["feature_id"] for item in normalized_map["features"]]
            allowed_scope = ["docs/INDEX.md", "docs/features/INDEX.md", KNOWLEDGE_MAP_RELATIVE]
            for feature in normalized_map["features"]:
                allowed_scope.extend(feature["documents"].values())
                allowed_scope.extend(feature["shared_refs"])
        job, idempotent = create_background_job(
            target,
            task_kind="knowledge_bootstrap",
            estimate=estimate,
            parent_task_id=None,
            feature_ids=feature_ids,
            categories=KNOWLEDGE_CATEGORIES,
            allowed_read_scope=("**",),
            allowed_write_scope=allowed_scope,
            objective="遍历当前项目并建立 L2 功能知识库",
            authorization_basis="project_init_bootstrap",
            assessment_ref=assessment_ref,
        )
        return 0, {"action": "bootstrap", "status": job["status"], "job_id": job["job_id"], "idempotent": idempotent, "dispatch_contract": job}
    if args.action in {"job-status", "dispatch", "retry", "verify"}:
        legacy_action = args.action
        args.action = "status" if legacy_action == "job-status" else legacy_action
        code, payload = command_background(args)
        args.action = legacy_action
        return code, {
            **payload,
            "action": legacy_action,
            "deprecated_alias": True,
            "replacement_command": f"background {'status' if legacy_action == 'job-status' else legacy_action}",
        }
    if args.action == "status":
        status = knowledge_status(target)
        jobs = [
            {"job_id": job.get("job_id"), "status": job.get("status"), "parent_task_id": job.get("parent_task_id")}
            for job in list_background_jobs(target)
            if str(job.get("task_kind", "")).startswith("knowledge_")
        ]
        return 0, {"action": "status", **status, "jobs": jobs}

    if args.action == "audit":
        if not args.assessment:
            artifact = knowledge_runtime_root(target) / "assessment.json"
            inventory, excluded_summary, explicit_includes = knowledge_scan_inventory_details(target)
            inventory_fingerprint = knowledge_inventory_fingerprint(target)
            return 0, {
                "action": "audit",
                "status": knowledge_status(target)["status"],
                "next_action": "inspect_project_knowledge",
                "reason_code": "knowledge_assessment_required",
                "artifact_ref": str(artifact),
                "assessment_schema": KNOWLEDGE_ASSESSMENT_SCHEMA,
                "inventory": inventory,
                "excluded_summary": excluded_summary,
                "explicit_includes": explicit_includes,
                "knowledge_inventory_fingerprint": inventory_fingerprint,
                "inventory_fingerprint": inventory_fingerprint,
            }
        source, assessment, normalized_map = normalize_knowledge_assessment(target, args.assessment)
        runtime = knowledge_runtime_root(target)
        runtime.mkdir(parents=True, exist_ok=True)
        assessment_fingerprint = file_fingerprint(source)
        inventory_fingerprint = knowledge_inventory_fingerprint(target)
        atomic_write_json(runtime / "last-assessment.json", {**assessment, "source_ref": str(source), "source_fingerprint": assessment_fingerprint, "inventory_fingerprint": inventory_fingerprint, "recorded_at": utc_now()})
        if assessment["status"] == "partial":
            declined_path = runtime / "declined.json"
            if declined_path.is_file():
                with contextlib.suppress(HarnessError):
                    declined = read_json(declined_path)
                    if declined.get("assessment_fingerprint") == assessment_fingerprint and declined.get("inventory_fingerprint") == inventory_fingerprint:
                        return 0, {
                            "action": "audit",
                            "status": "declined_cached",
                            "gaps": assessment["gaps"],
                            "next_action": "none",
                            "reason_code": "valid_decline_receipt",
                        }
            return 3, {
                "action": "audit",
                "status": "needs_confirmation",
                "gaps": assessment["gaps"],
                "next_action": "request_knowledge_update_consent",
                "reason_code": "knowledge_update_consent_required",
                "assessment_fingerprint": assessment_fingerprint,
                "inventory_fingerprint": inventory_fingerprint,
                "authorized_scope": sorted({
                    "docs/INDEX.md", "docs/features/INDEX.md", KNOWLEDGE_MAP_RELATIVE,
                    *(path for feature in normalized_map["features"] for path in feature["documents"].values()),
                    *(path for feature in normalized_map["features"] for path in feature["shared_refs"]),
                }),
                "next_command_argv": [],
            }
        atomic_write_json(knowledge_map_path(target), normalized_map)
        current = knowledge_status(target)
        return (0 if current["status"] == "ready" else 1), {"action": "audit", **current, "changed": [KNOWLEDGE_MAP_RELATIVE]}

    if args.action == "update":
        if not args.assessment:
            raise HarnessError("knowledge update 必须提供 --assessment", code="missing_knowledge_input")
        assessment_path, assessment, normalized_map = normalize_knowledge_assessment(target, args.assessment)
        assessment_fingerprint = file_fingerprint(assessment_path)
        inventory_fingerprint = knowledge_inventory_fingerprint(target)
        allowed_scope = ["docs/INDEX.md", "docs/features/INDEX.md", KNOWLEDGE_MAP_RELATIVE]
        for feature in normalized_map["features"]:
            allowed_scope.extend(feature["documents"].values())
            allowed_scope.extend(feature["shared_refs"])
        config = project_config(target) or {}
        knowledge_config = config.get("knowledge", {}) if isinstance(config.get("knowledge"), dict) else {}
        existing_docs_require_consent = bool(knowledge_config.get("docs_preexisting_at_install", True))
        consent_path: Path | None = None
        consent: dict[str, Any] = {"approved": True}
        authorization_basis = "project_init_bootstrap"
        if existing_docs_require_consent:
            if not args.consent:
                raise HarnessError(
                    "已有 docs 的知识更新必须提供 --consent",
                    code="knowledge_update_consent_required",
                    exit_code=3,
                )
            consent_path, consent = load_knowledge_consent(
                args.consent,
                sorted(set(allowed_scope)),
                assessment_fingerprint=assessment_fingerprint,
                inventory_fingerprint=inventory_fingerprint,
            )
            authorization_basis = "reported_user_consent"
        elif args.consent:
            consent_path, consent = load_knowledge_consent(
                args.consent,
                sorted(set(allowed_scope)),
                assessment_fingerprint=assessment_fingerprint,
                inventory_fingerprint=inventory_fingerprint,
            )
            authorization_basis = "reported_user_consent"
        if not consent["approved"]:
            runtime = knowledge_runtime_root(target)
            runtime.mkdir(parents=True, exist_ok=True)
            atomic_write_json(runtime / "declined.json", {"assessment_fingerprint": assessment_fingerprint, "inventory_fingerprint": inventory_fingerprint, "authorized_scope": sorted(set(allowed_scope)), "consent_ref": str(consent_path), "recorded_at": utc_now()})
            return 0, {"action": "update", "status": "declined", "changed": []}
        estimate = workload_estimate(target)
        job, idempotent = create_background_job(
            target,
            task_kind="knowledge_bootstrap",
            estimate=estimate,
            parent_task_id=None,
            feature_ids=[item["feature_id"] for item in normalized_map["features"]],
            categories=KNOWLEDGE_CATEGORIES,
            allowed_read_scope=("**",),
            allowed_write_scope=sorted(set(allowed_scope)),
            objective="遍历当前项目并建立 L2 功能知识库",
            authorization_basis=authorization_basis,
            assessment_ref=str(assessment_path),
            consent_ref=str(consent_path) if consent_path else None,
        )
        return 0, {"action": "update", "status": job["status"], "job_id": job["job_id"], "idempotent": idempotent, "dispatch_contract": job}

    raise HarnessError("未知 knowledge 动作", code="invalid_knowledge_action")


def managed_agent_block() -> str:
    return f"""{MANAGED_BEGIN}
## Docs Harness 任务入口

Docs Harness 当前版本：{VERSION}

每个用户任务的第一条任务动作必须是：

```bash
python3 scripts/harness.py run --target . --task "<原始用户任务>" --json
```

- 只有 `ready_direct`、`ready_planned`、`ready_extended` 允许进入对应执行阶段；`context_quality=degraded` 只表示知识不完整，必须现场核实事实，不改变准入状态。
- `planned/extended` 先运行 `context --stage plan`，形成正式方案后再次 `run` 取得执行准入。
- `extended` 每个工作包依次执行 `context`、`progress begin`、`progress submit|block`。
- 范围、目标、准备动作、授权或 Gate 变化时立即停止并重新运行 `run`。
- 最终必须运行 `verify`；只有其返回 `完成` 才是 Docs Harness 完成状态。
- 安装响应为 `knowledge_flow.mode=bootstrap_new` 时，安装已经完成，按 `execution_route` 异步派发 L2 知识初始化；响应为 `audit_existing` 时先零写入审查，只有确认不完整后才询问用户是否更新。
- `verify` 返回完成后，父任务状态已经原子终结；宿主只按任务包冻结的 `background_deliverables` 和返回的 `background_jobs` 派发后台治理，未声明时不得创建 Job。
- `background_direct` 创建有界后台子智能体；`background_goal|background_goal_phased` 必须建立持续目标、方案和进度，不能静默降级为直接任务。
- 宿主能力不足时将 Job 置为 `queued_manual` 并保留原 `execution_route`；不得误报已派发。
- 后台 Job 只能写 `allowed_write_scope`，不得触碰代码、提交、推送、发布或外部状态；所有 Job 固定 `may_mutate_parent=false`、`may_spawn_child_jobs=false` 和 `suppress_post_completion_dispatch=true`。
- 知识 Job 只有在控制器复算最终状态为 `ready` 时才能以 `updated|no_change` 完成；非终态 bootstrap 阻塞增量 Job，失败依赖不得释放等待者。
- 功能知识来自 `docs/knowledge-map.json` 和 `docs/features/`；任务无法唯一定位功能时使用 `run --feature <id>` 重新准入，不得全量加载 `docs/`。
- 只有用户明确要求“添加到质量账本”或同义写入动作时，才整理脱敏复盘 JSON 并运行 `ledger add`；不得自动记录，也不得在每个任务结束后主动询问。
- 后续任务需要复用历史经验时，按任务编号或关键词运行 `ledger read`；不得自动注入全部个人账本。
- `--scope` 是可重复单值参数，一次只传一个项目内相对路径；禁止把 JSON 数组整体作为单个值传入（会报 `invalid_scope_json`）。`--facts`/`--plan`/`--evidence`/`--authorization` 等文件参数一律使用工作区相对路径，Windows 上不要传 Git Bash 的 `/tmp` 路径。
- 每步响应的 `contract_snapshot` 是当前合同真源：重准入修 scope 时必须同时核对 `allowed_scope`/`read_scope`/`write_scope` 三个字段的实际值；verify 前先按 `contract_snapshot.evidence_types` 一次性备齐证据再跑。
- `--facts` 仅在 blocked 或 scope_changed 的重准入时生效；响应出现 `facts_ignored=true` 即表示本次 facts 被忽略，需先使任务进入 blocked/scope_changed 状态再提交。
- 低风险文档/规则/测试类小任务可在 facts 声明 `fast_track: true` 走轻量准入：生效时响应带 `evidence_profile: "fast_track"`，只需备 `code_diff`（声明验证命令时加 `test_run`）证据；返回 `fast_track_denied_reason` 即已降级普通流程。fast_track 不豁免任何 Gate；可用 `inline_note`（≤200 字）替代独立 plan 文档，非 fast_track 携带会被忽略（`inline_note_ignored`）。
- planned 路线改方案后必须先 `context --stage plan` 再 `run --plan`，顺序错了会被 `plan_context_required` 挡回。
{MANAGED_END}"""


def managed_version_block() -> str:
    return f"{MANAGED_VERSION_BEGIN}\nDocs Harness 当前版本：{VERSION}\n{MANAGED_VERSION_END}"


def managed_block_version(text: str, begin: str, end: str) -> str | None:
    pattern = re.compile(
        re.escape(begin)
        + rf".*?Docs Harness\s*当前版本：\s*v?({SEMVER_PATTERN}).*?"
        + re.escape(end),
        re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1) if match else None


def replace_managed_version_block(text: str) -> str:
    begin_count = text.count(MANAGED_VERSION_BEGIN)
    end_count = text.count(MANAGED_VERSION_END)
    if begin_count or end_count:
        if begin_count != 1 or end_count != 1 or text.index(MANAGED_VERSION_BEGIN) > text.index(MANAGED_VERSION_END):
            raise HarnessError(
                "Docs Harness 版本受管区块不完整或重复，需人工迁移",
                code="version_marker_conflict",
                exit_code=3,
            )
        return replace_managed_block(
            text,
            MANAGED_VERSION_BEGIN,
            MANAGED_VERSION_END,
            managed_version_block(),
        )
    block = managed_version_block()
    lines = text.splitlines(keepends=True)
    if lines and lines[0].lstrip().startswith("# "):
        first = lines[0].rstrip("\r\n")
        rest = "".join(lines[1:]).lstrip("\r\n")
        return f"{first}\n\n{block}\n" + (f"\n{rest}" if rest else "")
    prefix = text.rstrip()
    return (prefix + "\n\n" if prefix else "") + block + "\n"


def legacy_version_index_state(target: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    exact_pattern = re.compile(
        rf"(?m)^Docs Harness\s*当前版本：\s*v?({SEMVER_PATTERN})\s*$"
    )
    broad_pattern = re.compile(
        rf"(?im)^.*Docs Harness.*?\bv?({SEMVER_PATTERN})\b.*$"
    )
    for relative in LEGACY_VERSION_INDEX_PATHS:
        path = target / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if MANAGED_VERSION_BEGIN in text or MANAGED_VERSION_END in text:
            version = managed_block_version(text, MANAGED_VERSION_BEGIN, MANAGED_VERSION_END)
            if version != VERSION:
                results.append(
                    {
                        "path": relative,
                        "action": "update_managed_version",
                        "from_version": version,
                        "to_version": VERSION,
                    }
                )
            continue
        exact = list(exact_pattern.finditer(text))
        broad = list(broad_pattern.finditer(text))
        if len(exact) == 1 and len(broad) == 1:
            results.append(
                {
                    "path": relative,
                    "action": "migrate_legacy_version_template",
                    "from_version": exact[0].group(1),
                    "to_version": VERSION,
                }
            )
        elif broad:
            results.append(
                {
                    "path": relative,
                    "action": "needs_manual_migration",
                    "reason_code": "unowned_legacy_version_reference",
                }
            )
    return results


def apply_legacy_version_index_updates(target: Path) -> list[str]:
    changed: list[str] = []
    exact_pattern = re.compile(
        rf"(?m)^Docs Harness\s*当前版本：\s*v?({SEMVER_PATTERN})\s*$"
    )
    for item in legacy_version_index_state(target):
        if item["action"] == "needs_manual_migration":
            continue
        path = target / str(item["path"])
        before = path.read_text(encoding="utf-8")
        if item["action"] == "migrate_legacy_version_template":
            after = exact_pattern.sub(managed_version_block(), before, count=1)
        else:
            after = replace_managed_version_block(before)
        if after != before:
            atomic_write_text(path, after)
            changed.append(str(item["path"]))
    return changed


def claude_block() -> str:
    return f"""{CLAUDE_BEGIN}
执行任何任务前，先完整读取 `AGENTS.md`，并把其中的 Docs Harness 命令作为任务控制入口。
{CLAUDE_END}"""


def replace_managed_block(text: str, begin: str, end: str, block: str) -> str:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    if pattern.search(text):
        return pattern.sub(block, text)
    prefix = text.rstrip()
    return (prefix + "\n\n" if prefix else "") + block + "\n"


def remove_managed_block(text: str, begin: str, end: str) -> str:
    pattern = re.compile(r"\n*" + re.escape(begin) + r".*?" + re.escape(end) + r"\n*", re.DOTALL)
    if not pattern.search(text):
        return text
    return pattern.sub("\n", text).strip() + "\n"


def read_version_sources(source_root: Path) -> dict[str, str | None]:
    """读取四处版本真源；缺失或不可解析的项返回 None（validate_project_source 与 release sync 共用）。"""
    sources: dict[str, str | None] = {
        "VERSION": (source_root / "VERSION").read_text(encoding="utf-8").strip()
        if (source_root / "VERSION").is_file()
        else None,
        "controller": None,
        "skill": None,
        "package": None,
    }
    source_script = source_root / "scripts" / "harness.py"
    if source_script.is_file():
        controller_match = re.search(
            rf'(?m)^VERSION\s*=\s*["\']({SEMVER_PATTERN})["\']\s*$',
            source_script.read_text(encoding="utf-8"),
        )
        sources["controller"] = controller_match.group(1) if controller_match else None
    skill = source_root / "SKILL.md"
    if skill.is_file():
        metadata, _ = parse_frontmatter(skill.read_text(encoding="utf-8"))
        sources["skill"] = metadata.get("version")
    package = source_root / "package.json"
    if package.is_file():
        package_value = read_json(package)
        if isinstance(package_value, dict) and isinstance(package_value.get("version"), str):
            sources["package"] = package_value["version"]
    return sources


def changelog_top_version(source_root: Path) -> str | None:
    """读取 CHANGELOG.md 顶部条目版本号；缺失或无版本条目返回 None。"""
    path = source_root / "CHANGELOG.md"
    if not path.is_file():
        return None
    match = re.search(rf"(?m)^##\s+\[?v?({SEMVER_PATTERN})\]?", path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def release_sync_package_content(raw: str, truth: str) -> str:
    pattern = re.compile(r'(?m)^([ \t]*"version"[ \t]*:[ \t]*")' + SEMVER_PATTERN + r'(")')
    if len(pattern.findall(raw)) != 1:
        raise HarnessError(
            "package.json 的 version 字段缺失或出现多次，归属不明，失败关闭",
            code="release_managed_file_unrecognized",
        )
    updated = pattern.sub(rf"\g<1>{truth}\g<2>", raw, count=1)
    parsed = json.loads(updated)
    if not isinstance(parsed, dict) or parsed.get("version") != truth:
        raise HarnessError("package.json 写入内容校验失败", code="release_managed_file_unrecognized")
    return updated


def release_sync_skill_content(raw: str, truth: str) -> str:
    if not raw.startswith("---\n"):
        raise HarnessError("SKILL.md 缺少 frontmatter，归属不明，失败关闭", code="release_managed_file_unrecognized")
    end = raw.find("\n---\n", 4)
    if end < 0:
        raise HarnessError("SKILL.md frontmatter 不完整，归属不明，失败关闭", code="release_managed_file_unrecognized")
    front = raw[4:end]
    pattern = re.compile(rf"(?m)^([ \t]*version[ \t]*:[ \t]*)([\"']?){SEMVER_PATTERN}([\"']?)[ \t]*$")
    matches = list(pattern.finditer(front))
    if len(matches) != 1 or matches[0].group(2) != matches[0].group(3):
        raise HarnessError(
            "SKILL.md frontmatter 的 version 字段缺失或归属不明，失败关闭",
            code="release_managed_file_unrecognized",
        )
    match = matches[0]
    new_front = front[: match.start()] + f"{match.group(1)}{match.group(2)}{truth}{match.group(3)}" + front[match.end():]
    updated = raw[:4] + new_front + raw[end:]
    metadata, _ = parse_frontmatter(updated)
    if metadata.get("version") != truth:
        raise HarnessError("SKILL.md 写入内容校验失败", code="release_managed_file_unrecognized")
    return updated


def apply_release_sync_writes(target: Path, writes: list[tuple[str, str]]) -> None:
    """全部目标先写临时文件并校验，再统一替换；任一失败整体回滚，无部分写入。"""
    temps: list[tuple[Path, Path, bytes]] = []
    try:
        for relative, content in writes:
            path = target / relative
            if path.exists() and not path.is_file():
                raise HarnessError(
                    f"{relative} 不是普通文件，无法写入；已整体拒绝，无部分写入",
                    code="release_write_failed",
                    exit_code=1,
                )
            original = path.read_bytes()
            fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            temp = Path(raw)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(raw)
                raise
            if temp.read_bytes() != content.encode("utf-8"):
                raise HarnessError(f"{relative} 临时文件校验失败", code="release_write_failed", exit_code=1)
            temps.append((path, temp, original))
        replaced: list[tuple[Path, bytes]] = []
        try:
            for path, temp, original in temps:
                os.replace(temp, path)
                replaced.append((path, original))
        except OSError as exc:
            for path, original in reversed(replaced):
                with contextlib.suppress(OSError):
                    path.write_bytes(original)
            raise HarnessError(
                "release sync 写入失败，已整体回滚，无部分写入",
                code="release_write_failed",
                exit_code=1,
            ) from exc
    finally:
        for _, temp, _ in temps:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp)


def validate_project_source(source_root: Path) -> tuple[Path, Path]:
    source_script = source_root / "scripts" / "harness.py"
    source_rules = source_root / "harness-home" / "rules"
    if not source_script.is_file() or not source_rules.is_dir() or not rule_file_fingerprints(source_rules):
        raise HarnessError(
            "project init/upgrade/diff 必须从包含 harness-home/rules 的 Docs Harness 来源包执行",
            code="invalid_source",
        )
    if any(value != VERSION for value in read_version_sources(source_root).values()):
        raise HarnessError(
            "Docs Harness 来源包版本真源不一致",
            code="source_version_inconsistent",
        )
    return source_script, source_rules


def project_changes(
    target: Path,
    source_root: Path,
    *,
    sync_existing_version_markers: bool = True,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    script = target / "scripts" / "harness.py"
    source_script, source_rules = validate_project_source(source_root)
    if not script.is_file():
        changes.append({"path": "scripts/harness.py", "action": "create"})
    elif cached_file_fingerprint(script) != cached_file_fingerprint(source_script):
        changes.append({"path": "scripts/harness.py", "action": "update"})
    managed_entries = (
        ("AGENTS.md", MANAGED_BEGIN, MANAGED_END, managed_agent_block()),
        ("CLAUDE.md", CLAUDE_BEGIN, CLAUDE_END, claude_block()),
    )
    for relative, begin, end, block in managed_entries:
        path = target / relative
        if not path.is_file():
            changes.append({"path": relative, "action": "create_or_merge"})
            continue
        current = path.read_text(encoding="utf-8")
        expected = replace_managed_block(current, begin, end, block)
        if current != expected:
            action = "update_managed_block" if begin in current else "create_or_merge"
            changes.append({"path": relative, "action": action})
    docs_exists = (target / KNOWLEDGE_ROOT_RELATIVE).is_dir()
    map_exists = knowledge_map_path(target).is_file()
    if not docs_exists or map_exists:
        for relative in KNOWLEDGE_SCAFFOLD:
            if not (target / relative).is_file():
                changes.append({"path": relative, "action": "create"})
        if not map_exists:
            changes.append({"path": KNOWLEDGE_MAP_RELATIVE, "action": "create"})
    docs_index = target / "docs" / "INDEX.md"
    if sync_existing_version_markers and docs_index.is_file():
        current = docs_index.read_text(encoding="utf-8")
        try:
            expected = replace_managed_version_block(current)
        except HarnessError:
            changes.append(
                {
                    "path": "docs/INDEX.md",
                    "action": "needs_manual_migration",
                    "reason_code": "invalid_managed_version_block",
                }
            )
        else:
            if current != expected:
                changes.append(
                    {
                        "path": "docs/INDEX.md",
                        "action": "update_managed_version",
                        "from_version": managed_block_version(
                            current, MANAGED_VERSION_BEGIN, MANAGED_VERSION_END
                        ),
                        "to_version": VERSION,
                    }
                )
    if sync_existing_version_markers:
        changes.extend(legacy_version_index_state(target))
    target_rules = target / PROJECT_RULES_RELATIVE
    for name, fingerprint in rule_file_fingerprints(source_rules).items():
        target_rule = target_rules / name
        if not target_rule.is_file():
            changes.append({"path": f"{PROJECT_RULES_RELATIVE}/{name}", "action": "create"})
        elif file_fingerprint(target_rule) != fingerprint:
            changes.append({"path": f"{PROJECT_RULES_RELATIVE}/{name}", "action": "update"})
    config = target / ".docs-harness" / "config.json"
    current_config = project_config(target)
    if current_config is not None:
        configured_volatile_verification_patterns(target)
    _, route_config_errors = document_route_config(target)
    if route_config_errors:
        changes.append({
            "path": ".docs-harness/config.json",
            "action": "needs_manual_migration",
            "reason_code": "invalid_document_route_config",
        })
    expected_rules = rule_file_fingerprints(source_rules)
    if not config.is_file():
        changes.append({"path": ".docs-harness/config.json", "action": "create"})
    elif (
        current_config is None
        or current_config.get("version") != VERSION
        or current_config.get("rules_root") != PROJECT_RULES_RELATIVE
        or current_config.get("installed_script_fingerprint") != script_fingerprint_tolerant(source_script)
        or current_config.get("installed_rule_fingerprints") != expected_rules
        or not isinstance(current_config.get("knowledge"), dict)
        or not isinstance(current_config.get("background_governance"), dict)
    ):
        changes.append({"path": ".docs-harness/config.json", "action": "update"})
    return changes


def apply_project_install(
    target: Path,
    source_root: Path,
    *,
    docs_preexisted: bool | None = None,
    sync_existing_version_markers: bool = False,
) -> list[str]:
    changed: list[str] = []
    source_script, source_rules = validate_project_source(source_root)
    target_script = target / "scripts" / "harness.py"
    config = project_config(target)
    if config is not None:
        configured_volatile_verification_patterns(target)
    if target_script.exists() and not config and script_fingerprint_tolerant(target_script) != script_fingerprint_tolerant(source_script):
        raise HarnessError("目标 scripts/harness.py 已存在且不受 Docs Harness 管理", code="install_conflict")
    if target_script.exists() and config:
        current_fingerprint = script_fingerprint_tolerant(target_script)
        installed_fingerprint = config.get("installed_script_fingerprint")
        source_fingerprint = script_fingerprint_tolerant(source_script)
        if current_fingerprint not in {installed_fingerprint, source_fingerprint}:
            raise HarnessError("项目任务控制脚本存在用户改动，拒绝覆盖；需人工 preserve-and-merge", code="install_conflict")
    target_script.parent.mkdir(parents=True, exist_ok=True)
    if not target_script.is_file() or file_fingerprint(target_script) != file_fingerprint(source_script):
        shutil.copy2(source_script, target_script)
        target_script.chmod(target_script.stat().st_mode | 0o111)
        changed.append("scripts/harness.py")

    agent_path = target / "AGENTS.md"
    agent_text = agent_path.read_text(encoding="utf-8") if agent_path.is_file() else "# AGENTS.md\n"
    new_agent = replace_managed_block(agent_text, MANAGED_BEGIN, MANAGED_END, managed_agent_block())
    if new_agent != agent_text:
        atomic_write_text(agent_path, new_agent)
        changed.append("AGENTS.md")
    claude_path = target / "CLAUDE.md"
    claude_text = claude_path.read_text(encoding="utf-8") if claude_path.is_file() else "# CLAUDE.md\n"
    new_claude = replace_managed_block(claude_text, CLAUDE_BEGIN, CLAUDE_END, claude_block())
    if new_claude != claude_text:
        atomic_write_text(claude_path, new_claude)
        changed.append("CLAUDE.md")
    if docs_preexisted is None:
        docs_preexisted = (target / KNOWLEDGE_ROOT_RELATIVE).is_dir()
    existing_map = knowledge_map_path(target).is_file()
    # repowiki 只消费项目不创建 docs/ 知识骨架
    if (not docs_preexisted or existing_map) and repowiki_knowledge_root(target) is None:
        for relative, content in KNOWLEDGE_SCAFFOLD.items():
            path = target / relative
            if not path.exists():
                atomic_write_text(path, content)
                changed.append(relative)
        if not knowledge_map_path(target).is_file():
            atomic_write_json(knowledge_map_path(target), empty_knowledge_map())
            changed.append(KNOWLEDGE_MAP_RELATIVE)
    docs_index = target / "docs" / "INDEX.md"
    if sync_existing_version_markers and docs_index.is_file():
        before = docs_index.read_text(encoding="utf-8")
        after = replace_managed_version_block(before)
        if after != before:
            atomic_write_text(docs_index, after)
            changed.append("docs/INDEX.md")
        changed.extend(apply_legacy_version_index_updates(target))
    target_rules = target / PROJECT_RULES_RELATIVE
    source_rule_fingerprints = rule_file_fingerprints(source_rules)
    installed_rule_fingerprints = config.get("installed_rule_fingerprints", {}) if config else {}
    if config and not isinstance(installed_rule_fingerprints, dict):
        raise HarnessError("项目规则安装指纹无效", code="install_conflict")
    for name, source_fingerprint in source_rule_fingerprints.items():
        target_rule = target_rules / name
        if target_rule.is_file():
            current_fingerprint = file_fingerprint(target_rule)
            installed_fingerprint = installed_rule_fingerprints.get(name)
            if installed_fingerprint and current_fingerprint not in {installed_fingerprint, source_fingerprint}:
                raise HarnessError(
                    f"项目规则 {name} 存在用户改动，拒绝覆盖；需人工 preserve-and-merge",
                    code="install_conflict",
                )
        target_rule.parent.mkdir(parents=True, exist_ok=True)
        if not target_rule.is_file() or file_fingerprint(target_rule) != source_fingerprint:
            shutil.copy2(source_rules / name, target_rule)
            changed.append(f"{PROJECT_RULES_RELATIVE}/{name}")
    config_path = target / ".docs-harness" / "config.json"
    existing_config = project_config(target)
    _, route_config_errors = document_route_config(target)
    if route_config_errors:
        raise HarnessError(
            "现有 document_routes 非法，升级不得覆盖或静默保留",
            code="invalid_document_route_config", exit_code=3,
        )
    existing_governance = (
        existing_config.get("background_governance", {})
        if existing_config and isinstance(existing_config.get("background_governance"), dict)
        else {}
    )
    config_value = {
        "schema_version": CONFIG_SCHEMA,
        "version": VERSION,
        "rules_root": PROJECT_RULES_RELATIVE,
        "installed_script_fingerprint": script_fingerprint_tolerant(source_script),
        "installed_rule_fingerprints": source_rule_fingerprints,
        "background_governance": {
            "enabled": True,
            "non_blocking": True,
            "workload_estimator": "v1",
            "simple_threshold": 24,
            "complex_threshold": 59,
            "host_dispatch": "required_when_supported",
        },
        "knowledge": {
            "root": KNOWLEDGE_ROOT_RELATIVE,
            "map": KNOWLEDGE_MAP_RELATIVE,
            "target_level": "L2",
            "post_completion_sync": True,
            "allow_degraded_admission": True,
            "bootstrap_async": True,
            "block_main_completion": False,
            "docs_preexisting_at_install": bool(
                existing_config.get("knowledge", {}).get("docs_preexisting_at_install")
                if existing_config and isinstance(existing_config.get("knowledge"), dict)
                else docs_preexisted
            ),
        },
        "installed_at": existing_config.get("installed_at") if existing_config else utc_now(),
    }
    if "document_routes" in existing_governance:
        config_value["background_governance"]["document_routes"] = existing_governance["document_routes"]
    existing_knowledge = existing_config.get("knowledge", {}) if existing_config and isinstance(existing_config.get("knowledge"), dict) else {}
    if "inventory_include" in existing_knowledge:
        config_value["knowledge"]["inventory_include"] = existing_knowledge["inventory_include"]
    existing_verification = existing_config.get("verification", {}) if existing_config and isinstance(existing_config.get("verification"), dict) else {}
    if "volatile_paths" in existing_verification:
        config_value["verification"] = {
            "volatile_paths": validate_volatile_verification_paths(existing_verification["volatile_paths"])
        }
    if existing_config != config_value:
        atomic_write_json(config_path, config_value)
        changed.append(".docs-harness/config.json")
    return list(dict.fromkeys(changed))


def project_findings(target: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    config = project_config(target)
    if not config or config.get("schema_version") != CONFIG_SCHEMA:
        findings.append({"severity": "red", "code": "missing_config", "message": "缺少有效项目配置"})
    elif config.get("version") != VERSION:
        findings.append(
            {
                "severity": "red",
                "code": "controller_version_mismatch",
                "message": f"项目配置版本 {config.get('version')} 与控制器版本 {VERSION} 不一致",
            }
        )
    _, route_config_errors = document_route_config(target)
    if route_config_errors:
        findings.append({
            "severity": "red", "code": "invalid_document_route_config",
            "message": "background_governance.document_routes 配置非法",
        })
    source_metadata = (SCRIPT_ROOT / "VERSION", SCRIPT_ROOT / "SKILL.md", SCRIPT_ROOT / "package.json")
    if all(path.is_file() for path in source_metadata):
        try:
            validate_project_source(SCRIPT_ROOT)
        except HarnessError as exc:
            if exc.code == "source_version_inconsistent":
                findings.append({"severity": "red", "code": exc.code, "message": str(exc)})
    script = target / "scripts" / "harness.py"
    if not script.is_file():
        findings.append({"severity": "red", "code": "missing_entry_script", "message": "缺少 scripts/harness.py"})
    elif config and config.get("installed_script_fingerprint") != script_fingerprint_tolerant(script):
        findings.append({"severity": "red", "code": "script_drift", "message": "项目任务控制脚本与安装指纹不一致"})
    for relative, marker in (("AGENTS.md", MANAGED_BEGIN), ("CLAUDE.md", CLAUDE_BEGIN)):
        path = target / relative
        if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
            findings.append({"severity": "red", "code": "missing_entry_chain", "message": f"{relative} 缺少 Docs Harness 入口"})
    agents = target / "AGENTS.md"
    if agents.is_file() and MANAGED_BEGIN in agents.read_text(encoding="utf-8"):
        agent_version = managed_block_version(
            agents.read_text(encoding="utf-8"), MANAGED_BEGIN, MANAGED_END
        )
        if agent_version != (config.get("version") if config else VERSION):
            findings.append(
                {
                    "severity": "red",
                    "code": "managed_entry_version_mismatch",
                    "message": "AGENTS.md 受管版本与项目配置不一致",
                }
            )
    docs_index = target / "docs" / "INDEX.md"
    if docs_index.is_file() and (
        MANAGED_VERSION_BEGIN in docs_index.read_text(encoding="utf-8")
        or MANAGED_VERSION_END in docs_index.read_text(encoding="utf-8")
    ):
        index_version = managed_block_version(
            docs_index.read_text(encoding="utf-8"),
            MANAGED_VERSION_BEGIN,
            MANAGED_VERSION_END,
        )
        if index_version != (config.get("version") if config else VERSION):
            findings.append(
                {
                    "severity": "red",
                    "code": "knowledge_index_version_mismatch",
                    "message": "docs/INDEX.md 受管版本与项目配置不一致",
                }
            )
    for item in legacy_version_index_state(target):
        if item["action"] == "needs_manual_migration":
            findings.append(
                {
                    "severity": "yellow",
                    "code": "legacy_version_reference",
                    "message": f"{item['path']} 含有归属不明的旧版 Docs Harness 版本标记",
                }
            )
    current_knowledge = knowledge_status(target)
    if current_knowledge["status"] == "invalid":
        findings.append({"severity": "red", "code": "invalid_knowledge_base", "message": "；".join(current_knowledge["gaps"])})
    elif current_knowledge["status"] != "ready":
        findings.append({"severity": "yellow", "code": "knowledge_pending", "message": f"功能知识库状态：{current_knowledge['status']}"})
    now = dt.datetime.now(dt.timezone.utc)
    for job in list_background_jobs(target):
        if legacy_governance_route_job(job) and job.get("status") not in {"updated", "no_change", "completed_with_finding", "failed"}:
            findings.append({
                "severity": "yellow", "code": "legacy_governance_route_contract",
                "message": f"治理 Job {job.get('job_id')} 缺少文档路由合同，需要停止宿主、取消并 route repair",
            })
        contract = job.get("document_route_contract")
        if isinstance(contract, dict) and contract.get("status") != "resolved" and job.get("status") not in BACKGROUND_TERMINAL_STATES:
            findings.append({
                "severity": "yellow", "code": str(contract.get("reason_code") or "document_route_missing"),
                "message": f"治理 Job {job.get('job_id')} 的文档路由需要处理",
            })
        if job.get("status") in BACKGROUND_TERMINAL_STATES - {"failed"}:
            continue
        stale = job.get("stale_after")
        is_stale = job.get("status") in {"failed", "needs_user_input", "needs_rebase", "queued_manual"}
        if stale:
            with contextlib.suppress(ValueError):
                is_stale = dt.datetime.fromisoformat(str(stale).replace("Z", "+00:00")) <= now
        if is_stale:
            findings.append({"severity": "yellow", "code": "background_job_stale", "message": f"后台治理 Job {job.get('job_id')} 状态为 {job.get('status')}"})
    if not route_config_errors and not any(
        isinstance(job.get("document_route_contract"), dict)
        and job.get("document_route_contract", {}).get("status") != "resolved"
        and job.get("status") not in BACKGROUND_TERMINAL_STATES
        for job in list_background_jobs(target)
    ):
        discovery = resolve_document_routes(target, required_kinds=DOCUMENT_ROUTE_KINDS)
        if discovery.get("status") == "unresolved":
            for error in discovery.get("errors", []):
                if error.get("reason_code") in {"document_route_missing", "document_route_ambiguous", "document_route_unsafe"}:
                    findings.append({
                        "severity": "yellow", "code": str(error["reason_code"]),
                        "message": f"文档类别 {error.get('kind')} 尚无唯一可信真源",
                    })
    try:
        rules_root = rules_root_for(target)
    except HarnessError as exc:
        findings.append({"severity": "red", "code": "invalid_config", "message": str(exc)})
        return findings
    if not rules_root.is_dir():
        findings.append({"severity": "red", "code": "missing_harness_home", "message": "Harness Home 缺失；任务控制必须失败关闭"})
    else:
        configured_fingerprints = config.get("installed_rule_fingerprints", {}) if config else {}
        if not isinstance(configured_fingerprints, dict) or not configured_fingerprints:
            findings.append({"severity": "red", "code": "missing_rule_snapshot", "message": "缺少规则安装指纹"})
        else:
            live_fingerprints = rule_file_fingerprints(rules_root)
            if live_fingerprints != configured_fingerprints:
                findings.append({"severity": "red", "code": "rule_snapshot_drift", "message": "项目规则快照缺失、增加或已变化"})
        active_rules, errors = load_active_rules(target, GATE_ORDER, " ".join(GATE_ORDER), match_all=True)
        findings.extend({"severity": "red", "code": "invalid_active_rule", "message": item} for item in errors)
        if not errors and not active_rules:
            findings.append({"severity": "red", "code": "missing_active_rules", "message": "没有可执行的 active 规则"})
    ignored_install_paths = git_ignored_install_paths(target, project_portable_install_paths(target))
    if ignored_install_paths:
        findings.append(
            {
                "severity": "red",
                "code": "git_delivery_ignored",
                "message": "Git 忽略了 Docs Harness 安装快照：" + ", ".join(ignored_install_paths),
            }
        )
    return findings


def migrate_background_jobs_v2(target: Path) -> list[str]:
    """幂等迁移 v1 Job；status 查询本身不会调用此函数。"""
    migrated: list[str] = []
    seen: set[str] = set()
    for parent in (background_jobs_root(target), knowledge_jobs_root(target)):
        if not parent.is_dir():
            continue
        for path in sorted(parent.glob("*/job.json")):
            with contextlib.suppress(HarnessError):
                raw = read_json(path)
                job_id = str(raw.get("job_id", "")) if isinstance(raw, dict) else ""
                if not job_id or job_id in seen or raw.get("schema_version") != LEGACY_BACKGROUND_JOB_SCHEMA:
                    continue
                seen.add(job_id)
                root, job = read_knowledge_job(target, job_id)
                before_status = str(job.get("status"))
                if before_status == "waiting_for_bootstrap_merge":
                    dependency_ids = list(job.get("dependency_job_ids", []))
                    if not dependency_ids:
                        job["status"] = "needs_user_input"
                        job["dependency_reason_code"] = "bootstrap_dependency_missing"
                    else:
                        try:
                            _, dependency = read_knowledge_job(target, str(dependency_ids[0]))
                            outcome = knowledge_dependency_outcome(dependency, target)
                        except HarnessError:
                            outcome = "blocked"
                        if outcome == "success":
                            job["dependency_job_ids"] = dependency_ids[1:]
                            job["status"] = "contract_ready"
                            job["baseline_rebuilt_after_bootstrap"] = True
                            refresh_knowledge_job_baseline(target, job)
                        elif outcome in {"blocked", "unknown"}:
                            job["status"] = "needs_user_input"
                            job["dependency_reason_code"] = "bootstrap_dependency_not_ready"
                job["schema_version"] = BACKGROUND_JOB_SCHEMA
                job["may_spawn_child_jobs"] = False
                job["migrated_from_schema"] = LEGACY_BACKGROUND_JOB_SCHEMA
                job["updated_at"] = utc_now()
                write_background_job(target, root, job)
                append_background_event(
                    root, job, "schema_migrated",
                    from_status=str(before_status), status=str(job.get("status")),
                    reason_code="background_job_v1_to_v2",
                )
                migrated.append(job_id)
    return migrated


def prepare_knowledge_flow(
    target: Path,
    operation: str,
    docs_preexisted: bool,
    *,
    apply: bool,
) -> dict[str, Any]:
    flow = knowledge_handoff(target, operation, docs_preexisted)
    estimate = workload_estimate(target)
    estimate_path = persist_workload_estimate(target, estimate) if apply else None
    job: dict[str, Any] | None = None
    error: str | None = None
    if apply and flow["mode"] == "bootstrap_new":
        try:
            job, _ = create_background_job(
                target,
                task_kind="knowledge_bootstrap",
                estimate=estimate,
                parent_task_id=None,
                categories=KNOWLEDGE_CATEGORIES,
                allowed_read_scope=("**",),
                allowed_write_scope=("docs/**",),
                objective="遍历当前项目并建立 L2 功能知识库",
                authorization_basis=f"project_{operation}_bootstrap",
            )
        except (HarnessError, OSError) as exc:
            error = exc.code if isinstance(exc, HarnessError) else "background_job_runtime_error"
    if job:
        flow.update(
            {
                "job_id": job["job_id"],
                "dispatch_required": True,
                "dispatch_status": "dispatch_required",
                "dispatch_contract": job,
            }
        )
    elif error:
        flow.update({"dispatch_required": False, "dispatch_status": "dispatch_failed", "reason_code": error})
    flow.update(
        {
            "workload_class": estimate["workload_class"],
            "execution_route": estimate["execution_route"],
            "workload_estimate_ref": str(estimate_path) if estimate_path else None,
            "blocking_install": False,
        }
    )
    return flow


def legacy_governance_route_migrations(target: Path) -> list[dict[str, Any]]:
    migrations: list[dict[str, Any]] = []
    for job in list_background_jobs(target):
        if not legacy_governance_route_job(job):
            continue
        if job.get("status") in {"updated", "no_change", "completed_with_finding", "failed"}:
            continue
        migrations.append({
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "action": "cancel_then_route_repair" if job.get("status") != "cancelled" else "route_repair",
            "host_quiescence_required": job.get("status") in {"running", "dispatched"},
            "reason_code": "legacy_governance_route_contract",
        })
    return migrations


def command_project(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    source_root = source_root_for(target)
    if args.action == "rollback-check":
        active: list[str] = []
        runs = runtime_root(target)
        if runs.is_dir():
            for state in sorted(path for path in runs.iterdir() if path.is_dir()):
                package_path = state / "task-package.json"
                compiled_path = state / "compiled-task.json"
                if not package_path.is_file() or not compiled_path.is_file():
                    continue
                with contextlib.suppress(HarnessError):
                    package = read_json(package_path)
                    compiled = read_json(compiled_path)
                    if package.get("schema_version") == TASK_SCHEMA and compiled.get("control_status") not in ACTIVE_TASK_TERMINAL_STATUSES:
                        active.append(str(package.get("task_id") or state.name))
        route_blockers = [
            str(job.get("job_id")) for job in list_background_jobs(target)
            if job.get("task_kind") == "delivery_governance"
            and job.get("status") not in {"updated", "no_change", "completed_with_finding", "failed", "cancelled"}
        ]
        allowed = not active and not route_blockers
        return (0 if allowed else 3), {
            "action": "rollback-check",
            "rollback_allowed": allowed,
            "active_v2_task_ids": active,
            "active_document_route_job_ids": route_blockers,
            "reason_code": None if allowed else ("active_v2_tasks" if active else "active_document_route_jobs"),
            "storage_policy": "v2_objects_read_only_preserved",
            "legacy_controller_policy": "fail_closed_on_v2",
        }
    if args.action == "init":
        docs_preexisted = (target / KNOWLEDGE_ROOT_RELATIVE).is_dir()
        _, source_rules = validate_project_source(source_root)
        controller_paths = portable_install_paths(rule_file_fingerprints(source_rules).keys())
        portable_paths = list(controller_paths)
        if not docs_preexisted:
            portable_paths.extend([*KNOWLEDGE_SCAFFOLD, KNOWLEDGE_MAP_RELATIVE])
        ignored = git_ignored_install_paths(target, portable_paths)
        if ignored:
            raise HarnessError(
                "Git 忽略了 Docs Harness 必需安装文件，拒绝写入：" + ", ".join(ignored),
                code="git_delivery_ignored",
                exit_code=3,
            )
        changes = project_changes(
            target,
            source_root,
            sync_existing_version_markers=False,
        )
        changed = apply_project_install(
            target,
            source_root,
            docs_preexisted=docs_preexisted,
            sync_existing_version_markers=False,
        )
        knowledge_flow = prepare_knowledge_flow(
            target,
            "init",
            docs_preexisted,
            apply=True,
        )
        findings = project_findings(target)
        red = sum(item["severity"] == "red" for item in findings)
        delivery = project_delivery_summary(target, controller_paths)
        pending = delivery["delivery_status"] == "pending_commit"
        status = "failed" if red else ("needs_delivery" if delivery["delivery_status"] == "pending_commit" else "installed")
        code = 1 if red else (3 if pending else 0)
        return code, {
            "action": "init",
            "target": str(target),
            "version": VERSION,
            "status": status,
            "runtime_status": "blocked" if red else "healthy",
            **delivery,
            "planned_changes": changes,
            "changed": changed,
            "findings": findings,
            "preserved_existing_docs": True,
            "rules_copied_to_project": True,
            "knowledge_status": knowledge_status(target)["status"],
            "knowledge_next_action": knowledge_flow["knowledge_next_action"],
            "knowledge_next_command_argv": knowledge_flow["knowledge_next_command_argv"],
            "knowledge_flow": knowledge_flow,
        }
    if args.action == "upgrade":
        docs_preexisted = (target / KNOWLEDGE_ROOT_RELATIVE).is_dir()
        changes = project_changes(target, source_root)
        route_migrations = legacy_governance_route_migrations(target)
        _, route_config_errors = document_route_config(target)
        if not args.apply:
            manual_migrations = [
                item for item in changes if item.get("action") == "needs_manual_migration"
            ]
            manual_migrations.extend(route_migrations)
            knowledge_flow = prepare_knowledge_flow(target, "upgrade", docs_preexisted, apply=False)
            return 0, {
                "action": "upgrade",
                "mode": "preview",
                "target": str(target),
                "changes": changes,
                "manual_migrations": manual_migrations,
                "apply_completion_possible": not manual_migrations and not route_config_errors,
                "knowledge_status": knowledge_status(target)["status"],
                "knowledge_next_action": knowledge_flow["knowledge_next_action"],
                "knowledge_next_command_argv": knowledge_flow["knowledge_next_command_argv"],
                "knowledge_flow": knowledge_flow,
            }
        if route_config_errors:
            raise HarnessError(
                "document_routes 非法，升级应用已失败关闭",
                code="invalid_document_route_config", exit_code=3,
            )
        _, source_rules = validate_project_source(source_root)
        controller_paths = portable_install_paths(rule_file_fingerprints(source_rules).keys())
        ignored = git_ignored_install_paths(target, controller_paths)
        if ignored:
            raise HarnessError(
                "Git 忽略了 Docs Harness 必需安装文件，拒绝写入：" + ", ".join(ignored),
                code="git_delivery_ignored",
                exit_code=3,
            )
        changed = apply_project_install(
            target,
            source_root,
            docs_preexisted=docs_preexisted,
            sync_existing_version_markers=True,
        )
        migrated_background_jobs = migrate_background_jobs_v2(target)
        knowledge_flow = prepare_knowledge_flow(target, "upgrade", docs_preexisted, apply=True)
        findings = project_findings(target)
        red = sum(item["severity"] == "red" for item in findings)
        manual_migration = bool(route_migrations) or any(
            item["code"] in {"legacy_version_reference", "legacy_governance_route_contract"} for item in findings
        )
        delivery = project_delivery_summary(target, controller_paths)
        pending = delivery["delivery_status"] == "pending_commit"
        knowledge_settled = knowledge_flow["mode"] in {"already_ready", "external_consume_only"}
        status = (
            "failed"
            if red
            else (
                "needs_manual_migration"
                if manual_migration
                else (
                    "needs_delivery"
                    if pending
                    else "upgraded" if knowledge_settled
                    else "upgraded_knowledge_pending"
                )
            )
        )
        code = 1 if red else (3 if manual_migration or pending or not knowledge_settled else 0)
        return code, {
            "action": "upgrade",
            "mode": "apply",
            "target": str(target),
            "status": status,
            "runtime_status": "blocked" if red else "healthy",
            **delivery,
            "changed": changed,
            "findings": findings,
            "manual_migrations": [
                item for item in changes if item.get("action") == "needs_manual_migration"
            ] + route_migrations,
            "preserved_existing_docs": True,
            "migrated_background_job_ids": migrated_background_jobs,
            "knowledge_status": knowledge_status(target)["status"],
            "knowledge_next_action": knowledge_flow["knowledge_next_action"],
            "knowledge_next_command_argv": knowledge_flow["knowledge_next_command_argv"],
            "knowledge_flow": knowledge_flow,
        }
    if args.action == "check":
        findings = project_findings(target)
        red = sum(item["severity"] == "red" for item in findings)
        yellow = sum(item["severity"] == "yellow" for item in findings)
        config = project_config(target)
        rules_root = target / PROJECT_RULES_RELATIVE
        controller_paths = portable_install_paths(installed_rule_names(config, rules_root))
        delivery = project_delivery_summary(target, controller_paths)
        pending_delivery = not red and delivery["delivery_status"] == "pending_commit"
        manual_migration = not red and any(
            item["code"] == "legacy_version_reference" for item in findings
        )
        code = 1 if red else (3 if manual_migration or pending_delivery else 0)
        status = (
            "failed"
            if red
            else (
                "needs_manual_migration"
                if manual_migration
                else (
                    "needs_delivery"
                    if delivery["delivery_status"] == "pending_commit"
                    else (
                        "knowledge_pending"
                        if delivery["delivery_status"] == "knowledge_pending"
                        else "passed"
                    )
                )
            )
        )
        return code, {
            "action": "check",
            "target": str(target),
            "status": status,
            "runtime_status": "blocked" if red else "healthy",
            **delivery,
            "red": red,
            "yellow": yellow,
            "findings": findings,
            "empty_rules_legal": False,
        }
    if args.action == "diff":
        return 0, {"action": "diff", "target": str(target), "changes": project_changes(target, source_root)}
    if not args.apply:
        return 0, {"action": "uninstall", "mode": "preview", "target": str(target), "would_remove": ["Docs Harness managed entry and version blocks", ".docs-harness/config.json", "owned scripts/harness.py"], "purge_runtime": bool(args.purge_runtime)}
    removed: list[str] = []
    for relative, begin, end in (("AGENTS.md", MANAGED_BEGIN, MANAGED_END), ("CLAUDE.md", CLAUDE_BEGIN, CLAUDE_END)):
        path = target / relative
        if path.is_file():
            before = path.read_text(encoding="utf-8")
            after = remove_managed_block(before, begin, end)
            if after != before:
                atomic_write_text(path, after)
                removed.append(f"{relative}:managed_block")
    for relative in ("docs/INDEX.md", *LEGACY_VERSION_INDEX_PATHS):
        path = target / relative
        if path.is_file():
            before = path.read_text(encoding="utf-8")
            after = remove_managed_block(
                before, MANAGED_VERSION_BEGIN, MANAGED_VERSION_END
            )
            if after != before:
                atomic_write_text(path, after)
                removed.append(f"{relative}:managed_version_block")
    config = project_config(target)
    script = target / "scripts" / "harness.py"
    if script.is_file() and config and config.get("installed_script_fingerprint") == script_fingerprint_tolerant(script):
        script.unlink()
        removed.append("scripts/harness.py")
    config_path = target / ".docs-harness" / "config.json"
    if config_path.is_file():
        config_path.unlink()
        removed.append(".docs-harness/config.json")
    if args.purge_runtime:
        runs = runtime_root(target)
        if runs.is_dir() and runs.name == "runs" and runs.parent.name in {"docs-harness", ".docs-harness"}:
            shutil.rmtree(runs)
            removed.append(str(runs))
    return 0, {"action": "uninstall", "mode": "apply", "target": str(target), "removed": removed, "project_docs_preserved": True, "harness_home_preserved": True}


def command_authorization(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    if args.action != "template":
        raise HarnessError(f"authorization {args.action} 暂不支持", code="invalid_authorization_action")
    if not args.task_id:
        raise HarnessError("authorization template 必须提供 --task-id", code="missing_task_id")
    validate_task_id(args.task_id)
    state = task_state_dir(target, args.task_id)
    package_path = state / "task-package.json"
    if not package_path.is_file():
        raise HarnessError(f"任务包不存在：{args.task_id}", code="missing_task_package")
    package = read_json(package_path)
    template: dict[str, Any] = {
        "schema_version": AUTH_SCHEMA,
        "task_id": package["task_id"],
        "package_fingerprint": package_fingerprint(package),
        "approved": True,
        "authorized_at": None,
        "authorized_by": None,
        "expires_at": None,
        "authorized_actions": sorted(package.get("authorization_requirements", [])),
        "authorized_scope": sorted(package.get("allowed_scope", [])),
        "authorized_git_scope": sorted(package.get("git_scope", [])),
        "authorized_external_scope": sorted(package.get("external_scope", [])),
        "external_target": package.get("external_target"),
        "constraints": [],
        "_template_hints": {
            "git_scope_format": ".git:refs/remotes/<remote>/<branch>",
            "external_scope_format": "<remote> (not git-remote:<remote>)",
            "write_scope_format": "project-relative path or glob, must match task package exactly",
            "note": "authorized_at/authorized_by/expires_at 需手动填充；expires_at 为 ISO 8601 格式，如 2026-08-07T00:00:00Z",
        },
    }
    output_path = args.output
    if output_path:
        path = Path(output_path).expanduser().resolve()
        atomic_write_json(path, template)
        return 0, {
            "action": "template",
            "task_id": args.task_id,
            "output": str(path),
            "message": "授权模板已生成，请编辑填充 authorized_at/authorized_by/expires_at 后使用",
        }
    return 0, {
        "action": "template",
        "task_id": args.task_id,
        "template": template,
        "message": "授权模板已生成，请编辑填充 authorized_at/authorized_by/expires_at 后使用",
    }


def command_release_sync(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    if args.action != "sync":
        raise HarnessError(f"release {args.action} 暂不支持", code="invalid_release_action")
    sources = read_version_sources(target)
    truth = sources["controller"]
    if truth is None:
        raise HarnessError(
            "无法从 scripts/harness.py 读取 VERSION 常量，release sync 失败关闭",
            code="release_source_unreadable",
            exit_code=1,
        )
    if args.target_version is not None:
        if not re.fullmatch(SEMVER_PATTERN, args.target_version):
            raise HarnessError("--target-version 必须是 X.Y.Z 语义版本", code="invalid_target_version")
        if args.target_version != truth:
            raise HarnessError(
                "--target-version 与 scripts/harness.py 的 VERSION 常量不一致，失败关闭",
                code="release_version_conflict",
                actual_vs_expected={"expected": truth, "actual": args.target_version},
            )
    missing = [name for name, value in sources.items() if value is None]
    diffs = [
        {"source": name, "expected": truth, "actual": value}
        for name, value in sources.items()
        if value is not None and value != truth
    ]
    changelog = changelog_top_version(target)
    payload: dict[str, Any] = {
        "action": "sync",
        "target": str(target),
        "version_truth": truth,
        "sources": sources,
        "diffs": diffs,
        "changelog_top_version": changelog,
    }
    if changelog is None:
        payload["changelog_hint"] = "CHANGELOG.md 缺失或无版本条目，请人工确认"
    elif changelog != truth:
        payload["changelog_hint"] = "CHANGELOG 顶部条目版本号与 VERSION 常量不一致，请人工同步"
    if not args.apply:
        payload["mode"] = "check"
        if missing:
            payload["status"] = "unreadable"
            payload["missing_sources"] = missing
            return 1, payload
        payload["status"] = "inconsistent" if diffs else "consistent"
        return (2 if diffs else 0), payload
    payload["mode"] = "apply"
    if missing:
        raise HarnessError(
            "版本真源缺失或不可解析，--apply 失败关闭：" + ", ".join(missing),
            code="release_source_unreadable",
            exit_code=1,
        )
    builders = (
        ("VERSION", "VERSION", lambda raw, version: f"{version}\n"),
        ("package", "package.json", release_sync_package_content),
        ("skill", "SKILL.md", release_sync_skill_content),
    )
    writes: list[tuple[str, str]] = []
    changed: list[str] = []
    for source_name, relative, builder in builders:
        if sources[source_name] == truth:
            continue
        raw = (target / relative).read_text(encoding="utf-8")
        content = builder(raw, truth)
        if content != raw:
            writes.append((relative, content))
            changed.append(relative)
    if not writes:
        payload["status"] = "already_consistent"
        payload["changed"] = []
        return 0, payload
    apply_release_sync_writes(target, writes)
    payload["status"] = "synced"
    payload["version"] = truth
    payload["changed"] = changed
    return 0, payload


def command_self_test(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = safe_target(args.target)
    rules = rules_root_for(target)
    parser_help = build_parser().format_help()
    active_rules, rule_errors = load_active_rules(target, GATE_ORDER, " ".join(GATE_ORDER), match_all=True)
    config = project_config(target)
    version_truth = (
        config.get("version") == VERSION and config.get("schema_version") == CONFIG_SCHEMA
        if config
        else all(value == VERSION for value in read_version_sources(SCRIPT_ROOT).values())
    )
    bridge_contract = host_dispatch_contract(target, "bg-20000101T000000-0000000000", "background_goal")
    checks = {
        "script_version": version_truth,
        "command_parser": all(name in parser_help for name in ("run", "context", "progress", "verify", "task", "ledger", "knowledge", "background", "project", "release", "self-test")),
        "rules_root": rules.is_dir(),
        "active_rules_valid": bool(active_rules) and not rule_errors,
        "independent_runtime_name": runtime_root(target).parent.name in {"docs-harness", ".docs-harness"},
        "v2_task_contract": TASK_SCHEMA == "docs-harness/task-package/v2" and COMPILED_SCHEMA == "docs-harness/compiled-task/v2",
        "v2_evidence_contract": EVIDENCE_RECEIPT_SCHEMA == "docs-harness/evidence-receipt/v2" and RECEIPT_SCHEMA == "docs-harness/context-receipt/v2",
        "background_goal_host_bridge": (
            BACKGROUND_ARTIFACT_REVISION == 2
            and bridge_contract.get("required_preparation") == "background_goal_artifacts"
            and bridge_contract.get("control_plane_write_policy") == "harness_cli_only"
            and bridge_contract.get("dispatch_sequence") == ["prepare", "create_host_goal", "dispatched", "running"]
            and isinstance(bridge_contract.get("progress_argv_template"), list)
        ),
        "background_control_plane_scope_guard": (
            scope_claims_background_control_plane(target, [".docs-harness/**"])
            and not scope_claims_background_control_plane(target, ["docs/**"])
        ),
        "document_route_contract": (
            DOCUMENT_ROUTE_SCHEMA == "docs-harness/document-routes/v1"
            and set(DOCUMENT_ROUTE_KINDS) == {
                "architecture", "changelog", "todo", "adr_root", "reviews_root"
            }
            and callable(resolve_document_routes)
        ),
        "completion_manifest_contract": completion_manifest_valid(
            build_completion_manifest(
                task_intent="query",
                mutation_profile="read_only",
                gates=[],
                evidence_types=["source_trace"],
                verification_commands=[],
            )
        ),
    }
    passed = all(checks.values())
    return (0 if passed else 1), {"version": VERSION, "status": "passed" if passed else "failed", "checks": checks, "rules": [item["rule_id"] for item in active_rules], "rule_errors": rule_errors, "empty_rules_legal": False}


def add_common_target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", default=".")
    parser.add_argument("--json", action="store_true", help="输出 JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness", description=f"Docs Harness v{VERSION} 独立任务控制器")
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="任务路由、任务包编译与执行准入")
    add_common_target(run)
    run.add_argument("--task")
    run.add_argument("--task-id", help="继续已有任务并完成方案、授权或重新准入")
    run.add_argument(
        "--new-task",
        action="store_true",
        help="跳过活动任务幂等复用，强制创建独立任务",
    )
    run.add_argument(
        "--facts",
        metavar="FACTS_FILE",
        help="结构化任务事实 JSON 文件路径，不接受内联内容",
    )
    run.add_argument(
        "--plan",
        metavar="PLAN_FILE",
        help="正式方案 Markdown 或 JSON 文件路径，不接受内联内容",
    )
    run.add_argument(
        "--authorization",
        metavar="AUTHORIZATION_FILE",
        help="结构化授权 JSON 文件路径，不接受内联内容",
    )
    run.add_argument("--scope", action="append", help="项目内允许范围，可重复")
    run.add_argument("--feature", action="append", help="显式选择功能 ID，可重复")
    run.add_argument("--action", action="append", help="允许动作，可重复")
    run.add_argument("--success", action="append", help="成功标准，可重复")

    context = commands.add_parser("context", help="按阶段加载精确上下文并写回执")
    add_common_target(context)
    context.add_argument("--task-id", required=True)
    context.add_argument("--stage", choices=("plan", "action", "acceptance"), default="action")
    context.add_argument("--work-package")

    progress = commands.add_parser("progress", help="推进 extended 工作包状态")
    progress.add_argument("action", choices=("status", "begin", "submit", "block"))
    add_common_target(progress)
    progress.add_argument("--task-id", required=True)
    progress.add_argument("--work-package")
    progress.add_argument(
        "--evidence",
        metavar="EVIDENCE_FILE",
        help="结构化证据 JSON 文件路径，不接受内联内容",
    )
    progress.add_argument("--reason")
    progress.add_argument("--scope-changed", action="store_true")
    progress.add_argument("--handoff", action="store_true")

    verify = commands.add_parser("verify", help="同源验收、补证或重新准入")
    add_common_target(verify)
    verify.add_argument("--task-id", required=True)
    verify.add_argument(
        "--evidence",
        action="append",
        metavar="EVIDENCE_FILE",
        help="结构化证据 JSON 文件路径，不接受内联内容，可重复",
    )

    task = commands.add_parser("task", help="查询、取消、归档、清理任务或显式迁移 v1 在途任务")
    task.add_argument("action", choices=("status", "migrate", "cancel", "archive", "list", "prune", "adopt", "changes-preview"))
    add_common_target(task)
    task.add_argument("--task-id")
    task.add_argument("--apply", action="store_true", help="显式应用迁移、取消、归档或清理；缺省仅预览")
    task.add_argument("--reason-code", help="受控取消或归档原因码")
    task.add_argument("--older-than", type=int, help="prune 候选的最小天数")
    task.add_argument("--dry-run", action="store_true", help="显式声明仅生成 prune 候选")
    task.add_argument("--include-archived", action="store_true", help="list 包含已归档 v1 对象")
    task.add_argument("--outcome", help="adopt 时的外部完成结果摘要")
    task.add_argument("--external-evidence", metavar="EVIDENCE_FILE", help="adopt 时的外部证据文件路径")
    task.add_argument("--bypass-reason", help="adopt 时的绕过原因")

    ledger = commands.add_parser("ledger", help="人工触发的个人本地质量账本")
    ledger.add_argument("action", choices=("add", "read"))
    add_common_target(ledger)
    ledger.add_argument("--task-id", help="要记录或精确读取的 Docs Harness 任务编号")
    ledger.add_argument(
        "--review",
        metavar="REVIEW_FILE",
        help="脱敏质量复盘 JSON 文件路径，不接受内联内容",
    )
    ledger.add_argument("--query", help="按任务摘要、范围、Gate、价值、经验或风险进行文本检索")
    ledger.add_argument("--limit", type=int, default=5, help="读取条数，范围 1-20，默认 5")

    knowledge = commands.add_parser("knowledge", help="功能知识库审查、评估与兼容后台入口")
    knowledge.add_argument("action", choices=("status", "estimate", "audit", "bootstrap", "update", "verify", "job-status", "dispatch", "retry"))
    add_common_target(knowledge)
    knowledge.add_argument("--assessment", metavar="ASSESSMENT_FILE", help="结构化知识审查报告")
    knowledge.add_argument("--consent", metavar="CONSENT_FILE", help="已有 docs 的知识更新同意回执")
    knowledge.add_argument("--job-id", help="知识维护 Job ID")
    knowledge.add_argument("--job-status", help="宿主报告的 Job 调度状态")
    knowledge.add_argument("--result", choices=("updated", "no_change"), default="updated")

    background = commands.add_parser("background", help="统一后台文档治理 Job 控制器")
    background.add_argument("action", choices=("estimate", "list", "status", "prepare", "progress", "dispatch", "verify", "retry", "prune"))
    add_common_target(background)
    background.add_argument("--candidate", metavar="CANDIDATE_FILE", help="后台候选项 JSON 文件路径，不接受内联内容")
    background.add_argument("--job-id", help="统一后台 Job ID")
    background.add_argument("--job-status", help="宿主报告的 Job 状态")
    background.add_argument("--work-package-id", help="冻结方案中的工作包 ID")
    background.add_argument("--work-package-status", choices=("in_progress", "completed", "blocked"), help="工作包目标状态")
    background.add_argument("--reason-code", help="有界、受控的工作包原因码")
    background.add_argument("--repair", action="store_true", help="显式归档并修复无效 Goal 工件")
    background.add_argument(
        "--prepare-and-run",
        action="store_true",
        help="声明制合并：单命令顺序执行 prepare→dispatched→running（仅 change_scoped 估算且分数 <60 的复杂路线，需同时给出 --job-status running）",
    )
    background.add_argument(
        "--all",
        dest="all_packages",
        choices=("completed",),
        help="声明制批量推进冻结 Plan 全部工作包到 completed；任一非法前置态整体拒绝不部分提交",
    )
    background.add_argument("--assessment", metavar="ASSESSMENT_FILE", help="知识或重大发现验收报告文件")
    background.add_argument("--result", choices=("updated", "no_change", "completed_with_finding"), default="updated")
    background.add_argument("--older-than", type=int, help="prune 候选的最小天数")
    background.add_argument("--apply", action="store_true", help="显式应用 prune；缺省仅 dry-run")
    background.add_argument("--dry-run", action="store_true", help="显式声明仅生成 prune 候选")

    project = commands.add_parser("project", help="项目安装生命周期")
    project.add_argument("action", choices=("init", "upgrade", "uninstall", "check", "diff", "rollback-check"))
    add_common_target(project)
    project.add_argument("--apply", action="store_true")
    project.add_argument("--purge-runtime", action="store_true")

    authorization = commands.add_parser("authorization", help="授权文件模板生成与管理")
    authorization.add_argument("action", choices=("template",), help="生成授权文件模板")
    add_common_target(authorization)
    authorization.add_argument("--task-id", help="要生成授权模板的任务编号")
    authorization.add_argument("--output", metavar="OUTPUT_FILE", help="模板输出文件路径；缺省输出到 stdout")

    release = commands.add_parser("release", help="发版版本真源一致性检查与原子同步")
    release.add_argument("action", choices=("sync",), nargs="?", default="sync")
    add_common_target(release)
    release.add_argument(
        "--apply",
        action="store_true",
        help="以 scripts/harness.py 的 VERSION 常量为唯一真源，原子写入 VERSION 文件、package.json、SKILL.md",
    )
    release.add_argument(
        "--target-version",
        help="显式确认目标版本；与 VERSION 常量不一致时失败关闭（release_version_conflict）",
    )

    self_test = commands.add_parser("self-test", help="运行内置合同自检")
    add_common_target(self_test)
    return parser


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value}")


def enrich_next_step_response(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    if (
        "next_action" not in payload
        or "next_command_argv" in payload
        or not payload.get("task_id")
        or not hasattr(args, "target")
    ):
        return payload
    target = safe_target(args.target)
    state, package, _, _ = load_state(target, str(payload["task_id"]))
    original_action = str(payload["next_action"])
    normalized_action = original_action
    work_package = None
    if original_action.startswith("load_context:"):
        normalized_action = "load_work_package_context"
        work_package = original_action.split(":", 1)[1]
    elif original_action.startswith("begin:"):
        normalized_action = "begin_work_package"
        work_package = original_action.split(":", 1)[1]
    step = next_step_payload(
        target,
        state,
        package,
        normalized_action,
        reason_code=str(payload.get("reason_code") or original_action),
        work_package=work_package,
    )
    step["next_action"] = original_action
    payload.update(step)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            code, payload = command_run(args)
        elif args.command == "context":
            code, payload = command_context(args)
        elif args.command == "progress":
            if args.action != "status" and not args.work_package:
                raise HarnessError("begin/submit/block 必须提供 --work-package", code="missing_work_package")
            if args.action == "submit" and not args.evidence:
                raise HarnessError("submit 必须提供 --evidence", code="missing_evidence")
            code, payload = command_progress(args)
        elif args.command == "verify":
            code, payload = command_verify(args)
        elif args.command == "task":
            code, payload = command_task(args)
        elif args.command == "ledger":
            code, payload = command_ledger(args)
        elif args.command == "knowledge":
            code, payload = command_knowledge(args)
        elif args.command == "background":
            code, payload = command_background(args)
        elif args.command == "project":
            code, payload = command_project(args)
        elif args.command == "authorization":
            code, payload = command_authorization(args)
        elif args.command == "release":
            code, payload = command_release_sync(args)
        else:
            code, payload = command_self_test(args)
        payload = enrich_next_step_response(args, payload)
        emit(payload, args.json)
        return code
    except HarnessError as exc:
        error_payload: dict[str, Any] = {"status": "error", "code": exc.code, "message": str(exc)}
        if exc.suggested_fix is not None:
            error_payload["suggested_fix"] = exc.suggested_fix
        if exc.missing_items is not None:
            error_payload["missing_items"] = exc.missing_items
        if exc.actual_vs_expected is not None:
            error_payload["actual_vs_expected"] = exc.actual_vs_expected
        if exc.extra_payload:
            error_payload.update(exc.extra_payload)
        emit(error_payload, getattr(args, "json", False))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
