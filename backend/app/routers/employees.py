from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.controllers import employee_controller
from app.database import get_db
from app.dependencies import require_any_permission, require_permission
from app.models.people import Employee
from app.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeCredentialsOut,
    EmployeeHistoryOut,
    EmployeeOut,
    EmployeeRoleUpdateRequest,
    EmployeeUpdateRequest,
    PersonalEmailUpdateRequest,
)

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    skip: int = Query(0, ge=0, description="How many records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return (1-200)"),
    db: Session = Depends(get_db),
    # Admin/HR (full directory) OR Manager (needs the list to pick a
    # team member to edit via 'edit_employee_assignment').
    _current_user=Depends(require_any_permission("manage_employees", "edit_employee_assignment")),
):
    return db.query(Employee).offset(skip).limit(limit).all()


@router.post("", response_model=EmployeeCredentialsOut, status_code=201)
def create_employee(
    payload: EmployeeCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("assign_roles")),
):
    """Admin and HR can both reach this (both hold 'assign_roles'). Admin
    may create an account with any role; HR may only create Manager or
    Employee accounts — that scoping is enforced in the controller,
    since a permission row can't express "except Admin/HR"."""
    _employee, email, invitation_queued = employee_controller.create_employee_with_account(
        db, payload, current_user.user_id, current_user.role.role_name,
    )
    message = (
        f"User created. An invitation was queued for {payload.personal_email}."
        if invitation_queued else
        "User created, but the invitation could not be queued. Use 'Resend Invitation'."
    )
    return EmployeeCredentialsOut(
        email=email, personal_email=payload.personal_email,
        invitation_queued=invitation_queued, message=message,
    )


@router.post("/{employee_id}/resend-invitation", status_code=200)
def resend_invitation(
    employee_id: int,
    db: Session = Depends(get_db),
    # Same permission + same role rule as creating the account.
    current_user=Depends(require_permission("assign_roles")),
):
    employee_controller.resend_invitation(db, employee_id, current_user.user_id, current_user.role.role_name)
    return {"message": "Invitation queued."}


@router.patch("/{employee_id}/personal-email", response_model=EmployeeOut, status_code=200)
def change_personal_email(
    employee_id: int,
    payload: PersonalEmailUpdateRequest,
    db: Session = Depends(get_db),
    # Admin/HR only. NOT the Manager's 'edit_employee_assignment': this
    # address receives password-reset codes, so changing it is account-takeover-sensitive.
    current_user=Depends(require_permission("manage_employees")),
):
    return employee_controller.set_personal_email(
        db, employee_id, payload.personal_email, current_user.user_id, current_user.role.role_name,
    )


@router.patch("/{employee_id}/role", response_model=EmployeeOut, status_code=200)
def change_role(
    employee_id: int,
    payload: EmployeeRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("assign_roles")),
):
    """
    Promotes/demotes an existing employee between Employee / Manager /
    HR / Admin. Admin can assign any role; HR can only promote/demote an
    employee into or out of Manager/Employee (never touching an Admin
    or HR account, and never granting Admin or HR) — enforced in the
    controller.
    """
    return employee_controller.change_employee_role(
        db, employee_id, payload.role_name, current_user.user_id, current_user.role.role_name,
    )


@router.patch("/{employee_id}/suspend", status_code=200)
def suspend(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_employees")),
):
    employee_controller.suspend_employee(db, employee_id, current_user.user_id)
    return {"message": "Employee account suspended."}


@router.patch("/{employee_id}/reactivate", status_code=200)
def reactivate(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_employees")),
):
    employee_controller.reactivate_employee(db, employee_id, current_user.user_id)
    return {"message": "Employee account reactivated."}


@router.delete("/{employee_id}", status_code=200)
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    # Same scope as suspend/reactivate: Admin/HR only. Manager has
    # 'edit_employee_assignment' but not 'manage_employees', so Manager
    # can edit a team member's assignment but not delete their record.
    current_user=Depends(require_permission("manage_employees")),
):
    employee_controller.delete_employee(db, employee_id, current_user.user_id)
    return {"message": "Employee deleted."}


@router.patch("/{employee_id}", response_model=EmployeeOut, status_code=200)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    db: Session = Depends(get_db),
    # Admin/HR via 'manage_employees', or a Manager via
    # 'edit_employee_assignment' — same endpoint, same fields
    # (department/position/employment type/shift/manager only).
    current_user=Depends(require_any_permission("manage_employees", "edit_employee_assignment")),
):
    return employee_controller.update_employee(db, employee_id, payload, current_user.user_id)


@router.get("/{employee_id}/history", response_model=list[EmployeeHistoryOut])
def employee_history(
    employee_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(require_permission("manage_employees")),
):
    return employee_controller.get_employee_history(db, employee_id)
