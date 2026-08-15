"""关联 Plan、逐条记录证据并可重验的 Acceptance 资产生命周期。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from managed_assets import (
    AssetError,
    AssetSpec,
    archive_asset,
    asset_pair,
    check_assets,
    load_asset,
    output_pair,
    rewrite_links,
    seal_asset,
    write_asset,
)
from plan_governance import (
    PLAN_SCHEMAS,
    PlanGovernanceError,
    add_acceptance_ref,
    remove_acceptance_ref,
)


ACCEPTANCE_TARGET_INPUT_SCHEMA = "docs-harness/acceptance-target-input/v1"
ACCEPTANCE_ASSET_SCHEMA = "docs-harness/acceptance-asset/v1"
ACCEPTANCE_SETTLE_STATUSES = ("passed", "failed", "superseded")
ACCEPTANCE_TYPES = {"contract_check", "behavior_acceptance", "user_acceptance"}
ACCEPTANCE_LAYERS = {
    "L1": "source_contract",
    "L2": "focused_behavior",
    "L3": "local_runtime",
    "L4": "package_or_install",
    "L5": "user_visible",
}
ACCEPTANCE_EVIDENCE_LAYERS = {
    "focused_test": "L2",
    "repository_full_test": "L2",
    "local_runtime": "L3",
    "package_or_install": "L4",
    "real_device": "L5",
}
CRITERION_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
STATUS_LABELS = {
    "pending": "有效（待验收）",
    "passed": "已验收-仅追溯",
    "failed": "有效（验收失败）",
    "superseded": "已废弃-被替代",
}

ACCEPTANCE_SPEC = AssetSpec(
    kind="acceptance",
    root="docs/acceptance",
    heading="验收资产",
    index_begin="<!-- docs-harness:acceptance-index:start -->",
    index_end="<!-- docs-harness:acceptance-index:end -->",
    marker="<!-- docs-harness:acceptance-document/v1 -->",
    schema=ACCEPTANCE_ASSET_SCHEMA,
    readme="""# 验收资产

本目录保存复杂任务的验收目标、逐条标准、证据层级和结果。JSON 是可审计真源，
Markdown 是可读投影，`docs/INDEX.md` 提供状态入口。

合同、测试、运行、安装与用户可见验收保持分层；用户验收通过必须来自明确的用户确认。
被取代的验收资产移入 `archive/`。
""",
)


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise AssetError(f"{label} 必须是单行非空字符串", "acceptance_target_invalid")
    return value.strip()


def _symbols(value: Any) -> list[str]:
    if not isinstance(value, list) or not 2 <= len(value) <= 4:
        raise AssetError("key_symbols 必须包含 2-4 项", "acceptance_target_invalid")
    symbols = [_string(item, "key_symbols 项") for item in value]
    if len(symbols) != len(set(symbols)) or any("`" in item for item in symbols):
        raise AssetError("key_symbols 必须唯一且不能包含反引号", "acceptance_target_invalid")
    return symbols


def _project_file(
    target: Path,
    raw: str,
    schema: str | Sequence[str] | None = None,
) -> Path:
    relative = raw.rsplit(":", 1)[0] if re.search(r":\d+$", raw) else raw
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise AssetError("引用必须是项目内相对路径", "acceptance_ref_invalid")
    resolved = (target / path).resolve()
    try:
        resolved.relative_to(target.resolve())
    except ValueError as exc:
        raise AssetError("引用越出项目目录", "acceptance_ref_invalid") from exc
    if not resolved.is_file() or resolved.is_symlink():
        parts = path.parts
        if len(parts) == 3 and parts[0] == "docs" and parts[1] in {"plans", "knowledge"}:
            archived = (target / parts[0] / parts[1] / "archive" / parts[2]).resolve()
            if archived.is_file() and not archived.is_symlink():
                resolved = archived
            else:
                raise AssetError(f"引用不存在：{raw}", "acceptance_ref_missing")
        else:
            raise AssetError(f"引用不存在：{raw}", "acceptance_ref_missing")
    if schema:
        try:
            value = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AssetError(f"引用无法读取：{raw}", "acceptance_ref_invalid") from exc
        allowed_schemas = {schema} if isinstance(schema, str) else set(schema)
        if not isinstance(value, dict) or value.get("schema_version") not in allowed_schemas:
            raise AssetError(f"引用 Schema 无效：{raw}", "acceptance_ref_invalid")
    return resolved


def _criterion(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssetError("criteria 每项必须是对象", "acceptance_target_invalid")
    criterion_id = _string(value.get("id"), "criterion id")
    if not CRITERION_ID_PATTERN.fullmatch(criterion_id):
        raise AssetError("criterion id 格式无效", "acceptance_target_invalid")
    acceptance_type = value.get("acceptance_type")
    layer = value.get("layer")
    evidence_layer = value.get("evidence_layer")
    if acceptance_type not in ACCEPTANCE_TYPES or layer not in ACCEPTANCE_LAYERS:
        raise AssetError("criterion 类型或层级无效", "acceptance_target_invalid")
    if acceptance_type == "contract_check" and (layer != "L1" or evidence_layer is not None):
        raise AssetError("合同检查必须是 L1 且无 evidence_layer", "acceptance_target_invalid")
    if acceptance_type == "behavior_acceptance" and ACCEPTANCE_EVIDENCE_LAYERS.get(evidence_layer) != layer:
        raise AssetError("行为验收 evidence_layer 与 layer 不匹配", "acceptance_target_invalid")
    if acceptance_type == "user_acceptance" and (layer != "L5" or evidence_layer is not None):
        raise AssetError("用户验收必须是 L5 且无 evidence_layer", "acceptance_target_invalid")
    return {
        "id": criterion_id,
        "title": _string(value.get("title"), "criterion title"),
        "acceptance_type": acceptance_type,
        "layer": layer,
        "evidence_layer": evidence_layer,
        "status": "pending",
        "records": [],
    }


def validate_input(target: Path, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != ACCEPTANCE_TARGET_INPUT_SCHEMA:
        raise AssetError("Acceptance 目标输入 Schema 无效", "acceptance_target_invalid")
    allowed = {"schema_version", "title", "key_symbols", "objective", "plan_ref", "knowledge_refs", "criteria"}
    if set(value) - allowed:
        raise AssetError("Acceptance 目标包含未注册字段", "acceptance_target_invalid")
    plan_ref = value.get("plan_ref")
    if plan_ref is not None:
        plan_ref = _string(plan_ref, "plan_ref")
        _project_file(target, plan_ref, PLAN_SCHEMAS)
    knowledge_refs = value.get("knowledge_refs", [])
    if not isinstance(knowledge_refs, list):
        raise AssetError("knowledge_refs 必须是数组", "acceptance_target_invalid")
    knowledge_refs = [_string(item, "knowledge_ref") for item in knowledge_refs]
    for ref in knowledge_refs:
        _project_file(target, ref, "docs-harness/knowledge-asset/v1")
    raw_criteria = value.get("criteria")
    if not isinstance(raw_criteria, list) or not raw_criteria:
        raise AssetError("criteria 必须是非空数组", "acceptance_target_invalid")
    criteria = [_criterion(item) for item in raw_criteria]
    ids = [item["id"] for item in criteria]
    if len(ids) != len(set(ids)):
        raise AssetError("criterion id 不得重复", "acceptance_target_invalid")
    return {
        "title": _string(value.get("title"), "title"),
        "key_symbols": _symbols(value.get("key_symbols")),
        "objective": _string(value.get("objective"), "objective"),
        "plan_ref": plan_ref,
        "knowledge_refs": knowledge_refs,
        "criteria": criteria,
    }


def validate_asset(value: dict[str, Any]) -> None:
    if value.get("status") not in STATUS_LABELS:
        raise AssetError("Acceptance 状态无效", "acceptance_asset_invalid")
    if not isinstance(value.get("revision"), int) or value["revision"] < 1:
        raise AssetError("Acceptance revision 无效", "acceptance_asset_invalid")
    if not isinstance(value.get("criteria"), list) or not value["criteria"]:
        raise AssetError("Acceptance criteria 无效", "acceptance_asset_invalid")
    ids: list[str] = []
    for criterion in value["criteria"]:
        if not isinstance(criterion, dict) or not CRITERION_ID_PATTERN.fullmatch(str(criterion.get("id", ""))):
            raise AssetError("Acceptance criterion 结构无效", "acceptance_asset_invalid")
        if criterion.get("status") not in {"pending", "passed", "failed"}:
            raise AssetError("Acceptance criterion 状态无效", "acceptance_asset_invalid")
        if not isinstance(criterion.get("records"), list):
            raise AssetError("Acceptance records 无效", "acceptance_asset_invalid")
        ids.append(criterion["id"])
    if len(ids) != len(set(ids)):
        raise AssetError("Acceptance criterion id 重复", "acceptance_asset_invalid")
    if value["status"] != "superseded" and value["status"] != _aggregate(value["criteria"]):
        raise AssetError("Acceptance 总体状态与 criteria 不一致", "acceptance_asset_invalid")


def _criterion_markdown(criterion: dict[str, Any]) -> str:
    records = criterion["records"]
    latest = records[-1] if records else None
    evidence = "、".join(f"`{ref}`" for ref in latest.get("evidence_refs", [])) if latest else "尚无"
    return (
        f"### `{criterion['id']}` {criterion['title']}\n\n"
        f"- 状态：{criterion['status']}\n- 类型：{criterion['acceptance_type']}\n"
        f"- 层级：{criterion['layer']}\n- 证据：{evidence}"
    )


def render_markdown(asset: dict[str, Any]) -> str:
    symbols = "、".join(f"`{item}`" for item in asset["key_symbols"])
    criteria = "\n\n".join(_criterion_markdown(item) for item in asset["criteria"])
    refs = []
    if asset.get("plan_ref"):
        refs.append(f"- 关联方案：`{asset['plan_ref']}`")
    if asset.get("knowledge_refs"):
        refs.append("- 关联知识：" + "、".join(f"`{item}`" for item in asset["knowledge_refs"]))
    if asset.get("replacement"):
        refs.append(f"- 替代资产：`{asset['replacement']}`")
    return (
        f"> 状态：{STATUS_LABELS[asset['status']]}\n{ACCEPTANCE_SPEC.marker}\n\n# {asset['title']}\n\n"
        f"- 修订：{asset['revision']}\n- 关键符号：{symbols}\n"
        f"- 资产指纹：`{asset['asset_fingerprint']}`\n" + "\n".join(refs) +
        f"\n\n## 验收目标\n\n{asset['objective']}\n\n## 验收标准\n\n{criteria}\n"
    )


def _change_plan_backref(
    target: Path,
    plan_ref: str,
    acceptance_ref: str,
    *,
    add: bool,
) -> bool:
    try:
        action = add_acceptance_ref if add else remove_acceptance_ref
        return action(target, plan_ref, acceptance_ref)
    except PlanGovernanceError as exc:
        raise AssetError(str(exc), "acceptance_plan_ref_invalid") from exc


def create(target: Path, value: Any, raw_output: str, now: str) -> dict[str, Any]:
    content = validate_input(target, value)
    output, document = output_pair(target, raw_output, ACCEPTANCE_SPEC)
    if output.exists() or document.exists():
        raise AssetError("Acceptance 输出已存在", "acceptance_already_exists")
    asset = seal_asset({
        "schema_version": ACCEPTANCE_ASSET_SCHEMA,
        **content,
        "status": "pending",
        "revision": 1,
        "revision_history": [],
        "created_at": now,
        "updated_at": now,
        "settled_at": None,
    })
    linked = False
    if content.get("plan_ref"):
        linked = _change_plan_backref(
            target, content["plan_ref"], raw_output, add=True
        )
    try:
        write_asset(
            target, ACCEPTANCE_SPEC, output, document, asset,
            render_markdown(asset), STATUS_LABELS["pending"],
        )
    except Exception:
        if linked:
            _change_plan_backref(target, content["plan_ref"], raw_output, add=False)
        raise
    return {"status": "created", "acceptance_ref": raw_output, "document_ref": raw_output[:-5] + ".md", "criteria": len(asset["criteria"])}


def _aggregate(criteria: Sequence[dict[str, Any]]) -> str:
    statuses = {item["status"] for item in criteria}
    if "failed" in statuses:
        return "failed"
    if statuses == {"passed"}:
        return "passed"
    return "pending"


def _next_revision(current: dict[str, Any], now: str) -> tuple[int, list[dict[str, Any]]]:
    history = list(current.get("revision_history", []))
    history.append({"revision": current["revision"], "asset_fingerprint": current["asset_fingerprint"], "updated_at": current["updated_at"]})
    return current["revision"] + 1, history


def record(target: Path, raw_asset: str, criterion_id: str, record_value: dict[str, Any], now: str, reaccept: bool) -> dict[str, Any]:
    source, document, archived = asset_pair(target, raw_asset, ACCEPTANCE_SPEC)
    if archived:
        raise AssetError("归档 Acceptance 不可记录", "acceptance_archived")
    current = load_asset(source, ACCEPTANCE_SPEC)
    validate_asset(current)
    if current.get("settled_at") and not reaccept:
        raise AssetError("已结项 Acceptance 必须显式 --reaccept", "acceptance_reaccept_required")
    if reaccept and current["status"] not in {"failed", "passed"}:
        raise AssetError("只有已通过或失败的 Acceptance 可重验", "acceptance_reaccept_invalid")
    criterion = next((item for item in current["criteria"] if item["id"] == criterion_id), None)
    if criterion is None:
        raise AssetError("criterion_id 不存在", "acceptance_criterion_missing")
    for key in ("acceptance_type", "layer", "evidence_layer"):
        if criterion[key] != record_value.get(key):
            raise AssetError(f"验收记录与 criterion 的 {key} 不一致", "acceptance_record_mismatch")
    criterion["records"].append(record_value)
    criterion["status"] = "passed" if record_value["status"] == "passed" else "failed" if record_value["status"] == "failed" else "pending"
    revision, history = _next_revision(current, now)
    current.update({"status": _aggregate(current["criteria"]), "revision": revision, "revision_history": history, "updated_at": now, "settled_at": None})
    asset = seal_asset(current)
    write_asset(target, ACCEPTANCE_SPEC, source, document, asset, render_markdown(asset), STATUS_LABELS[asset["status"]])
    return {"status": asset["status"], "acceptance_ref": raw_asset, "criterion_id": criterion_id, "revision": revision}


def settle(target: Path, raw_asset: str, status: str, replacement: str | None, now: str, markdown_files: Sequence[Path]) -> dict[str, Any]:
    if status not in ACCEPTANCE_SETTLE_STATUSES:
        raise AssetError("Acceptance settle 状态无效", "acceptance_settle_invalid")
    source, document, archived = asset_pair(target, raw_asset, ACCEPTANCE_SPEC)
    if archived:
        raise AssetError("Acceptance 已归档", "acceptance_archived")
    current = load_asset(source, ACCEPTANCE_SPEC)
    validate_asset(current)
    if status in {"passed", "failed"} and current["status"] != status:
        raise AssetError("结项状态与逐条验收聚合状态不一致", "acceptance_settle_mismatch")
    if status == "superseded" and not replacement:
        raise AssetError("superseded 必须提供 replacement", "acceptance_replacement_required")
    if replacement:
        replacement_source, _, replacement_archived = asset_pair(target, replacement, ACCEPTANCE_SPEC)
        if replacement_source == source:
            raise AssetError("replacement 不能指向自身", "acceptance_replacement_invalid")
        if replacement_archived:
            raise AssetError("replacement 必须是活跃 Acceptance", "acceptance_replacement_invalid")
    revision, history = _next_revision(current, now)
    current.update({"status": status, "replacement": replacement, "revision": revision, "revision_history": history, "updated_at": now, "settled_at": now})
    asset = seal_asset(current)
    write_asset(target, ACCEPTANCE_SPEC, source, document, asset, render_markdown(asset), STATUS_LABELS[status])
    if status != "superseded":
        return {"status": status, "acceptance_ref": raw_asset, "revision": revision}
    archived_source, archived_document = archive_asset(target, ACCEPTANCE_SPEC, source, document)
    rewritten = rewrite_links(target, ACCEPTANCE_SPEC, source.stem, markdown_files)
    if current.get("plan_ref"):
        _change_plan_backref(target, current["plan_ref"], raw_asset, add=False)
    return {"status": status, "acceptance_ref": archived_source.relative_to(target).as_posix(), "document_ref": archived_document.relative_to(target).as_posix(), "rewritten_links": rewritten}


def _validate_live_refs(target: Path, asset: dict[str, Any]) -> None:
    if asset.get("plan_ref"):
        _project_file(target, asset["plan_ref"], PLAN_SCHEMAS)
    for ref in asset.get("knowledge_refs", []):
        _project_file(target, ref, "docs-harness/knowledge-asset/v1")
    for criterion in asset["criteria"]:
        for record_value in criterion["records"]:
            if (
                criterion["acceptance_type"] == "user_acceptance"
                and record_value["status"] == "passed"
                and record_value.get("user_confirmation", {}).get("confirmed_by") != "user"
            ):
                raise AssetError("用户验收记录缺少明确确认", "acceptance_user_confirmation_missing")
            if record_value["status"] == "passed":
                for ref in record_value.get("evidence_refs", []):
                    _project_file(target, ref)


def check(target: Path) -> dict[str, Any]:
    def validate(value: dict[str, Any]) -> None:
        validate_asset(value)
        _validate_live_refs(target, value)

    return check_assets(target, ACCEPTANCE_SPEC, validate)
