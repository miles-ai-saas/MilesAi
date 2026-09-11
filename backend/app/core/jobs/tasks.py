"""Celery 任务名常量：投递方与注册方共用的唯一来源。"""

TASK_NAMES = {
    "ingest_document": "app.workers.tasks.ingest.ingest_document",
    "run_generative_video_job": "app.workers.tasks.generative.run_generative_video_job",
    "run_generative_image_job": "app.workers.tasks.generative.run_generative_image_job",
    "probe_models_health": "app.workers.tasks.model_health.probe_models_health",
    "run_agent_schedule": "app.workers.tasks.agent_schedule.run_agent_schedule",
    "tick_agent_schedules": "app.workers.tasks.agent_schedule.tick_agent_schedules",
}

INGEST_DOCUMENT = TASK_NAMES["ingest_document"]
RUN_GENERATIVE_VIDEO_JOB = TASK_NAMES["run_generative_video_job"]
RUN_GENERATIVE_IMAGE_JOB = TASK_NAMES["run_generative_image_job"]
