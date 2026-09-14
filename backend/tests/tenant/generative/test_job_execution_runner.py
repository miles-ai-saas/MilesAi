"""``run_generative_{video,image}_job_async`` 特征化测试（重构前锁定行为）。

重点锁定**时序不变式**：每次 ``publish_generative_job_update`` 都必须携带
「刚刚写入 job 的」``status``/``percent``/``message``。

这正是不宜把 publish 实参提前绑定成闭包的原因——四个调用点的源码字面量
``status=job.status.value`` 完全相同，但每个调用点前都刚发生过一次状态赋值，
运行时取到的是四个不同状态。若按「实参大段相同」提取，会把取值冻结在
第一次，导致四种终态全部推送成 RUNNING。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_ai.integrations.generative.constants import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
from miles_ai.integrations.generative.jobs.errors import GenerativeJobCancelled, GenerativeJobNotFound
from miles_core.models.model.generative_job import GenerativeJobStatus
from miles_core.tenant import TenantContext
from miles_portal.tenant.generative.services import job_execution


def _job(**overrides) -> SimpleNamespace:
    """最小 job 替身；只带被测代码实际访问的字段。"""
    base = dict(
        id=uuid4(),
        tenant_id=uuid4(),
        kind="video",
        status=GenerativeJobStatus.PENDING,
        source="api",
        source_ref_type=None,
        source_ref_id=None,
        params={"prompt": "一只猫"},
        result=None,
        error_message=None,
        progress_message=None,
        progress_percent=None,
        created_by=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


async def _fake_model(db, ctx, **kwargs):  # noqa: ANN001
    return SimpleNamespace(model_config_id=uuid4(), provider="fake")


async def _fake_video(db, ctx, model, **kwargs):  # noqa: ANN001
    return SimpleNamespace(attachment_id=uuid4(), mime_type="video/mp4", duration_sec=5, media_asset_id=uuid4())


async def _fake_image(db, ctx, model, **kwargs):  # noqa: ANN001
    return SimpleNamespace(attachment_ids=[uuid4()], media_asset_ids=[uuid4()], mime_type="image/png")


@pytest.fixture
def env(monkeypatch):
    """装配可观察替身；``env.build(...)`` 返回本次装配的观测记录。"""
    monkeypatch.setattr(job_execution, "resolve_video_gen_model", _fake_model)
    monkeypatch.setattr(job_execution, "resolve_image_gen_model", _fake_model)

    def build(job, *, user=None, video=None, image=None):
        records = SimpleNamespace(publishes=[], syncs=[], video_calls=[], image_calls=[], commits=0)

        async def _publish(tenant_id, job_id, *, status, percent=None, message=None):
            records.publishes.append(
                SimpleNamespace(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    status=status,
                    percent=percent,
                    message=message,
                )
            )

        async def _sync(db, job):  # noqa: ANN001
            records.syncs.append(job)

        async def _commit():
            records.commits += 1

        async def _get(model, pk):  # noqa: ANN001
            if model is job_execution.GenerativeJob:
                return job
            if model is job_execution.User:
                return user
            return None

        db = SimpleNamespace(get=_get, commit=_commit)

        @asynccontextmanager
        async def _session():
            yield db

        async def _video(*args, **kwargs):
            records.video_calls.append(SimpleNamespace(args=args, kwargs=kwargs))
            return await (video or _fake_video)(*args, **kwargs)

        async def _image(*args, **kwargs):
            records.image_calls.append(SimpleNamespace(args=args, kwargs=kwargs))
            return await (image or _fake_image)(*args, **kwargs)

        monkeypatch.setattr(job_execution, "get_worker_session", lambda: _session())
        monkeypatch.setattr(job_execution, "publish_generative_job_update", _publish)
        monkeypatch.setattr(job_execution, "_sync_chat_after_job", _sync)
        monkeypatch.setattr(job_execution, "generate_video_for_model", _video)
        monkeypatch.setattr(job_execution, "generate_image_for_model", _image)
        return records

    env.build = build
    return env


# --------------------------------------------------------------------------- #
# 视频任务
# --------------------------------------------------------------------------- #


async def test_video_job_not_found_raises_before_any_publish(env):  # noqa: ANN001
    records = env.build(None)

    with pytest.raises(GenerativeJobNotFound):
        await job_execution.run_generative_video_job_async(uuid4())

    assert records.publishes == []
    assert records.commits == 0


async def test_video_job_already_cancelled_returns_silently(env):  # noqa: ANN001
    job = _job(status=GenerativeJobStatus.CANCELLED)
    records = env.build(job)

    await job_execution.run_generative_video_job_async(job.id)

    assert records.publishes == []
    assert records.commits == 0
    assert records.syncs == []


async def test_video_happy_path_publishes_running_then_success_with_fresh_values(env):  # noqa: ANN001
    """核心不变式：两次推送分别携带 running/5 与 success/100，而非同一个值。"""
    job = _job(params={"prompt": "一只猫", "duration": 8})
    records = env.build(job)

    await job_execution.run_generative_video_job_async(job.id)

    assert [p.status for p in records.publishes] == ["running", "success"]
    assert [p.percent for p in records.publishes] == [5, 100]
    assert [p.message for p in records.publishes] == ["生成中", "已完成"]
    assert all(p.tenant_id == job.tenant_id and p.job_id == job.id for p in records.publishes)


async def test_video_happy_path_writes_result_and_clears_error(env):  # noqa: ANN001
    job = _job(error_message="上一次失败")
    records = env.build(job, video=None)

    await job_execution.run_generative_video_job_async(job.id)

    assert job.status == GenerativeJobStatus.SUCCESS
    assert job.error_message is None
    assert job.result["kind"] == "video"
    assert job.result["duration_sec"] == 5
    assert job.result["attachment_id"]
    assert records.commits == 2  # RUNNING 一次、SUCCESS 一次
    assert len(records.syncs) == 1


async def test_video_cancel_exception_publishes_cancelled_and_does_not_reraise(env):  # noqa: ANN001
    async def _boom(*args, **kwargs):
        raise GenerativeJobCancelled()

    job = _job()
    records = env.build(job, video=_boom)

    await job_execution.run_generative_video_job_async(job.id)  # 不抛出

    assert [p.status for p in records.publishes] == ["running", "cancelled"]
    assert records.publishes[-1].message == "已取消"
    assert records.publishes[-1].percent is None  # 终态取消不公布 percent
    assert job.status == GenerativeJobStatus.CANCELLED
    assert len(records.syncs) == 1


async def test_video_cancellation_detected_after_generation_skips_success(env):  # noqa: ANN001
    """生成期间用户取消：重取 job 后发现已 CANCELLED，不得再推 success。"""

    async def _cancel_during(*args, **kwargs):
        job.status = GenerativeJobStatus.CANCELLED
        return await _fake_video(*args, **kwargs)

    job = _job()
    records = env.build(job, video=_cancel_during)

    await job_execution.run_generative_video_job_async(job.id)

    assert [p.status for p in records.publishes] == ["running"]
    assert records.syncs == []


async def test_video_failure_publishes_failed_and_reraises(env):  # noqa: ANN001
    async def _boom(*args, **kwargs):
        raise RuntimeError("厂商超时")

    job = _job()
    records = env.build(job, video=_boom)

    with pytest.raises(RuntimeError, match="厂商超时"):
        await job_execution.run_generative_video_job_async(job.id)

    assert [p.status for p in records.publishes] == ["running", "failed"]
    assert records.publishes[-1].percent is None  # 终态失败不公布 percent
    assert job.status == GenerativeJobStatus.FAILED
    assert job.progress_message == "失败"
    assert job.error_message == "厂商超时"
    assert len(records.syncs) == 1


async def test_video_failure_after_external_cancel_is_swallowed_not_reraised(env):  # noqa: ANN001
    """既有行为：生成期间被外部取消、随后又抛异常时，异常只记日志不重抛。

    后果是 Celery 任务会看到正常返回（回写 SUCCESS/"ok"），而 job 停在 CANCELLED。
    此处仅锁定现状，是否收敛另议。
    """

    async def _boom(*args, **kwargs):
        job.status = GenerativeJobStatus.CANCELLED
        raise RuntimeError("取消后仍报错")

    job = _job()
    records = env.build(job, video=_boom)

    await job_execution.run_generative_video_job_async(job.id)  # 不抛出

    assert [p.status for p in records.publishes] == ["running"]
    assert job.status == GenerativeJobStatus.CANCELLED
    assert records.syncs == []


async def test_video_error_message_is_truncated_to_2000_chars(env):  # noqa: ANN001
    async def _boom(*args, **kwargs):
        raise RuntimeError("x" * 5000)

    job = _job()
    env.build(job, video=_boom)

    with pytest.raises(RuntimeError):
        await job_execution.run_generative_video_job_async(job.id)

    assert len(job.error_message) == 2000


async def test_video_builds_worker_context_from_job_and_user(env):  # noqa: ANN001
    created_by = uuid4()
    job = _job(created_by=created_by)
    records = env.build(job, user=SimpleNamespace(username="小李"))

    await job_execution.run_generative_video_job_async(job.id)

    ctx = records.video_calls[0].args[1]
    assert isinstance(ctx, TenantContext)
    assert ctx.tenant_id == job.tenant_id
    assert ctx.user_id == created_by
    assert ctx.username == "小李"
    assert ctx.is_superuser is False
    assert ctx.permissions == frozenset(["attachment:read", "attachment:upload"])


async def test_video_falls_back_to_worker_username_without_user(env):  # noqa: ANN001
    job = _job(created_by=None)
    records = env.build(job)

    await job_execution.run_generative_video_job_async(job.id)

    assert records.video_calls[0].args[1].username == "worker"


async def test_video_purpose_depends_on_source(env):  # noqa: ANN001
    flow_job = _job(source="flow_node")
    flow_records = env.build(flow_job)
    await job_execution.run_generative_video_job_async(flow_job.id)
    assert flow_records.video_calls[0].kwargs["purpose"] == PURPOSE_FLOW_GENERATED

    chat_job = _job(source="agent_tool")
    chat_records = env.build(chat_job)
    await job_execution.run_generative_video_job_async(chat_job.id)
    assert chat_records.video_calls[0].kwargs["purpose"] == PURPOSE_CHAT_GENERATED


async def test_video_agent_config_preset_duration_wins(env):  # noqa: ANN001
    job = _job(params={"prompt": "猫", "duration": 5, "agent_config": {"_generative_video_duration": 9}})
    records = env.build(job)

    await job_execution.run_generative_video_job_async(job.id)

    assert records.video_calls[0].kwargs["duration"] == 9


@pytest.mark.parametrize("preset", ["abc", 0, -3, None])
async def test_video_invalid_preset_duration_keeps_params_duration(env, preset):  # noqa: ANN001
    job = _job(params={"prompt": "猫", "duration": 6, "agent_config": {"_generative_video_duration": preset}})
    records = env.build(job)

    await job_execution.run_generative_video_job_async(job.id)

    assert records.video_calls[0].kwargs["duration"] == 6


async def test_video_duration_defaults_to_five(env):  # noqa: ANN001
    job = _job(params={"prompt": "猫"})
    records = env.build(job)

    await job_execution.run_generative_video_job_async(job.id)

    assert records.video_calls[0].kwargs["duration"] == 5


async def test_video_agent_id_falls_back_to_source_ref(env):  # noqa: ANN001
    ref = uuid4()
    job = _job(params={"prompt": "猫"}, source_ref_type="agent", source_ref_id=ref)
    records = env.build(job)

    await job_execution.run_generative_video_job_async(job.id)

    assert records.video_calls[0].kwargs["agent_id"] == ref
    assert records.video_calls[0].kwargs["generative_job_id"] == job.id


# --------------------------------------------------------------------------- #
# 图片任务
# --------------------------------------------------------------------------- #


async def test_image_happy_path_publishes_running_then_success_with_fresh_values(env):  # noqa: ANN001
    job = _job(kind="image")
    records = env.build(job, image=None)

    await job_execution.run_generative_image_job_async(job.id)

    assert [p.status for p in records.publishes] == ["running", "success"]
    assert [p.percent for p in records.publishes] == [5, 100]
    assert [p.message for p in records.publishes] == ["生图中", "已完成"]
    assert job.result["kind"] == "image"
    assert len(records.syncs) == 1


async def test_image_result_keeps_all_attachment_ids(env):  # noqa: ANN001
    first, second = uuid4(), uuid4()
    mid_a, mid_b = uuid4(), uuid4()

    async def _two(*args, **kwargs):
        return SimpleNamespace(
            attachment_ids=[first, second],
            media_asset_ids=[mid_a, mid_b],
            mime_type="image/png",
        )

    job = _job(kind="image")
    env.build(job, image=_two)

    await job_execution.run_generative_image_job_async(job.id)

    assert job.result["attachment_id"] == str(first)
    assert job.result["attachment_ids"] == [str(first), str(second)]
    assert job.result["media_asset_id"] == str(mid_a)
    assert job.result["media_asset_ids"] == [str(mid_a), str(mid_b)]


async def test_image_preset_n_overrides_user_n(env):  # noqa: ANN001
    job = _job(kind="image", params={"prompt": "猫", "n": 2, "agent_config": {"_generative_image_n": 3}})
    records = env.build(job)

    await job_execution.run_generative_image_job_async(job.id)

    assert records.image_calls[0].kwargs["n"] == 3


@pytest.mark.parametrize(("preset", "expected"), [(9, 4), (0, 1), (-2, 1), ("3", 3)])
async def test_image_preset_n_is_clamped_to_1_4(env, preset, expected):  # noqa: ANN001
    job = _job(kind="image", params={"prompt": "猫", "agent_config": {"_generative_image_n": preset}})
    records = env.build(job)

    await job_execution.run_generative_image_job_async(job.id)

    assert records.image_calls[0].kwargs["n"] == expected


@pytest.mark.parametrize("raw_n", ["abc", None])
async def test_image_invalid_n_falls_back_to_one(env, raw_n):  # noqa: ANN001
    job = _job(kind="image", params={"prompt": "猫", "n": raw_n})
    records = env.build(job)

    await job_execution.run_generative_image_job_async(job.id)

    assert records.image_calls[0].kwargs["n"] == 1


async def test_image_allow_collage_from_params_or_agent_config(env):  # noqa: ANN001
    from_params = _job(kind="image", params={"prompt": "猫", "allow_collage": True})
    records = env.build(from_params)
    await job_execution.run_generative_image_job_async(from_params.id)
    assert records.image_calls[0].kwargs["allow_collage"] is True

    from_cfg = _job(kind="image", params={"prompt": "猫", "agent_config": {"_image_allow_collage": True}})
    cfg_records = env.build(from_cfg)
    await job_execution.run_generative_image_job_async(from_cfg.id)
    assert cfg_records.image_calls[0].kwargs["allow_collage"] is True

    default = _job(kind="image", params={"prompt": "猫"})
    default_records = env.build(default)
    await job_execution.run_generative_image_job_async(default.id)
    assert default_records.image_calls[0].kwargs["allow_collage"] is False


async def test_image_cancel_exception_publishes_cancelled(env):  # noqa: ANN001
    async def _boom(*args, **kwargs):
        raise GenerativeJobCancelled()

    job = _job(kind="image")
    records = env.build(job, image=_boom)

    await job_execution.run_generative_image_job_async(job.id)

    assert [p.status for p in records.publishes] == ["running", "cancelled"]
    assert records.publishes[-1].message == "已取消"
    assert records.publishes[-1].percent is None


async def test_image_failure_publishes_failed_and_reraises(env):  # noqa: ANN001
    async def _boom(*args, **kwargs):
        raise RuntimeError("内容审核拒绝")

    job = _job(kind="image")
    records = env.build(job, image=_boom)

    with pytest.raises(RuntimeError, match="内容审核拒绝"):
        await job_execution.run_generative_image_job_async(job.id)

    assert [p.status for p in records.publishes] == ["running", "failed"]
    assert records.publishes[-1].percent is None
    assert job.error_message == "内容审核拒绝"
    assert len(records.syncs) == 1


async def test_image_job_not_found_raises(env):  # noqa: ANN001
    env.build(None)

    with pytest.raises(GenerativeJobNotFound):
        await job_execution.run_generative_image_job_async(uuid4())
