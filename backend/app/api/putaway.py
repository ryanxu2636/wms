"""库位/上架 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BizError
from app.models.master import Location
from app.schemas import PutawayConfirmIn, PutawayRecommendOut
from app.services import putaway_service

router = APIRouter(prefix="/putaway", tags=["库位/上架"])


@router.get("/locations")
def list_locations(
    status: str | None = None,
    shelf_no: str | None = None,
    db: Session = Depends(get_db),
):
    """库位列表（可按状态/货架过滤），按 货架→列→层 排序。"""
    q = select(Location)
    if status is not None:
        q = q.where(Location.status == status)
    if shelf_no is not None:
        q = q.where(Location.shelf_no == shelf_no)
    q = q.order_by(Location.shelf_no, Location.column_no, Location.layer_no)
    return db.execute(q).scalars().all()


@router.get("/recommend", response_model=PutawayRecommendOut)
def recommend(sku_id: int, db: Session = Depends(get_db)):
    """上架推荐（空库位/既有位）。"""
    loc_id = putaway_service.recommend_location(db, sku_id)
    return PutawayRecommendOut(sku_id=sku_id, to_location_id=loc_id)


@router.post("/confirm")
def confirm(payload: PutawayConfirmIn, db: Session = Depends(get_db)):
    """上架确认：库存从来源库位移到目标库位，更新库位状态。"""
    try:
        putaway_service.confirm_putaway(
            db,
            sku_id=payload.sku_id,
            from_location_id=payload.from_location_id,
            to_location_id=payload.to_location_id,
            qty=payload.qty,
            task_id=payload.task_id,
        )
        db.commit()
        return {"ok": True}
    except BizError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
