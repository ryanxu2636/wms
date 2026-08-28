"""库存 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BizError
from app.models.inventory import Stock, StockTransaction
from app.schemas import AdjustIn, TransferIn
from app.services import stock_service

router = APIRouter(prefix="/stock", tags=["库存"])


@router.get("")
def list_stock(
    sku_id: int | None = None,
    location_id: int | None = None,
    batch_no: str | None = None,
    db: Session = Depends(get_db),
):
    q = select(Stock)
    if sku_id is not None:
        q = q.where(Stock.sku_id == sku_id)
    if location_id is not None:
        q = q.where(Stock.location_id == location_id)
    if batch_no is not None:
        q = q.where(Stock.batch_no == batch_no)
    return db.execute(q).scalars().all()


@router.get("/{stock_id}/transactions")
def list_transactions(stock_id: int, db: Session = Depends(get_db)):
    return db.execute(
        select(StockTransaction)
        .where(StockTransaction.stock_id == stock_id)
        .order_by(StockTransaction.id.desc())
    ).scalars().all()


@router.post("/adjust")
def adjust(payload: AdjustIn, db: Session = Depends(get_db)):
    try:
        stock_service.adjust(db, payload.stock_id, payload.delta, payload.remark)
        db.commit()
        return {"ok": True}
    except BizError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)


@router.post("/transfer")
def transfer(payload: TransferIn, db: Session = Depends(get_db)):
    try:
        stock_service.transfer(db, payload.from_stock_id, payload.to_stock_id, payload.qty, payload.remark)
        db.commit()
        return {"ok": True}
    except BizError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)
