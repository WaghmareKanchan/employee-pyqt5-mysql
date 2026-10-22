from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.controllers import org_controller
from app.database import get_db
from app.dependencies import get_current_user, require_any_permission, require_permission
from app.schemas.org import (
    DepartmentCreate,
    DepartmentOut,
    PositionCreate,
    PositionOut,
    ShiftCreate,
    ShiftOut,
)

router = APIRouter(prefix="/api", tags=["organization"])


# ---- Departments ----
@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return org_controller.list_departments(db, skip, limit)


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_departments")),
):
    return org_controller.create_department(db, payload, current_user.user_id)


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int,
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    # Admin/HR/Manager can EDIT an existing department. Add/delete stay
    # 'manage_departments' only (Admin), enforced on the POST/DELETE
    # routes below, which weren't changed.
    current_user=Depends(require_any_permission("manage_departments", "edit_org_structure")),
):
    return org_controller.update_department(db, department_id, payload, current_user.user_id)


@router.delete("/departments/{department_id}", status_code=200)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_departments")),
):
    org_controller.delete_department(db, department_id, current_user.user_id)
    return {"message": "Department deleted."}


# ---- Positions ----
@router.get("/positions", response_model=list[PositionOut])
def list_positions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return org_controller.list_positions(db, skip, limit)


@router.post("/positions", response_model=PositionOut, status_code=201)
def create_position(
    payload: PositionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_departments")),
):
    return org_controller.create_position(db, payload, current_user.user_id)


@router.patch("/positions/{position_id}", response_model=PositionOut)
def update_position(
    position_id: int,
    payload: PositionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission("manage_departments", "edit_org_structure")),
):
    return org_controller.update_position(db, position_id, payload, current_user.user_id)


@router.delete("/positions/{position_id}", status_code=200)
def delete_position(
    position_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_departments")),
):
    org_controller.delete_position(db, position_id, current_user.user_id)
    return {"message": "Position deleted."}


# ---- Shifts ----
@router.get("/shifts", response_model=list[ShiftOut])
def list_shifts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return org_controller.list_shifts(db, skip, limit)


@router.post("/shifts", response_model=ShiftOut, status_code=201)
def create_shift(
    payload: ShiftCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_shifts")),
):
    return org_controller.create_shift(db, payload, current_user.user_id)


@router.patch("/shifts/{shift_id}", response_model=ShiftOut)
def update_shift(
    shift_id: int,
    payload: ShiftCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission("manage_shifts", "edit_org_structure")),
):
    return org_controller.update_shift(db, shift_id, payload, current_user.user_id)


@router.delete("/shifts/{shift_id}", status_code=200)
def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_shifts")),
):
    org_controller.delete_shift(db, shift_id, current_user.user_id)
    return {"message": "Shift deleted."}
