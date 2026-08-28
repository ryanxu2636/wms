"""库存记账单元测试：数量守恒 + 流水留痕。"""
import pytest

from app.core.exceptions import InsufficientStockError
from app.models import StockTransaction
from app.services import stock_service


class TestStockService:
    def test_allocate_moves_available_to_allocated(self, db, make_sku, make_location, make_stock):
        sku = make_sku("CS1")
        loc = make_location()
        stock = make_stock(sku, loc, available=10)

        stock_service.allocate(db, stock.id, 3, "ALLOCATE", 1)
        db.flush()

        assert stock.available_qty == 7
        assert stock.allocated_qty == 3

        txn = db.query(StockTransaction).one()
        assert txn.change_type == "allocate"
        assert txn.change_qty == 3
        assert txn.before_qty == 0
        assert txn.after_qty == 3

    def test_allocate_insufficient(self, db, make_sku, make_location, make_stock):
        sku = make_sku("CS1")
        loc = make_location()
        stock = make_stock(sku, loc, available=2)

        with pytest.raises(InsufficientStockError):
            stock_service.allocate(db, stock.id, 5, "ALLOCATE", 1)

    def test_release_moves_allocated_back(self, db, make_sku, make_location, make_stock):
        sku = make_sku("CS1")
        loc = make_location()
        stock = make_stock(sku, loc, available=7, allocated=3)

        stock_service.release(db, stock.id, 2, "RELEASE", 1)
        db.flush()

        assert stock.available_qty == 9
        assert stock.allocated_qty == 1

    def test_outbound_deducts_allocated(self, db, make_sku, make_location, make_stock):
        sku = make_sku("CS1")
        loc = make_location()
        stock = make_stock(sku, loc, available=7, allocated=3)

        stock_service.outbound_deduct(db, stock.id, 3, "OUTBOUND", 1)
        db.flush()

        assert stock.available_qty == 7  # available 不变
        assert stock.allocated_qty == 0  # allocated 扣减

        txn = db.query(StockTransaction).one()
        assert txn.change_type == "outbound"
        assert txn.change_qty == -3
        assert txn.before_qty == 3
        assert txn.after_qty == 0

    def test_transfer_between_stocks(self, db, make_sku, make_location, make_stock):
        sku = make_sku("CS1")
        loc1 = make_location(shelf_no="A01")
        loc2 = make_location(shelf_no="A02")
        s1 = make_stock(sku, loc1, available=5)
        s2 = make_stock(sku, loc2, available=0)

        stock_service.transfer(db, s1.id, s2.id, 3, "调拨")
        db.flush()

        assert s1.available_qty == 2
        assert s2.available_qty == 3
        assert db.query(StockTransaction).count() == 2  # 一减一加两条流水

    def test_adjust_rejects_negative(self, db, make_sku, make_location, make_stock):
        sku = make_sku("CS1")
        loc = make_location()
        stock = make_stock(sku, loc, available=3)

        with pytest.raises(InsufficientStockError):
            stock_service.adjust(db, stock.id, -5, "盘点盘亏")

    def test_full_flow_conservation(self, db, make_sku, make_location, make_stock):
        """分配→出库全程守恒：available 减少量 = 最终 allocated 归零。"""
        sku = make_sku("CS1")
        loc = make_location()
        stock = make_stock(sku, loc, available=100)

        stock_service.allocate(db, stock.id, 30, "ALLOCATE", 1)
        stock_service.outbound_deduct(db, stock.id, 30, "OUTBOUND", 1)
        db.flush()

        assert stock.available_qty == 70
        assert stock.allocated_qty == 0
        txns = db.query(StockTransaction).all()
        assert len(txns) == 2
        # 数量守恒：allocate(+30 allocated) + outbound(-30 allocated) = 0
        assert sum(t.change_qty for t in txns) == 0
