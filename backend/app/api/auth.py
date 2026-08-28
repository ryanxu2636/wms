"""认证/权限 API：登录、用户管理、角色管理、操作日志查询。

T3.2 权限留痕：
- POST /auth/login：登录获取 JWT
- GET  /auth/users：用户列表（admin）
- GET  /auth/roles：角色列表（admin）
- POST /auth/users：创建用户（admin）
- GET  /auth/logs：操作日志查询（admin）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BizError
from app.core.security import get_current_user, hash_password, require_permission
from app.models.system import OperationLog, Role, User
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证/权限"])


@router.post("/login")
def login(payload: dict, db: Session = Depends(get_db)):
    """登录：{username, password} → {access_token, user}。"""
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        raise HTTPException(400, "缺少 username 或 password")
    try:
        result = auth_service.login(db, username, password)
        return result
    except BizError as e:
        raise HTTPException(e.status_code, e.message)


@router.get("/users")
def list_users(
    _: User = Depends(require_permission("user_role", "write")),
    db: Session = Depends(get_db),
):
    """用户列表（需 user_role 写权限，即 admin）。"""
    return auth_service.list_users(db)


@router.get("/roles")
def list_roles(
    _: User = Depends(require_permission("user_role", "write")),
    db: Session = Depends(get_db),
):
    """角色列表 + 权限矩阵（需 admin）。"""
    return auth_service.list_roles(db)


@router.post("/users")
def create_user(
    payload: dict,
    _: User = Depends(require_permission("user_role", "write")),
    db: Session = Depends(get_db),
):
    """创建用户（需 admin）。{username, password, real_name, role_code}"""
    username = payload.get("username")
    password = payload.get("password")
    role_code = payload.get("role_code")
    if not username or not password or not role_code:
        raise HTTPException(400, "缺少 username/password/role_code")

    role = db.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise HTTPException(400, f"角色 {role_code} 不存在")

    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        raise HTTPException(409, f"用户名 {username} 已存在")

    user = User(
        username=username,
        password_hash=hash_password(password),
        real_name=payload.get("real_name"),
        role_id=role.id,
        status=1,
    )
    db.add(user)
    db.commit()
    return {"id": user.id, "username": user.username, "role_code": role_code}


@router.get("/logs")
def list_logs(
    _: User = Depends(require_permission("operation_log", "write")),
    db: Session = Depends(get_db),
    module: str | None = None,
    limit: int = 100,
):
    """操作日志查询（需 admin）。可按 module 过滤。"""
    q = select(OperationLog).order_by(OperationLog.id.desc()).limit(min(limit, 500))
    if module:
        q = q.where(OperationLog.module == module)
    logs = db.execute(q).scalars().all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "module": l.module,
            "action": l.action,
            "ref_type": l.ref_type,
            "ref_id": l.ref_id,
            "detail": l.detail,
            "ip": l.ip,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]
