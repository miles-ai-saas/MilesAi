"""P1 能力冒烟测试。"""

from miles_portal.tenant.tasks.schemas.task import TaskBatchCancelBody
from miles_portal.tenant.generative.schemas.job import GenerativeJobBatchCancelBody
from uuid import uuid4


def test_task_batch_cancel_body():
    body = TaskBatchCancelBody(task_ids=["a", "b"])
    assert len(body.task_ids) == 2


def test_generative_batch_cancel_body():
    body = GenerativeJobBatchCancelBody(job_ids=[uuid4()])
    assert len(body.job_ids) == 1
