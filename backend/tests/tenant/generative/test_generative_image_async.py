"""生图异步任务参数与配置。"""

from miles_ai.integrations.generative.jobs.image_params import build_image_job_params
from miles_portal.tenant.generative.meta import generative_jobs_meta_dict
from miles_portal.tenant.generative.services.job import GenerativeJobService


def test_build_image_job_params():
    params = build_image_job_params(
        prompt="a cat",
        size="1280x720",
        n=2,
    )
    assert params["prompt"] == "a cat"
    assert params["size"] == "1280x720"
    assert params["n"] == 2


def test_generative_jobs_meta_includes_image_kind():
    meta = generative_jobs_meta_dict()
    kinds = {o.value for o in meta["kinds"]}
    assert "image" in kinds
    assert "video" in kinds


def test_image_async_enabled_default():
    assert GenerativeJobService.image_async_enabled() is True
