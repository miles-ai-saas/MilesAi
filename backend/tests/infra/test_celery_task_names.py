"""Celery 任务名「线级协议」冻结测试。

背景
----
任务名曾取自模块路径（``app.workers.tasks.*``）。后端拆分为 uv workspace 时，
codemod 把这些字面量**一致地**改成了 ``miles_worker.tasks.*``：投递方与注册方仍
自洽，所以单测全绿，但 broker 中在途消息（旧名）随即全部
``KeyError: 'app.workers.tasks...'``。当时的断言也写在同一次 codemod 的射程内，
因此**没有任何测试拦住这次协议破坏**。

本文件刻意**重复字面量**而非引用常量：改任务名必须显式修改本测试，
使「破坏性协议变更」成为可见动作，而不是一次顺手的全局替换。
"""

import miles_worker.tasks  # noqa: F401  # 导入即注册全部任务（等价于 worker 的 include）
from miles_core.jobs.tasks import TASK_NAMES, TASK_NAMESPACE
from miles_worker.app import celery_app

# 冻结的协议字面量。改动此处 = 破坏性协议变更：
# 需先排空 broker 在途消息（或为旧名注册别名）再部署。
FROZEN_TASK_NAMES = {
    "ingest_document": "milesai.tasks.ingest.ingest_document",
    "run_generative_video_job": "milesai.tasks.generative.run_generative_video_job",
    "run_generative_image_job": "milesai.tasks.generative.run_generative_image_job",
    "probe_models_health": "milesai.tasks.model_health.probe_models_health",
    "run_agent_schedule": "milesai.tasks.agent_schedule.run_agent_schedule",
    "tick_agent_schedules": "milesai.tasks.agent_schedule.tick_agent_schedules",
    "ping": "milesai.tasks.health.ping",
}

# 协议名中不得出现的包 / 模块路径片段
_FORBIDDEN_IN_NAME = (
    "app.",
    "miles_worker.",
    "miles_core.",
    "miles_portal.",
    "miles_ai.",
    "miles_admin.",
    "miles_openapi.",
    "miles_exec.",
    "miles_common.",
    "miles_runner.",
)


def _registered_task_names() -> set[str]:
    """worker 实际注册的任务名（排除 celery 内置）。"""
    return {name for name in celery_app.tasks if not name.startswith("celery.")}


def test_task_names_are_frozen_literals():
    """任务名字面量被冻结：任何改动都必须显式修改本测试。"""
    assert TASK_NAMES == FROZEN_TASK_NAMES


def test_task_names_are_decoupled_from_module_paths():
    """协议名不得嵌入包 / 模块路径，否则下一次搬迁会再次静默改协议。"""
    assert TASK_NAMESPACE == "milesai.tasks."
    for name in TASK_NAMES.values():
        assert name.startswith(TASK_NAMESPACE), f"{name} 脱离协议命名空间"
        for fragment in _FORBIDDEN_IN_NAME:
            assert fragment not in name, f"{name} 含包路径片段 {fragment!r}"


def test_every_dispatchable_task_is_registered():
    """投递侧 TASK_NAMES 的每个名字都必须已注册，否则运行时 ``KeyError``。"""
    missing = sorted(set(TASK_NAMES.values()) - _registered_task_names())
    assert not missing, f"投递名未注册: {missing}"


def test_no_orphan_registered_tasks():
    """注册侧不得出现 TASK_NAMES 之外的任务名（防装饰器写死字符串而漂移）。"""
    orphans = sorted(_registered_task_names() - set(TASK_NAMES.values()))
    assert not orphans, f"注册了未登记的任务名: {orphans}"


def test_task_routes_stay_in_frozen_namespace():
    """路由模式必须限定在冻结命名空间内。"""
    routes = celery_app.conf.task_routes or {}
    assert routes, "task_routes 不应为空（ingest 必须路由到 parse 队列）"
    for pattern in routes:
        assert pattern.startswith(TASK_NAMESPACE), f"路由模式脱离协议命名空间: {pattern}"


def test_beat_schedule_tasks_are_registered():
    """beat 调度项引用的任务必须已注册。"""
    registered = _registered_task_names()
    for entry in (celery_app.conf.beat_schedule or {}).values():
        assert entry["task"] in registered, f"beat 引用了未注册任务: {entry['task']}"


def test_task_annotations_keys_are_registered():
    """task_annotations 的键必须是已注册的任务名（写错键会静默失效）。"""
    registered = _registered_task_names()
    for key in celery_app.conf.task_annotations or {}:
        assert key in registered, f"annotations 键未注册: {key}"
