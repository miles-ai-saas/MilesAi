"""生成任务取消与进度字段。"""

from miles_core.models.model.generative_job import GenerativeJobStatus


def test_generative_job_status_includes_cancelled():
    assert GenerativeJobStatus.CANCELLED.value == "cancelled"


def test_terminal_statuses_for_cancel_api():
    terminal = {
        GenerativeJobStatus.SUCCESS,
        GenerativeJobStatus.FAILED,
        GenerativeJobStatus.CANCELLED,
    }
    assert GenerativeJobStatus.PENDING not in terminal
    assert GenerativeJobStatus.RUNNING not in terminal
