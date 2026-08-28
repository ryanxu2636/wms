"""出库 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BizError
from app.models.fulfillment import Outbound
from app.schemas import OutboundMarkPrintedIn, OutboundShipIn
from app.services import outbound_service

router = APIRouter(prefix="/outbound", tags=["出库"])


@router.get("/by_package/{package_id}")
def get_by_package(package_id: int, db: Session = Depends(get_db)):
    """按包裹 ID 查出库单（前端出库/面单操作需要 outbound_id）。"""
    ob = db.execute(
        select(Outbound).where(Outbound.package_id == package_id)
    ).scalars().first()
    if ob is None:
        raise HTTPException(404, "出库单不存在")
    return {"outbound_id": ob.id, "outbound_no": ob.outbound_no, "status": ob.status, "label_printed": ob.label_printed}


@router.post("/mark_printed")
def mark_printed(payload: OutboundMarkPrintedIn, db: Session = Depends(get_db)):
    """标记面单已打印（S2 桩实现，供出库卡点使用）。"""
    try:
        outbound_service.mark_label_printed(db, payload.outbound_id)
        db.commit()
        return {"ok": True}
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.post("/ship")
def ship(payload: OutboundShipIn, db: Session = Depends(get_db)):
    try:
        outbound_service.ship(db, payload.outbound_id)
        db.commit()
        return {"ok": True, "outbound_id": payload.outbound_id}
    except BizError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
