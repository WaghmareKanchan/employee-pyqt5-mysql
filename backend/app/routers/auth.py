from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.controllers import auth_controller
from app.core import security
from app.database import get_db
from app.dependencies import get_current_user
from app.models.people import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
    SetPasswordRequest,
    SetupPasswordRequest,
    TwoFAConfirmRequest,
    TwoFASetupResponse,
    TwoFAStatusResponse,
    TwoFAVerifyRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _full_login_response(user: User) -> LoginResponse:
    return LoginResponse(
        requires_2fa=False,
        access_token=auth_controller.issue_token(user),
        role=user.role.role_name,
        must_reset_password=bool(user.must_reset_password),
        full_name=user.employee.full_name if user.employee else user.username,
        two_fa_enabled=bool(user.totp_enabled),
    )


@router.post("/login", response_model=LoginResponse, status_code=200)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    user = auth_controller.authenticate_user(db, credentials)

    if user.totp_enabled:
        # Password was correct, but that's not enough on its own for a
        # 2FA account — hand back a short-lived partial token instead
        # of a real one, and make the client ask for the 6-digit code.
        return LoginResponse(
            requires_2fa=True,
            partial_token=security.create_partial_2fa_token(user.user_id),
        )

    auth_controller.finalize_login(db, user)
    return _full_login_response(user)


@router.post("/2fa/verify", response_model=LoginResponse, status_code=200)
def verify_2fa(payload: TwoFAVerifyRequest, db: Session = Depends(get_db)):
    """Second step of login for a 2FA-enabled account: exchanges the
    partial token + the 6-digit code for a real access
    token, same shape as a non-2FA /login success."""
    user = auth_controller.verify_2fa_and_login(db, payload.partial_token, payload.code)
    auth_controller.finalize_login(db, user)
    return _full_login_response(user)


@router.post("/set-password", status_code=200)
def set_password(
    payload: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_controller.set_new_password(db, current_user, payload)
    return {"message": "Password updated successfully."}


@router.get("/setup-password/check", status_code=200)
def check_setup_link(token: str, db: Session = Depends(get_db)):
    """Public. Lets the setup page show 'link expired' before the person types anything."""
    user = auth_controller.check_setup_token(db, token)
    return {"valid": True, "full_name": user.employee.full_name if user.employee else user.username,
            "login_id": user.email}


@router.post("/setup-password", status_code=200)
def setup_password(payload: SetupPasswordRequest, db: Session = Depends(get_db)):
    """Public. First password from the invitation link (one-time token)."""
    user = auth_controller.setup_password_with_token(db, payload)
    return {"message": "Password set. You can now log in.", "login_id": user.email}


@router.post("/forgot-password", status_code=200)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    auth_controller.request_password_reset(db, payload.email)
    # Same message whether or not the email exists — never reveal which emails are registered.
    return {"message": "If that email exists, an OTP has been sent."}


@router.post("/reset-password", status_code=200)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    auth_controller.reset_password_with_otp(db, payload)
    return {"message": "Password reset successfully. You can now log in."}


@router.get("/me", status_code=200)
def me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role.role_name,
        "full_name": current_user.employee.full_name if current_user.employee else current_user.username,
    }


# ------------------------------------------------------------------
# Two-factor auth enrollment — offered to every user right after login
# (not from Profile). Once enabled it is permanent: there is no disable
# endpoint.
# ------------------------------------------------------------------

@router.get("/2fa/status", response_model=TwoFAStatusResponse, status_code=200)
def two_fa_status(current_user: User = Depends(get_current_user)):
    return TwoFAStatusResponse(enabled=bool(current_user.totp_enabled))


@router.post("/2fa/setup", response_model=TwoFASetupResponse, status_code=200)
def two_fa_setup(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return auth_controller.start_2fa_setup(db, current_user)


@router.post("/2fa/confirm", status_code=200)
def two_fa_confirm(
    payload: TwoFAConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_controller.confirm_2fa_setup(db, current_user, payload.code)
    return {"message": "Two-factor authentication enabled."}

#disable 
@router.post("/2fa/disable", status_code=200)
def two_fa_disable(
    payload: TwoFAConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_controller.disable_2fa(db, current_user, payload.code)
    return {"message": "Two-factor authentication disabled."}