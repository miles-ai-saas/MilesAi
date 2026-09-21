"""Celery 应用配置 smoke 测试。"""

from miles_core.config import get_settings
from miles_core.jobs.tasks import TASK_NAMES
from miles_worker.app import celery_app


def test_celery_global_time_limits_from_settings():
    settings = get_settings()
    assert celery_app.conf.task_soft_time_limit == settings.celery_task_soft_time_limit_sec
    assert celery_app.conf.task_time_limit == settings.celery_task_time_limit_sec


def test_celery_task_annotations_for_long_running_jobs():
    settings = get_settings()
    annotations = celery_app.conf.task_annotations
    ingest = annotations[TASK_NAMES["ingest_document"]]
    assert ingest["soft_time_limit"] == settings.celery_ingest_soft_time_limit_sec
    assert ingest["time_limit"] == settings.celery_ingest_time_limit_sec

    video = annotations[TASK_NAMES["run_generative_video_job"]]
    assert video["soft_time_limit"] == settings.celery_generative_soft_time_limit_sec
    assert video["time_limit"] == settings.celery_generative_time_limit_sec

    image = annotations[TASK_NAMES["run_generative_image_job"]]
    assert image["soft_time_limit"] == settings.celery_generative_soft_time_limit_sec
    assert image["time_limit"] == settings.celery_generative_time_limit_sec
