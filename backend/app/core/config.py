"""
Central application configuration.

Coding standard: nothing here is hardcoded in business logic files.
All secrets/paths are read from environment variables (.env), with
safe defaults only for local development.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load backend/.env (if present) so the settings below can come from it.
load_dotenv(BASE_DIR / ".env")

# Database (MySQL). Set DB_USER / DB_PASSWORD / ... in backend/.env.
# The password may contain any characters (@, #, / ...) — no URL-encoding
# needed, because the URL is built safely below. Alternatively set a full
# DATABASE_URL, which takes priority.
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "employee_management")

DATABASE_URL = os.getenv("DATABASE_URL") or URL.create(
    "mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)

# JWT / auth
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION_ENV_FILE")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Login security policy (kept in one place, per our earlier design discussion)
MAX_FAILED_LOGIN_ATTEMPTS = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
ACCOUNT_LOCK_MINUTES = int(os.getenv("ACCOUNT_LOCK_MINUTES", "15"))

# Company email domain enforced on employee accounts
COMPANY_EMAIL_DOMAIN = os.getenv("COMPANY_EMAIL_DOMAIN", "meridian.com")

# OTP policy (email verification / first-login flows)
OTP_LENGTH = 6
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))

# Two-factor auth (TOTP)
TOTP_ISSUER_NAME = os.getenv("TOTP_ISSUER_NAME", "Meridian Systems")
# How long the "password was correct, now enter your 2FA code" partial
# token is valid for. Short on purpose — it only grants the right to
# finish logging in, nothing else (see dependencies.get_current_user,
# which rejects it outright for every other endpoint).
TWO_FA_PARTIAL_TOKEN_EXPIRE_MINUTES = int(os.getenv("TWO_FA_PARTIAL_TOKEN_EXPIRE_MINUTES", "5"))

# Outgoing email (SMTP). If SMTP_HOST is unset, email sending falls back
# to printing the message to the console — so local dev works with zero
# setup, but setting these in .env sends real mail (e.g. via Gmail SMTP,
# SendGrid, Mailgun, AWS SES, or your company mail server).
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip().strip("'\"")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip().strip("'\"")
if SMTP_HOST.lower().endswith("gmail.com"):
    # Google shows App Passwords as "abcd efgh ijkl mnop"; the spaces are
    # only for display, so a copy-pasted value still works.
    SMTP_PASSWORD = SMTP_PASSWORD.replace(" ", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"   # STARTTLS (port 587)
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"   # implicit SSL (port 465)
EMAIL_FROM = os.getenv("EMAIL_FROM", f"no-reply@{COMPANY_EMAIL_DOMAIN}")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Meridian Systems")


# ------------------------------------------------------------------
# Email notification service (queue + background worker)
# ------------------------------------------------------------------
# Base URL put in invitation links. Must be reachable from the PERSON'S
# device: 127.0.0.1 only works on the machine running the backend. Use
# your server's LAN IP / domain (e.g. http://192.168.1.20:8000) when real
# users open the link.
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SETUP_TOKEN_EXPIRE_HOURS = int(os.getenv("SETUP_TOKEN_EXPIRE_HOURS", "48"))

EMAIL_WORKER_ENABLED = os.getenv("EMAIL_WORKER_ENABLED", "true").lower() == "true"
EMAIL_WORKER_INTERVAL_SECONDS = int(os.getenv("EMAIL_WORKER_INTERVAL_SECONDS", "5"))
# Wait before retry #1, #2, #3 ... After the last delay is used up the job
# becomes Failed (attempts allowed = number of delays + 1).
EMAIL_RETRY_DELAYS_MINUTES = [
    int(x) for x in os.getenv("EMAIL_RETRY_DELAYS_MINUTES", "1,5,15").split(",") if x.strip()
]
EMAIL_MAX_ATTEMPTS = len(EMAIL_RETRY_DELAYS_MINUTES) + 1
# A worker "leases" a job while sending; if the app dies mid-send the job
# becomes due again after this many minutes.
EMAIL_SEND_LEASE_MINUTES = 2

# Daily reminder job
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "9"))                       # local time, 0-23
REMINDER_PENDING_AFTER_DAYS = int(os.getenv("REMINDER_PENDING_AFTER_DAYS", "2"))
REMINDER_REPEAT_EVERY_DAYS = int(os.getenv("REMINDER_REPEAT_EVERY_DAYS", "3"))
INVITE_REMINDER_HOURS_BEFORE_EXPIRY = int(os.getenv("INVITE_REMINDER_HOURS_BEFORE_EXPIRY", "12"))

EMAIL_ALLOW_COMPANY_ADDRESS_FALLBACK = os.getenv("EMAIL_ALLOW_COMPANY_ADDRESS_FALLBACK", "false").lower() == "true"