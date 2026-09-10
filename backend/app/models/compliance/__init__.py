"""合规纯逻辑中立域（无 ORM/DB 依赖）。

子模块：constants（SensitiveAction 枚举）、pipeline（子串匹配流水线）。
L1 侧保留 ``tenant.compliance.models`` / ``tenant.compliance.services.pipeline``
re-export shim，路径稳定。
"""
