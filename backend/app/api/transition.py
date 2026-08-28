"""订单状态机 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BizError
from app.core.state_machine import ALLOWED_TRANSITIONS, PackageStatus
from app.models.fulfillment import Package
from app.schemas import TransitionIn

router = APIRouter(prefix="/orders", tags=["订单状态机"])


@router.get("/{package_id}/state")
def get_state(package_id: int, db: Session = Depends(get_db)):
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise HTTPException(404, "包裹不存在")
    allowed = [t.value for t in ALLOWED_TRANSITIONS.get(PackageStatus(pkg.status), set())]
    return {"package_id": package_id, "status": pkg.status, "allowed_transitions": allowed}


@router.post("/transition")
def transition(payload: TransitionIn, db: Session = Depends(get_db)):
    from app.core.state_machine import assert_can_transition

    pkg = db.get(Package, payload.package_id)
    if pkg is None:
        raise HTTPException(404, "包裹不存在")
    try:
        assert_can_transition(pkg.status, payload.target)
        pkg.status = payload.target
        db.commit()
        return {"ok": True, "status": payload.target}
    except BizError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)
