"""端到端联调演示数据准备脚本。

直接通过 SQLAlchemy 写 PostgreSQL，准备：
- SKU：1 个 base + 1 个 combo（含 BOM）+ 1 个 marker
- 货架 + 库位 + 库存
- 2 个订单：P1（正常全链路）、P2（缺货验证 shortage_hold）
"""
from datetime import datetime, timedelta

from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.master import Sku, Shelf, Location, Bom
from app.models.inventory import Stock, StockTransaction, Allocation
from app.models.fulfillment import Package, PackageItem, Outbound, PickingTask, Packing

db = SessionLocal()


def clean():
    """清空业务表并重置自增序列，保证可重复执行且 id 从 1 开始。"""
    tables = [
        "allocation", "stock_transaction",
        "outbound", "picking_task", "packing",
        "package_item", "package",
        "stock", "bom",
        "location", "shelf",
        "sku",
    ]
    db.execute(text("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
    db.commit()
    print("已清空业务数据")


def seed():
    clean()

    # --- SKU ---
    sku_base = Sku(sku_code="SKU-BASE-001", sku_name="普通商品A", sku_type="base", unit="pcs")
    sku_comp = Sku(sku_code="SKU-COMP-001", sku_name="组合子件X", sku_type="base", unit="pcs")
    sku_combo = Sku(sku_code="SKU-COMBO-001", sku_name="组合套装*2", sku_type="combo", unit="set")
    sku_marker = Sku(sku_code="CS99-No!!!", sku_name="拦截标记", sku_type="marker", unit="pcs")
    db.add_all([sku_base, sku_comp, sku_combo, sku_marker])
    db.flush()

    # --- BOM：combo = 2 * comp ---
    db.add(Bom(combo_sku_id=sku_combo.id, component_sku_id=sku_comp.id, qty=2, sort_order=1))
    db.flush()

    # --- 货架 + 库位 ---
    shelf = Shelf(warehouse_id=1, code="S-A-01", name="A区01货架")
    db.add(shelf)
    db.flush()

    loc_base = Location(shelf_id=shelf.id, code="A-01-01-01", shelf_no="A-01", column_no="01", layer_no="01", status="occupied")
    loc_comp = Location(shelf_id=shelf.id, code="A-01-01-02", shelf_no="A-01", column_no="01", layer_no="02", status="occupied")
    loc_empty = Location(shelf_id=shelf.id, code="A-01-01-03", shelf_no="A-01", column_no="01", layer_no="03", status="empty")
    db.add_all([loc_base, loc_comp, loc_empty])
    db.flush()

    # --- 库存 ---
    db.add(Stock(sku_id=sku_base.id, location_id=loc_base.id, batch_no="B001", available_qty=100, allocated_qty=0, locked_qty=0, in_transit_qty=0))
    db.add(Stock(sku_id=sku_comp.id, location_id=loc_comp.id, batch_no="B002", available_qty=20, allocated_qty=0, locked_qty=0, in_transit_qty=0))
    db.flush()

    # --- 订单 P1：正常全链路（1 base + 1 combo*1）---
    p1 = Package(
        package_no="PKG-20250828-001",
        tracking_no="TRK-001",
        logistics_channel="SF",
        sla_deadline=datetime.now() + timedelta(hours=24),
        status="unassigned",
        total_qty=2,
    )
    db.add(p1)
    db.flush()
    db.add(PackageItem(package_id=p1.id, sku_id=sku_base.id, qty=2, is_virtual=0, is_marker=0, picked_qty=0))
    db.add(PackageItem(package_id=p1.id, sku_id=sku_combo.id, qty=1, is_virtual=0, is_marker=0, picked_qty=0))
    db.add(Outbound(package_id=p1.id, outbound_no="OB-001", status="pending", label_printed=0))
    db.flush()

    # --- 订单 P2：缺货验证（base 需求 999，超库存 → shortage_hold）---
    p2 = Package(
        package_no="PKG-20250828-002",
        tracking_no="TRK-002",
        logistics_channel="SF",
        sla_deadline=datetime.now() + timedelta(hours=24),
        status="unassigned",
        total_qty=1,
    )
    db.add(p2)
    db.flush()
    db.add(PackageItem(package_id=p2.id, sku_id=sku_base.id, qty=999, is_virtual=0, is_marker=0, picked_qty=0))
    db.add(Outbound(package_id=p2.id, outbound_no="OB-002", status="pending", label_printed=0))
    db.flush()

    db.commit()
    print("=== 演示数据准备完成 ===")
    print(f"base SKU id={sku_base.id}  库存 100 @ {loc_base.code}")
    print(f"comp SKU id={sku_comp.id}  库存 20  @ {loc_comp.code}")
    print(f"combo SKU id={sku_combo.id} (BOM: 2*comp)")
    print(f"marker SKU id={sku_marker.id}")
    print(f"订单 P1 id={p1.id} (正常链路: 2*base + 1*combo)")
    print(f"订单 P2 id={p2.id} (缺货链路: 999*base)")
    print(f"空库位 id={loc_empty.id} @ {loc_empty.code}")


if __name__ == "__main__":
    seed()
