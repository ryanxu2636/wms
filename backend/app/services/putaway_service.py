"""库位与上架推荐服务。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InsufficientStockError
from app.models.inventory import Stock
from app.models.master import Location
from app.models.purchase import PutawayTask
from app.services import stock_service


def recommend_location(db: Session, sku_id: int) -> int | None:
    """上架推荐：
    1. 优先推荐已有该 SKU 的库位（一品多库位，补入既有位）。
    2. 否则按 货架→列→层 升序找第一个 empty 库位。
    返回 location.id，无空位返回 None。
    """
    # 1. 已有该 SKU 且未满的库位
    existing = db.execute(
        select(Location)
        .join(Stock, Stock.location_id == Location.id)
        .where(Stock.sku_id == sku_id, Location.status.in_(["empty", "occupied"]))
        .order_by(Location.shelf_no, Location.column_no, Location.layer_no)
        .limit(1)
    ).scalars().first()
    if existing:
        return existing.id

    # 2. 第一个空库位
    empty = db.execute(
        select(Location)
        .where(Location.status == "empty")
        .order_by(Location.shelf_no, Location.column_no, Location.layer_no)
        .limit(1)
    ).scalars().first()
    return empty.id if empty else None


def confirm_putaway(
    db: Session,
    *,
    sku_id: int,
    from_location_id: int,
    to_location_id: int,
    qty: int,
    task_id: int | None = None,
) -> None:
    """上架确认：把库存从来源库位移到目标库位，并更新库位状态。

    - 来源库位库存扣减（暂存区 → 目标库位）
    - 目标库位库存增加（复用已有 stock 行或新建）
    - 目标库位状态 empty → occupied
    - 关联 putaway_task → done
    """
    from sqlalchemy import select as _select

    # 1. 查找来源库位该 SKU 的库存行
    src_stock = db.execute(
        _select(Stock).where(
            Stock.sku_id == sku_id,
            Stock.location_id == from_location_id,
        ).with_for_update()
    ).scalars().first()

    if src_stock is None or src_stock.available_qty < qty:
        avail = src_stock.available_qty if src_stock else 0
        raise InsufficientStockError(f"sku#{sku_id}@loc#{from_location_id}", qty, avail)

    # 2. 查找/新建目标库位该 SKU 的库存行
    dst_stock = db.execute(
        _select(Stock).where(
            Stock.sku_id == sku_id,
            Stock.location_id == to_location_id,
        ).with_for_update()
    ).scalars().first()

    if dst_stock is None:
        dst_stock = Stock(
            sku_id=sku_id,
            location_id=to_location_id,
            batch_no=src_stock.batch_no,
            production_date=src_stock.production_date,
            expiry_date=src_stock.expiry_date,
            available_qty=0,
            allocated_qty=0,
            locked_qty=0,
            in_transit_qty=0,
        )
        db.add(dst_stock)
        db.flush()

    # 3. 用 transfer 完成库存移动（一减一增，留痕）
    stock_service.transfer(db, src_stock.id, dst_stock.id, qty, f"上架确认 task#{task_id or '-'}")

    # 4. 更新库位状态
    dst_loc = db.get(Location, to_location_id)
    if dst_loc and dst_loc.status == "empty":
        dst_loc.status = "occupied"

    src_loc = db.get(Location, from_location_id)
    if src_loc and src_stock.available_qty == 0 and src_stock.allocated_qty == 0:
        src_loc.status = "empty"

    # 5. 更新上架任务
    if task_id is not None:
        task = db.get(PutawayTask, task_id)
        if task is not None:
            task.status = "done"
            task.to_location_id = to_location_id
