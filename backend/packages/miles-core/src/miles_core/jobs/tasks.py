"""Celery 任务名常量：**线级协议**，投递方与注册方共用的唯一来源。

这些字符串是投递侧（``send_task``）与 worker 注册侧（装饰器 ``name=``）之间的契约，
一经验证即为对外协议，**不得跟随模块 / 包路径改动**。

历史教训：任务名曾取自模块路径（``app.workers.tasks.*``），后端拆分为 uv workspace
时 codemod 一致改名为 ``miles_worker.tasks.*``，导致 broker 中在途消息全部
``KeyError: 'app.workers.tasks...'``（未被任何测试拦住——测试里的字面量也被同一次
codemod 改掉了）。故改用与目录无关的 ``milesai.tasks.*`` 命名空间并冻结。

**修改本文件的任何值都属破坏性协议变更**：需先排空 broker 在途消息（或注册旧名
别名）再部署，并同步更新 ``tests/infra/test_celery_task_names.py`` 中冻结的字面量。
"""

# 协议命名空间：与包 / 模块布局解耦，永不变更
TASK_NAMESPACE = "milesai.tasks."

TASK_NAMES = {
    # 文档入库（路由到 parse 队列）
    "ingest_document": "milesai.tasks.ingest.ingest_document",
    # 生成式媒体作业
    "run_generative_video_job": "milesai.tasks.generative.run_generative_video_job",
    "run_generative_image_job": "milesai.tasks.generative.run_generative_image_job",
    # 定时 / 健康探测
    "probe_models_health": "milesai.tasks.model_health.probe_models_health",
    "run_agent_schedule": "milesai.tasks.agent_schedule.run_agent_schedule",
    "tick_agent_schedules": "milesai.tasks.agent_schedule.tick_agent_schedules",
    "ping": "milesai.tasks.health.ping",
}

INGEST_DOCUMENT = TASK_NAMES["ingest_document"]
RUN_GENERATIVE_VIDEO_JOB = TASK_NAMES["run_generative_video_job"]
RUN_GENERATIVE_IMAGE_JOB = TASK_NAMES["run_generative_image_job"]
