"""敏感词流水线（re-export shim）。

实现已下沉中立域 ``app.models.compliance.pipeline``；保留本路径供 L1 既有引用
（``compliance/services/compliance/intercept.py`` 等）。
"""

from app.models.compliance.pipeline import (  # noqa: F401
    CompliancePipeline,
    ScanMatch,
    ScanResult,
)
