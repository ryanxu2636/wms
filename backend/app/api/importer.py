"""导入引擎 API：上传 Excel、预览、确认导入、复核队列。"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ImportBatch, ReviewQueue
from app.services.importer.importer import commit_import, preview

router = APIRouter(prefix="/import", tags=["导入引擎"])


@router.post("/preview")
async def preview_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """阶段一：上传 Excel → 解析 + 校验 → 预览（不写主数据）。"""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    try:
        result = preview(content, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/commit")
async def confirm_import(
    file: UploadFile = File(...),
    operator: str = "",
    overwrite: bool = False,
    db: Session = Depends(get_db),
):
    """阶段二：确认导入（事务写入）。"""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    try:
        result = commit_import(content, db, operator=operator, overwrite=overwrite)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/batches")
def list_batches(db: Session = Depends(get_db)):
    return db.scalars(select(ImportBatch).order_by(ImportBatch.id.desc())).all()


@router.get("/review")
def list_reviews(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(ReviewQueue)
    if status:
        stmt = stmt.where(ReviewQueue.status == status)
    return db.scalars(stmt.order_by(ReviewQueue.id.desc())).all()


@router.post("/review/{review_id}/resolve")
def resolve_review(review_id: int, resolution: str, status: str = "resolved", db: Session = Depends(get_db)):
    """处理人工复核项。"""
    from datetime import datetime, timezone

    item = db.get(ReviewQueue, review_id)
    if not item:
        raise HTTPException(status_code=404, detail="复核项不存在")
    item.resolution = resolution
    item.status = status
    item.handled_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": item.id, "status": item.status, "resolution": item.resolution}
