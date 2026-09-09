"""异步生成任务提交与执行。

- 提交：``submit_video_generative_job``（L1 ``job.py`` 调用）
- 执行编排：已上移 L1 ``tenant.generative.services.job_execution``（worker 用例）
"""

from app.integrations.generative.jobs.submit import submit_video_generative_job

__all__ = ["submit_video_generative_job"]
