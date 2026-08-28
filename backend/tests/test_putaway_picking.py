"""上架推荐 + 拣货路径排序单元测试。"""
from app.services import putaway_service, picking_service
from app.models import Allocation


class TestPutawayRecommend:
    def test_prefer_existing_location(self, db, make_sku, make_location, make_stock):
        """一品多库位：优先推荐已有该 SKU 的库位。"""
        sku = make_sku("CS1")
        loc1 = make_location(shelf_no="A01", column_no="01", layer_no="01", status="occupied")
        loc2 = make_location(shelf_no="B02", column_no="01", layer_no="01", status="empty")
        make_stock(sku, loc1, available=5)

        result = putaway_service.recommend_location(db, sku.id)
        assert result == loc1.id  # 推荐已有 SKU 的库位，而非空库位

    def test_fallback_to_empty(self, db, make_sku, make_location):
        """无既有库位时按路径排序找空库位。"""
        sku = make_sku("CS1")
        loc_a = make_location(shelf_no="A01", column_no="02", layer_no="01", status="empty")
        loc_b = make_location(shelf_no="A01", column_no="01", layer_no="01", status="empty")

        result = putaway_service.recommend_location(db, sku.id)
        assert result == loc_b.id  # 列号更小的先推荐

    def test_no_empty_returns_none(self, db, make_sku, make_location):
        sku = make_sku("CS1")
        make_location(status="occupied")
        result = putaway_service.recommend_location(db, sku.id)
        assert result is None


class TestPickingPathSort:
    def test_items_sorted_by_path(self, db, make_sku, make_location, make_stock, make_package, make_item):
        """拣货项按库位 货架→列→层 排序。"""
        sku = make_sku("CS1")
        loc1 = make_location(shelf_no="A01", column_no="03", layer_no="01", status="occupied")
        loc2 = make_location(shelf_no="A01", column_no="01", layer_no="01", status="occupied")
        s1 = make_stock(sku, loc1, available=5)
        s2 = make_stock(sku, loc2, available=5)

        pkg = make_package("XMELRY000001", total_qty=2)
        item = make_item(pkg, sku, qty=2)

        # 手动构造两条分配（同 SKU 不同库位）
        db.add(Allocation(package_item_id=item.id, sku_id=sku.id, stock_id=s1.id, alloc_qty=1, status="allocated"))
        db.add(Allocation(package_item_id=item.id, sku_id=sku.id, stock_id=s2.id, alloc_qty=1, status="allocated"))
        db.flush()

        items = picking_service.pick_items_with_path(db, pkg.id)
        assert len(items) == 1  # 同 SKU 汇总为一项
        assert items[0]["total_qty"] == 2
        # 路径排序：列 01 应在列 03 之前
        codes = [l["location_code"] for l in items[0]["locations"]]
        assert codes == [loc2.code, loc1.code]
