"""库存域：stock、stock_transaction、allocation（对齐数据字典 §2 / §4.3）。"""
from datetime import date

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import AuditMixin


class Stock(Base, AuditMixin):
    """库存台账：sku + location + batch 三维度记账（数据字典 §2.1）。"""

    __tablename__ = "stock"
    __table_args__ = (
        UniqueConstraint("sku_id", "location_id", "batch_no", name="uk_stock_sku_loc_batch"),
        CheckConstraint("available_qty >= 0", name="ck_stock_available_nonneg"),
        CheckConstraint("allocated_qty >= 0", name="ck_stock_allocated_nonneg"),
        CheckConstraint("locked_qty >= 0", name="ck_stock_locked_nonneg"),
        CheckConstraint("in_transit_qty >= 0", name="ck_stock_intransit_nonneg"),
    )

    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("location.id"), nullable=False, index=True)
    batch_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    production_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    available_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allocated_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    in_transit_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StockTransaction(Base, AuditMixin):
    """库存流水：只增不改，全程留痕（数据字典 §2.2）。"""

    __tablename__ = "stock_transaction"

    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stock.id"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.id"), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # inbound/outbound/allocate/release/adjust/transfer
    change_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    before_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    after_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Allocation(Base, AuditMixin):
    """库存分配（锁定来源记录，数据字典 §4.3）。"""

    __tablename__ = "allocation"

    package_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("package_item.id"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.id"), nullable=False, index=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stock.id"), nullable=False, index=True)
    alloc_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="allocated", index=True
    )  # allocated/released
