"""兼容转发 → app.rag.load。"""

from app.rag.load import load_kb_sync, load_kbs_for_tenant

__all__ = ["load_kb_sync", "load_kbs_for_tenant"]
