"""任务批量取消请求体：``task_ids`` 原样保留（P1 能力冒烟）。"""

from miles_portal.tenant.tasks.schemas.task import TaskBatchCancelBody


def test_task_batch_cancel_body():
    body = TaskBatchCancelBody(task_ids=["a", "b"])
    assert len(body.task_ids) == 2
