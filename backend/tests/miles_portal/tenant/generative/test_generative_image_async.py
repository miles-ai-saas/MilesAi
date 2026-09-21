"""生图异步任务参数与配置。"""

from miles_portal.tenant.generative.meta import generative_jobs_meta_dict
from miles_portal.tenant.generative.services.job import GenerativeJobService


def test_generative_jobs_meta_includes_image_kind():
    meta = generative_jobs_meta_dict()
    kinds = {o.value for o in meta["kinds"]}
    assert "image" in kinds
    assert "video" in kinds


def test_image_async_enabled_default():
    assert GenerativeJobService.image_async_enabled() is True
