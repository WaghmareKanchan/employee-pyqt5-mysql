"""
Auth-related calls: login, first-login password reset, forgot/reset
password (OTP), two-factor auth (TOTP), and fetching the logged-in
user's own profile.
"""
from controllers.api_client import api_client


def login(email: str, password: str) -> dict:
    """
    Returns the raw response dict. The caller (login_view.py) must
    check `requires_2fa`:
      - False: session is already set up below, login is complete.
      - True: nothing is set yet — the caller collects a 2FA code from
        the user and calls verify_2fa(data['partial_token'], code).
    """
    data = api_client.post("/api/auth/login", {"email": email, "password": password})
    if data.get("requires_2fa"):
        return data
    _apply_session(data, email)
    return data


def verify_2fa(partial_token: str, code: str, email: str) -> dict:
    """Second step of login for a 2FA-enabled account — exchanges the
    partial token + a 6-digit code for a real session,
    same as a non-2FA login() success. `email` is threaded through
    explicitly because api_client.email isn't set until this succeeds
    (login() deliberately doesn't touch session state on the
    requires_2fa branch)."""
    data = api_client.post("/api/auth/2fa/verify", {"partial_token": partial_token, "code": code})
    _apply_session(data, email)
    return data


def _apply_session(data: dict, email: str | None) -> None:
    api_client.token = data["access_token"]
    api_client.role = data["role"]
    api_client.full_name = data.get("full_name")
    api_client.email = email
    api_client.must_reset_password = bool(data.get("must_reset_password", False))
    api_client.two_fa_enabled = bool(data.get("two_fa_enabled", False))


def get_2fa_status() -> dict:
    return api_client.get("/api/auth/2fa/status")


def start_2fa_setup() -> dict:
    return api_client.post("/api/auth/2fa/setup")


def confirm_2fa_setup(code: str) -> dict:
    result = api_client.post("/api/auth/2fa/confirm", {"code": code})
    api_client.two_fa_enabled = True
    return result

#disable 
def disable_2fa(code: str) -> dict:
    result = api_client.post("/api/auth/2fa/disable", {"code": code})
    api_client.two_fa_enabled = False
    return result


def set_password(new_password: str, confirm_password: str) -> dict:
    result = api_client.post(
        "/api/auth/set-password",
        {"new_password": new_password, "confirm_password": confirm_password},
    )
    api_client.must_reset_password = False
    return result


def forgot_password(email: str) -> dict:
    return api_client.post("/api/auth/forgot-password", {"email": email})


def reset_password_with_otp(email: str, otp_code: str, new_password: str, confirm_password: str) -> dict:
    return api_client.post(
        "/api/auth/reset-password",
        {
            "email": email,
            "otp_code": otp_code,
            "new_password": new_password,
            "confirm_password": confirm_password,
        },
    )


def me() -> dict:
    data = api_client.get("/api/auth/me")
    api_client.user_id = data.get("user_id")
    return data


def logout() -> None:
    api_client.clear_session()
