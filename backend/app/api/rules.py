"""虚拟/标记规则 API（字段对齐数据字典 §7.3）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import VirtualRule
from app.schemas import VirtualRuleCreate, VirtualRuleOut

router = APIRouter(prefix="/rules", tags=["规则配置"])


@router.get("", response_model=list[VirtualRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.scalars(select(VirtualRule).order_by(VirtualRule.priority)).all()


@router.post("", response_model=VirtualRuleOut, status_code=201)
def create_rule(payload: VirtualRuleCreate, db: Session = Depends(get_db)):
    exists = db.scalar(
        select(VirtualRule).where(VirtualRule.match_value == payload.match_value)
    )
    if exists:
        raise HTTPException(status_code=409, detail=f"规则已存在：{payload.match_value}")
    rule = VirtualRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(VirtualRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    db.commit()
