"""打印域：print_template、print_queue（对齐数据字典 §8）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import AuditMixin


class PrintTemplate(Base, AuditMixin):
    """打印模板（数据字典 §8.1）。"""

    __tablename__ = "print_template"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    template_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="label"
    )  # label/waybill
    content: Mapped[str | None] = mapped_column(Text, nullable=True)


class PrintQueue(Base, AuditMixin):
    """打印队列（数据字典 §8.2）。"""

    __tablename__ = "print_queue"

    package_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("package.id"), nullable=False, index=True
    )
    template_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("print_template.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="queued", index=True
    )  # queued/printing/success/failed
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
