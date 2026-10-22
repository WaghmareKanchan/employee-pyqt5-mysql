"""
Background email worker (DFD 6.4 / 6.5 / 6.6).

Started with the FastAPI app (see main.py lifespan). Every few seconds it
takes due Pending jobs from `email_queue`, sends each one and marks it
Sent, or records the error and schedules a retry (1, 5, 15 minutes by
default); after the last attempt the job becomes Failed. Once a day (at
REMINDER_HOUR) it also runs the reminder job.

Unsent jobs live in the database, so a restart loses nothing.
"""
import logging
import threading
from datetime import date, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core import config
from app.core.email import EmailDeliveryError, deliver_email
from app.database import SessionLocal
from app.models.email import EmailQueue
from app.services import email_service

logger = logging.getLogger("app.email_worker")


def process_due_emails(db: Session, limit: int = 20) -> int:
    """Sends up to `limit` due jobs. Returns how many were processed."""
    now = datetime.utcnow()
    ids = [r[0] for r in db.query(EmailQueue.email_id).filter(
        EmailQueue.status == "Pending", EmailQueue.next_attempt_at <= now,
    ).order_by(EmailQueue.email_id).limit(limit).all()]

    processed = 0
    for email_id in ids:
        # "Lease" the job: push next_attempt_at forward in one atomic UPDATE.
        # If two workers race, only one gets rowcount == 1.
        lease_until = now + timedelta(minutes=config.EMAIL_SEND_LEASE_MINUTES)
        claimed = db.execute(
            update(EmailQueue)
            .where(EmailQueue.email_id == email_id, EmailQueue.status == "Pending",
                   EmailQueue.next_attempt_at <= now)
            .values(next_attempt_at=lease_until)
        ).rowcount
        db.commit()
        if claimed != 1:
            continue

        job = db.get(EmailQueue, email_id)
        job.attempts = (job.attempts or 0) + 1
        try:
            really_sent = deliver_email(job.to_address, job.subject, job.body, job.body_html)
        except EmailDeliveryError as exc:
            job.last_error = str(exc)[:500]
            if job.attempts >= config.EMAIL_MAX_ATTEMPTS:
                job.status = "Failed"
            else:
                delay = config.EMAIL_RETRY_DELAYS_MINUTES[job.attempts - 1]
                job.next_attempt_at = datetime.utcnow() + timedelta(minutes=delay)
        else:
            job.status = "Sent"
            job.sent_at = datetime.utcnow()
            job.last_error = None if really_sent else "Simulated: SMTP_HOST not configured (printed to console)"
            if job.category in email_service.SENSITIVE_CATEGORIES:
                job.body = "[content removed after sending]"
                job.body_html = None
        db.commit()
        processed += 1
    return processed


class EmailWorker:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_reminder_date: date | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="email-worker", daemon=True)
        self._thread.start()
        logger.info("Email worker started (every %ss)", config.EMAIL_WORKER_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.wait(config.EMAIL_WORKER_INTERVAL_SECONDS):
            db = SessionLocal()
            try:
                process_due_emails(db)
                self._maybe_run_reminders(db)
            except Exception:  # noqa: BLE001 — the loop must never die
                logger.exception("Email worker cycle failed")
            finally:
                db.close()

    def _maybe_run_reminders(self, db: Session) -> None:
        now = datetime.now()
        if now.hour >= config.REMINDER_HOUR and self._last_reminder_date != now.date():
            self._last_reminder_date = now.date()
            result = email_service.run_daily_reminders(db)
            logger.info("Daily reminders: %s", result)
