"""
Sets the personal (real mailbox) email of an existing account - e.g. for
the seeded Admin or for employees created before the email service existed.

Usage (from inside the 'backend' folder, with venv activated):
    python dev_tools/set_personal_email.py priya.nair@meridian.com priya@gmail.com
"""
import sys

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.people import Employee

if len(sys.argv) < 3:
    print("Usage: python dev_tools/set_personal_email.py <company_email> <personal_email>")
    sys.exit(1)

company_email, personal_email = sys.argv[1], sys.argv[2].strip().lower()
db = SessionLocal()
employee = db.query(Employee).filter(Employee.email == company_email).first()
if employee is None:
    print(f"No employee found with email: {company_email}")
else:
    employee.personal_email = personal_email
    db.commit()
    print(f"{company_email} -> personal email set to {personal_email}")
db.close()
