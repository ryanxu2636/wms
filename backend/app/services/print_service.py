"""打印服务：三类型包裹识别 + 打印队列 + 云途面单对接 + 打印卡点。

对齐 S3 技术方案 §3.1-3.3 与数据字典 §8：
- 三种包裹类型：single_single（单品单件）/ single_multi（单品多件）/ multi_sku（多品）
- virtual / marker 明细不参与打印
- 打印队列状态机：queued → printing → success / failed
- 打印卡点：outbound.label_printed == 0 时禁止出库（由 outbound_service 执行）
"""
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.exceptions import BizError
from app.models.fulfillment import Outbound, Package, PackageItem
from app.models.print_domain import PrintQueue, PrintTemplate
from app.services import yuntu_client


def classify_package(db: Session, package_id: int) -> str:
    """识别包裹类型。

    规则（S3 方案 §3.1，verbatim）：
    - 过滤掉 virtual / marker 明细
    - 单品单件：非虚拟/非标记 SKU 仅 1 种 且 总数 1
    - 单品多件：非虚拟/非标记 SKU 仅 1 种 且 总数 > 1
    - 多品：其余
    """
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise BizError("包裹不存在", 404)

    items = db.execute(
        select(PackageItem).where(
            PackageItem.package_id == package_id,
            PackageItem.is_virtual == 0,
            PackageItem.is_marker == 0,
        )
    ).scalars().all()

    distinct_skus = len({item.sku_id for item in items})
    total_qty = sum(item.qty for item in items)

    if distinct_skus == 1 and total_qty == 1:
        return "single_single"
    if distinct_skus == 1:
        return "single_multi"
    return "multi_sku"


def _get_or_create_template(db: Session, template_type: str = "label") -> PrintTemplate:
    """获取或创建默认打印模板（label）。"""
    tpl = db.execute(
        select(PrintTemplate).where(PrintTemplate.template_type == template_type)
    ).scalars().first()
    if tpl is None:
        tpl = PrintTemplate(name=f"默认{template_type}模板", template_type=template_type)
        db.add(tpl)
        db.flush()
    return tpl


def create_print_queue(db: Session, package_id: int) -> PrintQueue:
    """打包完成后为包裹生成打印队列项（status=queued）。"""
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise BizError("包裹不存在", 404)
    if pkg.status != "packed":
        raise BizError("仅已打包(packed)的包裹可进入打印队列", 409)

    # 幂等：已有 queued/printing 的队列项则直接返回
    existing = db.execute(
        select(PrintQueue).where(
            PrintQueue.package_id == package_id,
            PrintQueue.status.in_(["queued", "printing"]),
        )
    ).scalars().first()
    if existing:
        return existing

    tpl = _get_or_create_template(db)
    q = PrintQueue(package_id=package_id, template_id=tpl.id, status="queued")
    db.add(q)
    db.flush()
    return q


def list_queue(db: Session, status: str | None = None) -> list[dict]:
    """查询打印队列，附带包裹号、运单号与类型。"""
    stmt = select(PrintQueue).order_by(PrintQueue.id.desc())
    if status:
        stmt = stmt.where(PrintQueue.status == status)
    rows = db.execute(stmt).scalars().all()

    out = []
    for q in rows:
        pkg = db.get(Package, q.package_id)
        out.append({
            "id": q.id,
            "package_id": q.package_id,
            "package_no": pkg.package_no if pkg else None,
            "tracking_no": pkg.tracking_no if pkg else None,
            "status": q.status,
            "retry_count": q.retry_count,
            "printed_at": q.printed_at.isoformat() if q.printed_at else None,
        })
    return out


def _mark_printed_for_package(db: Session, package_id: int) -> None:
    """将包裹对应的 outbound 标记为已打印（打印卡点放开）。"""
    ob = db.execute(
        select(Outbound).where(Outbound.package_id == package_id)
    ).scalars().first()
    if ob is not None and not ob.label_printed:
        ob.label_printed = 1
        db.flush()


def process_queue(db: Session, queue_ids: list[int] | None = None) -> dict:
    """执行打印：调用云途获取面单，更新队列状态与 outbound.label_printed。

    - queue_ids 为空时处理所有 queued/failed 项
    - 成功：status=success，printed_at=now，outbound.label_printed=1
    - 失败：status=failed，retry_count += 1
    返回 {success: n, failed: n, labels: {tracking_no: url}}
    """
    stmt = select(PrintQueue).where(PrintQueue.status.in_(["queued", "failed"]))
    if queue_ids:
        stmt = stmt.where(PrintQueue.id.in_(queue_ids))
    items = db.execute(stmt).scalars().all()

    # 收集 tracking_no（运单号）→ 队列项映射
    tno_to_queue: dict[str, list[PrintQueue]] = {}
    for q in items:
        pkg = db.get(Package, q.package_id)
        if pkg is None:
            continue
        q.status = "printing"
        tno_to_queue.setdefault(pkg.tracking_no, []).append(q)
    db.flush()

    tracking_nos = list(tno_to_queue.keys())
    labels: dict[str, str] = {}
    try:
        labels = yuntu_client.fetch_labels(tracking_nos)
    except Exception as e:  # noqa: BLE001 —— 云途整体异常按全失败处理
        labels = {}

    success = 0
    failed = 0
    for tno, qs in tno_to_queue.items():
        url = labels.get(tno)
        if url:
            for q in qs:
                q.status = "success"
                q.printed_at = datetime.now()
                _mark_printed_for_package(db, q.package_id)
                success += 1
        else:
            for q in qs:
                q.status = "failed"
                q.retry_count += 1
                failed += 1
    db.flush()

    return {"success": success, "failed": failed, "labels": labels}


def retry_queue(db: Session, queue_id: int) -> dict:
    """重试单个失败的打印队列项。"""
    q = db.get(PrintQueue, queue_id)
    if q is None:
        raise BizError("打印队列项不存在", 404)
    if q.status == "success":
        raise BizError("该队列项已打印成功，无需重试", 409)

    result = process_queue(db, queue_ids=[queue_id])
    q = db.get(PrintQueue, queue_id)  # 刷新
    return {
        "id": q.id,
        "status": q.status,
        "retry_count": q.retry_count,
        "printed_at": q.printed_at.isoformat() if q.printed_at else None,
    }


def mark_label_printed(db: Session, package_id: int) -> dict:
    """手动标记包裹已打印（跳过云途，供人工打印场景）。"""
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise BizError("包裹不存在", 404)
    _mark_printed_for_package(db, package_id)

    # 若存在队列项，同步置为 success
    items = db.execute(
        select(PrintQueue).where(
            PrintQueue.package_id == package_id,
            PrintQueue.status != "success",
        )
    ).scalars().all()
    for q in items:
        q.status = "success"
        q.printed_at = datetime.now()
    db.flush()
    return {"package_id": package_id, "label_printed": 1}
