"""
内置工具 handler 包。

``handlers.BUILTIN_HANDLERS`` 映射 slug → async handler；新增内置工具时加 handler 文件并注册即可。
由 ``tenant.tools.invoke.builtin.invoke_builtin`` 统一分发，勿在 views 中直接 import 单 handler。
"""

from app.tenant.tools.builtins.calculator import safe_calculate
from app.tenant.tools.builtins.handlers import BUILTIN_HANDLERS
from app.tenant.tools.builtins.template import apply_template

__all__ = ["BUILTIN_HANDLERS", "safe_calculate", "apply_template"]
