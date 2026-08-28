"""认证服务：登录、用户/角色管理、8 角色权限矩阵。

对齐 S3 方案 §4：
- 8 角色：receiver/putaway/picker/checker/packer/shipper/purchaser/admin
- role.permissions JSON：页面 key → write/read/none
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BizError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.system import Role, User

# ── 8 角色权限矩阵（对齐方案 §4.1，26 页面）──
# 页面 key 采用 snake_case，权限：write=● / read=○ / none=-
ROLE_PERMISSIONS: dict[str, dict[str, str]] = {
    "receiver": {
        "order_list": "read", "arrival_receipt": "write",
        "cross_dock_dispatch": "write",
        "purchase_order": "read", "supplier": "read",
    },
    "putaway": {
        "location_manage": "write", "putaway_task": "write",
        "stock_ledger": "read", "order_list": "read",
    },
    "picker": {
        "order_list": "write", "picking_task": "write",
        "stock_ledger": "read", "batch_expiry": "read",
    },
    "checker": {
        "order_list": "write", "manual_review_queue": "write",
        "exception_queue": "write", "check_operation": "write",
        "stock_ledger": "read", "batch_expiry": "read",
    },
    "packer": {
        "order_list": "write", "pack_operation": "write",
        "label_print": "write",
    },
    "shipper": {
        "order_list": "write", "outbound_manage": "write",
        "label_print": "write", "stock_ledger": "read",
    },
    "purchaser": {
        "purchase_order": "write", "replenishment_advice": "write",
        "supplier": "write", "warning_center": "read",
        "stock_ledger": "read", "order_list": "read",
        "arrival_receipt": "read", "sku_master": "read",
    },
    "admin": {
        # admin 拥有全部页面写权限（require_permission 直接放行）
        "order_list": "write", "order_import": "write",
        "manual_review_queue": "write", "exception_queue": "write",
        "picking_task": "read", "check_operation": "read",
        "pack_operation": "read", "outbound_manage": "write",
        "label_print": "write", "stock_ledger": "write",
        "stock_transaction": "write", "location_manage": "write",
        "stock_adjust": "write", "batch_expiry": "write",
        "warning_center": "write", "purchase_order": "write",
        "replenishment_advice": "write", "arrival_receipt": "write",
        "putaway_task": "read", "cross_dock_dispatch": "write",
        "sku_master": "write", "initial_import": "write",
        "supplier": "write", "rule_config": "write",
        "user_role": "write", "operation_log": "write",
        "stocktake": "write",
    },
}

ROLE_NAMES: dict[str, str] = {
    "receiver": "收货员",
    "putaway": "上架员",
    "picker": "拣货员",
    "checker": "复核员",
    "packer": "打包员",
    "shipper": "发货员",
    "purchaser": "采购员",
    "admin": "管理员",
}


def seed_roles(db: Session) -> list[Role]:
    """幂等初始化 8 角色及其权限矩阵。已存在则更新 permissions。"""
    created = []
    for code, name in ROLE_NAMES.items():
        role = db.scalar(select(Role).where(Role.code == code))
        perms = ROLE_PERMISSIONS.get(code, {})
        if role is None:
            role = Role(name=name, code=code, permissions=perms)
            db.add(role)
        else:
            role.name = name
            role.permissions = perms
        created.append(role)
    db.flush()
    return created


def seed_admin_user(db: Session, username: str = "admin", password: str = "admin123") -> User:
    """创建默认管理员用户（幂等）。"""
    seed_roles(db)
    admin_role = db.scalar(select(Role).where(Role.code == "admin"))
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            password_hash=hash_password(password),
            real_name="系统管理员",
            role_id=admin_role.id,
            status=1,
        )
        db.add(user)
        db.flush()
    return user


def login(db: Session, username: str, password: str) -> dict:
    """登录：校验用户名密码，返回 JWT。"""
    user = db.scalar(select(User).where(User.username == username))
    if user is None or user.status != 1:
        raise BizError("用户名或密码错误", 401)
    if not verify_password(password, user.password_hash):
        raise BizError("用户名或密码错误", 401)

    role = db.get(Role, user.role_id)
    token = create_access_token(user.id, role.code if role else "")
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "role_code": role.code if role else None,
            "role_name": role.name if role else None,
        },
    }


def list_users(db: Session) -> list[dict]:
    """用户列表（含角色信息）。"""
    rows = db.execute(select(User, Role).join(Role, User.role_id == Role.id)).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name,
            "status": u.status,
            "role_code": r.code,
            "role_name": r.name,
        }
        for u, r in rows
    ]


def list_roles(db: Session) -> list[dict]:
    """角色列表（含权限矩阵）。"""
    rows = db.execute(select(Role).order_by(Role.id)).scalars().all()
    return [
        {"id": r.id, "name": r.name, "code": r.code, "permissions": r.permissions}
        for r in rows
    ]
