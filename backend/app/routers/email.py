"""Email Log (Admin/HR) and email preferences (every user)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.controllers import audit_controller
from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.email import EmailQueue
from app.models.people import User
from app.schemas.email import EmailLogOut, EmailPreferenceItem, EmailPreferencesUpdate
from app.services import email_service

router = APIRouter(prefix="/api/email", tags=["email"])


@router.get("/log", response_model=list[EmailLogOut])
def email_log(
    status: str | None = Query(None, pattern="^(Pending|Sent|Failed)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(require_permission("manage_employees")),   # Admin + HR
):
    q = db.query(EmailQueue)
    if status:
        q = q.filter(EmailQueue.status == status)
    return q.order_by(EmailQueue.email_id.desc()).offset(skip).limit(limit).all()


@router.post("/log/{email_id}/retry", response_model=EmailLogOut)
def retry_email(
    email_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_employees")),
):
    job = db.query(EmailQueue).filter(EmailQueue.email_id == email_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Email not found.")
    if job.status != "Failed":
        raise HTTPException(status_code=400, detail="Only Failed emails can be retried.")
    from datetime import datetime
    job.status, job.attempts, job.last_error = "Pending", 0, None
    job.next_attempt_at = datetime.utcnow()
    db.commit()
    audit_controller.log_action(db, current_user.user_id, "RETRY_EMAIL", "email_queue", email_id,
                                f"Retry: {job.template} to {job.to_address}")
    db.refresh(job)
    return job


@router.get("/preferences", response_model=list[EmailPreferenceItem])
def get_preferences(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = email_service.get_preferences(db, current_user.user_id)
    return [EmailPreferenceItem(category=c, label=email_service.PREFERENCE_CATEGORIES[c], enabled=e)
            for c, e in prefs.items()]


@router.put("/preferences", response_model=list[EmailPreferenceItem])
def save_preferences(payload: EmailPreferencesUpdate, current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    prefs = email_service.set_preferences(db, current_user.user_id, payload.preferences)
    return [EmailPreferenceItem(category=c, label=email_service.PREFERENCE_CATEGORIES[c], enabled=e)
            for c, e in prefs.items()]
