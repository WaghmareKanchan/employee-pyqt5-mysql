"""
Run this once to create the first Admin account.
After this, the Admin logs in and creates every other employee
through the app itself — this script is only for the very first account.

Usage (from inside the 'backend' folder, with venv activated):
    python seed_admin.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, ".")

from app.core import config  # noqa: F401  (loads .env)
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.org import Role
from app.models.people import Employee, User

ADMIN_NAME = "Priya Nair"
ADMIN_EMAIL = "priya.nair@meridian.com"
ADMIN_PASSWORD = "Admin@123"
# A REAL mailbox the admin can read. Password-reset codes and approval emails go here
# (the @meridian.com login ID is not a mailbox). Set ADMIN_PERSONAL_EMAIL in .env or edit here.
ADMIN_PERSONAL_EMAIL = os.getenv("ADMIN_PERSONAL_EMAIL", "")

db = SessionLocal()

existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
if existing:
    print(f"Admin '{ADMIN_EMAIL}' already exists. Nothing to do.")
else:
    admin_role = db.query(Role).filter(Role.role_name == "Admin").first()
    if admin_role is None:
        print("ERROR: 'Admin' role not found. Did you run schema.sql (create_db.py) first?")
        sys.exit(1)

    employee = Employee(
        full_name=ADMIN_NAME,
        email=ADMIN_EMAIL,
        personal_email=ADMIN_PERSONAL_EMAIL or None,
        date_joined=date(2024, 1, 1),
        status="Active",
    )
    db.add(employee)
    db.flush()

    user = User(
        employee_id=employee.employee_id,
        username=ADMIN_EMAIL.split("@")[0],
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        role_id=admin_role.role_id,
        role_name=admin_role.role_name,
        must_reset_password=0,
        is_active=1,
        is_verified=1,
    )
    db.add(user)
    db.commit()
    print(f"Admin created: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")

db.close()
