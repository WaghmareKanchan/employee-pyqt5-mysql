"""
Outgoing email utility (low-level SMTP sender).

Nothing in the app calls this directly any more, except the background
worker (app/services/email_worker.py). Controllers call
app/services/email_service.py, which saves a row in `email_queue`; the
worker then calls deliver_email() below.

Design goal: never make local development depend on a real mail server.
If SMTP_HOST is not set, deliver_email() prints the message to the console
(including any setup link / OTP, so you can test) and reports "simulated".
"""
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core import config

logger = logging.getLogger("app.email")


class EmailDeliveryError(Exception):
    """Raised when the SMTP server could not accept the message."""


def deliver_email(to: str, subject: str, body: str, html_body: str | None = None) -> bool:
    """
    Sends one email (plain text, plus an HTML alternative if given).

    Returns True  -> really handed to the SMTP server.
    Returns False -> SMTP not configured, message was only printed (dev).
    Raises EmailDeliveryError if SMTP is configured but sending failed,
    so the worker can record the error and retry.
    """
    if not config.SMTP_HOST:
        logger.info("[EMAIL - console fallback] To: %s | Subject: %s", to, subject)
        print(f"\n[EMAIL - SMTP not configured] To: {to} | Subject: {subject}\n{body}\n")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((config.EMAIL_FROM_NAME, config.EMAIL_FROM))
    msg["To"] = to
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        if config.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        with server:
            if config.SMTP_USE_TLS and not config.SMTP_USE_SSL:
                server.starttls()
            if config.SMTP_USERNAME:
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg, from_addr=config.EMAIL_FROM, to_addrs=[to])
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        raise EmailDeliveryError(str(exc)) from exc


def send_email(to: str, subject: str, body: str) -> bool:
    """Old direct-send helper, kept so any leftover caller still works.
    Prefer email_service (queued) for new code."""
    try:
        return deliver_email(to, subject, body)
    except EmailDeliveryError:
        return False
