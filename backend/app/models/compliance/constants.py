"""合规扫描枚举（中立域，ORM/schemas/L3 共用）。"""

import enum


class SensitiveAction(str, enum.Enum):
    """敏感词处置动作。"""

    WARN = "warn"
    BLOCK = "block"
