"""标准审计字段 mixin + 枚举约定（对齐数据字典 §0.2 / §0.4）。

所有业务表统一包含：id/created_at/updated_at/created_by/updated_by/deleted。
枚举值统一英文（避免中文在 SQL/JSON 里的坑）。
"""
import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

# 主键：PostgreSQL 用 BIGSERIAL，SQLite 退化为 INTEGER（SQLite 仅 INTEGER PRIMARY KEY 自增）
_PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class AuditMixin:
    """标准审计字段（对齐数据字典）。"""

    id: Mapped[int] = mapped_column(_PK_TYPE, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # 软删标记：0=否 1=是
    deleted: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", nullable=False
    )


class SkuType(str, enum.Enum):
    """SKU 类型（数据字典 §0.4）。"""

    base = "base"       # 基础（实物库存）
    combo = "combo"     # 组合（BOM 展开）
    virtual = "virtual"  # 虚拟（如 YUN 运费）
    marker = "marker"   # 标记（CS99/CS00/CS000）


class PackageStatus(str, enum.Enum):
    """订单状态机（数据字典 §4.1）。"""

    unassigned = "unassigned"
    assigned = "assigned"
    picking = "picking"
    checked = "checked"
    packed = "packed"
    outbound = "outbound"
    intercepted = "intercepted"
    manual_review = "manual_review"
    shortage_hold = "shortage_hold"


class LocationStatus(str, enum.Enum):
    """库位状态（数据字典 §1.5）。"""

    empty = "empty"
    occupied = "occupied"
    full = "full"
    locked = "locked"
