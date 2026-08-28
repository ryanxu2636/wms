"""pytest 共享 fixture：SQLite 内存库 + 测试数据工厂。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app import models  # noqa: F401  注册所有模型
from app.models import (
    Sku, Shelf, Location, Stock, Package, PackageItem,
    Bom, Allocation, Outbound, PickingTask, Packing, StockTransaction,
)


@pytest.fixture
def db():
    """每个测试一个独立 SQLite 内存库。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def make_sku(db):
    def _make(sku_code, sku_name="", sku_type="base"):
        sku = Sku(sku_code=sku_code, sku_name=sku_name, sku_type=sku_type)
        db.add(sku)
        db.flush()
        return sku
    return _make


@pytest.fixture
def make_location(db):
    _counter = {"n": 0}

    def _make(shelf_no="A07", column_no="03", layer_no="04", code=None, status="empty"):
        # shelf.code 唯一，用计数器保证同测试内多次创建不冲突
        _counter["n"] += 1
        shelf = Shelf(warehouse_id=1, code=f"{shelf_no}-{_counter['n']}")
        db.add(shelf)
        db.flush()
        code = code or f"{shelf_no}-{column_no}-{layer_no}-{_counter['n']}"
        loc = Location(
            shelf_id=shelf.id, code=code,
            shelf_no=shelf_no, column_no=column_no, layer_no=layer_no,
            status=status,
        )
        db.add(loc)
        db.flush()
        return loc
    return _make


@pytest.fixture
def make_stock(db):
    def _make(sku, location, available=0, allocated=0, locked=0, in_transit=0, batch_no=None):
        stock = Stock(
            sku_id=sku.id, location_id=location.id, batch_no=batch_no,
            available_qty=available, allocated_qty=allocated,
            locked_qty=locked, in_transit_qty=in_transit,
        )
        db.add(stock)
        db.flush()
        return stock
    return _make


@pytest.fixture
def make_package(db):
    def _make(package_no, tracking_no=None, status="unassigned", total_qty=0):
        pkg = Package(
            package_no=package_no, tracking_no=tracking_no or f"YT{package_no[-6:]}",
            status=status, total_qty=total_qty,
        )
        db.add(pkg)
        db.flush()
        return pkg
    return _make


@pytest.fixture
def make_item(db):
    def _make(package, sku, qty=1, is_virtual=0, is_marker=0):
        item = PackageItem(
            package_id=package.id, sku_id=sku.id, qty=qty,
            is_virtual=is_virtual, is_marker=is_marker, picked_qty=0,
        )
        db.add(item)
        db.flush()
        return item
    return _make
