"""出站 HTTP URL 校验（工具、MCP、技能包 Git 导入共用）。

``validate_outbound_url`` 是**所有出站地址**的唯一判据；作用域见
``settings.outbound_allow_private_hosts``。
"""

import ipaddress
from urllib.parse import urlparse

from miles_common.exceptions import BadRequestError
from miles_core.config import get_settings


def validate_outbound_url(url: str) -> str:
    """校验即将发起 HTTP 请求的 URL；返回规范化字符串。

    仅允许 ``http(s)`` scheme；本机 / 内网地址的拦截由
    ``settings.outbound_allow_private_hosts`` 控制（默认 ``True`` 即放行，
    为自托管连接内网 MCP / 对象存储所需）。**不解析域名**，故「域名解析到内网」
    不在此拦截范围内（由 ``httpx`` 连接时解析）。
    """
    raw = (url or "").strip()
    if not raw:
        raise BadRequestError("URL 不能为空")

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise BadRequestError("URL 仅支持 http 或 https")
    if not parsed.netloc:
        raise BadRequestError("URL 无效")

    host = parsed.hostname
    if not host:
        raise BadRequestError("URL 无效")

    if not get_settings().outbound_allow_private_hosts:
        _reject_unsafe_host(host)
    return raw


def _reject_unsafe_host(host: str) -> None:
    """阻止明显内网/本机地址；域名不在此解析 DNS（由 httpx 连接时解析）。"""
    lowered = host.lower()
    if lowered in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise BadRequestError("不允许连接本机地址")

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return

    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
        raise BadRequestError("不允许连接内网或保留地址段")
