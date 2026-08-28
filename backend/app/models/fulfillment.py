"""订单履约域：package、package_item、picking_task、packing、outbound（对齐数据字典 §4）。"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import AuditMixin


class Package(Base, AuditMixin):
    """包裹（订单/运单粒度，数据字典 §4.1）。"""

    __tablename__ = "package"

    package_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    tracking_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    logistics_channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pay_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unassigned", index=True
    )  # unassigned/assigned/picking/checked/packed/outbound/intercepted/manual_review/shortage_hold
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_resend: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PackageItem(Base, AuditMixin):
    """包裹明细（数据字典 §4.2）。"""

    __tablename__ = "package_item"
    __table_args__ = (
        UniqueConstraint("package_id", "sku_id", name="uk_package_item_pkg_sku"),
    )

    package_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("package.id"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.id"), nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_virtual: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_marker: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    picked_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PickingTask(Base, AuditMixin):
    """拣货任务（数据字典 §4.4）。"""

    __tablename__ = "picking_task"

    task_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    package_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("package.id"), nullable=True, index=True
    )
    assignee_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )  # pending/doing/done/cancelled
    picked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Packing(Base, AuditMixin):
    """复核/打包记录（数据字典 §4.5）。"""

    __tablename__ = "packing"

    package_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("package.id"), nullable=False, index=True)
    packer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )  # pending/checked/packed
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    packed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Outbound(Base, AuditMixin):
    """出库单（1:1 包裹，数据字典 §4.6）。"""

    __tablename__ = "outbound"

    package_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("package.id"), nullable=False, unique=True
    )
    outbound_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )  # pending/shipped/cancelled
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    label_printed: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
