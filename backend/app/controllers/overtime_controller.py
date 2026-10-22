"""
Overtime business logic. Mirrors the leave_requests pattern, plus the
corporate rule we designed: overtime is capped at the shift's
max_ot_hours_per_day, and requires approval before it counts.
"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.controllers import audit_controller, notification_controller
from app.models.attendance import Overtime
from app.models.people import Employee, User
from app.schemas.overtime import OvertimeCreate
from app.services import email_service


def apply_overtime(db: Session, employee_id: int, payload: OvertimeCreate) -> Overtime:
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if employee is None or employee.shift_id is None:
        raise HTTPException(status_code=400, detail="No shift assigned to this employee.")

    shift = employee.shift
    capped_hours = min(payload.hours, float(shift.max_ot_hours_per_day))

    overtime = Overtime(
        employee_id=employee_id,
        work_date=payload.work_date,
        hours=capped_hours,
        status="Pending" if shift.requires_ot_approval else "Approved",
    )
    db.add(overtime)
    db.commit()
    db.refresh(overtime)

    notification_controller.notify_manager_of_employee(
        db, employee_id,
        title="New overtime request",
        message=f"An overtime request for {payload.work_date} ({capped_hours} hrs) is awaiting your decision.",
        reference_table="overtime",
        reference_id=overtime.overtime_id,
    )
    # Only email an approver when a decision is actually awaited
    # (shifts that don't require OT approval auto-approve it).
    if overtime.status == "Pending":
        email_service.notify_approvers_of_new_request(db, employee_id, "overtime", _ot_details(overtime))
    return overtime


def _ot_details(overtime: Overtime) -> list[tuple[str, str]]:
    return [("Date", str(overtime.work_date)), ("Hours", str(float(overtime.hours)))]


def decide_overtime(db: Session, overtime_id: int, approver: User, approve: bool) -> Overtime:
    overtime = db.query(Overtime).filter(Overtime.overtime_id == overtime_id).first()
    if overtime is None:
        raise HTTPException(status_code=404, detail="Overtime request not found.")

    # Same corporate-level safeguard as leave: never allow self-approval.
    if overtime.employee_id == approver.employee_id:
        raise HTTPException(status_code=403, detail="You cannot approve your own overtime request.")

    overtime.status = "Approved" if approve else "Rejected"
    overtime.approved_by = approver.user_id
    db.commit()
    db.refresh(overtime)

    audit_controller.log_action(db, approver.user_id, overtime.status.upper(), "overtime", overtime.overtime_id)

    notification_controller.notify_employee(
        db, overtime.employee_id,
        title=f"Overtime request {overtime.status.lower()}",
        message=f"Your overtime request for {overtime.work_date} was {overtime.status.lower()}.",
        reference_table="overtime",
        reference_id=overtime.overtime_id,
    )
    email_service.notify_requester_of_decision(
        db, overtime.employee_id, "overtime", overtime.status, _ot_details(overtime),
        approver.employee.full_name if approver.employee else approver.username,
    )
    return overtime


def list_my_overtime(db: Session, employee_id: int) -> list[Overtime]:
    return db.query(Overtime).filter(Overtime.employee_id == employee_id).all()


def list_all_overtime(db: Session, skip: int = 0, limit: int = 50) -> list[Overtime]:
    return db.query(Overtime).offset(skip).limit(limit).all()
