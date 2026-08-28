"""BOM 解析与展开单元测试（数据字典点名的「最后一个 *」陷阱）。"""
from app.services.allocation_service import parse_bom_segment, expand_bom
from app.models import Bom


class TestParseBomSegment:
    def test_sku_name_with_star(self):
        """SKU 名内含 *，必须用最后一个 * 切分数量。"""
        comp, qty = parse_bom_segment("CS190-Dark grey-130*150CM-UK*3")
        assert comp == "CS190-Dark grey-130*150CM-UK"
        assert qty == 3

    def test_sku_name_with_multiple_stars(self):
        comp, qty = parse_bom_segment("CS28-100 inches(221*125 cm)*2")
        assert comp == "CS28-100 inches(221*125 cm)"
        assert qty == 2

    def test_simple(self):
        comp, qty = parse_bom_segment("CS123*5")
        assert comp == "CS123"
        assert qty == 5

    def test_no_quantity_defaults_to_one(self):
        comp, qty = parse_bom_segment("CS456")
        assert comp == "CS456"
        assert qty == 1


class TestExpandBom:
    def test_expand_combo(self, db, make_sku):
        combo = make_sku("COMBO1", sku_type="combo")
        child_a = make_sku("A")
        child_b = make_sku("B")
        db.add(Bom(combo_sku_id=combo.id, component_sku_id=child_a.id, qty=2))
        db.add(Bom(combo_sku_id=combo.id, component_sku_id=child_b.id, qty=1))
        db.flush()

        result = expand_bom(db, combo.id)
        result_map = {c.sku_id: c.per_qty for c in result}
        assert result_map == {child_a.id: 2, child_b.id: 1}

    def test_nested_combo(self, db, make_sku):
        """嵌套组合递归展开，子件用量相乘。"""
        outer = make_sku("OUTER", sku_type="combo")
        inner = make_sku("INNER", sku_type="combo")
        base = make_sku("BASE")
        db.add(Bom(combo_sku_id=outer.id, component_sku_id=inner.id, qty=2))
        db.add(Bom(combo_sku_id=inner.id, component_sku_id=base.id, qty=3))
        db.flush()

        result = expand_bom(db, outer.id)
        assert len(result) == 1
        assert result[0].sku_id == base.id
        assert result[0].per_qty == 6  # 2 * 3
