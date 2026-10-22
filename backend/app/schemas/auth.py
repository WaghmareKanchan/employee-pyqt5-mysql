"""
Request/response validation for auth endpoints.

Coding standard: every field the client sends is validated HERE,
before it reaches any controller. Controllers trust these types.
"""
import re

from pydantic import BaseModel, EmailStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Password is required.")
        return v


class LoginResponse(BaseModel):
    """
    Two shapes depending on whether this account has 2FA enabled:
      - No 2FA: access_token/role/must_reset_password/full_name are set,
        requires_2fa is False, partial_token is None — behaves exactly
        like before 2FA existed.
      - 2FA enabled: requires_2fa is True and partial_token carries the
        short-lived token for POST /api/auth/2fa/verify; nothing else
        is set yet because the password alone isn't enough to log in.
    POST /api/auth/2fa/verify always returns the first shape (by then
    the user is fully authenticated).
    """
    requires_2fa: bool = False
    partial_token: str | None = None
    access_token: str | None = None
    token_type: str = "bearer"
    role: str | None = None
    must_reset_password: bool | None = None
    full_name: str | None = None
    two_fa_enabled: bool = False


class TwoFAVerifyRequest(BaseModel):
    partial_token: str
    code: str

    @field_validator("code")
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Enter your 6-digit code.")
        return v.strip()


class TwoFASetupResponse(BaseModel):
    # QR only — the raw secret / otpauth URI are intentionally never returned.
    qr_code_base64: str


class TwoFAConfirmRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def code_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v.strip()):
            raise ValueError("Enter the 6-digit code from your authenticator app.")
        return v.strip()


class TwoFAStatusResponse(BaseModel):
    enabled: bool


class SetPasswordRequest(BaseModel):
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_strength(cls, v: str) -> str:
        """
        Mirrors the exact rules from our UI prototype:
        min 8 chars, 1 uppercase, 1 number, 1 special character.
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

    def passwords_match(self) -> bool:
        return self.new_password == self.confirm_password


class SetupPasswordRequest(SetPasswordRequest):
    """Set the first password from the invitation link (public endpoint —
    the one-time token in the link is the proof of identity)."""
    token: str


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: str

    @field_validator("otp_code")
    @classmethod
    def otp_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("OTP must be a 6-digit code.")
        return v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str
    new_password: str
    confirm_password: str

    @field_validator("otp_code")
    @classmethod
    def otp_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("OTP must be a 6-digit code.")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

    def passwords_match(self) -> bool:
        return self.new_password == self.confirm_password
