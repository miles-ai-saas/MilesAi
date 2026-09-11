"""A2A 路由包；``peers.router`` 挂载为租户 API 的 ``/a2a/peers`` 前缀。"""

from miles_portal.tenant.a2a.views import peers

__all__ = ["peers"]
