"""
Shared dependencies: get_current_user (from JWT) and require_permission
(checks the role_permissions table — matches our Roles & Permissions
matrix UI exactly).
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.org import Permission, Role, role_permissions
from app.models.people import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    # A partial 2FA token (issued after a correct password, before the
    # TOTP code is verified) must never work as a real access token —
    # it's only valid at POST /api/auth/2fa/verify, which reads it
    # directly rather than through this dependency.
    if payload.get("purpose") == "2fa_pending":
        raise HTTPException(status_code=401, detail="Two-factor verification required.")

    user = db.query(User).filter(User.user_id == int(payload["sub"])).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")
    return user


def require_permission(permission_name: str):
    """
    Usage: @router.get(..., dependencies=[Depends(require_permission("approve_leave"))])
    Mirrors exactly what the Roles & Permissions matrix UI controls.
    """

    def checker(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        has_permission = (
            db.query(Permission)
            .join(role_permissions, Permission.permission_id == role_permissions.c.permission_id)
            .join(Role, Role.role_id == role_permissions.c.role_id)
            .filter(Role.role_id == current_user.role_id, Permission.permission_name == permission_name)
            .first()
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role does not have the '{permission_name}' permission.",
            )
        return current_user

    return checker


def require_any_permission(*permission_names: str):
    """
    Like require_permission, but succeeds if the user's role has ANY one
    of the given permissions. Used where two different roles are allowed
    to reach the same route for different reasons — e.g. PATCH
    /api/employees/{id} is reachable by Admin/HR via 'manage_employees'
    (full edit) OR by a Manager via 'edit_employee_assignment' (their
    team's department/position/shift/manager only).
    """

    def checker(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        has_permission = (
            db.query(Permission)
            .join(role_permissions, Permission.permission_id == role_permissions.c.permission_id)
            .join(Role, Role.role_id == role_permissions.c.role_id)
            .filter(Role.role_id == current_user.role_id, Permission.permission_name.in_(permission_names))
            .first()
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role does not have any of the required permissions: {', '.join(permission_names)}.",
            )
        return current_user

    return checker
