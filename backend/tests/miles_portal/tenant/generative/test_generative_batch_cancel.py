"""生成任务批量取消请求体：``job_ids`` 原样保留（P1 能力冒烟）。"""

from uuid import uuid4

from miles_portal.tenant.generative.schemas.job import GenerativeJobBatchCancelBody


def test_generative_batch_cancel_body():
    body = GenerativeJobBatchCancelBody(job_ids=[uuid4()])
    assert len(body.job_ids) == 1
