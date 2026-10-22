"""
Upgrade an EXISTING database for the email service. Safe to run many times.

  python migrate_email_service.py                      # add / repair what is missing
  python migrate_email_service.py --recreate-email-queue
        # DROPS and re-creates email_queue (use if you created that table by
        # hand for an older design and it still has leftover/incompatible
        # columns; queued-but-unsent emails are lost, sent history too).

Run from inside the 'database' folder with the backend venv activated.
Fresh installs do not need this: schema.sql already contains everything.
"""
import sys
from pathlib import Path

import pymysql

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app.core import config  # noqa: E402

RECREATE = "--recreate-email-queue" in sys.argv

# (table, column, definition)
COLUMNS = [
    ("employees", "personal_email", "VARCHAR(190) NULL"),
    ("users", "setup_token_hash", "VARCHAR(64) NULL"),
    ("users", "setup_token_expiry", "DATETIME NULL"),
    ("users", "setup_token_used_at", "DATETIME NULL"),
    ("users", "setup_reminded_at", "DATETIME NULL"),
    ("leave_requests", "last_reminded_at", "DATETIME NULL"),
    ("overtime", "last_reminded_at", "DATETIME NULL"),
]
INDEXES = [
    ("employees", "uq_emp_personal_email", "CREATE UNIQUE INDEX uq_emp_personal_email ON employees(personal_email)"),
    ("users", "idx_users_setup_token", "CREATE INDEX idx_users_setup_token ON users(setup_token_hash)"),
]

EMAIL_QUEUE_COLUMNS = [  # every column the service reads/writes
    ("to_address", "VARCHAR(190) NOT NULL"),
    ("user_id", "INT NULL"),
    ("category", "VARCHAR(30) NOT NULL"),
    ("template", "VARCHAR(50) NOT NULL DEFAULT ''"),
    ("subject", "VARCHAR(255) NOT NULL"),
    ("body", "MEDIUMTEXT NOT NULL"),
    ("body_html", "MEDIUMTEXT NULL"),
    ("status", "ENUM('Pending','Sent','Failed') NOT NULL DEFAULT 'Pending'"),
    ("attempts", "INT NOT NULL DEFAULT 0"),
    ("last_error", "VARCHAR(500) NULL"),
    ("next_attempt_at", "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ("created_at", "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ("sent_at", "DATETIME NULL"),
]

CREATE_EMAIL_QUEUE = """
CREATE TABLE email_queue (
    email_id        INT AUTO_INCREMENT PRIMARY KEY,
    to_address      VARCHAR(190) NOT NULL,
    user_id         INT NULL,
    category        VARCHAR(30)  NOT NULL,
    template        VARCHAR(50)  NOT NULL DEFAULT '',
    subject         VARCHAR(255) NOT NULL,
    body            MEDIUMTEXT   NOT NULL,
    body_html       MEDIUMTEXT   NULL,
    status          ENUM('Pending','Sent','Failed') NOT NULL DEFAULT 'Pending',
    attempts        INT NOT NULL DEFAULT 0,
    last_error      VARCHAR(500) NULL,
    next_attempt_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at         DATETIME NULL,
    CONSTRAINT fk_eq_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_eq_due (status, next_attempt_at),
    INDEX idx_eq_user (user_id)
) ENGINE=InnoDB"""

CREATE_PREFS = """
CREATE TABLE IF NOT EXISTS email_preferences (
    user_id  INT NOT NULL,
    category VARCHAR(30) NOT NULL,
    enabled  TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, category),
    CONSTRAINT fk_ep_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB"""


def fix_foreign_key(cur, db, table, wanted_rule, new_name):
    """Make sure <table>.user_id -> users(user_id) uses ON DELETE <wanted_rule>.
    A table created by hand usually has the default (RESTRICT), which makes
    'delete employee' fail with error 1451."""
    cur.execute("""SELECT rc.CONSTRAINT_NAME, rc.DELETE_RULE
                   FROM information_schema.REFERENTIAL_CONSTRAINTS rc
                   JOIN information_schema.KEY_COLUMN_USAGE k
                     ON k.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA AND k.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                        AND k.TABLE_NAME = rc.TABLE_NAME
                   WHERE rc.CONSTRAINT_SCHEMA=%s AND rc.TABLE_NAME=%s AND k.COLUMN_NAME='user_id'
                     AND rc.REFERENCED_TABLE_NAME='users'""", (db, table))
    rows = cur.fetchall()
    if any(rule == wanted_rule for _, rule in rows):
        print(f"  ok     {table}.user_id  (ON DELETE {wanted_rule})")
        return
    for name, rule in rows:
        cur.execute(f"ALTER TABLE {table} DROP FOREIGN KEY `{name}`")
        print(f"  fixed  dropped {table}.{name} (was ON DELETE {rule})")
    if wanted_rule == "SET NULL":
        cur.execute(f"ALTER TABLE {table} MODIFY user_id INT NULL")
    cur.execute(f"ALTER TABLE {table} ADD CONSTRAINT {new_name} FOREIGN KEY (user_id) "
                f"REFERENCES users(user_id) ON DELETE {wanted_rule}")
    print(f"  fixed  {table}.user_id now ON DELETE {wanted_rule}")


def main() -> None:
    conn = pymysql.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER,
                           password=config.DB_PASSWORD, database=config.DB_NAME, autocommit=True)
    db = config.DB_NAME
    try:
        with conn.cursor() as cur:
            def has_column(table, col):
                cur.execute("SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                            (db, table, col))
                return cur.fetchone() is not None

            def has_table(table):
                cur.execute("SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s", (db, table))
                return cur.fetchone() is not None

            print("== columns")
            for table, column, ddl in COLUMNS:
                if has_column(table, column):
                    print(f"  ok     {table}.{column}")
                else:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
                    print(f"  added  {table}.{column}")

            print("== indexes")
            for table, index, ddl in INDEXES:
                # Already there under ANY name? (schema.sql names its unique key 'personal_email')
                col = "personal_email" if "personal_email" in index else "setup_token_hash"
                cur.execute("SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s"
                            + (" AND NON_UNIQUE=0" if "uq_" in index else ""), (db, table, col))
                if cur.fetchone():
                    print(f"  ok     index on {table}.{col}")
                    continue
                try:
                    cur.execute(ddl)
                    print(f"  added  {index}")
                except pymysql.err.MySQLError as exc:
                    print(f"  WARN   could not create {index}: {exc}")
                    print("         (probably duplicate personal emails already exist - make them unique, then re-run)")

            print("== email_queue")
            if RECREATE and has_table("email_queue"):
                cur.execute("DROP TABLE email_queue")
                print("  dropped old email_queue (--recreate-email-queue)")
            if not has_table("email_queue"):
                cur.execute(CREATE_EMAIL_QUEUE)
                print("  created email_queue")
            else:
                for col, ddl in EMAIL_QUEUE_COLUMNS:
                    if not has_column("email_queue", col):
                        cur.execute(f"ALTER TABLE email_queue ADD COLUMN {col} {ddl}")
                        print(f"  added  email_queue.{col}")
                # status must accept exactly the values the service uses
                cur.execute("ALTER TABLE email_queue MODIFY status ENUM('Pending','Sent','Failed') NOT NULL DEFAULT 'Pending'")
                # Columns from an older design that the service never fills and that would
                # make INSERTs fail (NOT NULL, no default):
                cur.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS
                               WHERE TABLE_SCHEMA=%s AND TABLE_NAME='email_queue'
                                 AND IS_NULLABLE='NO' AND COLUMN_DEFAULT IS NULL
                                 AND EXTRA NOT LIKE '%%auto_increment%%'""", (db,))
                needed = {c for c, _ in EMAIL_QUEUE_COLUMNS} | {"email_id"}
                problems = [r[0] for r in cur.fetchall() if r[0] not in needed
                            and r[0] not in ("to_address", "category", "subject", "body")]
                if problems:
                    print(f"  WARN   leftover NOT NULL columns without default: {problems}")
                    print("         Inserts will fail. Re-run with:  python migrate_email_service.py --recreate-email-queue")
                else:
                    print("  ok     table matches what the service needs")
            cur.execute(CREATE_PREFS)
            print("== email_preferences ready")

            # Deleting an employee deletes their login account. Rows in these tables that
            # point to that account must not block the delete.
            print("== foreign keys on user_id")
            fix_foreign_key(cur, db, "email_queue", "SET NULL", "fk_eq_user")
            fix_foreign_key(cur, db, "email_preferences", "CASCADE", "fk_ep_user")
        print("\nMigration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()