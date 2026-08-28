"""SKU 与 BOM 相关 API（字段对齐数据字典）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Bom, Sku
from app.schemas import BomCreate, SkuCreate, SkuOut, SkuUpdate

router = APIRouter(prefix="/sku", tags=["SKU 主数据"])


@router.get("", response_model=list[SkuOut])
def list_skus(
    sku_type: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Sku)
    if sku_type:
        stmt = stmt.where(Sku.sku_type == sku_type)
    if keyword:
        stmt = stmt.where(Sku.sku_code.ilike(f"%{keyword}%") | Sku.sku_name.ilike(f"%{keyword}%"))
    stmt = stmt.order_by(Sku.id)
    return db.scalars(stmt).all()


@router.post("", response_model=SkuOut, status_code=201)
def create_sku(payload: SkuCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(Sku).where(Sku.sku_code == payload.sku_code))
    if exists:
        raise HTTPException(status_code=409, detail=f"SKU 已存在：{payload.sku_code}")
    sku = Sku(**payload.model_dump())
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku


@router.get("/{sku_id}", response_model=SkuOut)
def get_sku(sku_id: int, db: Session = Depends(get_db)):
    sku = db.get(Sku, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU 不存在")
    return sku


@router.patch("/{sku_id}", response_model=SkuOut)
def update_sku(sku_id: int, payload: SkuUpdate, db: Session = Depends(get_db)):
    sku = db.get(Sku, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU 不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(sku, k, v)
    db.commit()
    db.refresh(sku)
    return sku


# ── BOM ──
@router.post("/bom", status_code=201)
def create_bom(payload: BomCreate, db: Session = Depends(get_db)):
    combo = db.scalar(select(Sku).where(Sku.sku_code == payload.combo_sku_code))
    if not combo:
        raise HTTPException(status_code=404, detail=f"组合 SKU 不存在：{payload.combo_sku_code}")
    if combo.sku_type != "combo":
        raise HTTPException(status_code=400, detail="BOM 的组合 SKU 必须是「combo」类型")

    for comp in payload.components:
        component = db.scalar(select(Sku).where(Sku.sku_code == comp.component_sku_code))
        if not component:
            raise HTTPException(status_code=404, detail=f"子 SKU 不存在：{comp.component_sku_code}")
        if component.id == combo.id:
            raise HTTPException(status_code=400, detail="组合 SKU 不能包含自身")

    # 简单处理：先删旧 BOM 再重建（单层无嵌套）
    db.query(Bom).filter(Bom.combo_sku_id == combo.id).delete()
    for comp in payload.components:
        component = db.scalar(select(Sku).where(Sku.sku_code == comp.component_sku_code))
        db.add(Bom(combo_sku_id=combo.id, component_sku_id=component.id, qty=comp.qty))
    db.commit()
    return {"combo_sku_code": payload.combo_sku_code, "components": len(payload.components)}


@router.get("/{sku_id}/bom")
def get_bom(sku_id: int, db: Session = Depends(get_db)):
    sku = db.get(Sku, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU 不存在")
    rows = db.scalars(select(Bom).where(Bom.combo_sku_id == sku_id)).all()
    return [
        {
            "component_sku_code": row.component_sku.sku_code,
            "qty": row.qty,
        }
        for row in rows
    ]
