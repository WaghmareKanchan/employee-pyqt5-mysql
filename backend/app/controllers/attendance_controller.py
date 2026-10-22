"""
Attendance business logic.

This is a direct implementation of the flowchart we designed earlier:

  ON CHECK-IN:
    if check_in.time() > shift.late_cutoff:
        status = 'Half Day', reason = 'Late arrival'   -> day already decided
    else:
        status = 'Pending', reason = 'Check-out pending'

  ON CHECK-OUT (only matters if status was still 'Pending'):
    total_hours = check_out - check_in
    if total_hours < shift.min_half_day_hours:
        status = 'Half Day', reason = 'Early leave'
    else:
        status = 'Present', reason = 'Present'
"""
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.controllers import notification_controller
from app.models.attendance import Attendance
from app.models.people import Employee
from app.services import email_service


def check_in(db: Session, employee_id: int) -> Attendance:
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if employee is None or employee.shift_id is None:
        raise HTTPException(status_code=400, detail="No shift assigned to this employee.")

    today = date.today()
    existing = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee_id, Attendance.work_date == today)
        .first()
    )
    if existing is not None and existing.check_in is not None:
        raise HTTPException(status_code=409, detail="Already checked in today.")

    now = datetime.now()
    shift = employee.shift

    if shift.late_cutoff and now.time() > shift.late_cutoff:
        status, reason, is_late = "Half Day", "Late arrival", 1
    else:
        status, reason, is_late = "Pending", "Check-out pending", 0

    attendance = existing or Attendance(employee_id=employee_id, shift_id=employee.shift_id, work_date=today)
    attendance.check_in = now
    attendance.status = status
    attendance.status_reason = reason
    attendance.is_late = is_late

    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    # One attendance row per person per day, and a second check-in is
    # rejected above, so this alert can be sent at most once a day.
    if is_late:
        # In-app notice (kept from the original project) + email.
        # Done AFTER the commit so attendance_id is filled in.
        notification_controller.notify_employee(
            db, employee_id,
            title="Late arrival recorded",
            message=f"Your check-in on {attendance.work_date} was recorded after the shift's late cutoff.",
            reference_table="attendance",
            reference_id=attendance.attendance_id,
        )
        email_service.notify_late_arrival(db, employee, attendance)
    return attendance


def check_out(db: Session, employee_id: int) -> Attendance:
    today = date.today()
    attendance = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee_id, Attendance.work_date == today)
        .first()
    )
    if attendance is None or attendance.check_in is None:
        raise HTTPException(status_code=400, detail="You have not checked in today.")
    if attendance.check_out is not None:
        raise HTTPException(status_code=409, detail="Already checked out today.")

    now = datetime.now()
    total_hours = round((now - attendance.check_in).total_seconds() / 3600, 2)

    # If check-in already decided "Half Day / Late arrival", that stands regardless of hours worked.
    if attendance.status == "Pending":
        employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
        shift = employee.shift
        if total_hours < float(shift.min_half_day_hours):
            attendance.status, attendance.status_reason = "Half Day", "Early leave"
        else:
            attendance.status, attendance.status_reason = "Present", "Present"

    attendance.check_out = now
    attendance.total_hours = total_hours
    db.commit()
    db.refresh(attendance)
    return attendance


def list_my_attendance(db: Session, employee_id: int) -> list[Attendance]:
    return (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee_id)
        .order_by(Attendance.work_date.desc())
        .all()
    )


def list_all_attendance(db: Session, skip: int = 0, limit: int = 50) -> list[Attendance]:
    return db.query(Attendance).order_by(Attendance.work_date.desc()).offset(skip).limit(limit).all()
