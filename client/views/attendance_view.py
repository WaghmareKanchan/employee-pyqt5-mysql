from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget,
    QGroupBox, QTabWidget,
)

from controllers import attendance_controller
from controllers.api_client import APIError, api_client
from views.common import show_error, show_info, populate_table


class MyAttendanceTab(QWidget):
    """Read-only history now — Check In / Check Out live only on the My
    Account tab (see profile_view.py), so this tab just shows the record
    those actions produced."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        actions = QHBoxLayout()
        hint = QLabel("Use the My Account tab to check in / check out.")
        hint.setObjectName("hintLabel")
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        actions.addWidget(hint)
        actions.addStretch()
        actions.addWidget(refresh_button)
        layout.addLayout(actions)

        self.table = QTableWidget()
        layout.addWidget(self.table)

    def refresh(self):
        try:
            rows = attendance_controller.my_attendance()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [
            ("Date", "work_date"), ("Check-in", "check_in"), ("Check-out", "check_out"),
            ("Total hours", "total_hours"), ("Status", "status"), ("Reason", "status_reason"),
            ("Late?", lambda r: "Yes" if r.get("is_late") else "No"),
        ]
        populate_table(self.table, rows, columns)


class AllAttendanceTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)
        self.table = QTableWidget()
        layout.addWidget(self.table)

    def refresh(self):
        try:
            rows = attendance_controller.all_attendance()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [
            ("Employee ID", "employee_id"), ("Date", "work_date"),
            ("Check-in", "check_in"), ("Check-out", "check_out"),
            ("Total hours", "total_hours"), ("Status", "status"), ("Reason", "status_reason"),
        ]
        populate_table(self.table, rows, columns)


class AttendanceView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Attendance")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        self.my_tab = MyAttendanceTab()
        tabs.addTab(self.my_tab, "My Attendance")

        self.can_view_all = api_client.has_role("Admin", "HR", "Manager")
        if self.can_view_all:
            self.all_tab = AllAttendanceTab()
            tabs.addTab(self.all_tab, "All Employees")

        layout.addWidget(tabs)

    def refresh(self):
        self.my_tab.refresh()
        if self.can_view_all:
            self.all_tab.refresh()
