from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget

from controllers import audit_controller
from controllers.api_client import APIError, api_client
from views.common import show_error, populate_table

# What each role is told it can see here, matching the backend's
# _VISIBLE_ROLES scoping exactly (see audit_controller.py).
_SCOPE_HINT = {
    "Admin": "Shows every user's actions across the system.",
    "HR": "Shows your own actions, plus Manager's and Employee's (not Admin's).",
    "Manager": "Shows your own actions, plus HR's and Employee's (not Admin's).",
    "Employee": "Shows only actions performed by your own account.",
}


class AuditView(QWidget):
    """Open to every role. Visibility is role-scoped on the backend:
    Admin sees everyone; HR sees HR/Manager/Employee; Manager sees
    Manager/HR/Employee; Employee sees only its own."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Audit Log")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        hint = QLabel(_SCOPE_HINT.get(api_client.role, "Shows only actions performed by your own account."))
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)

        self.table = QTableWidget()
        layout.addWidget(self.table)

    def refresh(self):
        try:
            rows = audit_controller.list_audit_log()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [
            ("Log ID", "log_id"),
            ("Performed by", lambda r: r.get("username") or (f"User #{r['user_id']}" if r.get("user_id") else "System")),
            ("Role", lambda r: r.get("role_name") or "-"),
            ("Action", "action"),
            ("Table", "table_name"), ("Record ID", "record_id"),
            ("Details", "details"), ("Timestamp", "timestamp"),
        ]
        populate_table(self.table, rows, columns)
