"""安全模块：JWT 认证 + 密码哈希 + 权限依赖注入。

T3.2 权限留痕核心：
- 密码哈希（passlib bcrypt）
- JWT 生成/校验（python-jose）
- require_permission(route)：从 JWT 解析 user → role → permissions，无权限返回 403
"""
from datetime import datetime, timedelta
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.system import Role, User

# JWT 算法
ALGORITHM = "HS256"

# Bearer token 安全方案
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """密码哈希（bcrypt 直接调用，规避 passlib 与 bcrypt 5.x 的兼容问题）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int, role_code: str) -> str:
    """生成 JWT access token。"""
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role_code,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """解析 JWT，失败返回 None。"""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI 依赖：从 Bearer token 解析当前用户。

    无 token 或无效 token 返回 401。
    """
    if credentials is None:
        raise HTTPException(401, "未认证：缺少 Bearer token")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(401, "无效或过期的 token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(401, "token 缺少用户标识")

    user = db.get(User, int(user_id))
    if user is None or user.status != 1:
        raise HTTPException(401, "用户不存在或已禁用")
    return user


def get_current_role(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Role:
    """获取当前用户的角色。"""
    role = db.get(Role, user.role_id)
    if role is None:
        raise HTTPException(403, "用户未绑定有效角色")
    return role


def require_permission(page: str, level: str = "write"):
    """权限校验依赖工厂。

    :param page: 页面 key（对齐权限矩阵，如 "order_list" / "print_label"）
    :param level: 所需最低权限 "read" / "write"（write 高于 read）

    返回依赖函数：解析 JWT → user → role → permissions，判断该页面的权限等级。
    - 无 token：401
    - 权限不足：403
    - admin 角色直接放行（拥有全部页面写权限）
    """
    def _check(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        role = db.get(Role, user.role_id)
        if role is None:
            raise HTTPException(403, "用户未绑定有效角色")

        # admin 角色拥有全部权限
        if role.code == "admin":
            return user

        perms = role.permissions or {}
        page_perm = perms.get(page, "none")

        # 权限等级：write > read > none
        rank = {"write": 2, "read": 1, "none": 0}
        if rank.get(page_perm, 0) < rank.get(level, 1):
            raise HTTPException(
                403,
                f"权限不足：角色 {role.code} 对页面 {page} 无 {level} 权限（当前 {page_perm}）",
            )
        return user

    return _check


def write_operation_log(
    db: Session,
    user_id: int | None,
    module: str,
    action: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
    detail: str | None = None,
    ip: str | None = None,
) -> None:
    """写操作日志（同一事务内调用）。

    对齐数据字典 §9.3。打印/出库为强制留痕点。
    """
    from app.models.system import OperationLog

    log = OperationLog(
        user_id=user_id or 0,
        module=module,
        action=action,
        ref_type=ref_type,
        ref_id=ref_id,
        detail=detail,
        ip=ip,
    )
    db.add(log)
