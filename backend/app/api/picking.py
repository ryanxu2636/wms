"""拣货/复核/打包 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.fulfillment import Package, PickingTask
from app.schemas import CheckIn, PackIn, PickingCreateIn, PickingCompleteIn
from app.services import picking_service

router = APIRouter(prefix="/picking", tags=["拣货/复核/打包"])


@router.get("/orders")
def list_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """订单列表（可按状态过滤），供订单分配/拣货页面使用。"""
    q = select(Package)
    if status is not None:
        q = q.where(Package.status == status)
    q = q.order_by(Package.sla_deadline.asc().nulls_last(), Package.id.desc())
    return db.execute(q).scalars().all()


@router.post("/tasks")
def create_task(payload: PickingCreateIn, db: Session = Depends(get_db)):
    try:
        task = picking_service.create_picking_task(db, payload.package_id, payload.assignee_id)
        db.commit()
        return {"ok": True, "task_id": task.id, "task_no": task.task_no}
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("/{package_id}/items")
def pick_items(package_id: int, db: Session = Depends(get_db)):
    return picking_service.pick_items_with_path(db, package_id)


@router.get("/package/{package_id}/task")
def get_task(package_id: int, db: Session = Depends(get_db)):
    """按包裹 ID 查询其拣货任务（前端「拣货完成」需要 task_id）。"""
    task = db.execute(
        select(PickingTask)
        .where(PickingTask.package_id == package_id, PickingTask.status == "pending")
    ).scalars().first()
    if task is None:
        raise HTTPException(404, "无待完成拣货任务")
    return {"task_id": task.id, "task_no": task.task_no}


@router.post("/tasks/complete")
def complete_task(payload: PickingCompleteIn, db: Session = Depends(get_db)):
    try:
        picking_service.complete_picking(db, payload.task_id)
        db.commit()
        return {"ok": True}
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.post("/check")
def check(payload: CheckIn, db: Session = Depends(get_db)):
    """复核。"""
    try:
        picking_service.check_package(db, payload.package_id, payload.packer_id)
        db.commit()
        return {"ok": True}
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.post("/{package_id}/pack")
def pack(package_id: int, payload: PackIn | None = None, db: Session = Depends(get_db)):
    try:
        packer_id = payload.packer_id if payload else None
        picking_service.pack_package(db, package_id, packer_id)
        db.commit()
        return {"ok": True}
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
