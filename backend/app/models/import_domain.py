"""导入域：import_batch、import_mapping、virtual_rule、import_error、review_queue（对齐数据字典 §7）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import AuditMixin


class VirtualRule(Base, AuditMixin):
    """虚拟/标记 SKU 规则（数据字典 §7.3）。"""

    __tablename__ = "virtual_rule"

    rule_type: Mapped[str] = mapped_column(String(16), nullable=False)  # virtual/marker
    match_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="exact"
    )  # exact/prefix/contains/regex
    match_value: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # skip/intercept/manual_review/ignore
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class ImportBatch(Base, AuditMixin):
    """导入批次（数据字典 §7.1）。"""

    __tablename__ = "import_batch"

    batch_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    import_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="order", index=True
    )  # order/stock/bom
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="importing", index=True
    )  # importing/preview/done/failed


class ImportMapping(Base, AuditMixin):
    """字段映射（数据字典 §7.2）。"""

    __tablename__ = "import_mapping"

    import_type: Mapped[str] = mapped_column(String(32), nullable=False)  # order/stock/bom
    source_column: Mapped[str] = mapped_column(String(64), nullable=False)
    target_field: Mapped[str] = mapped_column(String(64), nullable=False)
    header_row: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    transform_rule: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ImportError(Base, AuditMixin):
    """导入错误报告（错误行隔离，不进入主数据）。"""

    __tablename__ = "import_error"

    batch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("import_batch.id"), nullable=False, index=True
    )
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    package_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewQueue(Base, AuditMixin):
    """人工复核队列。"""

    __tablename__ = "review_queue"

    batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("import_batch.id"), nullable=True, index=True
    )
    package_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(32), nullable=False)  # R-01~R-05
    reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )  # pending/resolved/ignored
    handler: Mapped[str | None] = mapped_column(String(128), nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(255), nullable=True)
