import re
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.core import config

# The four roles seeded in database/schema.sql. Kept here (rather than
# querying the DB for valid values) purely for fast, friendly 422
# validation errors before we even touch the database.
VALID_ROLE_NAMES = {"Admin", "HR", "Manager", "Employee"}


class EmployeeCreateRequest(BaseModel):
    """
    Used by the Admin-provisioned account flow: admin fills this in,
    backend auto-generates the company email + temp password.

    `role_name` defaults to "Employee" (the original behavior). Admin/HR
    can set it to "Manager", "HR", or "Admin" instead — who is actually
    allowed to grant which role is enforced in the controller, not here
    (an HR user, for example, is blocked from creating another Admin).
    """
    full_name: str
    department_id: int
    position_id: int
    employment_type_id: int
    shift_id: int
    manager_id: int | None = None
    date_joined: date
    role_name: str = "Employee"
    # Real mailbox where the invitation is delivered. The generated company
    # address is only a login ID — nobody can read mail sent to it.
    personal_email: EmailStr

    @field_validator("personal_email")
    @classmethod
    def validate_personal_email(cls, v: str) -> str:
        v = v.strip().lower()
        if v.endswith("@" + config.COMPANY_EMAIL_DOMAIN.lower()):
            raise ValueError(
                f"Use a personal/real email, not a @{config.COMPANY_EMAIL_DOMAIN} address "
                "(that one is created automatically as the login ID)."
            )
        return v

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or not re.fullmatch(r"[A-Za-z ]+", v):
            raise ValueError("Full name must be at least 2 characters, letters and spaces only.")
        return v

    @field_validator("role_name")
    @classmethod
    def validate_role_name(cls, v: str) -> str:
        if v not in VALID_ROLE_NAMES:
            raise ValueError(f"role_name must be one of {sorted(VALID_ROLE_NAMES)}.")
        return v


class EmployeeRoleUpdateRequest(BaseModel):
    """Used by PATCH /api/employees/{employee_id}/role to promote/demote
    an existing employee's account between Employee / Manager / HR / Admin."""
    role_name: str

    @field_validator("role_name")
    @classmethod
    def validate_role_name(cls, v: str) -> str:
        if v not in VALID_ROLE_NAMES:
            raise ValueError(f"role_name must be one of {sorted(VALID_ROLE_NAMES)}.")
        return v


class EmployeeOut(BaseModel):
    employee_id: int
    full_name: str
    email: str
    department_id: int | None
    position_id: int | None
    shift_id: int | None
    status: str
    role_name: str | None = None

    class Config:
        from_attributes = True


class EmployeeUpdateRequest(BaseModel):
    """
    All fields optional — only the ones the admin actually wants to
    change need to be sent. Each changed field is logged to
    employee_history automatically.
    """
    department_id: int | None = None
    position_id: int | None = None
    employment_type_id: int | None = None
    shift_id: int | None = None
    manager_id: int | None = None


class EmployeeHistoryOut(BaseModel):
    history_id: int
    field_changed: str
    old_value: str | None
    new_value: str | None
    changed_by: int | None
    changed_at: datetime

    class Config:
        from_attributes = True


class EmployeeCredentialsOut(BaseModel):
    """Returned after creating an account. No password is shown any more:
    the person receives an invitation link at their personal email."""
    email: str                     # the generated company login ID
    personal_email: str
    invitation_queued: bool
    message: str


class PersonalEmailUpdateRequest(BaseModel):
    personal_email: EmailStr

    @field_validator("personal_email")
    @classmethod
    def validate_personal_email(cls, v: str) -> str:
        v = v.strip().lower()
        if v.endswith("@" + config.COMPANY_EMAIL_DOMAIN.lower()):
            raise ValueError(f"Use a real personal email, not a @{config.COMPANY_EMAIL_DOMAIN} address.")
        return v
