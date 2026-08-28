"""拣货/复核/打包服务。"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.state_machine import assert_can_transition
from app.models.fulfillment import Package, PackageItem, PickingTask, Packing
from app.models.inventory import Allocation, Stock
from app.models.master import Location


def _gen_task_no(seq: int) -> str:
    return f"PK{datetime.now().strftime('%Y%m%d')}{seq:04d}"


def create_picking_task(db: Session, package_id: int, assignee_id: int | None = None) -> PickingTask:
    """订单 assigned → picking 时生成拣货任务。

    按 allocation 汇总，同 SKU 合并，库位按 货架→列→层 排序（由前端展示，
    此处返回按路径排序后的拣货项数据）。
    """
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise ValueError("包裹不存在")
    assert_can_transition(pkg.status, "picking")

    # 生成任务号
    seq = (db.scalar(select(func.count()).select_from(PickingTask))) + 1
    task = PickingTask(
        task_no=_gen_task_no(seq),
        package_id=package_id,
        assignee_id=assignee_id,
        status="pending",
    )
    db.add(task)
    pkg.status = "picking"
    db.flush()
    return task


def pick_items_with_path(db: Session, package_id: int) -> list[dict]:
    """返回包裹的拣货项，按库位路径排序（货架→列→层），同 SKU 合并。"""
    rows = db.execute(
        select(Allocation, Stock, Location)
        .join(Stock, Allocation.stock_id == Stock.id)
        .join(Location, Stock.location_id == Location.id)
        .where(
            Allocation.package_item_id.in_(
                select(PackageItem.id).where(PackageItem.package_id == package_id)
            ),
            Allocation.status == "allocated",
        )
        .order_by(Location.shelf_no, Location.column_no, Location.layer_no)
    ).all()

    items: dict[int, dict] = {}
    for alloc, stock, loc in rows:
        key = alloc.sku_id
        if key not in items:
            items[key] = {
                "sku_id": alloc.sku_id,
                "total_qty": 0,
                "locations": [],
            }
        items[key]["total_qty"] += alloc.alloc_qty
        items[key]["locations"].append(
            {
                "location_code": loc.code,
                "shelf_no": loc.shelf_no,
                "column_no": loc.column_no,
                "layer_no": loc.layer_no,
                "qty": alloc.alloc_qty,
            }
        )
    return list(items.values())


def complete_picking(db: Session, task_id: int) -> None:
    """拣货完成：picking → checked。"""
    task = db.get(PickingTask, task_id)
    if task is None:
        raise ValueError("拣货任务不存在")
    pkg = db.get(Package, task.package_id)
    assert_can_transition(pkg.status, "checked")
    task.status = "done"
    task.picked_at = datetime.now()
    pkg.status = "checked"
    # 生成/更新复核记录
    packing = db.execute(
        select(Packing).where(Packing.package_id == pkg.id)
    ).scalars().first()
    if packing is None:
        packing = Packing(package_id=pkg.id, status="checked", checked_at=datetime.now())
        db.add(packing)
    else:
        packing.status = "checked"
        packing.checked_at = datetime.now()
    db.flush()


def check_package(db: Session, package_id: int, packer_id: int | None = None) -> None:
    """复核。"""
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise ValueError("包裹不存在")
    packing = db.execute(
        select(Packing).where(Packing.package_id == package_id)
    ).scalars().first()
    if packing is None:
        packing = Packing(package_id=package_id, packer_id=packer_id, status="checked", checked_at=datetime.now())
        db.add(packing)
    else:
        packing.status = "checked"
        packing.checked_at = datetime.now()
    db.flush()


def pack_package(db: Session, package_id: int, packer_id: int | None = None) -> None:
    """打包：checked → packed。"""
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise ValueError("包裹不存在")
    assert_can_transition(pkg.status, "packed")
    packing = db.execute(
        select(Packing).where(Packing.package_id == package_id)
    ).scalars().first()
    if packing is None:
        packing = Packing(package_id=package_id, packer_id=packer_id)
        db.add(packing)
    packing.status = "packed"
    packing.packed_at = datetime.now()
    pkg.status = "packed"
    db.flush()
