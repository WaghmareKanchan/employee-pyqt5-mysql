"""
Security utilities used across the app.

Coding standard: this is the ONLY file that touches password hashing,
JWT encoding, or OTP generation. Controllers call these functions —
they never hash/verify passwords themselves.
"""
import base64
import hashlib
import random
import secrets
import string
from datetime import datetime, timedelta
from io import BytesIO

import pyotp
import qrcode
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core import config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a password with bcrypt. Never store plain text passwords."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_temp_password(length: int = 10) -> str:
    """
    Generate a temporary password for admin-provisioned accounts.
    Guaranteed to contain upper, lower, digit, and special char so it
    passes our own password-strength validator immediately.
    """
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("!@#$%&*")
    remaining = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(length - 4)
    )
    password = list(upper + lower + digit + special + remaining)
    random.SystemRandom().shuffle(password)
    return "".join(password)


def generate_otp() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(config.OTP_LENGTH))


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or config.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
    except JWTError:
        return None


# ------------------------------------------------------------------
# Two-factor auth (TOTP — RFC 6238, same standard Google/Microsoft/Authy
# authenticator apps implement). A user's totp_secret is a random base32
# string; the app and our server independently compute the same rolling
# 6-digit code from it plus the current time, so nothing ever crosses
# the network except that 6-digit code.
# ------------------------------------------------------------------

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_totp_uri(secret: str, account_email: str) -> str:
    """The otpauth:// URI an authenticator app reads (usually via QR
    code) to add this account — encodes the secret, issuer, and account
    label all at once."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_email, issuer_name=config.TOTP_ISSUER_NAME
    )


def generate_qr_code_base64(data: str) -> str:
    """Renders a QR code for `data` as a base64 PNG, so the desktop
    client can display it directly (QPixmap from base64) without
    needing its own QR-generation library."""
    img = qrcode.make(data)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def verify_totp_code(secret: str, code: str) -> bool:
    """valid_window=1 tolerates the code from one 30s step before/after
    now, which absorbs ordinary clock drift between the user's phone
    and the server without widening the window enough to meaningfully
    help a brute-force attempt."""
    if not code or not code.isdigit():
        return False
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)


def create_partial_2fa_token(user_id: int) -> str:
    """Issued right after a correct password when 2FA is enabled.
    Deliberately NOT a normal access token: it carries a 'purpose'
    claim that get_current_user rejects, so it can't be used to call
    any authenticated endpoint except /api/auth/2fa/verify."""
    return create_access_token(
        data={"sub": str(user_id), "purpose": "2fa_pending"},
        expires_minutes=config.TWO_FA_PARTIAL_TOKEN_EXPIRE_MINUTES,
    )


# ------------------------------------------------------------------
# Invitation / account-setup tokens. The raw token only ever exists in
# the email link; the database keeps just its SHA-256 hash, so a leaked
# database does not contain working links. 32 random bytes = 256 bits of
# entropy, so a plain (unsalted) hash is enough here.
# ------------------------------------------------------------------

def hash_setup_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_setup_token() -> tuple[str, str]:
    """Returns (raw_token_for_the_link, hash_to_store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_setup_token(raw)
