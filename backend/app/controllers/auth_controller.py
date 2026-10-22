"""
Auth business logic — routers call these functions, never touch the
DB or password hashing directly. This is the "Controller" in our MVC
split (View = PyQt5 client, Model = SQLAlchemy models, Controller = here).
"""
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import config, security
from app.models.people import User
from app.controllers import audit_controller
from app.schemas.auth import LoginRequest, SetPasswordRequest, SetupPasswordRequest
from app.services import email_service


def authenticate_user(db: Session, credentials: LoginRequest) -> User:
    """
    Implements the exact rules from our earlier design:login
      - generic error message (never reveal whether the email exists)
      - account lockout after MAX_FAILED_LOGIN_ATTEMPTS
      - inactive/suspended accounts rejected
    """
    user = db.query(User).filter(User.email == credentials.email).first()

    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )

    # now = datetime.utcnow()
    
    if user is None:
        raise generic_error

    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked. Try again after {user.locked_until.strftime('%H:%M')}.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended. Contact your administrator.",
        )

    if user.locked_until and user.locked_until <= datetime.utcnow():
        user.failed_login_attempts= 0
        user.locked_until=None 
        db.commit()
        
    if(user.failed_login_attempts or 0) > config.MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=config.ACCOUNT_LOCK_MINUTES)
        db.commit()
        raise generic_error
        
    if not security.verify_password(credentials.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= config.MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=config.ACCOUNT_LOCK_MINUTES)
        db.commit()
        raise generic_error

    # Correct password: reset the failure counter right away (that's
    # what it's protecting against). last_login is stamped by
    # finalize_login() instead, once the login is FULLY complete —
    # for a 2FA account that's after the code is verified, not here.
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    db.refresh(user)
    return user


def finalize_login(db: Session, user: User) -> None:
    """Call once a login is fully complete (password, and 2FA code if
    enabled) — stamps last_login. Separate from authenticate_user so a
    2FA account's last_login reflects when they actually got in, not
    just when they typed a correct password."""
    user.last_login = datetime.utcnow()
    db.commit()


def set_new_password(db: Session, user: User, payload: SetPasswordRequest) -> None:
    """First-login (or forgot-password) flow: employee sets their own password."""
    if not payload.passwords_match():
        raise HTTPException(status_code=422, detail="Passwords do not match.")

    user.password_hash = security.hash_password(payload.new_password)
    user.must_reset_password = 0
    db.commit()


def issue_token(user: User) -> str:
    return security.create_access_token(
        data={"sub": str(user.user_id), "role_id": user.role_id}
    )


def request_password_reset(db: Session, email: str) -> None:
    """
    Generates an OTP for password reset. Always behaves the same
    (no error) whether or not the email exists — this prevents an
    attacker from using this endpoint to discover which emails are
    registered.
    """
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return  # silently do nothing — same response either way

    otp = security.generate_otp()
    user.otp_code = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=config.OTP_EXPIRE_MINUTES)
    db.commit()

    # Goes to the user's PERSONAL email (the company login address is not a mailbox).
    email_service.send_password_reset_otp(db, user, otp)


def reset_password_with_otp(db: Session, payload) -> None:
    user = db.query(User).filter(User.email == payload.email).first()

    generic_error = HTTPException(status_code=400, detail="Invalid or expired OTP.")

    if user is None or user.otp_code is None or user.otp_expiry is None:
        raise generic_error
    if user.otp_code != payload.otp_code:
        raise generic_error
    if user.otp_expiry < datetime.utcnow():
        raise generic_error
    if not payload.passwords_match():
        raise HTTPException(status_code=422, detail="Passwords do not match.")

    user.password_hash = security.hash_password(payload.new_password)
    user.must_reset_password = 0
    user.otp_code = None
    user.otp_expiry = None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    email_service.send_security_alert(
        db, user, "Your password was reset",
        "your password was just reset using a one-time code.")


_BAD_LINK = "This setup link is invalid, has expired, or was already used. Ask your administrator to resend the invitation."


def _user_for_setup_token(db: Session, raw_token: str) -> User:
    """One generic error for every failure so the link reveals nothing."""
    user = None
    if raw_token:
        user = db.query(User).filter(User.setup_token_hash == security.hash_setup_token(raw_token)).first()
    if (user is None or user.setup_token_used_at is not None or not user.is_active
            or user.setup_token_expiry is None or user.setup_token_expiry < datetime.utcnow()):
        raise HTTPException(status_code=400, detail=_BAD_LINK)
    return user


def check_setup_token(db: Session, raw_token: str) -> User:
    return _user_for_setup_token(db, raw_token)


def setup_password_with_token(db: Session, payload: SetupPasswordRequest) -> User:
    """Invitation flow: the person picks their own password. The token is
    marked used, so the link can never be replayed."""
    user = _user_for_setup_token(db, payload.token)
    if not payload.passwords_match():
        raise HTTPException(status_code=422, detail="Passwords do not match.")
    user.password_hash = security.hash_password(payload.new_password)
    user.must_reset_password = 0
    user.is_verified = 1
    user.setup_token_used_at = datetime.utcnow()
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    audit_controller.log_action(db, user.user_id, "SETUP_PASSWORD", "users", user.user_id, "Set password from invitation")
    return user


# ------------------------------------------------------------------
# Two-factor auth (TOTP)
# ------------------------------------------------------------------

def start_2fa_setup(db: Session, user: User) -> dict:
    """
    Generates a new secret and stores it immediately (so the QR code
    scanned now will actually work when they confirm), but does NOT
    enable 2FA yet — that only happens once they prove they can
    generate a valid code from it, in confirm_2fa_setup(). Re-running
    this (e.g. the QR didn't scan) simply replaces the unconfirmed secret.

    Once 2FA is enabled it can never be re-enrolled or turned off from
    here (there is no disable feature), so this refuses to touch an
    already-enabled account. The secret is only ever returned inside the
    QR image — it is deliberately not sent back as text.
    """
    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="Two-factor authentication is already enabled.")

    secret = security.generate_totp_secret()
    user.totp_secret = secret
    db.commit()

    otpauth_uri = security.build_totp_uri(secret, user.email)
    return {"qr_code_base64": security.generate_qr_code_base64(otpauth_uri)}


def confirm_2fa_setup(db: Session, user: User, code: str) -> None:
    """Proves the user's authenticator app actually has the secret
    (not just that we generated one) before 2FA starts being enforced
    at login. Nothing else is generated or stored."""
    if user.totp_enabled:
        raise HTTPException(status_code=400, detail="Two-factor authentication is already enabled.")
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Start 2FA setup first.")
    if not security.verify_totp_code(user.totp_secret, code):
        raise HTTPException(status_code=400, detail="Incorrect code. Check your authenticator app and try again.")

    user.totp_enabled = 1
    db.commit()
    email_service.send_security_alert(
        db, user, "Two-factor authentication enabled",
        "two-factor authentication was just turned on for your account.")
    
#disable 
def disable_2fa(db: Session, user: User, code: str) -> None:
    """Turns 2FA off, but only if the user proves they still have the
    authenticator by giving a valid current code."""
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="Two-factor authentication is not enabled.")
    if not security.verify_totp_code(user.totp_secret, code):
        raise HTTPException(status_code=400, detail="Incorrect code. Check your authenticator app and try again.")

    user.totp_enabled = 0
    user.totp_secret = None
    db.commit()
    email_service.send_security_alert(
        db, user, "Two-factor authentication disabled",
        "two-factor authentication was just turned off for your account.")


def verify_2fa_and_login(db: Session, partial_token: str, code: str) -> User:
    """
    Second step of login for a 2FA-enabled account. Accepts the
    live 6-digit TOTP code. Reuses the
    same lockout counters as the password step, so brute-forcing the
    2FA code is rate-limited the same way brute-forcing the password is.
    """
    payload = security.decode_access_token(partial_token)
    generic_error = HTTPException(status_code=401, detail="Your session expired. Please log in again.")
    if payload is None or payload.get("purpose") != "2fa_pending":
        raise generic_error

    user = db.query(User).filter(User.user_id == int(payload["sub"])).first()
    if user is None or not user.is_active or not user.totp_enabled:
        raise generic_error

    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked. Try again after {user.locked_until.strftime('%H:%M')}.",
        )

    code_error = HTTPException(status_code=401, detail="Incorrect code.")

    if security.verify_totp_code(user.totp_secret, code):
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        return user

    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= config.MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=config.ACCOUNT_LOCK_MINUTES)
    db.commit()
    raise code_error
