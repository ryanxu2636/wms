"""仓库/货架/库位 API（字段对齐数据字典）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Location, Shelf, Warehouse
from app.schemas import LocationCreate, ShelfCreate, WarehouseCreate

router = APIRouter(prefix="/warehouse", tags=["库位管理"])


@router.post("", status_code=201)
def create_warehouse(payload: WarehouseCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(Warehouse).where(Warehouse.code == payload.code))
    if exists:
        raise HTTPException(status_code=409, detail="仓库已存在")
    wh = Warehouse(**payload.model_dump())
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return {"id": wh.id, "code": wh.code, "name": wh.name}


@router.get("")
def list_warehouses(db: Session = Depends(get_db)):
    return db.scalars(select(Warehouse)).all()


@router.post("/shelf", status_code=201)
def create_shelf(payload: ShelfCreate, db: Session = Depends(get_db)):
    wh = db.get(Warehouse, payload.warehouse_id)
    if not wh:
        raise HTTPException(status_code=404, detail="仓库不存在")
    shelf = Shelf(**payload.model_dump())
    db.add(shelf)
    db.commit()
    db.refresh(shelf)
    return {"id": shelf.id, "code": shelf.code}


@router.post("/location", status_code=201)
def create_location(payload: LocationCreate, db: Session = Depends(get_db)):
    shelf = db.get(Shelf, payload.shelf_id)
    if not shelf:
        raise HTTPException(status_code=404, detail="货架不存在")
    exists = db.scalar(select(Location).where(Location.code == payload.code))
    if exists:
        raise HTTPException(status_code=409, detail="库位已存在")
    loc = Location(**payload.model_dump())
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return {"id": loc.id, "code": loc.code, "status": loc.status}


@router.get("/location")
def list_locations(shelf_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Location)
    if shelf_id:
        stmt = stmt.where(Location.shelf_id == shelf_id)
    return db.scalars(stmt.order_by(Location.code)).all()
