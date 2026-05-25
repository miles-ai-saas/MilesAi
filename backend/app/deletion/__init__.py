"""删除编排：无 DB 外键时的级联清理。

- document：chunk/vector_ref/向量库
- cascade：before_delete_agent/kb/flow
- tenant.purge_tenant_data：运营硬删租户数据
"""

from app.deletion.document import (
    clear_document_derived_data_async,
    clear_document_derived_data_sync,
)

__all__ = [
    "clear_document_derived_data_async",
    "clear_document_derived_data_sync",
]
