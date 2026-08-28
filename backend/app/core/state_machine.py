"""订单状态机（对齐数据字典 package.status 枚举）。

主流程：unassigned → assigned → picking → checked → packed → outbound
异常态：intercepted（拦截）、manual_review（待人工复核）、shortage_hold（缺货挂起）
"""
from enum import Enum

from app.core.exceptions import IllegalTransitionError


class PackageStatus(str, Enum):
    UNASSIGNED = "unassigned"
    ASSIGNED = "assigned"
    PICKING = "picking"
    CHECKED = "checked"
    PACKED = "packed"
    OUTBOUND = "outbound"
    INTERCEPTED = "intercepted"
    MANUAL_REVIEW = "manual_review"
    SHORTAGE_HOLD = "shortage_hold"


# 允许的状态迁移表
ALLOWED_TRANSITIONS: dict[PackageStatus, set[PackageStatus]] = {
    PackageStatus.UNASSIGNED: {
        PackageStatus.ASSIGNED,
        PackageStatus.INTERCEPTED,
        PackageStatus.MANUAL_REVIEW,
        PackageStatus.SHORTAGE_HOLD,
    },
    PackageStatus.ASSIGNED: {
        PackageStatus.PICKING,
        PackageStatus.INTERCEPTED,
        PackageStatus.MANUAL_REVIEW,
        PackageStatus.UNASSIGNED,  # 释放分配回退
    },
    PackageStatus.PICKING: {
        PackageStatus.CHECKED,
        PackageStatus.INTERCEPTED,
        PackageStatus.MANUAL_REVIEW,
        PackageStatus.SHORTAGE_HOLD,
    },
    PackageStatus.CHECKED: {
        PackageStatus.PACKED,
        PackageStatus.MANUAL_REVIEW,
    },
    PackageStatus.PACKED: {
        PackageStatus.OUTBOUND,
        PackageStatus.INTERCEPTED,
    },
    PackageStatus.OUTBOUND: set(),  # 终态
    PackageStatus.INTERCEPTED: {
        PackageStatus.ASSIGNED,  # 人工放行
        PackageStatus.UNASSIGNED,
    },
    PackageStatus.MANUAL_REVIEW: {
        PackageStatus.ASSIGNED,  # 复核通过
        PackageStatus.INTERCEPTED,
        PackageStatus.UNASSIGNED,
    },
    PackageStatus.SHORTAGE_HOLD: {
        PackageStatus.UNASSIGNED,  # 补货后重新分配
    },
}


def can_transition(current: str, target: str) -> bool:
    try:
        cur = PackageStatus(current)
        tgt = PackageStatus(target)
    except ValueError:
        return False
    return tgt in ALLOWED_TRANSITIONS.get(cur, set())


def assert_can_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise IllegalTransitionError(current, target)
