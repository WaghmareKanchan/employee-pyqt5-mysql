from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.controllers import overtime_controller
from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.people import User
from app.schemas.overtime import OvertimeCreate, OvertimeDecision, OvertimeOut

router = APIRouter(prefix="/api/overtime", tags=["overtime"])


@router.post("", response_model=OvertimeOut, status_code=201)
def apply_overtime(
    payload: OvertimeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.employee_id is None:
        raise HTTPException(status_code=400, detail="This account is not linked to an employee record.")
    return overtime_controller.apply_overtime(db, current_user.employee_id, payload)


@router.put("/{overtime_id}/decision", response_model=OvertimeOut, status_code=200)
def decide_overtime(
    overtime_id: int,
    payload: OvertimeDecision,
    current_user: User = Depends(require_permission("approve_overtime")),
    db: Session = Depends(get_db),
):
    return overtime_controller.decide_overtime(db, overtime_id, current_user, payload.approve)


@router.get("/me", response_model=list[OvertimeOut])
def my_overtime(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.employee_id is None:
        raise HTTPException(status_code=400, detail="This account is not linked to an employee record.")
    return overtime_controller.list_my_overtime(db, current_user.employee_id)


@router.get("", response_model=list[OvertimeOut])
def all_overtime(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(require_permission("view_reports")),
):
    return overtime_controller.list_all_overtime(db, skip, limit)
