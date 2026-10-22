"""
Creates the MySQL database and all tables from schema.sql.
Connection details come from backend/.env (DB_USER, DB_PASSWORD, ...).

Usage (from inside the 'database' folder):
    python create_db.py
"""
import re
import sys
from pathlib import Path

import pymysql

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app.core import config  # noqa: E402

db_name = config.DB_NAME
conn = pymysql.connect(host=config.DB_HOST, port=config.DB_PORT,
                       user=config.DB_USER, password=config.DB_PASSWORD,
                       autocommit=True)
try:
    with conn.cursor() as cur:
        cur.execute("SHOW DATABASES LIKE %s", (db_name,))
        if cur.fetchone():
            raise SystemExit(f"Database '{db_name}' already exists. Drop it first to recreate.")
        sql = (HERE / "schema.sql").read_text(encoding="utf-8")
        sql = re.sub(r"^\s*--.*$", "", sql, flags=re.M)      # strip comment lines
        for stmt in (s.strip() for s in sql.split(";")):
            if stmt:
                cur.execute(stmt)
    print(f"Database '{db_name}' created successfully.")
finally:
    conn.close()
