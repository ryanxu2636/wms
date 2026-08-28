"""导入引擎解析器（对应导入引擎 PRD v1.1 §4）。

纯函数实现，输入为「已读取的订单模板行」，输出解析结果集。
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

# 订单模板 8 列（字段名）
COLUMNS = [
    "包裹号", "商品SKU", "运单号", "物流方式",
    "付款时间", "拣货备注", "商品图片网址", "商品总数",
]

# 包裹号格式：XMELRY + 6 位数字，可选 R1 补发后缀
PACKAGE_NO_RE = re.compile(r"^XMELRY\d{6}(R1)?$")
# 运单号格式：YT + 数字
TRACKING_NO_RE = re.compile(r"^YT\d+$")

PAID_AT_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class DetailRow:
    """解析后的明细行（合并前）。"""

    package_no: str
    sku: str
    tracking_no: str
    logistics_method: str
    paid_at: str
    remark: str
    image_url: str
    qty: int
    row_no: int  # 原始行号


@dataclass
class MergedItem:
    """合并后的包裹明细（按 包裹号+SKU 聚合）。"""

    package_no: str
    sku: str
    tracking_no: str
    logistics_method: str
    paid_at: str
    remark: str
    image_url: str
    qty: int
    row_nos: list[int] = field(default_factory=list)


def split_sku(cell: str) -> list[str]:
    """拆分单格多 SKU（形态 B）。仅按换行符切分，保留空格与 `*`，trim 首尾空格。"""
    if cell is None:
        return []
    parts = cell.split("\n")
    return [p.strip() for p in parts if p.strip() != ""]


def split_images(cell: str) -> list[str]:
    """拆分图片列（形态 B 与 SKU 按 \n 对齐）。"""
    if cell is None:
        return []
    return cell.split("\n")


def parse_rows(rows: list[dict]) -> tuple[list[MergedItem], list[str]]:
    """解析 Excel 行 → 合并后的明细列表。

    rows: 每行是 dict，键为 8 个字段名。
    返回 (合并明细, 结构级错误列表)。
    """
    details: list[DetailRow] = []
    errors: list[str] = []

    for idx, row in enumerate(rows, start=1):
        package_no = (row.get("包裹号") or "").strip()
        sku_cell = row.get("商品SKU")
        tracking_no = (row.get("运单号") or "").strip()
        logistics = (row.get("物流方式") or "").strip()
        paid_at = (row.get("付款时间") or "").strip()
        remark = (row.get("拣货备注") or "").strip()
        image_cell = row.get("商品图片网址")
        total_cell = row.get("商品总数")

        sku_list = split_sku(sku_cell)
        image_list = split_images(image_cell) if image_cell else []

        for i, sku in enumerate(sku_list):
            image = image_list[i] if i < len(image_list) else ""
            details.append(
                DetailRow(
                    package_no=package_no,
                    sku=sku,
                    tracking_no=tracking_no,
                    logistics_method=logistics,
                    paid_at=paid_at,
                    remark=remark,
                    image_url=image,
                    qty=0,  # 后续由商品总数解析填入
                    row_no=idx,
                )
            )

    return merge_details(details), errors


def merge_details(details: list[DetailRow]) -> list[MergedItem]:
    """按 包裹号+SKU 合并求和（229 对重复行 + 数量口径）。"""
    merged: dict[tuple[str, str], MergedItem] = {}
    for d in details:
        key = (d.package_no, d.sku)
        if key not in merged:
            merged[key] = MergedItem(
                package_no=d.package_no,
                sku=d.sku,
                tracking_no=d.tracking_no,
                logistics_method=d.logistics_method,
                paid_at=d.paid_at,
                remark=d.remark,
                image_url=d.image_url,
                qty=0,
                row_nos=[d.row_no],
            )
        else:
            merged[key].row_nos.append(d.row_no)
            # 运单号/物流/付款时间/备注取首行，不一致留给校验层判断
    return list(merged.values())


def parse_paid_at(text: str) -> datetime | None:
    """解析付款时间 YYYY-MM-DD HH:MM:SS。"""
    try:
        return datetime.strptime(text, PAID_AT_FORMAT)
    except (ValueError, TypeError):
        return None
