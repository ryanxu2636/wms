"""出库单元测试：打印卡点 + 库存扣减。"""
import pytest

from app.core.exceptions import LabelNotPrintedError, AlreadyShippedError
from app.models import Allocation, Outbound
from app.services import allocation_service, outbound_service


@pytest.fixture
def allocated_pkg(db, make_sku, make_location, make_stock, make_package, make_item):
    """构造一个已分配(assigned)且已打包(packed)的包裹，含出库单。"""
    sku = make_sku("CS1")
    loc = make_location()
    make_stock(sku, loc, available=10)
    pkg = make_package("XMELRY000001", total_qty=2)
    make_item(pkg, sku, qty=2)

    allocation_service.allocate_package(db, pkg.id)
    pkg.status = "packed"  # 直接置为已打包（跳过拣货/复核）
    db.flush()

    ob = Outbound(package_id=pkg.id, outbound_no="OB0001", status="pending", label_printed=0)
    db.add(ob)
    db.flush()
    return pkg, ob, sku


class TestOutbound:
    def test_blocked_without_label(self, db, allocated_pkg):
        """未打印面单被拦截。"""
        pkg, ob, sku = allocated_pkg
        with pytest.raises(LabelNotPrintedError):
            outbound_service.ship(db, ob.id)

    def test_ship_after_label(self, db, allocated_pkg):
        """打印面单后出库成功，扣减 allocated 并留痕。"""
        pkg, ob, sku = allocated_pkg
        ob.label_printed = 1
        db.flush()

        outbound_service.ship(db, ob.id)
        db.flush()

        assert pkg.status == "outbound"
        assert ob.status == "shipped"
        assert ob.shipped_at is not None

    def test_already_shipped(self, db, allocated_pkg):
        """已出库重复操作被拒绝。"""
        pkg, ob, sku = allocated_pkg
        ob.label_printed = 1
        db.flush()
        outbound_service.ship(db, ob.id)
        db.flush()

        with pytest.raises(AlreadyShippedError):
            outbound_service.ship(db, ob.id)
