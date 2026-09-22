"""生成任务重试规则。"""

from miles_core.models.model.generative_job import GenerativeJobStatus
from miles_portal.tenant.generative.schemas.job import GenerativeJobOut


def test_retryable_statuses():
    retryable = {GenerativeJobStatus.FAILED, GenerativeJobStatus.CANCELLED}
    assert GenerativeJobStatus.SUCCESS not in retryable
    assert GenerativeJobStatus.PENDING not in retryable


def test_generative_job_out_celery_task_record_field():
    assert "celery_task_record_id" in GenerativeJobOut.model_fields
