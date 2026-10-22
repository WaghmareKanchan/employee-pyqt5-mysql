from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.controllers import audit_controller, notification_controller
from app.models.leave import LeaveRequest
from app.models.people import User
from app.schemas.leave import LeaveRequestCreate
from app.services import email_service


def apply_leave(db: Session, employee_id: int, payload: LeaveRequestCreate) -> LeaveRequest:
    leave = LeaveRequest(
        employee_id=employee_id,
        leave_type_id=payload.leave_type_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        status="Pending",
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)

    notification_controller.notify_manager_of_employee(
        db, employee_id,
        title="New leave request",
        message=f"A leave request from {payload.start_date} to {payload.end_date} is awaiting your decision.",
        reference_table="leave_requests",
        reference_id=leave.leave_request_id,
    )

    email_service.notify_approvers_of_new_request(db, employee_id, "leave", _leave_details(leave))
    return leave


def _leave_details(leave: LeaveRequest) -> list[tuple[str, str]]:
    days = (leave.end_date - leave.start_date).days + 1
    return [
        ("Leave type", leave.leave_type.type_name if leave.leave_type else "-"),
        ("From", str(leave.start_date)),
        ("To", str(leave.end_date)),
        ("Days", str(days)),
        ("Reason", leave.reason or "-"),
    ]


def decide_leave(db: Session, leave_request_id: int, approver: User, approve: bool) -> LeaveRequest:
    leave = db.query(LeaveRequest).filter(LeaveRequest.leave_request_id == leave_request_id).first()
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave request not found.")

    # Corporate-level safeguard we designed earlier: never allow self-approval,
    # regardless of what the approver's role permissions say.
    if leave.employee_id == approver.employee_id:
        raise HTTPException(status_code=403, detail="You cannot approve your own leave request.")

    leave.status = "Approved" if approve else "Rejected"
    leave.approved_by = approver.user_id
    leave.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(leave)

    if approve:
        _update_leave_balance(db, leave)

    audit_controller.log_action(db, approver.user_id, leave.status.upper(), "leave_requests", leave.leave_request_id)

    notification_controller.notify_employee(
        db, leave.employee_id,
        title=f"Leave request {leave.status.lower()}",
        message=f"Your leave request from {leave.start_date} to {leave.end_date} was {leave.status.lower()}.",
        reference_table="leave_requests",
        reference_id=leave.leave_request_id,
    )
    email_service.notify_requester_of_decision(
        db, leave.employee_id, "leave", leave.status, _leave_details(leave),
        approver.employee.full_name if approver.employee else approver.username,
    )
    return leave


def _update_leave_balance(db: Session, leave: LeaveRequest) -> None:
    """
    Deducts approved days from the employee's leave balance for that
    leave type and year. Creates the balance row on first use, seeded
    from leave_types.max_days_per_year.
    """
    from app.models.leave import LeaveBalance, LeaveType

    days_taken = (leave.end_date - leave.start_date).days + 1
    year = leave.start_date.year

    balance = (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == leave.employee_id,
            LeaveBalance.leave_type_id == leave.leave_type_id,
            LeaveBalance.year == year,
        )
        .first()
    )

    if balance is None:
        leave_type = db.query(LeaveType).filter(LeaveType.leave_type_id == leave.leave_type_id).first()
        allocated = leave_type.max_days_per_year if leave_type and leave_type.max_days_per_year else 0
        balance = LeaveBalance(
            employee_id=leave.employee_id,
            leave_type_id=leave.leave_type_id,
            year=year,
            allocated_days=allocated,
            used_days=0,
        )
        db.add(balance)

    balance.used_days = float(balance.used_days or 0) + days_taken
    db.commit()


def get_leave_balance(db: Session, employee_id: int, year: int):
    from app.models.leave import LeaveBalance

    return db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id, LeaveBalance.year == year
    ).all()


def list_my_leave(db: Session, employee_id: int) -> list[LeaveRequest]:
    return (
        db.query(LeaveRequest)
        .filter(LeaveRequest.employee_id == employee_id)
        .order_by(LeaveRequest.leave_request_id.desc())
        .all()
    )


def list_all_leave(db: Session, skip: int = 0, limit: int = 50) -> list[LeaveRequest]:
    return (
        db.query(LeaveRequest)
        .order_by(LeaveRequest.leave_request_id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

