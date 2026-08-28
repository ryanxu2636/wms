"""出库服务：扣减库存 + 流水 + 打印卡点。"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import LabelNotPrintedError, AlreadyShippedError
from app.core.state_machine import assert_can_transition
from app.models.fulfillment import Outbound, Package, PackageItem
from app.models.inventory import Allocation
from app.services import stock_service


def mark_label_printed(db: Session, outbound_id: int) -> None:
    """标记面单已打印（S2 桩实现，供出库卡点使用）。"""
    ob = db.get(Outbound, outbound_id)
    if ob is None:
        raise ValueError("出库单不存在")
    ob.label_printed = 1
    db.flush()


def ship(db: Session, outbound_id: int) -> None:
    """出库执行：
    - 硬卡点：面单未打印禁止出库（label_printed == 0）
    - 扣减 allocated_qty（分配阶段已从 available 挪出）
    - 写 stock_transaction 留痕
    """
    ob = db.get(Outbound, outbound_id)
    if ob is None:
        raise ValueError("出库单不存在")
    if ob.status == "shipped":
        raise AlreadyShippedError()

    if settings.REQUIRE_LABEL_PRINTED and not ob.label_printed:
        raise LabelNotPrintedError()

    pkg = db.get(Package, ob.package_id)
    assert_can_transition(pkg.status, "outbound")

    # 锁定该包裹所有未释放的分配
    allocations = db.execute(
        select(Allocation).where(
            Allocation.package_item_id.in_(
                select(PackageItem.id).where(PackageItem.package_id == pkg.id)
            ),
            Allocation.status == "allocated",
        ).with_for_update()
    ).scalars().all()

    for alloc in allocations:
        stock_service.outbound_deduct(db, alloc.stock_id, alloc.alloc_qty, "OUTBOUND", ob.id)
        alloc.status = "released"  # 出库后分配记录置为已释放/已完成

    ob.status = "shipped"
    ob.shipped_at = datetime.now()
    pkg.status = "outbound"
    db.flush()
