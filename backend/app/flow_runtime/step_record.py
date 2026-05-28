"""流程运行 steps 审计条目（供调试面板与 LangGraph compiler 使用）。"""

from __future__ import annotations

from typing import Any

_MEDIA_KINDS = frozenset({"image", "video"})
_PREVIEW_MAX_LEN = 200


def _build_media_artifacts(
    kind: str,
    attachment_id: Any,
    result: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    artifact: dict[str, Any] = {
        "kind": kind,
        "attachment_id": str(attachment_id),
        "mime_type": result.get("mime_type"),
    }
    if kind != "image":
        return artifact, None
    extra_ids = result.get("attachment_ids")
    if not isinstance(extra_ids, list) or len(extra_ids) <= 1:
        return artifact, None
    mime = result.get("mime_type")
    extras = [
        {"kind": "image", "attachment_id": str(aid), "mime_type": mime}
        for aid in extra_ids
        if aid
    ]
    return artifact, extras or None


def build_flow_node_step(
    *,
    node_id: str,
    node_type: str,
    result: Any,
    engine: str = "langgraph",
) -> dict[str, Any]:
    """单节点执行结果 → step dict；生成物附带 ``artifact`` 供前端预览。"""
    step: dict[str, Any] = {
        "type": "flow_node",
        "engine": engine,
        "node_id": node_id,
        "node_type": node_type,
        "output_preview": str(result)[:_PREVIEW_MAX_LEN],
    }
    if not isinstance(result, dict):
        return step

    if result.get("child_flow_id"):
        step["child_flow_id"] = str(result["child_flow_id"])
        child_steps = result.get("child_steps")
        if isinstance(child_steps, list):
            step["child_steps"] = child_steps
        count = result.get("child_step_count")
        if isinstance(count, int):
            step["child_step_count"] = count

    job_id = result.get("generative_job_id")
    if job_id:
        step["generative_job"] = {
            "job_id": str(job_id),
            "kind": result.get("kind") or "video",
            "status": result.get("status") or "pending",
        }

    kind = result.get("kind")
    att = result.get("attachment_id")
    if kind in _MEDIA_KINDS and att:
        artifact, extras = _build_media_artifacts(str(kind), att, result)
        step["artifact"] = artifact
        if extras:
            step["artifacts"] = extras
    return step
