"""三级校验引擎（PRD §5）+ 虚拟/标记规则引擎（§5.3）。

校验级别：Error（阻断）、Review（人工复核）、Rule（规则处理）、Warning（预警）。
"""

from datetime import datetime, timedelta, timezone

from app.models import VirtualRule
from app.services.importer.bom import normalize_remark
from app.services.importer.parser import PACKAGE_NO_RE, TRACKING_NO_RE, parse_paid_at

# SLA 阈值：付款时间 + 5 天
SLA_DAYS = 5

# 数量陷阱：同包裹 2 个 SKU 且总数 ∈ {4,6}
TRAP_QTYS = {4, 6}


class ValidationResult:
    """单条明细的校验结果。"""

    def __init__(self, package_no: str, sku: str):
        self.package_no = package_no
        self.sku = sku
        self.errors: list[str] = []       # Error 阻断
        self.reviews: list[str] = []      # Review 人工复核
        self.warnings: list[str] = []     # Warning 预警
        self.rule_action: str | None = None  # 规则命中动作：虚拟/拦截/复核/采购跳过

    @property
    def is_blocked(self) -> bool:
        return bool(self.errors)


def _check_structure(item, result: ValidationResult):
    """结构级校验 V-01~V-06。"""
    # V-01 必填
    if not item.package_no or not item.sku or not item.tracking_no or not item.paid_at:
        result.errors.append("V-01 必填字段缺失（包裹号/商品SKU/运单号/付款时间）")
    # V-02 包裹号格式
    if item.package_no and not PACKAGE_NO_RE.match(item.package_no):
        result.errors.append(f"V-02 包裹号格式非法：{item.package_no}")
    # V-03 运单号格式
    if item.tracking_no and not TRACKING_NO_RE.match(item.tracking_no):
        result.errors.append(f"V-03 运单号格式非法：{item.tracking_no}")
    # V-05 商品总数（在 merge 阶段已按行解析，这里校验合并后 qty）
    if item.qty <= 0:
        result.errors.append(f"V-05 商品总数非正整数：{item.qty}")


def _check_business(item, result: ValidationResult, sku_codes: set[str], sku_types: dict[str, str]):
    """业务级校验 V-10~V-15。"""
    # V-10 SKU 建档校验（非 YUN、非标记，且不在主数据）
    # 注意：YUN 与标记 SKU 由规则引擎处理，这里只校验未建档的普通 SKU
    # V-11 付款时间解析
    paid_dt = parse_paid_at(item.paid_at)
    if item.paid_at and paid_dt is None:
        result.errors.append(f"V-11 付款时间无法解析：{item.paid_at}")
    # V-12 SLA 预警
    if paid_dt is not None:
        now = datetime.now(timezone.utc)
        paid_aware = paid_dt.replace(tzinfo=timezone.utc)
        if now - paid_aware > timedelta(days=SLA_DAYS):
            result.warnings.append(f"V-12 SLA 超时预警（付款已超 {SLA_DAYS} 天）")


def check_quantity_trap(items_by_package: dict[str, list], result_map: dict[str, ValidationResult]):
    """V-13 数量陷阱：同包裹 sku_count=2 且总数∈{4,6}。"""
    for pkg_no, items in items_by_package.items():
        # 统计该包裹去重后的 SKU 数
        skus = {it.sku for it in items}
        if len(skus) == 2:
            for it in items:
                if it.qty in TRAP_QTYS:
                    key = (pkg_no, it.sku)
                    if key in result_map:
                        result_map[key].reviews.append(
                            f"V-13 数量陷阱：包裹含 2 SKU 且总数={it.qty}，进人工复核"
                        )


def apply_virtual_rules(item, result: ValidationResult, rules: list[VirtualRule]):
    """虚拟/标记 SKU 规则引擎（§5.3，按优先级匹配）。

    字段对齐数据字典 §7.3：rule_type(virtual/marker) + match_type(exact/prefix/...) +
    match_value + action(skip/intercept/manual_review/ignore)。
    """
    for rule in rules:
        if not rule.enabled:
            continue
        matched = False
        if rule.match_type == "exact":
            matched = item.sku == rule.match_value
        elif rule.match_type == "prefix":
            matched = item.sku.startswith(rule.match_value)
        elif rule.match_type == "contains":
            matched = rule.match_value in item.sku
        if matched:
            result.rule_action = rule.action
            if rule.action == "intercept":
                result.reviews.append(f"规则命中：{rule.match_value} 拦截出库")
            elif rule.action == "manual_review":
                result.reviews.append(f"规则命中：{rule.match_value} 强制人工复核")
            elif rule.action == "skip":
                pass  # 虚拟品，免拣货免库存免面单
            elif rule.action == "ignore":
                pass  # 采购跳过
            # 命中后不再匹配低优先级规则
            break
