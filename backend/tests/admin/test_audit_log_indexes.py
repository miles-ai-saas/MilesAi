"""审计日志模型的索引声明。

``action`` 既是审计列表的筛选条件（``AuditLog.action == action``），也是筛选元数据
的来源（``SELECT DISTINCT action``）。缺索引时两处都要对 ``adm_audit_logs`` 全表扫描，
随日志量线性变慢——本文件把这个索引钉在模型上，防止后续被无意删掉。
"""

from miles_admin.models.audit import AuditLog


def _indexes() -> dict[str, list[str]]:
    return {idx.name: [col.name for col in idx.columns] for idx in AuditLog.__table__.indexes}


def test_action_index_is_declared():
    assert _indexes().get("idx_adm_audit_logs_action") == ["action"]


def test_existing_indexes_are_kept():
    """原有的三个索引是对筛选条件的支撑，不应在加索引时被顺手改动。"""
    indexes = _indexes()
    assert indexes.get("idx_adm_audit_logs_admin_id") == ["admin_id"]
    assert indexes.get("idx_adm_audit_logs_tenant_id") == ["tenant_id"]
    assert indexes.get("idx_adm_audit_logs_created_at") == ["created_at"]
