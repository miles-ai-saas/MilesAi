"""最小 Celery 应用：仅供业务侧按任务名投递，不含任务注册与调度。

任务注册（include）、执行期时限（task_annotations）、beat 调度由 worker 启动模块补齐，
以使 L1 业务代码投递任务时无需依赖 worker 包。

注意：队列路由（task_routes）**留在本模块**——它由投递方求值（send_task → amqp router），
API 进程不再 import worker 模块，路由若挪到 worker 会导致任务落错队列。
"""

from celery import Celery

from miles_core.config import get_settings
from miles_core.jobs.tasks import TASK_NAMESPACE

_settings = get_settings()

celery_app = Celery(
    "milesai",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_soft_time_limit=_settings.celery_task_soft_time_limit_sec,
    task_time_limit=_settings.celery_task_time_limit_sec,
    # 队列路由必须在最小 app 内：task_routes 由**投递方**求值
    # （send_task → amqp router），API 进程不再 import worker 模块，
    # 若把路由留在 worker，ingest 会被投到 default 而非 parse 队列。
    # 模式取自 miles_core.jobs.tasks.TASK_NAMESPACE（线级协议，勿改成模块路径）。
    task_routes={
        f"{TASK_NAMESPACE}ingest.*": {"queue": "parse"},
        f"{TASK_NAMESPACE}ocr.*": {"queue": "ocr"},
        f"{TASK_NAMESPACE}embed.*": {"queue": "embed"},
    },
)
