"""
Audit logging helper. Any controller that performs a meaningful admin
action calls log_action() — this keeps logging in one place instead
of scattered across the codebase (same pattern as notification_controller).
"""
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.people import User


def log_action(db: Session, user_id: int | None, action: str, table_name: str, record_id: int | None = None, details: str | None = None) -> None:
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        details=details,
    ))
    db.commit()


# Which OTHER roles' entries each role is allowed to see, in addition to
# its own. None means "no restriction" (sees every role, including
# system/unattributed entries). Admin is the only role with full
# visibility; everyone else is scoped so nobody below Admin can see
# Admin's actions.
_VISIBLE_ROLES: dict[str, list[str] | None] = {
    "Admin": None,
    "HR": ["HR", "Manager", "Employee"],
    "Manager": ["Manager", "HR", "Employee"],
    "Employee": ["Employee"],
}


def list_audit_log(db: Session, current_user: User, limit: int = 100) -> list[dict]:
    """
    Role-scoped audit trail:
      - Admin sees every user's actions.
      - HR sees its own actions plus Manager's and Employee's (not Admin's).
      - Manager sees its own actions plus HR's and Employee's (not Admin's).
      - Employee sees only its own actions.
    Each row is annotated with who performed it (username/role_name) so a
    multi-user log is actually readable, not just a list of bare user IDs.
    """
    visible_roles = _VISIBLE_ROLES.get(current_user.role_name, [current_user.role_name])

    query = db.query(AuditLog, User.username, User.role_name).outerjoin(
        User, AuditLog.user_id == User.user_id
    )
    if visible_roles is not None:
        query = query.filter(User.role_name.in_(visible_roles))

    rows = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    return [
        {
            "log_id": log.log_id,
            "user_id": log.user_id,
            "username": username,
            "role_name": actor_role,
            "action": log.action,
            "table_name": log.table_name,
            "record_id": log.record_id,
            "details": log.details,
            "timestamp": log.timestamp,
        }
        for log, username, actor_role in rows
    ]
