"""业务异常定义。"""


class BizError(Exception):
    """业务异常基类，携带 HTTP 状态码。"""

    status_code = 400

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class InsufficientStockError(BizError):
    """库存不足。"""

    def __init__(self, sku_code: str, need: int, avail: int):
        super().__init__(
            f"SKU {sku_code} 可用库存不足：需要 {need}，可用 {avail}", 409
        )


class IllegalTransitionError(BizError):
    """非法状态迁移。"""

    def __init__(self, current: str, target: str):
        super().__init__(f"非法状态迁移：{current} → {target}", 409)


class LabelNotPrintedError(BizError):
    """面单未打印，禁止出库。"""

    def __init__(self):
        super().__init__("面单未打印，禁止出库", 409)


class AlreadyShippedError(BizError):
    """已出库，禁止重复操作。"""

    def __init__(self):
        super().__init__("包裹已出库，禁止重复操作", 409)
