from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.controllers import audit_controller
from app.database import get_db
from app.dependencies import get_current_user
from app.models.people import User
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/api/audit-log", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    # Any authenticated role can reach this. Visibility is role-scoped
    # in the controller: Admin sees everyone; HR sees HR/Manager/Employee;
    # Manager sees Manager/HR/Employee; Employee sees only its own —
    # nobody below Admin can see Admin's entries.
    current_user: User = Depends(get_current_user),
):
    return audit_controller.list_audit_log(db, current_user, limit)
