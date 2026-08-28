"""统一导出所有 ORM 模型，供 alembic 与 Base.metadata 使用。"""
from app.models.base import SkuType, PackageStatus, LocationStatus, AuditMixin
from app.models.master import Sku, Warehouse, Shelf, Location, Bom, Supplier
from app.models.inventory import Stock, StockTransaction, Allocation
from app.models.fulfillment import Package, PackageItem, PickingTask, Packing, Outbound
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, Receiving, PutawayTask
from app.models.other_domains import CrossDockMatch, Stocktake, StocktakeItem, StockAdjustment
from app.models.import_domain import VirtualRule, ImportBatch, ImportMapping, ImportError, ReviewQueue
from app.models.print_domain import PrintTemplate, PrintQueue
from app.models.system import Role, User, OperationLog

__all__ = [
    # 主数据域
    "Sku", "Warehouse", "Shelf", "Location", "Bom", "Supplier",
    # 库存域
    "Stock", "StockTransaction", "Allocation",
    # 订单履约域
    "Package", "PackageItem", "PickingTask", "Packing", "Outbound",
    # 采购域
    "PurchaseOrder", "PurchaseOrderItem", "Receiving", "PutawayTask",
    # 快进快出 + 盘点
    "CrossDockMatch", "Stocktake", "StocktakeItem", "StockAdjustment",
    # 导入域
    "VirtualRule", "ImportBatch", "ImportMapping", "ImportError", "ReviewQueue",
    # 打印域
    "PrintTemplate", "PrintQueue",
    # 系统域
    "Role", "User", "OperationLog",
    # 枚举 + mixin
    "SkuType", "PackageStatus", "LocationStatus", "AuditMixin",
]
