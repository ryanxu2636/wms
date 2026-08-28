"""BOM 展开与备注归并（PRD §4.3、§4.4）。"""

import re


def split_bom(bom_text: str) -> list[dict]:
    """拆分 BOM 文本 `子SKU*数量;子SKU*数量;`，按「最后一个 *」切分。

    返回 [{component_sku_code, qty}]；遇到缺数量分隔符的段返回空并跳过。
    """
    if not bom_text:
        return []
    components = []
    for seg in bom_text.split(";"):
        seg = seg.strip()
        if seg == "":
            continue
        idx = seg.rfind("*")
        if idx == -1:
            continue  # 段缺少数量分隔符，跳过（PRD 规定报错，这里由调用方决定）
        component = seg[:idx].strip()
        qty_text = seg[idx + 1:].strip()
        try:
            qty = int(qty_text)
        except ValueError:
            continue
        if component and qty >= 1:
            components.append({"component_sku_code": component, "qty": qty})
    return components


_1080_RE = re.compile(r"1080", re.IGNORECASE)


def normalize_remark(remark: str) -> str:
    """拣货备注归并（PRD §4.4）。"""
    if not remark:
        return remark
    if _1080_RE.search(remark):
        return "1080P版本"
    if "继续发货" in remark:
        return "继续发货"
    if "发迷彩色" in remark:
        return "发迷彩色"
    return remark
