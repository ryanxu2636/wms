"""API 路由汇总。"""
from app.api import (
    stock,
    putaway,
    allocation,
    transition,
    picking,
    outbound,
    auth,
    print as print_api,
)

__all__ = ["stock", "putaway", "allocation", "transition", "picking", "outbound", "print_api", "auth"]
