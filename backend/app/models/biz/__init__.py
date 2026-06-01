"""业务中心 ORM（biz_* 表），位于 ``app/models/biz/``。

按业务域组织，由 ``app.models.registry.load_all_models`` 注册到 Alembic metadata。
域划分：枚举 → 销售（客户/商机）→ 交付（项目执行）→ 财务（合同/收付款）。
"""

from app.models.biz.client import BizClient, BizClientContact
from app.models.biz.contract import BizContract, BizPayment
from app.models.biz.enums import ConfidentialityLevel, ProjectStatus
from app.models.biz.opportunity import BizOpportunity
from app.models.biz.project import (
    BizDeliverable,
    BizProject,
    BizProjectMember,
    BizServiceLineTemplate,
    BizWorkPackage,
)

__all__ = [
    "ConfidentialityLevel",
    "ProjectStatus",
    "BizClient",
    "BizClientContact",
    "BizOpportunity",
    "BizProject",
    "BizWorkPackage",
    "BizDeliverable",
    "BizServiceLineTemplate",
    "BizProjectMember",
    "BizContract",
    "BizPayment",
]
