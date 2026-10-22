"""
Notification helper. Other controllers (leave, overtime) call
notify() to write a notification — this keeps notification creation
in one place instead of scattered across the codebase.
"""
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.people import Employee, User


def notify(db: Session, user_id: int, title: str, message: str, reference_table: str = None, reference_id: int = None, employee_id: int = None) -> None:
    if user_id is None:
        return  # no recipient (e.g. employee has no manager) — silently skip
    db.add(Notification(
        user_id=user_id,
        employee_id=employee_id,
        title=title,
        message=message,
        reference_table=reference_table,
        reference_id=reference_id,
    ))
    db.commit()


def notify_manager_of_employee(db: Session, employee_id: int, title: str, message: str, reference_table: str = None, reference_id: int = None) -> None:
    """Looks up the employee's manager and notifies their user account, if
    one exists. employee_id is stamped on the notification too, so the
    manager's notification list shows exactly which employee it's about."""
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if employee is None or employee.manager_id is None:
        return
    manager_user = db.query(User).filter(User.employee_id == employee.manager_id).first()
    if manager_user is None:
        return
    notify(db, manager_user.user_id, title, message, reference_table, reference_id, employee_id=employee_id)


def notify_employee(db: Session, employee_id: int, title: str, message: str, reference_table: str = None, reference_id: int = None) -> None:
    """Notifies the employee's own user account (e.g. their leave got approved)."""
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if user is None:
        return
    notify(db, user.user_id, title, message, reference_table, reference_id, employee_id=employee_id)


def list_my_notifications(db: Session, user_id: int) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


def mark_as_read(db: Session, notification_id: int, user_id: int) -> Notification:
    from fastapi import HTTPException

    notification = (
        db.query(Notification)
        .filter(Notification.notification_id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    notification.is_read = 1
    db.commit()
    db.refresh(notification)
    return notification
