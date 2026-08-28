"""API 路由汇总。"""
from app.api import (
    stock,
    putaway,
    allocation,
    transition,
    picking,
    outbound,
)

__all__ = ["stock", "putaway", "allocation", "transition", "picking", "outbound"]
