"""
Marketplace 聚合：应用上架、安装与评分。

目录职责
--------
- ``service.py``：``MarketplaceService`` 门面（仓库注入 + ``get_meta``）。
- ``catalog.py``：分类、列表、详情与 ``app_out`` 等浏览能力。
- ``publish.py``：创建/编辑应用、从 KB/Flow/Agent 生成 manifest、提交审核。
- ``install.py``：安装到租户（克隆 KB/Flow/Agent）、安装记录。
- ``review.py``：平台审核通过/驳回。
- ``ratings.py``：评分与 ``rating_avg`` 统计。

对外::

    from miles_portal.tenant.marketplace.services.marketplace import MarketplaceService
"""

from miles_portal.tenant.marketplace.services.marketplace.service import MarketplaceService

__all__ = ["MarketplaceService"]
