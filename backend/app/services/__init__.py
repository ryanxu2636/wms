"""核心服务包。"""
from app.services import stock_service, allocation_service, picking_service, outbound_service, putaway_service

__all__ = ["stock_service", "allocation_service", "picking_service", "outbound_service", "putaway_service"]
