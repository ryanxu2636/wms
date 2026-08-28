"""快进快出域 + 盘点域（对齐数据字典 §5 / §6）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import AuditMixin


class CrossDockMatch(Base, AuditMixin):
    """快进快出匹配（数据字典 §5.1）。"""

    __tablename__ = "cross_dock_match"

    receiving_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("receiving.id"), nullable=False, index=True
    )
    package_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("package.id"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.id"), nullable=False, index=True)
    match_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="matched", index=True
    )  # matched/diverted/completed


class Stocktake(Base, AuditMixin):
    """盘点单（数据字典 §6.1）。"""

    __tablename__ = "stocktake"

    stocktake_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id"), nullable=False, index=True
    )
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False, default="all")  # all/location/sku
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", index=True
    )  # draft/counting/reviewing/done
    counted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)


class StocktakeItem(Base, AuditMixin):
    """盘点明细（数据字典 §6.2）。"""

    __tablename__ = "stocktake_item"

    stocktake_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocktake.id"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.id"), nullable=False, index=True)
    location_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("location.id"), nullable=True, index=True
    )
    book_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diff_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)


class StockAdjustment(Base, AuditMixin):
    """库存调整（数据字典 §6.3）。"""

    __tablename__ = "stock_adjustment"

    adjust_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    stocktake_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stocktake.id"), nullable=True, index=True
    )
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sku.id"), nullable=False, index=True)
    adjust_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(
        String(64), nullable=False, default="other"
    )  # profit/loss/damage/other
    authorized_by: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
