from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.controllers import leave_controller
from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.people import User
from app.schemas.leave import LeaveBalanceOut, LeaveDecisionRequest, LeaveRequestCreate, LeaveRequestOut

router = APIRouter(prefix="/api/leave-requests", tags=["leave"])


@router.post("", response_model=LeaveRequestOut, status_code=201)
def apply_leave(
    payload: LeaveRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.employee_id is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="This account is not linked to an employee record.")
    return leave_controller.apply_leave(db, current_user.employee_id, payload)


@router.put("/{leave_request_id}/decision", response_model=LeaveRequestOut, status_code=200)
def decide_leave(
    leave_request_id: int,
    payload: LeaveDecisionRequest,
    current_user: User = Depends(require_permission("approve_leave")),
    db: Session = Depends(get_db),
):
    return leave_controller.decide_leave(db, leave_request_id, current_user, payload.approve)


@router.get("/me/balance", response_model=list[LeaveBalanceOut])
def my_leave_balance(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.employee_id is None:
        raise HTTPException(status_code=400, detail="This account is not linked to an employee record.")
    return leave_controller.get_leave_balance(db, current_user.employee_id, date.today().year)


@router.get("/me", response_model=list[LeaveRequestOut])
def my_leave_requests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mirrors GET /api/overtime/me — this employee's own leave requests
    and their status, browsable directly instead of via notifications."""
    if current_user.employee_id is None:
        raise HTTPException(status_code=400, detail="This account is not linked to an employee record.")
    return leave_controller.list_my_leave(db, current_user.employee_id)


@router.get("", response_model=list[LeaveRequestOut])
def all_leave_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    # Same permission OT's "All Requests / Approvals" list uses —
    # Admin/HR/Manager all hold 'view_reports'.
    _user=Depends(require_permission("view_reports")),
):
    return leave_controller.list_all_leave(db, skip, limit)
