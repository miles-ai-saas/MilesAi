"""工具输入参数 schema 校验与动态 Pydantic 模型（re-export shim）。

三函数已下沉中立 ``models/tool/parameters.py``；本模块保留 L1 import 路径。
"""

from app.models.tool.parameters import (  # noqa: F401
    normalize_parameters,
    parameters_to_pydantic,
    validate_tool_params,
)
