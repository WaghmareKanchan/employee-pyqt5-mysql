from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.controllers import attendance_controller
from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.people import User
from app.schemas.attendance import AttendanceOut

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


def _require_employee(current_user: User) -> int:
    if current_user.employee_id is None:
        raise HTTPException(status_code=400, detail="This account is not linked to an employee record.")
    return current_user.employee_id


@router.post("/check-in", response_model=AttendanceOut, status_code=201)
def check_in(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    employee_id = _require_employee(current_user)
    return attendance_controller.check_in(db, employee_id)


@router.post("/check-out", response_model=AttendanceOut, status_code=200)
def check_out(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    employee_id = _require_employee(current_user)
    return attendance_controller.check_out(db, employee_id)


@router.get("/me", response_model=list[AttendanceOut])
def my_attendance(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    employee_id = _require_employee(current_user)
    return attendance_controller.list_my_attendance(db, employee_id)


@router.get("", response_model=list[AttendanceOut])
def all_attendance(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(require_permission("view_reports")),
):
    return attendance_controller.list_all_attendance(db, skip, limit)
