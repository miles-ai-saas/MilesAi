"""chat_artifact_sync 单元测试。"""

from uuid import uuid4

from miles_core.models.model.generative_job import GenerativeJob, GenerativeJobStatus
from miles_portal.tenant.agents.services.chat_artifact_sync import artifacts_payload_from_job


def test_artifacts_payload_from_success_image_job():
    job = GenerativeJob(
        id=uuid4(),
        tenant_id=uuid4(),
        kind="image",
        status=GenerativeJobStatus.SUCCESS,
        source="agent_tool",
        params={"prompt": "cat"},
        result={
            "kind": "image",
            "attachment_ids": ["a1", "a2"],
            "media_asset_ids": ["m1", "m2"],
            "mime_type": "image/png",
        },
        progress_percent=100,
        progress_message="已完成",
    )
    arts = artifacts_payload_from_job(job)
    assert len(arts) == 2
    assert arts[0]["status"] == "success"
    assert arts[0]["job_id"] == str(job.id)
    assert arts[0]["attachment_id"] == "a1"
    assert arts[1]["attachment_id"] == "a2"


def test_artifacts_payload_from_pending_job():
    job = GenerativeJob(
        id=uuid4(),
        tenant_id=uuid4(),
        kind="image",
        status=GenerativeJobStatus.PENDING,
        source="agent_tool",
        params={},
    )
    arts = artifacts_payload_from_job(job)
    assert len(arts) == 1
    assert arts[0]["status"] == "pending"
