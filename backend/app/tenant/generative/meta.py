"""生成任务枚举展示元数据（GET /generative/jobs/meta）。"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options, literal_options
from app.models.model.generative_job import GenerativeJobStatus

GENERATIVE_JOB_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    GenerativeJobStatus.PENDING.value: ("等待中", "排队中"),
    GenerativeJobStatus.RUNNING.value: ("生成中", "调用厂商 API"),
    GenerativeJobStatus.SUCCESS.value: ("已完成", "可预览生成物"),
    GenerativeJobStatus.FAILED.value: ("失败", "见 error_message"),
    GenerativeJobStatus.CANCELLED.value: ("已取消", "用户取消"),
}

GENERATIVE_SOURCE_LABELS: dict[str, tuple[str, str | None]] = {
    "api": ("API 提交", None),
    "agent_tool": ("智能体工具", "generate_image / generate_video"),
    "flow_node": ("流程节点", "ImageGenerate / VideoGenerate"),
}

STATUS_FILTER_OPTIONS: list[tuple[str, str, str | None]] = [
    ("", "全部", None),
    *[(s.value, GENERATIVE_JOB_STATUS_LABELS[s.value][0], GENERATIVE_JOB_STATUS_LABELS[s.value][1]) for s in GenerativeJobStatus],
]


def generative_jobs_meta_dict() -> dict:
    return {
        "statuses": enum_options(GenerativeJobStatus, GENERATIVE_JOB_STATUS_LABELS),
        "status_filters": literal_options(STATUS_FILTER_OPTIONS),
        "sources": literal_options([(k, v[0], v[1]) for k, v in GENERATIVE_SOURCE_LABELS.items()]),
        "kinds": literal_options(
            [
                ("image", "生图", None),
                ("video", "生视频", None),
            ]
        ),
        "schema_version": META_SCHEMA_VERSION,
    }
