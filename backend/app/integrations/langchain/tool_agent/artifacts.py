"""generate_* 工具输出 → ChatArtifact。"""
from __future__ import annotations

from uuid import UUID

from app.tenant.agents.schemas.agent import ChatArtifact


def artifacts_from_tool_output(output: dict) -> list[ChatArtifact]:
    """将 invoke 返回的 generate_* 字典转为 ChatArtifact（供前端预览）。"""
    if not isinstance(output, dict):
        return []
    kind = str(output.get("kind") or "image")
    status = output.get("status")
    job_id = output.get("generative_job_id") or output.get("job_id")
    job_id_str = str(job_id) if job_id else None

    if status == "pending" and job_id_str:
        return [
            ChatArtifact(
                kind=kind if kind in ("image", "video") else "video",
                status="pending",
                job_id=job_id_str,
                caption=output.get("message"),
                progress_message=output.get("progress_message") or output.get("message"),
            )
        ]

    if status == "failed":
        return [
            ChatArtifact(
                kind=kind if kind in ("image", "video") else "image",
                status="failed",
                job_id=job_id_str,
                error_message=str(output.get("error_message") or output.get("message") or "生成失败"),
                caption=output.get("message"),
            )
        ]

    def _uuid_or_none(v) -> UUID | None:
        if v is None or v == "":
            return None
        return UUID(str(v))

    if kind == "image":
        ids = output.get("attachment_ids") or []
        if not ids and output.get("attachment_id"):
            ids = [output["attachment_id"]]
        mids = output.get("media_asset_ids") or []
        if not mids and output.get("media_asset_id"):
            mids = [output["media_asset_id"]]
        mime = output.get("mime_type")
        return [
            ChatArtifact(
                attachment_id=_uuid_or_none(aid),
                kind="image",
                mime_type=mime,
                caption=output.get("message"),
                status="success",
                job_id=job_id_str,
                media_asset_id=_uuid_or_none(mids[i] if i < len(mids) else (mids[0] if mids else None)),
            )
            for i, aid in enumerate(ids)
            if aid
        ]
    if kind == "video" and output.get("attachment_id"):
        return [
            ChatArtifact(
                attachment_id=UUID(str(output["attachment_id"])),
                kind="video",
                mime_type=output.get("mime_type") or "video/mp4",
                caption=output.get("message"),
                status="success",
                job_id=job_id_str,
                media_asset_id=_uuid_or_none(output.get("media_asset_id")),
            )
        ]
    return []
