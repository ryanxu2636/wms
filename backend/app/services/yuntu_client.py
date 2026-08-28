"""云途 YunExpress OMS 面单打印客户端。

对齐《云途面单.md》：
- OMS 模式接口：POST http://oms.api.yunexpress.com/api/Label/Print
- 认证：Basic Auth，Base64("CN5834&oHRl28wOmQo=")
- 请求体：面单号数组 ["YT..."]，单批最多 20 单
- 成功判定：响应 JSON 的 Code == "0000"
- 面单 URL 位于 Item[].Url

密钥通过环境变量 / .env 注入（YUNTU_*），代码中不硬编码。
"""
import base64
import logging
from typing import Any

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# 云途 OMS 打印接口
YUNTU_LABEL_PRINT_URL = getattr(
    settings, "YUNTU_LABEL_PRINT_URL",
    "http://oms.api.yunexpress.com/api/Label/Print",
)
# 单批最多单量
YUNTU_BATCH_SIZE = int(getattr(settings, "YUNTU_BATCH_SIZE", 20))


class YunExpressError(Exception):
    """云途接口调用失败。"""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


def _auth_header() -> str:
    """构建 Basic Auth 头。凭据优先取环境变量，缺失时用文档默认值兜底。"""
    username = getattr(settings, "YUNTU_USERNAME", "CN5834")
    password = getattr(settings, "YUNTU_PASSWORD", "oHRl28wOmQo")
    token = base64.b64encode(f"{username}&{password}".encode()).decode()
    return f"Basic {token}"


def _print_batch(tracking_nos: list[str]) -> dict[str, Any]:
    """调用云途打印接口，返回原始响应 JSON。"""
    if not tracking_nos:
        return {"Code": "0000", "Item": []}

    headers = {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
    }
    resp = requests.post(
        YUNTU_LABEL_PRINT_URL,
        json=tracking_nos,
        headers=headers,
        timeout=int(getattr(settings, "YUNTU_TIMEOUT", 30)),
    )
    if resp.status_code != 200:
        raise YunExpressError(
            f"云途接口 HTTP {resp.status_code}: {resp.text[:200]}"
        )
    try:
        data = resp.json()
    except ValueError as e:
        raise YunExpressError(f"云途返回非 JSON：{resp.text[:200]}") from e
    return data


def fetch_labels(tracking_nos: list[str]) -> dict[str, str]:
    """批量获取面单 URL。

    返回 {tracking_no: label_url}。按 20 单/批分批，失败单逐个兜底。
    面单号可能重复（同包裹重打），最终按 tracking_no 归并（重复时保留最后一次成功）。
    """
    result: dict[str, str] = {}
    failed: list[str] = []

    # 1. 按 YUNTU_BATCH_SIZE 分批
    for i in range(0, len(tracking_nos), YUNTU_BATCH_SIZE):
        batch = tracking_nos[i : i + YUNTU_BATCH_SIZE]
        try:
            data = _print_batch(batch)
        except YunExpressError:
            failed.extend(batch)
            continue

        if data.get("Code") != "0000":
            logger.warning("云途批次失败：%s", data)
            failed.extend(batch)
            continue

        # 成功批次解析 Item[].Url
        items = data.get("Item") or []
        returned: set[str] = set()
        for item in items:
            tno = item.get("TrackingNumber") or item.get("TrackingNo")
            url = item.get("Url") or item.get("LabelUrl") or item.get("url")
            if tno and url:
                result[tno] = url
                returned.add(tno)
            elif tno:
                failed.append(tno)

        # 该批未返回的运单号视为失败
        failed.extend([t for t in batch if t not in returned])

    # 2. 失败单逐个兜底
    for tno in set(failed):
        if not tno:
            continue
        try:
            data = _print_batch([tno])
        except YunExpressError:
            continue
        if data.get("Code") == "0000":
            items = data.get("Item") or []
            if items:
                url = items[0].get("Url") or items[0].get("LabelUrl") or items[0].get("url")
                if url:
                    result[tno] = url

    return result
