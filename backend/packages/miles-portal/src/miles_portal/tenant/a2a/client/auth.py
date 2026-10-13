"""A2A 出站鉴权头。"""

from __future__ import annotations

from miles_common.constants import AGENT_API_KEY_HEADER

JSONRPC_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def build_auth_headers(auth_config: dict | None) -> dict[str, str]:
    """``auth_config`` → 出站请求头（无有效配置时返回空字典）。

    约定（可叠加）：
    - ``{"headers": {"X-Foo": "bar"}}`` 任意头透传（对接自定义网关）
    - ``{"api_key": "..."}`` / ``{"x_api_key": "..."}`` → ``X-API-Key``（本平台发布
      A2A Server 的调用凭证）
    - ``{"bearer_token": "..."}`` → ``Authorization: Bearer ...``

    非法值（非字符串 / 空白 / 非字典 headers）逐项跳过而非整单失败：单项脏数据不应
    让整条 Peer 调用失去鉴权头，但也绝不把非法值拼进头里。
    """
    if not isinstance(auth_config, dict):
        return {}
    headers: dict[str, str] = {}

    raw_headers = auth_config.get("headers")
    if isinstance(raw_headers, dict):
        headers.update({str(k): str(v) for k, v in raw_headers.items() if isinstance(v, str)})

    for key in ("api_key", "x_api_key"):
        value = auth_config.get(key)
        if isinstance(value, str) and value.strip():
            headers[AGENT_API_KEY_HEADER] = value.strip()
            break

    bearer = auth_config.get("bearer_token")
    if isinstance(bearer, str) and bearer.strip():
        headers["Authorization"] = f"Bearer {bearer.strip()}"

    return headers
