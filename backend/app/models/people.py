"""
People models: employees (HR profile) and users (login/auth).

Kept as two separate tables/models on purpose: auth concerns
(password, OTP, lockout) never mix with HR profile data.
"""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    
    # Generated company login ID
    email = Column(String, unique=True, nullable=False)
    
    # Real inbox for invitations and notifications
    personal_email = Column(String(255), unique=True, nullable=True)
    
    phone = Column(String)
    date_of_birth = Column(Date)
    date_joined = Column(Date, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.department_id"))
    position_id = Column(Integer, ForeignKey("positions.position_id"))
    employment_type_id = Column(Integer, ForeignKey("employment_types.employment_type_id"))
    shift_id = Column(Integer, ForeignKey("shifts.shift_id"))
    manager_id = Column(Integer, ForeignKey("employees.employee_id"))
    status = Column(String, default="Active")  # Active / Inactive / Terminated

    department = relationship("Department")
    position = relationship("Position")
    employment_type = relationship("EmploymentType")
    shift = relationship("Shift")
    manager = relationship("Employee", remote_side=[employee_id])
    # passive_deletes=True: let the DB's ON DELETE CASCADE (users.employee_id,
    # schema.sql) actually delete the linked User row when this Employee is
    # deleted. Without this, SQLAlchemy's default behavior is to try to NULL
    # out user.employee_id before the delete — which "succeeds" silently but
    # leaves an orphaned login account behind instead of removing it (that
    # orphan then blocks re-creating an employee with the same email/username).
    user_account = relationship("User", back_populates="employee", uselist=False, passive_deletes=True)

    @property
    def role_name(self) -> str | None:
        """Convenience accessor so EmployeeOut can expose the linked
        account's role without every caller having to join Users/Roles
        by hand. None if this employee has no login account."""
        if self.user_account is None or self.user_account.role is None:
            return None
        return self.user_account.role.role_name


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), unique=True, nullable=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    # Denormalized copy of roles.role_name, set when the account is
    # created and kept in sync whenever role_id changes (see
    # employee_controller.create_employee_with_account /
    # change_employee_role). Lets anyone browsing the users table see
    # the role directly on the row, without joining to roles.
    role_name = Column(String, nullable=False)

    is_verified = Column(Integer, default=0)
    otp_code = Column(String)
    otp_expiry = Column(DateTime)
    verification_token = Column(String)

    must_reset_password = Column(Integer, default=1)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)

    is_active = Column(Integer, default=1)
    last_login = Column(DateTime)

    # Two-factor auth (TOTP). totp_secret is set as soon as the user starts
    # enrollment but totp_enabled stays 0 until they confirm a code from
    # their authenticator app — so a half-finished setup never locks
    # anyone out at login.
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Integer, default=0)

    # Invitation / account-setup link. Only the SHA-256 hash of the token is
    # stored (never the token itself), plus expiry and when it was used.
    setup_token_hash = Column(String, nullable=True, index=True)
    setup_token_expiry = Column(DateTime, nullable=True)
    setup_token_used_at = Column(DateTime, nullable=True)
    setup_reminded_at = Column(DateTime, nullable=True)

    employee = relationship("Employee", back_populates="user_account")
    role = relationship("Role")
