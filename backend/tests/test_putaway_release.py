"""上架确认 + 释放分配 + 面单标记 单元测试。"""
import pytest

from app.core.exceptions import InsufficientStockError
from app.models import Allocation, PutawayTask, Stock, Outbound
from app.services import allocation_service, putaway_service, outbound_service


class TestPutawayConfirm:
    def test_confirm_moves_stock(self, db, make_sku, make_location, make_stock):
        """上架确认：库存从来源库位移到目标库位，更新库位状态。"""
        sku = make_sku("CS1")
        src_loc = make_location(shelf_no="TMP", status="occupied")
        dst_loc = make_location(shelf_no="A01", status="empty")
        make_stock(sku, src_loc, available=5)

        putaway_service.confirm_putaway(
            db, sku_id=sku.id, from_location_id=src_loc.id,
            to_location_id=dst_loc.id, qty=5,
        )
        db.flush()

        src_stock = db.query(Stock).filter_by(sku_id=sku.id, location_id=src_loc.id).one()
        dst_stock = db.query(Stock).filter_by(sku_id=sku.id, location_id=dst_loc.id).one()
        assert src_stock.available_qty == 0
        assert dst_stock.available_qty == 5

        # 库位状态联动
        db.refresh(src_loc)
        db.refresh(dst_loc)
        assert src_loc.status == "empty"
        assert dst_loc.status == "occupied"

    def test_confirm_insufficient(self, db, make_sku, make_location, make_stock):
        sku = make_sku("CS1")
        src_loc = make_location(shelf_no="TMP", status="occupied")
        dst_loc = make_location(shelf_no="A01", status="empty")
        make_stock(sku, src_loc, available=2)

        with pytest.raises(InsufficientStockError):
            putaway_service.confirm_putaway(
                db, sku_id=sku.id, from_location_id=src_loc.id,
                to_location_id=dst_loc.id, qty=5,
            )

    def test_confirm_updates_task(self, db, make_sku, make_location, make_stock):
        sku = make_sku("CS1")
        src_loc = make_location(shelf_no="TMP", status="occupied")
        dst_loc = make_location(shelf_no="A01", status="empty")
        make_stock(sku, src_loc, available=3)

        task = PutawayTask(receiving_id=1, sku_id=sku.id, qty=3,
                           from_location_id=src_loc.id, status="pending")
        db.add(task)
        db.flush()

        putaway_service.confirm_putaway(
            db, sku_id=sku.id, from_location_id=src_loc.id,
            to_location_id=dst_loc.id, qty=3, task_id=task.id,
        )
        db.flush()

        assert task.status == "done"
        assert task.to_location_id == dst_loc.id


class TestReleasePackage:
    def test_release_returns_stock(self, db, make_sku, make_location, make_stock, make_package, make_item):
        """释放分配：库存回退，allocation 置 released，订单回 unassigned。"""
        sku = make_sku("CS1")
        loc = make_location()
        stock = make_stock(sku, loc, available=10)
        pkg = make_package("XMELRY000001", total_qty=3)
        make_item(pkg, sku, qty=3)

        allocation_service.allocate_package(db, pkg.id)
        db.flush()
        assert pkg.status == "assigned"
        db.refresh(stock)
        assert stock.allocated_qty == 3

        allocation_service.release_package(db, pkg.id)
        db.flush()

        db.refresh(stock)
        assert stock.allocated_qty == 0
        assert stock.available_qty == 10
        assert pkg.status == "unassigned"
        assert db.query(Allocation).filter_by(status="released").count() == 1

    def test_release_then_reallocate(self, db, make_sku, make_location, make_stock, make_package, make_item):
        """释放后可重新分配。"""
        sku = make_sku("CS1")
        loc = make_location()
        make_stock(sku, loc, available=10)
        pkg = make_package("XMELRY000001", total_qty=3)
        make_item(pkg, sku, qty=3)

        allocation_service.allocate_package(db, pkg.id)
        db.flush()
        allocation_service.release_package(db, pkg.id)
        db.flush()
        allocation_service.allocate_package(db, pkg.id)
        db.flush()

        assert pkg.status == "assigned"
        assert db.query(Allocation).filter_by(status="allocated").count() == 1


class TestMarkPrinted:
    def test_mark_printed(self, db, make_sku, make_location, make_stock, make_package, make_item):
        sku = make_sku("CS1")
        loc = make_location()
        make_stock(sku, loc, available=10)
        pkg = make_package("XMELRY000001", total_qty=2)
        make_item(pkg, sku, qty=2)
        allocation_service.allocate_package(db, pkg.id)
        db.flush()

        ob = Outbound(package_id=pkg.id, outbound_no="OB0001", status="pending", label_printed=0)
        db.add(ob)
        db.flush()

        outbound_service.mark_label_printed(db, ob.id)
        db.flush()
        assert ob.label_printed == 1
