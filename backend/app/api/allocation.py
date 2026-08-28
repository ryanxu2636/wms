"""库存分配 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import AllocateIn, ReleaseIn
from app.services import allocation_service

router = APIRouter(prefix="/orders", tags=["订单分配"])


@router.post("/allocate")
def allocate(payload: AllocateIn, db: Session = Depends(get_db)):
    try:
        allocation_service.allocate_package(db, payload.package_id)
        db.commit()
        return {"ok": True, "package_id": payload.package_id}
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(409, str(e))


@router.post("/release")
def release(payload: ReleaseIn, db: Session = Depends(get_db)):
    """释放分配（取消/拦截/复核驳回时调用），库存回退。"""
    try:
        allocation_service.release_package(db, payload.package_id)
        db.commit()
        return {"ok": True, "package_id": payload.package_id}
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
