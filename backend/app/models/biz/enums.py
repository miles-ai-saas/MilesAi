"""业务中心枚举。"""

import enum


class ConfidentialityLevel(str, enum.Enum):
    """客户数据安全分级。

    用于控制不同角色对客户信息的可见范围，RESTRICTED 级别客户仅限项目相关人员查看。
    """
    NORMAL = "normal"        # 普通客户，全公司可见
    INTERNAL = "internal"    # 内部客户/关联方，默认对全员可见但敏感字段脱敏
    RESTRICTED = "restricted"  # 受限客户，需显式授权才能查看


class SupplierCategory(str, enum.Enum):
    """供应商类型——广告/文创行业常见外包品类。"""
    PRINT = "print"
    VIDEO = "video"
    CONSTRUCTION = "construction"
    EVENT = "event"
    DESIGN = "design"
    LOGISTICS = "logistics"
    OTHER = "other"


class SupplierStatus(str, enum.Enum):
    """供应商合作状态。"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"


class ProjectStatus(str, enum.Enum):
    """项目生命周期状态。

    状态流转为单向：DRAFT → ACTIVE → DELIVERED → CLOSED，或从 ACTIVE 中途进入 ON_HOLD，任意节点可跳转到 CANCELLED。
    """
    DRAFT = "draft"          # 草稿，尚未正式启动
    ACTIVE = "active"        # 执行中
    ON_HOLD = "on_hold"      # 暂停，如客户方决策延迟、预算冻结
    DELIVERED = "delivered"  # 已交付，等待验收闭环
    CLOSED = "closed"        # 已结项归档
    CANCELLED = "cancelled"  # 已取消
