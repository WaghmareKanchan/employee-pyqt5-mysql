"""
Employee business logic: the Admin-provisioned account flow we
designed earlier — admin fills a form, backend generates the
company email + temp password, no public registration page exists.
"""
import re

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers import audit_controller
from app.core import config, security
from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.attendance import Overtime
from app.models.leave import LeaveRequest
from app.models.email import EmailPreference, EmailQueue
from app.models.employee_history import EmployeeHistory
from app.models.org import Department, EmploymentType, Position, Role, Shift
from app.models.people import Employee, User
from app.schemas.employee import EmployeeCreateRequest
from app.services import email_service


def _validate_foreign_keys(db: Session, payload: EmployeeCreateRequest) -> None:
    """
    Checks every referenced ID up front so a bad department/position/
    employment-type/shift/manager ID gets a clear, specific 400 instead
    of falling through to the generic IntegrityError handler (which used
    to mislabel every one of these as an email conflict).
    """
    checks = [
        (Department, payload.department_id, "department_id"),
        (Position, payload.position_id, "position_id"),
        (EmploymentType, payload.employment_type_id, "employment_type_id"),
        (Shift, payload.shift_id, "shift_id"),
    ]
    for model, value, field_name in checks:
        if value is None:
            continue
        pk_column = list(model.__table__.primary_key.columns)[0]
        if db.query(model).filter(pk_column == value).first() is None:
            raise HTTPException(
                status_code=400,
                detail=f"No {model.__tablename__[:-1] if model.__tablename__.endswith('s') else model.__tablename__} "
                       f"found with id {value} (field: {field_name}).",
            )

    if payload.manager_id is not None:
        if db.query(Employee).filter(Employee.employee_id == payload.manager_id).first() is None:
            raise HTTPException(
                status_code=400,
                detail=f"No employee found with id {payload.manager_id} (field: manager_id).",
            )


def _assert_personal_email_free(db: Session, personal_email: str, exclude_employee_id: int | None = None) -> None:
    """Personal email decides where password-reset codes go, so two accounts
    must never share one, and it must not be somebody's login address."""
    q = db.query(Employee).filter(Employee.personal_email == personal_email)
    if exclude_employee_id is not None:
        q = q.filter(Employee.employee_id != exclude_employee_id)
    clash = q.first() is not None or db.query(Employee).filter(Employee.email == personal_email).first() is not None
    if clash:
        raise HTTPException(status_code=409, detail="This personal email is already used by another account.")


def _unique_email(db: Session, full_name: str) -> str:
    """
    Slugifies the name into a company email and, if that address is
    already taken (e.g. two employees named "Kanchan"), appends the
    next available numeric suffix (kanchan2@, kanchan3@, ...) instead
    of failing outright. Checks both employees and users tables since
    both enforce email uniqueness.
    """
    base_slug = re.sub(r"\s+", ".", full_name.strip().lower())
    base_slug = re.sub(r"[^a-z.]", "", base_slug)

    candidate = f"{base_slug}@{config.COMPANY_EMAIL_DOMAIN}"
    suffix = 1
    while (
        db.query(Employee).filter(Employee.email == candidate).first() is not None
        or db.query(User).filter(User.email == candidate).first() is not None
    ):
        suffix += 1
        candidate = f"{base_slug}{suffix}@{config.COMPANY_EMAIL_DOMAIN}"

    return candidate


def _assert_role_assignment_allowed(acting_role_name: str, target_role_name: str, current_role_name: str | None = None) -> None:
    """
    Admin may assign any role. HR may only grant/hold the Manager or
    Employee role — HR can never create or promote someone into Admin
    or HR, and can never touch an account that is currently Admin or HR
    (that would be HR editing a peer or a superior's access).
    `current_role_name` is the employee's role BEFORE this change (None
    when creating a brand-new account).
    """
    if acting_role_name == "Admin":
        return
    if acting_role_name == "HR":
        if current_role_name in ("Admin", "HR"):
            raise HTTPException(
                status_code=403,
                detail="HR cannot change the role of an Admin or HR account.",
            )
        if target_role_name not in ("Manager", "Employee"):
            raise HTTPException(
                status_code=403,
                detail="HR can only assign the Manager or Employee role.",
            )
        return
    raise HTTPException(status_code=403, detail="You are not allowed to assign roles.")


def create_employee_with_account(db: Session, payload: EmployeeCreateRequest, acting_user_id: int, acting_role_name: str):
    """
    Creates the employee HR record AND its login account together,
    returns the one-time temporary password to show the admin.

    Reachable by Admin or HR (both hold 'assign_roles' — see schema.sql).
    Admin can create an account with any role; HR can only create a
    Manager or Employee account, checked below.
    """
    _assert_role_assignment_allowed(acting_role_name, payload.role_name)
    _validate_foreign_keys(db, payload)
    _assert_personal_email_free(db, payload.personal_email)
    email = _unique_email(db, payload.full_name)

    employee = Employee(
        personal_email=payload.personal_email,
        full_name=payload.full_name,
        email=email,
        date_joined=payload.date_joined,
        department_id=payload.department_id,
        position_id=payload.position_id,
        employment_type_id=payload.employment_type_id,
        shift_id=payload.shift_id,
        manager_id=payload.manager_id,
        status="Active",
    )
    db.add(employee)
    try:
        db.flush()  # get employee_id without committing yet
    except IntegrityError as exc:
        # Foreign keys are already validated above, so if we still land
        # here it's almost certainly a genuine email/username collision
        # from a concurrent request racing us — but we surface the raw
        # DB error too, so this never again gets misdiagnosed.
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Could not create employee due to a database constraint. Details: {exc.orig}",
        )

    role = db.query(Role).filter(Role.role_name == payload.role_name).first()
    if role is None:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"'{payload.role_name}' role is not seeded.")

    # The column is NOT NULL, so the account needs *some* password hash, but
    # this random value is never shown or emailed to anyone: the person sets
    # their own password through the invitation link.
    placeholder_password = security.generate_temp_password(length=16)

    user = User(
        employee_id=employee.employee_id,
        username=email.split("@")[0],
        email=email,
        password_hash=security.hash_password(placeholder_password),
        role_id=role.role_id,
        role_name=role.role_name,
        must_reset_password=1,
        is_active=1,
        is_verified=0,
    )
    db.add(user)
    db.commit()
    db.refresh(employee)

    audit_controller.log_action(
        db, acting_user_id, "CREATE", "employees", employee.employee_id,
        f"Created employee: {payload.full_name} (role: {payload.role_name})",
    )

    # Queue the invitation (returns immediately; the worker sends it).
    invitation = email_service.issue_invitation(db, user, employee)
    return employee, email, invitation is not None


def resend_invitation(db: Session, employee_id: int, acting_user_id: int, acting_role_name: str) -> None:
    """New link (old one stops working) for someone who has not set a
    password yet. Same role rule as account creation: HR can only do this
    for Manager/Employee accounts."""
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="This employee has no login account.")
    _assert_role_assignment_allowed(acting_role_name, user.role_name, current_role_name=user.role_name)
    if not user.is_active:
        raise HTTPException(status_code=400, detail="This account is suspended.")
    if not user.must_reset_password or user.setup_token_used_at is not None:
        raise HTTPException(status_code=400, detail="This user has already set their password.")
    if not employee.personal_email:
        raise HTTPException(status_code=400, detail="No personal email on file. Add one first, then resend.")

    if email_service.issue_invitation(db, user, employee) is None:
        raise HTTPException(status_code=500, detail="Could not queue the invitation. Check the server log.")
    audit_controller.log_action(db, acting_user_id, "RESEND_INVITATION", "employees", employee_id)


def set_personal_email(db: Session, employee_id: int, new_email: str, acting_user_id: int, acting_role_name: str) -> Employee:
    """Admin/HR only (route). This address receives password-reset codes, so
    it is logged to history + audit, and the OLD address (if any) is warned."""
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if user is not None:
        _assert_role_assignment_allowed(acting_role_name, user.role_name, current_role_name=user.role_name)
    if employee.personal_email == new_email:
        raise HTTPException(status_code=400, detail="That is already the personal email on file.")
    _assert_personal_email_free(db, new_email, exclude_employee_id=employee_id)

    old = employee.personal_email
    employee.personal_email = new_email
    db.add(EmployeeHistory(employee_id=employee_id, field_changed="personal_email",
                           old_value=old, new_value=new_email, changed_by=acting_user_id))
    db.commit()
    db.refresh(employee)
    audit_controller.log_action(db, acting_user_id, "UPDATE", "employees", employee_id, "Changed personal email")
    if old and user is not None:
        email_service.send_security_alert(
            db, user, "Your recovery email was changed",
            "the personal email on your account was changed by an administrator. "
            "Password-reset codes and notifications now go to the new address.",
            to_address=old,
        )
    return employee


def change_employee_role(db: Session, employee_id: int, role_name: str, acting_user_id: int, acting_role_name: str) -> Employee:
    """
    Promotes/demotes an existing employee's account to a different role
    (e.g. Employee -> Manager, or Manager -> HR).

    Reachable by Admin or HR (both hold 'assign_roles'). Admin can
    assign any role; HR is restricted to Manager/Employee on both ends
    (see _assert_role_assignment_allowed) and can never change its own
    role, checked below as defense-in-depth regardless of who holds the
    permission.
    """
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    user = db.query(User).filter(User.employee_id == employee_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="This employee has no login account to assign a role to.")

    old_role = db.query(Role).filter(Role.role_id == user.role_id).first()
    old_role_name = old_role.role_name if old_role else None

    if old_role_name == role_name:
        raise HTTPException(status_code=400, detail=f"This employee already has the '{role_name}' role.")

    if user.user_id == acting_user_id:
        raise HTTPException(status_code=403, detail="You cannot change your own role.")

    _assert_role_assignment_allowed(acting_role_name, role_name, current_role_name=old_role_name)

    new_role = db.query(Role).filter(Role.role_name == role_name).first()
    if new_role is None:
        raise HTTPException(status_code=500, detail=f"'{role_name}' role is not seeded.")

    user.role_id = new_role.role_id
    user.role_name = new_role.role_name
    db.add(EmployeeHistory(
        employee_id=employee_id,
        field_changed="role_name",
        old_value=old_role_name,
        new_value=role_name,
        changed_by=acting_user_id,
    ))
    db.commit()
    db.refresh(employee)

    audit_controller.log_action(
        db, acting_user_id, "UPDATE", "employees", employee_id,
        f"Changed role: {old_role_name} -> {role_name}",
    )
    return employee


def suspend_employee(db: Session, employee_id: int, acting_user_id: int) -> None:
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Employee account not found.")
    user.is_active = 0
    db.commit()
    audit_controller.log_action(db, acting_user_id, "SUSPEND", "employees", employee_id)


def reactivate_employee(db: Session, employee_id: int, acting_user_id: int) -> None:
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Employee account not found.")
    user.is_active = 1
    db.commit()
    audit_controller.log_action(db, acting_user_id, "REACTIVATE", "employees", employee_id)


def update_employee(db: Session, employee_id: int, payload, changed_by_user_id: int) -> Employee:
    """
    Updates only the fields that were actually sent, and writes one
    employee_history row per changed field — this is the write-through
    we designed earlier: nothing changes silently.
    """
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    updates = payload.model_dump(exclude_unset=True)
    changed_fields = []
    for field, new_value in updates.items():
        old_value = getattr(employee, field)
        if old_value == new_value:
            continue  # no actual change — don't log a no-op

        db.add(EmployeeHistory(
            employee_id=employee_id,
            field_changed=field,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            changed_by=changed_by_user_id,
        ))
        setattr(employee, field, new_value)
        changed_fields.append(field)

    db.commit()
    db.refresh(employee)

    if changed_fields:
        audit_controller.log_action(db, changed_by_user_id, "UPDATE", "employees", employee_id, f"Changed: {', '.join(changed_fields)}")
    return employee


def delete_employee(db: Session, employee_id: int, acting_user_id: int) -> None:
    """
    Hard-deletes the employee record. schema.sql cascades this to the
    linked user account, attendance, leave requests/balance, overtime,
    and employee_history rows — everything tied to this employee_id
    goes with it. Logged before the row disappears so the delete itself
    is still traceable in the audit log.
    """
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    acting_user = db.query(User).filter(User.user_id == acting_user_id).first()
    if acting_user is not None and acting_user.employee_id == employee_id:
        raise HTTPException(status_code=403, detail="You cannot delete your own employee record.")

    audit_controller.log_action(
        db, acting_user_id, "DELETE", "employees", employee_id,
        f"Deleted employee: {employee.full_name}",
    )
    
       # Delete
    db.query(Notification).filter(Notification.employee_id == employee_id).delete(synchronize_session=False)
    db.query(Employee).filter(Employee.manager_id == employee_id).update(
        {Employee.manager_id: None}, synchronize_session=False)

    account = db.query(User).filter(User.employee_id == employee_id).first()
    if account is not None:
        uid = account.user_id
        db.query(LeaveRequest).filter(LeaveRequest.approved_by == uid).update(
            {LeaveRequest.approved_by: None}, synchronize_session=False)
        db.query(Overtime).filter(Overtime.approved_by == uid).update(
            {Overtime.approved_by: None}, synchronize_session=False)
        db.query(EmployeeHistory).filter(EmployeeHistory.changed_by == uid).update(
            {EmployeeHistory.changed_by: None}, synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.user_id == uid).update(
            {AuditLog.user_id: None}, synchronize_session=False)
        db.query(EmailQueue).filter(EmailQueue.user_id == uid).update(
            {EmailQueue.user_id: None}, synchronize_session=False)
        db.query(EmailPreference).filter(EmailPreference.user_id == uid).delete(synchronize_session=False)
    db.flush()

    db.delete(employee)
    db.commit()


def get_employee_history(db: Session, employee_id: int) -> list[EmployeeHistory]:
    return (
        db.query(EmployeeHistory)
        .filter(EmployeeHistory.employee_id == employee_id)
        .order_by(EmployeeHistory.changed_at.desc())
        .all()
    )
