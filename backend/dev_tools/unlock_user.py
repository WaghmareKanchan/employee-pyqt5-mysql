"""
Testing utility: unlocks a user account immediately, instead of
waiting for ACCOUNT_LOCK_MINUTES to pass. Use this only during
development/testing.

Usage (from inside the 'backend' folder, with venv activated):
    python unlock_user.py priya.nair@meridian.com
"""
import sys

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.people import User

if len(sys.argv) < 2:
    print("Usage: python unlock_user.py <email>")
    sys.exit(1)

email = sys.argv[1]
db = SessionLocal()

user = db.query(User).filter(User.email == email).first()
if user is None:
    print(f"No user found with email: {email}")
else:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    print(f"Unlocked: {email}")

db.close()
