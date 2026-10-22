"""
Email templates. Each function returns a Rendered(subject, text, html).
Every dynamic value is HTML-escaped in the HTML version. To change wording
or branding, this is the only file you need to edit.
"""
from dataclasses import dataclass
from html import escape

from app.core import config


@dataclass
class Rendered:
    subject: str
    text: str
    html: str


def _layout(heading: str, paragraphs: list[str], details: list[tuple[str, str]] | None = None,
            button: tuple[str, str] | None = None, footer: str | None = None) -> tuple[str, str]:
    """Builds (plain_text, html) from the same pieces so they never drift apart."""
    company = config.EMAIL_FROM_NAME

    # ---- plain text
    lines = [heading, ""]
    for p in paragraphs:
        lines += [p, ""]
    if details:
        lines += [f"{k}: {v}" for k, v in details] + [""]
    if button:
        lines += [f"{button[0]}: {button[1]}", ""]
    if footer:
        lines += [footer, ""]
    lines += [f"— {company}"]
    text = "\n".join(lines)

    # ---- html
    parts = [f'<h2 style="margin:0 0 16px;color:#1f2937;font-size:20px">{escape(heading)}</h2>']
    for p in paragraphs:
        parts.append(f'<p style="margin:0 0 14px;color:#374151;line-height:1.5">{escape(p)}</p>')
    if details:
        rows = "".join(
            f'<tr><td style="padding:6px 12px 6px 0;color:#6b7280">{escape(k)}</td>'
            f'<td style="padding:6px 0;color:#111827"><b>{escape(v)}</b></td></tr>'
            for k, v in details
        )
        parts.append(f'<table style="margin:0 0 18px;border-collapse:collapse">{rows}</table>')
    if button:
        parts.append(
            f'<p style="margin:20px 0"><a href="{escape(button[1], quote=True)}" '
            'style="background:#2563eb;color:#fff;text-decoration:none;padding:11px 22px;'
            f'border-radius:6px;display:inline-block">{escape(button[0])}</a></p>'
            f'<p style="margin:0 0 14px;color:#6b7280;font-size:12px">Button not working? Copy this link into your browser:<br>'
            f'{escape(button[1])}</p>'
        )
    if footer:
        parts.append(f'<p style="margin:0 0 14px;color:#6b7280;font-size:13px">{escape(footer)}</p>')
    html = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;background:#f3f4f6;padding:24px">'
        '<div style="max-width:560px;margin:auto;background:#fff;border-radius:8px;padding:28px">'
        + "".join(parts)
        + f'<hr style="border:none;border-top:1px solid #e5e7eb;margin:22px 0 12px">'
        f'<p style="margin:0;color:#9ca3af;font-size:12px">{escape(company)} · automated message, please do not reply</p>'
        "</div></div>"
    )
    return text, html


def invitation(full_name: str, role_name: str, login_id: str, setup_url: str, valid_hours: int) -> Rendered:
    subject = f"Welcome to {config.EMAIL_FROM_NAME} — set up your account"
    text, html = _layout(
        f"Welcome, {full_name}!",
        [f"An account with the role {role_name} has been created for you. "
         "Use the button below to choose your own password."],
        details=[("Your login ID", login_id)],
        button=("Set my password", setup_url),
        footer=f"This link works once and expires in {valid_hours} hours. "
               "If it expires, ask your administrator to resend the invitation.",
    )
    return Rendered(subject, text, html)


def password_reset_otp(full_name: str, otp: str, minutes: int) -> Rendered:
    subject = f"Your {config.EMAIL_FROM_NAME} password reset code"
    text, html = _layout(
        "Password reset code",
        [f"Hi {full_name}, use this one-time code to reset your password:", otp,
         f"It expires in {minutes} minutes."],
        footer="If you didn't request this, you can safely ignore this email — your password has not changed.",
    )
    return Rendered(subject, text, html)


def security_alert(full_name: str, headline: str, detail: str) -> Rendered:
    subject = f"Security alert: {headline}"
    text, html = _layout(
        headline,
        [f"Hi {full_name}, {detail}"],
        footer="If this wasn't you, contact your administrator immediately.",
    )
    return Rendered(subject, text, html)


def new_request(approver_name: str, applicant_name: str, kind_label: str,
                details: list[tuple[str, str]]) -> Rendered:
    subject = f"New {kind_label} from {applicant_name} awaiting your decision"
    text, html = _layout(
        f"New {kind_label}",
        [f"Hi {approver_name}, {applicant_name} has submitted a {kind_label}. "
         "Please open Meridian Systems to approve or reject it."],
        details=[("Applicant", applicant_name)] + details,
    )
    return Rendered(subject, text, html)


def request_decision(name: str, kind_label: str, status: str, details: list[tuple[str, str]],
                     decided_by: str) -> Rendered:
    subject = f"Your {kind_label} was {status.lower()}"
    text, html = _layout(
        f"Your {kind_label} was {status.lower()}",
        [f"Hi {name}, your {kind_label} has been {status.lower()} by {decided_by}."],
        details=details + [("Decision", status)],
    )
    return Rendered(subject, text, html)


def late_arrival(name: str, work_date: str, check_in: str, cutoff: str | None) -> Rendered:
    subject = f"Late arrival recorded for {work_date}"
    details = [("Date", work_date), ("Checked in at", check_in)]
    if cutoff:
        details.append(("Late cutoff", cutoff))
    details.append(("Day marked as", "Half Day (Late arrival)"))
    text, html = _layout(
        "Late arrival recorded",
        [f"Hi {name}, your check-in today was after your shift's late cutoff."],
        details=details,
        footer="If you think this is a mistake, please speak to your manager or HR.",
    )
    return Rendered(subject, text, html)


def pending_reminder(approver_name: str, items: list[str], after_days: int) -> Rendered:
    n = len(items)
    subject = f"Reminder: {n} request{'s' if n != 1 else ''} waiting for your decision"
    text, html = _layout(
        "Requests waiting for your decision",
        [f"Hi {approver_name}, these requests have been pending for more than {after_days} day(s):"]
        + [f"• {i}" for i in items],
    )
    return Rendered(subject, text, html)


def invitation_expiring(creator_name: str, invitee_name: str, personal_email: str | None, hours_left: int) -> Rendered:
    subject = f"Invitation for {invitee_name} is about to expire"
    text, html = _layout(
        "Invitation about to expire",
        [f"Hi {creator_name}, {invitee_name} has not set a password yet and the invitation link "
         f"expires in about {hours_left} hour(s). Use 'Resend Invitation' in Employees to send a new link."],
        details=[("Sent to", personal_email or "—")],
    )
    return Rendered(subject, text, html)
