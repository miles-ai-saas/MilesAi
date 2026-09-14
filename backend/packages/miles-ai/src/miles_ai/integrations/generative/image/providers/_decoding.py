"""生图 Provider 响应里 base64 图片数据的容错解码。

三个 Provider（OpenAI 兼容 / 豆包 / 万相）都会把响应里的 ``b64_json`` / ``b64_image``
直接交给 ``base64.standard_b64decode``。而这是**外部响应**：可能被截断、夹带非 base64
字符、或根本不是 ASCII，此时解码抛 ``binascii.Error``（``ValueError`` 子类）会一路
冒到任务层，报错信息只有一串 "Invalid base64-encoded string"，看不出是哪家返回的脏数据。

统一收敛为「跳过并告警」，让调用方既有的「无可用图片数据」分支给出可读报错。
"""

from __future__ import annotations

import base64

from miles_core.logging import get_logger

logger = get_logger(__name__)


def decode_b64_image(data: str | bytes) -> bytes | None:
    """解码单张 base64 图片；脏数据记 warning 并返回 ``None``，不抛异常。

    ``standard_b64decode`` 对非法输入抛 ``binascii.Error``，对非 ASCII ``str`` 抛
    ``ValueError``——两者同属 ``ValueError``，故此处一并兜住。
    """
    try:
        return base64.standard_b64decode(data)
    except ValueError as e:
        logger.warning("生图响应含无法解码的 base64 图片，已跳过: %s", e)
        return None
