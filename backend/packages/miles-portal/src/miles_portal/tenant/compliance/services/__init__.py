"""
合规域业务服务层。

- ``compliance/``：``ComplianceService``（入出站扫描、词库/词条、拦截日志）。
- ``pipeline`` / ``word_resolve``：扫描引擎与词条解析，供子包与其它模块共用。

对外::

    from miles_portal.tenant.compliance.services.compliance import ComplianceService
"""
