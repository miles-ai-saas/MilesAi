"""
内置工具 handler 包（``handlers.BUILTIN_HANDLERS`` 映射 slug → async handler）。

新增内置工具时加 handler 文件并注册即可；由 ``tenant.tools.invoke.builtin.invoke_builtin``
统一分发，勿在 views 中直接 import 单 handler。

本包**只放 handler**。与内置/自定义无关的纯函数在 ``tenant.tools.primitives``
（``safe_calculate``、``apply_template``）；声明表在 ``tenant.tools.builtin_registry``。
"""

from miles_portal.tenant.tools.handlers.handlers import BUILTIN_HANDLERS

__all__ = ["BUILTIN_HANDLERS"]
