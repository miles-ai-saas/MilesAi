"""``SystemConfig.value`` 这类「JSON 包装标量」的取值与解析。

``SystemConfig.value`` 存的是 ``{"value": ...}`` 包装（见 ``SystemConfigService.upsert_config``），
读取配置的地方都要先剥一层再转类型。而这类配置由管理端按 key 直接写入、**没有 schema 约束**
（``SystemConfigUpsert.value`` 只要求是 dict），所以解析失败必须留下痕迹：静默回落会让
「上限 / 开关」类配置悄悄失效，而写配置的人以为限制已经生效。

解析失败一律以 warning 留痕；是否 fail-open 由调用方通过 ``default`` 决定——本模块不做取舍。
"""

from __future__ import annotations

from miles_core.logging import get_logger

logger = get_logger(__name__)


def system_config_int(raw: object, *, default: int, minimum: int = 1) -> int:
    """把 ``SystemConfig.value`` 解析为非负整数。

    - 未配置（``None``）→ ``default``，不告警（这是预期状态，不是异常）
    - 已配置但无法解析 → 记 warning 后回落 ``default``
    - 解析成功 → 夹取到 ``minimum`` 以上

    ``minimum`` 由调用方表达语义：文件大小上限用 1（不允许 0 字节上限），
    而「0 表示不限」的配额用 0。
    """
    if raw is None:
        return default
    if isinstance(raw, dict) and "value" in raw:
        raw = raw["value"]
    try:
        return max(minimum, int(raw))
    except (TypeError, ValueError):
        logger.warning("system_config 值无法解析为整数，已回落默认值 %s: %r", default, raw)
        return default
