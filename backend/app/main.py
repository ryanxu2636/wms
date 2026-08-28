"""FastAPI 应用入口：合并 S0~S3 全部路由。"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    allocation,
    importer,
    outbound,
    picking,
    print as print_api,
    putaway,
    rules,
    sku,
    stock,
    transition,
    warehouse,
)
from app.core.config import settings
from app.core.exceptions import BizError

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


# 注册路由
app.include_router(sku.router, prefix=settings.api_prefix)
app.include_router(rules.router, prefix=settings.api_prefix)
app.include_router(warehouse.router, prefix=settings.api_prefix)
app.include_router(importer.router, prefix=settings.api_prefix)
app.include_router(stock.router, prefix=settings.api_prefix)
app.include_router(putaway.router, prefix=settings.api_prefix)
app.include_router(allocation.router, prefix=settings.api_prefix)
app.include_router(transition.router, prefix=settings.api_prefix)
app.include_router(picking.router, prefix=settings.api_prefix)
app.include_router(outbound.router, prefix=settings.api_prefix)
app.include_router(print_api.router, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
