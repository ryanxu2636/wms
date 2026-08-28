"""库存服务：所有库存变动的唯一入口，强制流水留痕与数量守恒。

约束：
- 只允许通过本服务的方法变更 stock 数量，禁止直接 UPDATE。
- 每次变动必须在同一事务内写 stock_transaction（before/after 留痕）。
- 分配阶段：available_qty → allocated_qty；出库阶段：扣 allocated_qty（不二次扣 available）。
"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import InsufficientStockError
from app.models.inventory import Stock, StockTransaction


def _lock_stock_rows(db: Session, stock_ids: list[int]) -> dict[int, Stock]:
    """按 id 升序加行锁，返回 {stock_id: Stock}，避免死锁。"""
    if not stock_ids:
        return {}
    rows = db.execute(
        select(Stock).where(Stock.id.in_(sorted(stock_ids))).with_for_update()
    ).scalars().all()
    return {r.id: r for r in rows}


def _write_txn(
    db: Session,
    *,
    stock: Stock,
    change_type: str,
    change_qty: int,
    before_qty: int,
    after_qty: int,
    ref_type: str | None = None,
    ref_id: int | None = None,
    remark: str | None = None,
) -> None:
    """写一条库存流水。change_qty 为负表示扣减。"""
    db.add(
        StockTransaction(
            stock_id=stock.id,
            sku_id=stock.sku_id,
            change_type=change_type,
            change_qty=change_qty,
            before_qty=before_qty,
            after_qty=after_qty,
            ref_type=ref_type,
            ref_id=ref_id,
            remark=remark,
        )
    )


def _move(
    db: Session,
    stock: Stock,
    from_field: str,
    to_field: str,
    qty: int,
    change_type: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> None:
    """在 stock 行内做数量转移（如 available→allocated），并留痕。

    以 allocated 字段为记账基准写一条流水（记录目标字段的 before/after）。
    """
    from_val = getattr(stock, from_field)
    if from_val < qty:
        raise InsufficientStockError(
            f"stock#{stock.id}", qty, from_val
        )
    before = getattr(stock, to_field)
    setattr(stock, from_field, from_val - qty)
    setattr(stock, to_field, before + qty)
    _write_txn(
        db,
        stock=stock,
        change_type=change_type,
        change_qty=qty,
        before_qty=before,
        after_qty=before + qty,
        ref_type=ref_type,
        ref_id=ref_id,
    )


def allocate(db: Session, stock_id: int, qty: int, ref_type: str, ref_id: int) -> None:
    """分配：available → allocated，锁定可用库存。"""
    stock = _lock_stock_rows(db, [stock_id])[stock_id]
    _move(db, stock, "available_qty", "allocated_qty", qty, "allocate", ref_type, ref_id)


def release(db: Session, stock_id: int, qty: int, ref_type: str, ref_id: int) -> None:
    """释放：allocated → available，取消锁定。"""
    stock = _lock_stock_rows(db, [stock_id])[stock_id]
    _move(db, stock, "allocated_qty", "available_qty", qty, "release", ref_type, ref_id)


def outbound_deduct(db: Session, stock_id: int, qty: int, ref_type: str, ref_id: int) -> None:
    """出库：扣减 allocated_qty（分配阶段已从 available 挪出）。"""
    stock = _lock_stock_rows(db, [stock_id])[stock_id]
    if stock.allocated_qty < qty:
        raise InsufficientStockError(f"stock#{stock.id}", qty, stock.allocated_qty)
    before = stock.allocated_qty
    stock.allocated_qty = before - qty
    _write_txn(
        db,
        stock=stock,
        change_type="outbound",
        change_qty=-qty,
        before_qty=before,
        after_qty=stock.allocated_qty,
        ref_type=ref_type,
        ref_id=ref_id,
    )


def inbound(db: Session, stock_id: int, qty: int, ref_type: str, ref_id: int) -> None:
    """入库：available 增加。"""
    stock = _lock_stock_rows(db, [stock_id])[stock_id]
    before = stock.available_qty
    stock.available_qty = before + qty
    _write_txn(
        db,
        stock=stock,
        change_type="inbound",
        change_qty=qty,
        before_qty=before,
        after_qty=stock.available_qty,
        ref_type=ref_type,
        ref_id=ref_id,
    )


def adjust(db: Session, stock_id: int, delta: int, remark: str) -> None:
    """盘点调整：直接增减 available，必须授权+备注。"""
    stock = _lock_stock_rows(db, [stock_id])[stock_id]
    before = stock.available_qty
    after = before + delta
    if after < 0:
        raise InsufficientStockError(f"stock#{stock.id}", -delta, before)
    stock.available_qty = after
    _write_txn(
        db,
        stock=stock,
        change_type="adjust",
        change_qty=delta,
        before_qty=before,
        after_qty=after,
        remark=remark,
    )


def transfer(db: Session, from_stock_id: int, to_stock_id: int, qty: int, remark: str) -> None:
    """库位调拨：一个 stock 行减、另一个加。"""
    stocks = _lock_stock_rows(db, [from_stock_id, to_stock_id])
    src = stocks[from_stock_id]
    dst = stocks[to_stock_id]

    # 源扣减（available）
    if src.available_qty < qty:
        raise InsufficientStockError(f"stock#{src.id}", qty, src.available_qty)
    src_before = src.available_qty
    src.available_qty = src_before - qty
    _write_txn(
        db, stock=src, change_type="transfer", change_qty=-qty,
        before_qty=src_before, after_qty=src.available_qty, remark=remark,
    )

    # 目标增加（available）
    dst_before = dst.available_qty
    dst.available_qty = dst_before + qty
    _write_txn(
        db, stock=dst, change_type="transfer", change_qty=qty,
        before_qty=dst_before, after_qty=dst.available_qty, remark=remark,
    )


def get_available(db: Session, stock_id: int) -> int:
    stock = db.get(Stock, stock_id)
    return stock.available_qty if stock else 0
