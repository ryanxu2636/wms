"""系统域：user、role、operation_log（对齐数据字典 §9）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import AuditMixin


class Role(Base, AuditMixin):
    """角色表（数据字典 §9.2）。"""

    __tablename__ = "role"

    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True
    )  # receiver/putaway/picker/checker/packer/shipper/purchaser/admin
    permissions: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class User(Base, AuditMixin):
    """用户表（数据字典 §9.1）。"""

    __tablename__ = "user"

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("role.id"), nullable=False, index=True
    )
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)


class OperationLog(Base):
    """操作日志（数据字典 §9.3，仅 created_at，无审计 mixin）。"""

    __tablename__ = "operation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
