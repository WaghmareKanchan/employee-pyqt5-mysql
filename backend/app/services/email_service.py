"""
Email Notification Service (DFD process 6.0).

Controllers NEVER send email themselves. They call one of the event
helpers below, which:
    6.1 build the message from a template,
    6.2 find the recipient's reachable address and check their preference,
    6.3 save a row in `email_queue` (status Pending) and return at once.
The background worker (email_worker.py) does the actual sending.

Rules this module guarantees:
  * An email problem NEVER breaks the business request. Every public
    event helper catches its own errors and just logs them.
  * Call helpers only AFTER your own db.commit() (they commit too).
  * Essential categories ignore preferences; the rest respect them.
"""
import functools
import logging
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import config, security
from app.models.audit_log import AuditLog
from app.models.email import EmailPreference, EmailQueue
from app.models.leave import LeaveRequest
from app.models.attendance import Overtime
from app.models.people import Employee, User
from app.services import email_templates as templates
from app.services.email_templates import Rendered

logger = logging.getLogger("app.email_service")

# Always sent: they protect the account, preferences are ignored.
ESSENTIAL_CATEGORIES = {"invitation", "password_reset", "security"}
# User can switch these off (in-app notifications are never affected).
PREFERENCE_CATEGORIES = {
    "leave_overtime": "Leave & overtime requests and decisions",
    "attendance": "Attendance alerts (late arrival)",
    "reminder": "Reminders about pending items",
}
# Bodies containing a link/code are wiped from the table once delivered.
SENSITIVE_CATEGORIES = {"invitation", "password_reset"}


def never_raise(func):
    """Email must never break the caller's request."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:  # noqa: BLE001
            logger.exception("email_service.%s failed (ignored)", func.__name__)
            try:
                args[0].rollback()
            except Exception:  # noqa: BLE001
                pass
            return None
    return wrapper


# ------------------------------------------------------------------
# Recipient + preferences + queue
# ------------------------------------------------------------------

def display_name(user: User) -> str:
    return user.employee.full_name if user.employee else user.username


def resolve_address(user: User) -> str | None:
    if user.employee is not None and user.employee.personal_email:
        return user.employee.personal_email
    if config.EMAIL_ALLOW_COMPANY_ADDRESS_FALLBACK:
        return user.email
    logger.warning("User %s (%s) has no personal email - email skipped.", user.user_id, user.email)
    return None


def is_category_enabled(db: Session, user_id: int, category: str) -> bool:
    if category in ESSENTIAL_CATEGORIES:
        return True
    row = db.query(EmailPreference).filter(
        EmailPreference.user_id == user_id, EmailPreference.category == category
    ).first()
    return row is None or bool(row.enabled)


def queue_email(db: Session, *, to_address: str | None, rendered: Rendered, category: str,
                template: str, user_id: int | None = None) -> EmailQueue | None:
    """6.2 + 6.3. Returns the queued row, or None if skipped."""
    if not to_address:
        logger.warning("No address for %s email (user_id=%s) — skipped", template, user_id)
        return None
    if user_id is not None and not is_category_enabled(db, user_id, category):
        return None  # user switched this category off
    now = datetime.utcnow()
    job = EmailQueue(
        to_address=to_address, user_id=user_id, category=category, template=template,
        subject=rendered.subject, body=rendered.text, body_html=rendered.html,
        status="Pending", attempts=0, next_attempt_at=now, created_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_preferences(db: Session, user_id: int) -> dict[str, bool]:
    rows = {r.category: bool(r.enabled) for r in db.query(EmailPreference).filter(EmailPreference.user_id == user_id)}
    return {cat: rows.get(cat, True) for cat in PREFERENCE_CATEGORIES}


def set_preferences(db: Session, user_id: int, prefs: dict[str, bool]) -> dict[str, bool]:
    for category, enabled in prefs.items():
        if category not in PREFERENCE_CATEGORIES:
            continue
        row = db.query(EmailPreference).filter(
            EmailPreference.user_id == user_id, EmailPreference.category == category
        ).first()
        if row is None:
            db.add(EmailPreference(user_id=user_id, category=category, enabled=1 if enabled else 0))
        else:
            row.enabled = 1 if enabled else 0
    db.commit()
    return get_preferences(db, user_id)


# ------------------------------------------------------------------
# 1. Invitation (essential)
# ------------------------------------------------------------------

@never_raise
def issue_invitation(db: Session, user: User, employee: Employee) -> EmailQueue | None:
    """Creates a fresh one-time setup token (replacing any older one, so
    old links stop working) and queues the invitation to the personal
    email. Used for the first invite AND for 'Resend invitation'."""
    if not employee.personal_email:
        logger.warning("Employee %s has no personal_email — invitation not sent", employee.employee_id)
        return None
    raw_token, token_hash = security.generate_setup_token()
    user.setup_token_hash = token_hash
    user.setup_token_expiry = datetime.utcnow() + timedelta(hours=config.SETUP_TOKEN_EXPIRE_HOURS)
    user.setup_token_used_at = None
    user.setup_reminded_at = None
    db.commit()

    setup_url = f"{config.APP_BASE_URL}/setup-password?token={raw_token}"
    rendered = templates.invitation(employee.full_name, user.role_name, user.email, setup_url,
                                    config.SETUP_TOKEN_EXPIRE_HOURS)
    return queue_email(db, to_address=employee.personal_email, rendered=rendered,
                       category="invitation", template="invitation", user_id=user.user_id)


# ------------------------------------------------------------------
# Auth emails (essential)
# ------------------------------------------------------------------

@never_raise
def send_password_reset_otp(db: Session, user: User, otp: str) -> EmailQueue | None:
    rendered = templates.password_reset_otp(display_name(user), otp, config.OTP_EXPIRE_MINUTES)
    return queue_email(db, to_address=resolve_address(user), rendered=rendered,
                       category="password_reset", template="password_reset_otp", user_id=user.user_id)


@never_raise
def send_security_alert(db: Session, user: User, headline: str, detail: str,
                        to_address: str | None = None) -> EmailQueue | None:
    rendered = templates.security_alert(display_name(user), headline, detail)
    return queue_email(db, to_address=to_address or resolve_address(user), rendered=rendered,
                       category="security", template="security_alert", user_id=user.user_id)


# ------------------------------------------------------------------
# 2. Leave / overtime
# ------------------------------------------------------------------

def get_approver_users(db: Session, applicant: Employee) -> list[User]:
    """
    WHO GETS THE 'new request' EMAIL (change the rule here only):
      1. the applicant's manager, if they have one with an active account;
      2. otherwise all active HR users (so a Manager/Employee with no
         manager above them is not ignored);
      3. an HR applicant -> all active Admins;
      4. if there is no HR at all -> all active Admins.
    The applicant is never their own approver.
    """
    applicant_user = applicant.user_account
    own_id = applicant_user.user_id if applicant_user else None

    def active(query):
        return [u for u in query.filter(User.is_active == 1).all() if u.user_id != own_id]

    if applicant.manager_id:
        manager = active(db.query(User).filter(User.employee_id == applicant.manager_id))
        if manager:
            return manager

    role = applicant_user.role_name if applicant_user else "Employee"
    first_choice = "Admin" if role == "HR" else "HR"
    users = active(db.query(User).filter(User.role_name == first_choice))
    if not users and first_choice == "HR":
        users = active(db.query(User).filter(User.role_name == "Admin"))
    return users


KIND_LABELS = {"leave": "leave request", "overtime": "overtime request"}


@never_raise
def notify_approvers_of_new_request(db: Session, applicant_employee_id: int, kind: str,
                                    details: list[tuple[str, str]]) -> None:
    applicant = db.query(Employee).filter(Employee.employee_id == applicant_employee_id).first()
    if applicant is None:
        return
    for approver in get_approver_users(db, applicant):
        rendered = templates.new_request(display_name(approver), applicant.full_name, KIND_LABELS[kind], details)
        queue_email(db, to_address=resolve_address(approver), rendered=rendered,
                    category="leave_overtime", template="new_request", user_id=approver.user_id)


@never_raise
def notify_requester_of_decision(db: Session, employee_id: int, kind: str, status: str,
                                 details: list[tuple[str, str]], decided_by: str) -> None:
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if user is None:
        return
    rendered = templates.request_decision(display_name(user), KIND_LABELS[kind], status, details, decided_by)
    queue_email(db, to_address=resolve_address(user), rendered=rendered,
                category="leave_overtime", template="request_decision", user_id=user.user_id)


# ------------------------------------------------------------------
# 3. Attendance
# ------------------------------------------------------------------

@never_raise
def notify_late_arrival(db: Session, employee: Employee, attendance) -> None:
    user = db.query(User).filter(User.employee_id == employee.employee_id).first()
    if user is None:
        return
    cutoff = employee.shift.late_cutoff.strftime("%H:%M") if employee.shift and employee.shift.late_cutoff else None
    rendered = templates.late_arrival(
        display_name(user), attendance.work_date.strftime("%d %b %Y"),
        attendance.check_in.strftime("%H:%M"), cutoff,
    )
    queue_email(db, to_address=resolve_address(user), rendered=rendered,
                category="attendance", template="late_arrival", user_id=user.user_id)


# ------------------------------------------------------------------
# 7. Daily reminders (called by the worker once a day)
# ------------------------------------------------------------------

def _creator_of(db: Session, employee_id: int) -> User | None:
    """Who created this account? Read from the audit log (CREATE employees)."""
    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "CREATE", AuditLog.table_name == "employees", AuditLog.record_id == employee_id)
        .order_by(AuditLog.log_id.desc()).first()
    )
    if log is None or log.user_id is None:
        return None
    return db.query(User).filter(User.user_id == log.user_id, User.is_active == 1).first()


@never_raise
def run_daily_reminders(db: Session) -> dict:
    return {
        "pending_requests": _remind_pending_requests(db),
        "expiring_invitations": _remind_expiring_invitations(db),
    }


def _remind_pending_requests(db: Session) -> int:
    # applied_at is filled by the DB (CURRENT_TIMESTAMP, server local time),
    # so compare with local now(), not utcnow().
    now = datetime.now()
    older_than = now - timedelta(days=config.REMINDER_PENDING_AFTER_DAYS)
    repeat_after = now - timedelta(days=config.REMINDER_REPEAT_EVERY_DAYS)

    items: list[tuple[str, object, Employee]] = []
    for model, label in ((LeaveRequest, "Leave"), (Overtime, "Overtime")):
        rows = db.query(model).filter(
            model.status == "Pending", model.applied_at <= older_than,
            or_(model.last_reminded_at.is_(None), model.last_reminded_at <= repeat_after),
        ).all()
        for r in rows:
            items.append((label, r, r.employee))

    per_approver: dict[int, tuple[User, list[str]]] = {}
    handled = []
    for label, req, applicant in items:
        approvers = get_approver_users(db, applicant)
        if not approvers:
            continue
        if label == "Leave":
            line = f"Leave — {applicant.full_name}: {req.start_date} to {req.end_date}"
        else:
            line = f"Overtime — {applicant.full_name}: {req.work_date} ({float(req.hours)} hrs)"
        for a in approvers:
            per_approver.setdefault(a.user_id, (a, []))[1].append(line)
        handled.append(req)

    for approver, lines in per_approver.values():
        rendered = templates.pending_reminder(display_name(approver), lines, config.REMINDER_PENDING_AFTER_DAYS)
        queue_email(db, to_address=resolve_address(approver), rendered=rendered,
                    category="reminder", template="pending_reminder", user_id=approver.user_id)
    for req in handled:
        req.last_reminded_at = now
    db.commit()
    return len(per_approver)


def _remind_expiring_invitations(db: Session) -> int:
    now = datetime.utcnow()
    soon = now + timedelta(hours=config.INVITE_REMINDER_HOURS_BEFORE_EXPIRY)
    users = db.query(User).filter(
        User.setup_token_hash.isnot(None), User.setup_token_used_at.is_(None),
        User.must_reset_password == 1, User.is_active == 1,
        User.setup_token_expiry > now, User.setup_token_expiry <= soon,
        User.setup_reminded_at.is_(None),
    ).all()
    sent = 0
    for invitee in users:
        recipients = [c] if (c := _creator_of(db, invitee.employee_id)) else \
            db.query(User).filter(User.role_name == "Admin", User.is_active == 1).all()
        hours_left = max(1, int((invitee.setup_token_expiry - now).total_seconds() // 3600))
        for r in recipients:
            rendered = templates.invitation_expiring(
                display_name(r), display_name(invitee),
                invitee.employee.personal_email if invitee.employee else None, hours_left)
            if queue_email(db, to_address=resolve_address(r), rendered=rendered,
                           category="reminder", template="invitation_expiring", user_id=r.user_id):
                sent += 1
        invitee.setup_reminded_at = now
    db.commit()
    return sent
