"""
Testing utility: assigns a manager to an employee directly in the
database. The employee-create API doesn't accept manager_id yet,
so this fills that gap for testing the notification flow.

Usage (from inside the 'backend' folder, with venv activated):
    python set_manager.py <employee_email> <manager_email>

Example:
    python set_manager.py report.person@meridian.com manager.person@meridian.com
"""
import sys

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.people import Employee

if len(sys.argv) < 3:
    print("Usage: python set_manager.py <employee_email> <manager_email>")
    sys.exit(1)

employee_email, manager_email = sys.argv[1], sys.argv[2]
db = SessionLocal()

employee = db.query(Employee).filter(Employee.email == employee_email).first()
manager = db.query(Employee).filter(Employee.email == manager_email).first()

if employee is None:
    print(f"No employee found with email: {employee_email}")
elif manager is None:
    print(f"No employee found with email: {manager_email}")
else:
    employee.manager_id = manager.employee_id
    db.commit()
    print(f"Done: {employee_email} now reports to {manager_email}")

db.close()
