"""库存分配 + 缺货挂起单元测试。"""
import pytest

from app.models import Allocation, Bom
from app.services import allocation_service


class TestAllocation:
    def test_base_sku_allocate(self, db, make_sku, make_location, make_stock, make_package, make_item):
        sku = make_sku("CS1")
        loc = make_location()
        make_stock(sku, loc, available=10)
        pkg = make_package("XMELRY000001", total_qty=3)
        make_item(pkg, sku, qty=3)

        allocation_service.allocate_package(db, pkg.id)
        db.flush()

        assert pkg.status == "assigned"
        allocs = db.query(Allocation).all()
        assert len(allocs) == 1
        assert allocs[0].alloc_qty == 3
        assert allocs[0].status == "allocated"

    def test_virtual_sku_skipped(self, db, make_sku, make_location, make_stock, make_package, make_item):
        """虚拟 SKU(YUN) 免库存，跳过分配。"""
        sku = make_sku("YUN", sku_type="virtual")
        pkg = make_package("XMELRY000002", total_qty=1)
        make_item(pkg, sku, qty=1, is_virtual=1)

        allocation_service.allocate_package(db, pkg.id)
        db.flush()

        assert pkg.status == "assigned"
        assert db.query(Allocation).count() == 0  # 无分配记录

    def test_combo_sku_expands(self, db, make_sku, make_location, make_stock, make_package, make_item):
        """组合 SKU 按 BOM 展开锁定子件。"""
        combo = make_sku("COMBO1", sku_type="combo")
        child_a = make_sku("A")
        child_b = make_sku("B")
        loc = make_location()
        make_stock(child_a, loc, available=20)
        make_stock(child_b, loc, available=5)
        db.add(Bom(combo_sku_id=combo.id, component_sku_id=child_a.id, qty=2))
        db.add(Bom(combo_sku_id=combo.id, component_sku_id=child_b.id, qty=1))
        db.flush()

        pkg = make_package("XMELRY000003", total_qty=3)
        make_item(pkg, combo, qty=3)

        allocation_service.allocate_package(db, pkg.id)
        db.flush()

        assert pkg.status == "assigned"
        allocs = db.query(Allocation).all()
        by_sku = {a.sku_id: a.alloc_qty for a in allocs}
        assert by_sku[child_a.id] == 6  # 3 * 2
        assert by_sku[child_b.id] == 3  # 3 * 1

    def test_shortage_hold(self, db, make_sku, make_location, make_stock, make_package, make_item):
        """库存不足整单原子回滚并挂起。"""
        sku = make_sku("CS1")
        loc = make_location()
        make_stock(sku, loc, available=2)
        pkg = make_package("XMELRY000004", total_qty=5)
        make_item(pkg, sku, qty=5)

        allocation_service.allocate_package(db, pkg.id)
        db.flush()

        assert pkg.status == "shortage_hold"
        assert db.query(Allocation).count() == 0  # 原子回滚，无残留分配

    def test_combo_shortage_atomic(self, db, make_sku, make_location, make_stock, make_package, make_item):
        """组合 SKU 子件不足时，已锁定的部分全部回滚。"""
        combo = make_sku("COMBO1", sku_type="combo")
        child_a = make_sku("A")
        child_b = make_sku("B")
        loc = make_location()
        stock_a = make_stock(child_a, loc, available=20)
        stock_b = make_stock(child_b, loc, available=1)
        db.add(Bom(combo_sku_id=combo.id, component_sku_id=child_a.id, qty=1))
        db.add(Bom(combo_sku_id=combo.id, component_sku_id=child_b.id, qty=1))
        db.flush()

        pkg = make_package("XMELRY000005", total_qty=3)
        make_item(pkg, combo, qty=3)  # 需 A*3=3, B*3=3，但 B 只有 1

        allocation_service.allocate_package(db, pkg.id)
        db.flush()

        assert pkg.status == "shortage_hold"
        db.refresh(stock_a)
        db.refresh(stock_b)
        # 原子回滚：A 的 available 未被扣（锁定 B 失败后 A 的锁定也回滚）
        assert stock_a.available_qty == 20
        assert stock_a.allocated_qty == 0
        assert stock_b.available_qty == 1
