"""采购域：purchase_order、purchase_order_item、receiving、putaway_task（对齐数据字典 §3）。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import AuditMixin


class PurchaseOrder(Base, AuditMixin):
    """采购单（数据字典 §3.1）。"""

    __tablename__ = "purchase_order"

    po_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("supplier.id"), nullable=False, index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", index=True
    )  # draft/ordered/partial_received/received/completed/cancelled
    expect_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PurchaseOrderItem(Base, AuditMixin):
    """采购单明细（数据字典 §3.2）。"""

    __tablename__ = "purchase_order_item"

    po_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_order.id"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.id"), nullable=False, index=True)
    order_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)


class Receiving(Base, AuditMixin):
    """到货单（数据字典 §3.3）。"""

    __tablename__ = "receiving"

    po_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_order.id"), nullable=False, index=True
    )
    receiving_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="receiving", index=True
    )  # receiving/quality_check/qualified/rejected
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PutawayTask(Base, AuditMixin):
    """上架任务（数据字典 §3.4）。"""

    __tablename__ = "putaway_task"

    receiving_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.id"), nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    from_location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("location.id"), nullable=True, index=True
    )
    to_location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("location.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )  # pending/doing/done
