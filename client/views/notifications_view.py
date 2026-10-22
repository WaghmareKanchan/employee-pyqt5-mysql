from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget

from controllers import notification_controller
from controllers.api_client import APIError
from views.common import show_error, show_info, populate_table, selected_row_data


class NotificationsView(QWidget):
    def __init__(self):
        super().__init__()
        self._rows = []
        layout = QVBoxLayout(self)

        title = QLabel("Notifications")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        actions = QHBoxLayout()
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        mark_read_button = QPushButton("Mark selected as read")
        mark_read_button.clicked.connect(self._mark_read)
        actions.addWidget(refresh_button)
        actions.addWidget(mark_read_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.table = QTableWidget()
        layout.addWidget(self.table)

    def refresh(self):
        try:
            self._rows = notification_controller.my_notifications()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [
            ("Title", "title"), ("Message", "message"),
            ("Employee ID", lambda n: n.get("employee_id") if n.get("employee_id") is not None else "-"),
            ("Reference", lambda n: f"{n.get('reference_table') or '-'} #{n.get('reference_id') or '-'}"),
            ("Read?", lambda n: "Yes" if n.get("is_read") else "No"),
            ("Received", "created_at"),
        ]
        populate_table(self.table, self._rows, columns)

    def _mark_read(self):
        row = selected_row_data(self.table, self._rows)
        if not row:
            show_error(self, Exception("Select a notification first."))
            return
        try:
            notification_controller.mark_as_read(row["notification_id"])
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Notification marked as read.")
        self.refresh()
