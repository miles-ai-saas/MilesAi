"""异步生成任务模型与策略。"""

from miles_ai.integrations.generative.jobs.video_params import build_video_job_params
from miles_core.models.model.generative_job import GenerativeJobStatus


def test_build_video_job_params():
    params = build_video_job_params(prompt="test", duration=8, resolution="1080P")
    assert params["prompt"] == "test"
    assert params["duration"] == 8
    assert params["resolution"] == "1080P"


def test_generative_job_status_values():
    assert GenerativeJobStatus.PENDING.value == "pending"
    assert GenerativeJobStatus.SUCCESS.value == "success"
