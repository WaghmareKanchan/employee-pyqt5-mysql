"""
Quick sanity check: connects to the MySQL database the server uses
and prints key tables.

Usage (from inside the 'database' folder):
    python dev_tools/check_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import text

from app.database import engine

with engine.connect() as conn:
    for table, columns in [
        ("departments", "department_id, department_name, description"),
        ("positions", "position_id, department_id, title, level"),
        ("shifts", "shift_id, shift_name, start_time, end_time, late_cutoff, max_ot_hours_per_day"),
        ("users", "user_id, username, email, role_name, is_active, must_reset_password"),
    ]:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        print(f"\n--- {table} ({count} rows) ---")
        for row in conn.execute(text(f"SELECT {columns} FROM {table}")):
            print(row)
