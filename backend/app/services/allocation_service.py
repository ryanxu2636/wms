"""库存分配服务：订单分配（锁定库存）+ BOM 展开 + 缺货挂起。

关键点：
- SKU 分流：base 直接锁；combo 按 BOM 展开到子件；virtual(YUN) 跳过；marker 走拦截/人工复核。
- BOM 解析用「最后一个 *」切分数量（数据字典点名的陷阱）。
- 组合 SKU 虚拟库存 = min(子件可用 ÷ 用量)。
- 任一子件不足 → 整单原子回滚，package → shortage_hold。
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InsufficientStockError
from app.models.fulfillment import Package, PackageItem
from app.models.inventory import Allocation, Stock
from app.models.master import Bom, Sku
from app.services import stock_service

# sku_type 常量
SKU_TYPE_BASE = "base"
SKU_TYPE_COMBO = "combo"
SKU_TYPE_VIRTUAL = "virtual"
SKU_TYPE_MARKER = "marker"


@dataclass
class ComponentNeed:
    """BOM 展开后的子件需求。"""

    sku_id: int
    per_qty: int  # 单个组合的子件用量


def parse_bom_segment(seg: str) -> tuple[str, int]:
    """解析 BOM 段 `子SKU*数量`，用「最后一个 *」切分数量。

    SKU 名可能含 *（如 CS190-Dark grey-130*150CM），必须 rfind。
    """
    seg = seg.strip()
    idx = seg.rfind("*")
    if idx == -1:
        return seg, 1
    comp = seg[:idx].strip()
    try:
        qty = int(seg[idx + 1:].strip())
    except ValueError:
        qty = 1
    return comp, qty


def expand_bom(db: Session, combo_sku_id: int) -> list[ComponentNeed]:
    """把组合 SKU 展开为叶子子件需求列表（递归，子件也可能为 combo）。"""
    rows = db.execute(
        select(Bom).where(Bom.combo_sku_id == combo_sku_id).order_by(Bom.sort_order)
    ).scalars().all()

    result: list[ComponentNeed] = []
    for b in rows:
        comp = db.get(Sku, b.component_sku_id)
        if comp is None:
            continue
        if comp.sku_type == SKU_TYPE_COMBO:
            # 递归展开嵌套组合
            for sub in expand_bom(db, comp.id):
                result.append(ComponentNeed(sub.sku_id, sub.per_qty * b.qty))
        elif comp.sku_type in (SKU_TYPE_BASE,):
            result.append(ComponentNeed(comp.id, b.qty))
        # marker/virtual 子件不参与实物锁定
    return result


def _lock_base(db: Session, sku_id: int, need_qty: int, ref_type: str, ref_id: int) -> list[Allocation]:
    """锁定 base SKU 库存，按近效期/批次顺序。返回生成的 allocation。"""
    rows = db.execute(
        select(Stock)
        .where(Stock.sku_id == sku_id, Stock.available_qty > 0)
        .order_by(Stock.expiry_date.asc().nulls_last(), Stock.production_date.asc())
        .with_for_update()
    ).scalars().all()

    remaining = need_qty
    allocations: list[Allocation] = []
    for s in rows:
        if remaining <= 0:
            break
        take = min(s.available_qty, remaining)
        stock_service.allocate(db, s.id, take, ref_type, ref_id)
        alloc = Allocation(
            package_item_id=ref_id,
            sku_id=sku_id,
            stock_id=s.id,
            alloc_qty=take,
            status="allocated",
        )
        db.add(alloc)
        allocations.append(alloc)
        remaining -= take

    if remaining > 0:
        raise InsufficientStockError(f"sku#{sku_id}", need_qty, need_qty - remaining)
    return allocations


def allocate_package(db: Session, package_id: int) -> None:
    """为单个包裹做库存分配；不足则整单回滚并挂起。

    使用 savepoint（nested transaction）包裹分配逻辑：
    - 分配成功：pkg → assigned
    - 任一子件不足：仅回滚 savepoint 内的库存锁定，pkg → shortage_hold
      （不回滚外层事务，保证挂起状态能正常落库）
    """
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise ValueError(f"package {package_id} 不存在")
    if pkg.status != "unassigned":
        raise ValueError(f"package {package_id} 非待分配状态：{pkg.status}")

    items = db.execute(
        select(PackageItem).where(PackageItem.package_id == package_id)
    ).scalars().all()

    try:
        with db.begin_nested():  # savepoint
            for item in items:
                sku = db.get(Sku, item.sku_id)
                if sku is None:
                    continue
                need_qty = item.qty - item.picked_qty
                if need_qty <= 0:
                    continue

                if sku.sku_type == SKU_TYPE_VIRTUAL:
                    continue  # YUN 免库存
                if sku.sku_type == SKU_TYPE_MARKER:
                    # 标记 SKU 不参与分配，由上层决定拦截/人工复核
                    continue

                if sku.sku_type == SKU_TYPE_COMBO:
                    for comp in expand_bom(db, sku.id):
                        _lock_base(db, comp.sku_id, need_qty * comp.per_qty, "ALLOCATE", item.id)
                else:  # base
                    _lock_base(db, sku.id, need_qty, "ALLOCATE", item.id)

        pkg.status = "assigned"
        db.flush()
    except InsufficientStockError:
        pkg.status = "shortage_hold"
        db.flush()


def release_package(db: Session, package_id: int) -> None:
    """释放包裹的库存分配（取消/拦截/复核驳回时调用）。

    - 将所有 allocated 状态的 allocation 释放（allocated → available）
    - allocation.status → released
    - package 回到 unassigned（可重新分配）
    """
    pkg = db.get(Package, package_id)
    if pkg is None:
        raise ValueError(f"package {package_id} 不存在")

    allocations = db.execute(
        select(Allocation).where(
            Allocation.package_item_id.in_(
                select(PackageItem.id).where(PackageItem.package_id == package_id)
            ),
            Allocation.status == "allocated",
        ).with_for_update()
    ).scalars().all()

    for alloc in allocations:
        stock_service.release(db, alloc.stock_id, alloc.alloc_qty, "RELEASE", alloc.id)
        alloc.status = "released"

    pkg.status = "unassigned"
    db.flush()
