"""打印 API：三类型识别 + 打印队列 + 云途面单 + 标记打印。

5 个接口（S3 方案 §3.3）：
- POST /api/print/classify                包裹类型识别
- POST /api/print/queue                   创建打印队列项（打包完成）
- GET  /api/print/queue                   查询打印队列
- POST /api/print/labels/pdf              批量打印（云途面单）
- POST /api/print/labels/mark-printed     标记已打印（人工）
- POST /api/print/queue/{id}/retry        重试失败队列项
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BizError
from app.services import print_service

router = APIRouter(prefix="/print", tags=["打印"])


@router.post("/classify")
def classify(payload: dict, db: Session = Depends(get_db)):
    """包裹类型识别：single_single / single_multi / multi_sku。"""
    package_id = payload.get("package_id")
    if package_id is None:
        raise HTTPException(400, "缺少 package_id")
    try:
        ptype = print_service.classify_package(db, package_id)
        return {"package_id": package_id, "type": ptype}
    except BizError as e:
        raise HTTPException(e.status_code, e.message)


@router.post("/queue")
def create_queue(payload: dict, db: Session = Depends(get_db)):
    """打包完成后生成打印队列项。"""
    package_id = payload.get("package_id")
    if package_id is None:
        raise HTTPException(400, "缺少 package_id")
    try:
        q = print_service.create_print_queue(db, package_id)
        db.commit()
        return {"id": q.id, "package_id": q.package_id, "status": q.status}
    except BizError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)


@router.get("/queue")
def list_queue(status: str | None = None, db: Session = Depends(get_db)):
    """查询打印队列，可按 status 过滤。"""
    return print_service.list_queue(db, status)


@router.post("/labels/pdf")
def print_labels(payload: dict, db: Session = Depends(get_db)):
    """批量打印：调用云途获取面单 URL，更新队列与出库卡点。"""
    queue_ids = payload.get("queue_ids")
    try:
        result = print_service.process_queue(db, queue_ids)
        db.commit()
        return {
            "ok": True,
            "success": result["success"],
            "failed": result["failed"],
            "labels": result["labels"],
        }
    except BizError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)


@router.post("/labels/mark-printed")
def mark_printed(payload: dict, db: Session = Depends(get_db)):
    """手动标记包裹已打印（跳过云途）。"""
    package_id = payload.get("package_id")
    if package_id is None:
        raise HTTPException(400, "缺少 package_id")
    try:
        result = print_service.mark_label_printed(db, package_id)
        db.commit()
        return result
    except BizError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)


@router.post("/queue/{queue_id}/retry")
def retry(queue_id: int, db: Session = Depends(get_db)):
    """重试失败的打印队列项。"""
    try:
        result = print_service.retry_queue(db, queue_id)
        db.commit()
        return result
    except BizError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)
