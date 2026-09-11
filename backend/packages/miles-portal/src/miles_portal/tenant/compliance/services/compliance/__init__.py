"""
Compliance 聚合：敏感词扫描与词库管理。

目录职责
--------
- ``service.py``：``ComplianceService`` 门面（Mixin 组合 + ``get_meta``）。
- ``intercept.py``：``check_input`` / ``check_output`` / ``scan_text``（Agent、Flow 等调用）。
- ``scan_bindings.py``：租户启用哪些词库参与扫描。
- ``library.py`` / ``library_words.py`` / ``entry.py``：词库与词条 CRUD。
- ``logs.py``：拦截日志分页查询。

不在此包内
----------
``pipeline.py``（AC 自动机）、``word_resolve.py``（加载扫描词、去重建词条）。

对外::

    from miles_portal.tenant.compliance.services.compliance import ComplianceService
"""

from miles_portal.tenant.compliance.services.compliance.service import ComplianceService

__all__ = ["ComplianceService"]
