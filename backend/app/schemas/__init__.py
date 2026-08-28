"""Pydantic 请求/响应模型（统一 S0~S3，字段对齐数据字典）。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── SKU 主数据 ──
class SkuBase(BaseModel):
    sku_code: str = Field(..., max_length=128)
    sku_name: str | None = Field(None, max_length=255)
    sku_type: str = "base"  # base/combo/virtual/marker
    image_url: str | None = None
    status: int = 1


class SkuCreate(SkuBase):
    pass


class SkuUpdate(BaseModel):
    sku_name: str | None = None
    sku_type: str | None = None
    image_url: str | None = None
    status: int | None = None


class SkuOut(SkuBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: object | None = None
    updated_at: object | None = None


class BomComponent(BaseModel):
    component_sku_code: str
    qty: int = Field(..., ge=1)


class BomCreate(BaseModel):
    combo_sku_code: str
    components: list[BomComponent]


# ── 虚拟/标记规则（数据字典 §7.3）──
class VirtualRuleBase(BaseModel):
    rule_type: str  # virtual/marker
    match_type: str = "exact"  # exact/prefix/contains/regex
    match_value: str
    action: str  # skip/intercept/manual_review/ignore
    priority: int = 0
    enabled: int = 1
    description: str | None = None


class VirtualRuleCreate(VirtualRuleBase):
    pass


class VirtualRuleOut(VirtualRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ── 仓库/货架/库位 ──
class WarehouseCreate(BaseModel):
    code: str
    name: str


class ShelfCreate(BaseModel):
    warehouse_id: int
    code: str
    name: str | None = None


class LocationCreate(BaseModel):
    shelf_id: int
    code: str
    shelf_no: str
    column_no: str
    layer_no: str
    status: str = "empty"


# ── 库存 ──
class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_id: int
    location_id: int
    batch_no: str | None
    available_qty: int
    allocated_qty: int
    locked_qty: int
    in_transit_qty: int


class AdjustIn(BaseModel):
    stock_id: int
    delta: int
    remark: str


class TransferIn(BaseModel):
    from_stock_id: int
    to_stock_id: int
    qty: int
    remark: str


# ── 上架 ──
class PutawayRecommendOut(BaseModel):
    sku_id: int
    to_location_id: int | None


class PutawayConfirmIn(BaseModel):
    sku_id: int
    from_location_id: int
    to_location_id: int
    qty: int
    task_id: int | None = None


# ── 分配 / 状态 ──
class AllocateIn(BaseModel):
    package_id: int


class ReleaseIn(BaseModel):
    package_id: int


class TransitionIn(BaseModel):
    package_id: int
    target: str


# ── 拣货 / 复核 / 打包 ──
class PickingCreateIn(BaseModel):
    package_id: int
    assignee_id: int | None = None


class PickingCompleteIn(BaseModel):
    task_id: int


class CheckIn(BaseModel):
    package_id: int
    packer_id: int | None = None


class PackIn(BaseModel):
    packer_id: int | None = None


# ── 出库 ──
class OutboundShipIn(BaseModel):
    outbound_id: int


class OutboundMarkPrintedIn(BaseModel):
    outbound_id: int
