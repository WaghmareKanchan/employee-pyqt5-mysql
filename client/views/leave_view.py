"""
Leave tab — mirrors the Overtime tab's structure: a "My Leave" tab
(apply + balance + own request history) for everyone, and a separate
"All Requests / Approvals" tab for Admin/HR/Manager, backed by real
GET /api/leave-requests/me and GET /api/leave-requests endpoints.

Previously, approvals were reconstructed from this approver's
notifications (there was no GET endpoint to list leave requests), which
meant a request only showed up here if its notification was still
around, and it lived entirely tangled up with the Notifications tab.
That workaround is gone: Notifications is now purely informational (see
notifications_view.py) and approving/rejecting leave happens only here,
from real leave-request data — exactly like Overtime.
"""
from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QDateEdit,
    QTextEdit, QPushButton, QLabel, QTableWidget, QGroupBox, QTabWidget,
)

from controllers import leave_controller
from controllers.api_client import APIError, api_client
from views.common import show_error, show_info, populate_table, selected_row_data


class MyLeaveTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        layout.addWidget(self._build_apply_box())
        layout.addWidget(self._build_balance_box())

        history_box = QGroupBox("My leave requests")
        history_layout = QVBoxLayout(history_box)
        self.history_table = QTableWidget()
        history_layout.addWidget(self.history_table)
        refresh_history_button = QPushButton("Refresh my requests")
        refresh_history_button.clicked.connect(self._refresh_history)
        history_layout.addWidget(refresh_history_button)
        layout.addWidget(history_box)

        layout.addStretch()

    # ---- Apply for leave -------------------------------------------------
    def _build_apply_box(self) -> QGroupBox:
        box = QGroupBox("Apply for leave")
        form = QFormLayout(box)

        self.leave_type_combo = QComboBox()
        for lt in leave_controller.LEAVE_TYPES:
            self.leave_type_combo.addItem(lt["type_name"], lt["leave_type_id"])

        self.start_date_input = QDateEdit()
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDate(QDate.currentDate())

        self.end_date_input = QDateEdit()
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDate(QDate.currentDate())

        self.reason_input = QTextEdit()
        self.reason_input.setMaximumHeight(60)

        form.addRow("Leave type", self.leave_type_combo)
        form.addRow("Start date", self.start_date_input)
        form.addRow("End date", self.end_date_input)
        form.addRow("Reason", self.reason_input)

        apply_button = QPushButton("Submit leave request")
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self._apply_leave)
        form.addRow("", apply_button)
        return box

    def _apply_leave(self):
        leave_type_id = self.leave_type_combo.currentData()
        start_date = self.start_date_input.date().toString("yyyy-MM-dd")
        end_date = self.end_date_input.date().toString("yyyy-MM-dd")
        reason = self.reason_input.toPlainText().strip() or None
        try:
            leave_controller.apply_leave(leave_type_id, start_date, end_date, reason)
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Leave request submitted. Your manager has been notified.")
        self.reason_input.clear()
        self.refresh()

    # ---- My balance --------------------------------------------------------
    def _build_balance_box(self) -> QGroupBox:
        box = QGroupBox("My leave balance (this year)")
        layout = QVBoxLayout(box)
        self.balance_table = QTableWidget()
        layout.addWidget(self.balance_table)
        refresh_button = QPushButton("Refresh balance")
        refresh_button.clicked.connect(self._refresh_balance)
        layout.addWidget(refresh_button)
        return box

    def _refresh_balance(self):
        try:
            balances = leave_controller.my_leave_balance()
        except APIError as exc:
            show_error(self, exc)
            return

        rows = []
        for b in balances:
            rows.append({
                "leave_type": leave_controller.leave_type_name(b["leave_type_id"]),
                "year": b["year"],
                "allocated_days": b["allocated_days"],
                "used_days": b["used_days"],
                "remaining_days": (b["allocated_days"] or 0) - (b["used_days"] or 0),
            })
        columns = [
            ("Leave type", "leave_type"), ("Year", "year"),
            ("Allocated", "allocated_days"), ("Used", "used_days"),
            ("Remaining", "remaining_days"),
        ]
        populate_table(self.balance_table, rows, columns)

    # ---- My request history -------------------------------------------------
    def _refresh_history(self):
        try:
            rows = leave_controller.my_leave_requests()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [
            ("Leave request ID", "leave_request_id"),
            ("Leave type", lambda r: leave_controller.leave_type_name(r["leave_type_id"])),
            ("Start date", "start_date"), ("End date", "end_date"),
            ("Status", "status"),
        ]
        populate_table(self.history_table, rows, columns)

    def refresh(self):
        self._refresh_balance()
        self._refresh_history()


class AllLeaveTab(QWidget):
    def __init__(self):
        super().__init__()
        self._rows = []
        layout = QVBoxLayout(self)

        actions = QHBoxLayout()
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        approve_button = QPushButton("Approve selected")
        approve_button.clicked.connect(lambda: self._decide(True))
        reject_button = QPushButton("Reject selected")
        reject_button.clicked.connect(lambda: self._decide(False))
        actions.addWidget(refresh_button)
        actions.addWidget(approve_button)
        actions.addWidget(reject_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.table = QTableWidget()
        layout.addWidget(self.table)

    def refresh(self):
        try:
            self._rows = leave_controller.all_leave_requests()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [
            ("Leave request ID", "leave_request_id"), ("Employee ID", "employee_id"),
            ("Leave type", lambda r: leave_controller.leave_type_name(r["leave_type_id"])),
            ("Start date", "start_date"), ("End date", "end_date"),
            ("Status", "status"),
        ]
        populate_table(self.table, self._rows, columns)

    def _decide(self, approve: bool):
        row = selected_row_data(self.table, self._rows)
        if not row:
            show_error(self, Exception("Select a request first."))
            return
        try:
            leave_controller.decide_leave(row["leave_request_id"], approve)
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, f"Leave request #{row['leave_request_id']} {'approved' if approve else 'rejected'}.")
        self.refresh()


class LeaveView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Leave")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        self.my_tab = MyLeaveTab()
        tabs.addTab(self.my_tab, "My Leave")

        self.can_view_all = api_client.has_role("Admin", "HR", "Manager")
        if self.can_view_all:
            self.all_tab = AllLeaveTab()
            tabs.addTab(self.all_tab, "All Requests / Approvals")

        layout.addWidget(tabs)

    def refresh(self):
        self.my_tab.refresh()
        if self.can_view_all:
            self.all_tab.refresh()
