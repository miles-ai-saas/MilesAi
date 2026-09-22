"""异步生成任务模型与策略。"""

from miles_core.models.model.generative_job import GenerativeJobStatus


def test_generative_job_status_values():
    assert GenerativeJobStatus.PENDING.value == "pending"
    assert GenerativeJobStatus.SUCCESS.value == "success"
