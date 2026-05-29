"""FlowRunRequest schema."""

from uuid import uuid4

from app.common.schemas.media import MediaRefIn
from app.tenant.flows.schemas.flow import FlowRunRequest


def test_flow_run_request_kb_ids_default():
    body = FlowRunRequest(inputs={"query": "hi"})
    assert body.kb_ids == []


def test_flow_run_request_kb_ids():
    kid = uuid4()
    body = FlowRunRequest(inputs={"query": "hi"}, kb_ids=[kid])
    assert body.kb_ids == [kid]


def test_flow_run_request_with_media():
    body = FlowRunRequest(
        inputs={"query": "看图"},
        media=[MediaRefIn(attachment_id=uuid4())],
    )
    assert len(body.media) == 1
