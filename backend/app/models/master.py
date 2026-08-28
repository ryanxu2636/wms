"""主数据域：sku、bom、warehouse、shelf、location、supplier（对齐数据字典 §1）。"""
from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import AuditMixin


class Sku(Base, AuditMixin):
    """SKU 主数据（数据字典 §1.1）。

    SKU 名保留空格与 `*`（不 trim），这是数据字典的硬约束。
    """

    __tablename__ = "sku"

    sku_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    sku_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="base", index=True
    )  # base/combo/virtual/marker
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="pcs")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    batch_enabled: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_warn_days: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)  # 1启用/0停用


class Warehouse(Base, AuditMixin):
    """仓库表（数据字典 §1.3）。"""

    __tablename__ = "warehouse"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)


class Shelf(Base, AuditMixin):
    """货架表（数据字典 §1.4）。"""

    __tablename__ = "shelf"

    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouse.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)


class Location(Base, AuditMixin):
    """库位表（数据字典 §1.5）：三段式 货架-列-层。"""

    __tablename__ = "location"

    shelf_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shelf.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    shelf_no: Mapped[str] = mapped_column(String(16), nullable=False)
    column_no: Mapped[str] = mapped_column(String(16), nullable=False)
    layer_no: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="empty", index=True
    )  # empty/occupied/full/locked


class Bom(Base, AuditMixin):
    """组合 BOM（数据字典 §1.2）：单层无嵌套。"""

    __tablename__ = "bom"
    __table_args__ = (
        UniqueConstraint("combo_sku_id", "component_sku_id", name="uk_bom_combo_component"),
    )

    combo_sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sku.id"), nullable=False, index=True
    )
    component_sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sku.id"), nullable=False, index=True
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Supplier(Base, AuditMixin):
    """供应商表（数据字典 §1.6）。"""

    __tablename__ = "supplier"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
