"""
钩子执行器：按挂载时机调用 HTTP / Python 扩展（Event v1 envelope）。

目录职责
--------
- ``service.py``：``HookExecutor`` 门面（绑定加载 + 串行 dispatch）。
- ``http.py`` / ``python.py``：各类型钩子执行。
- ``log.py``：``HookExecutionLog`` 审计写入。

对外::

    from app.tenant.hooks.services.executor import HookExecutor
"""

from app.tenant.hooks.services.executor.service import HookExecutor

__all__ = ["HookExecutor"]
