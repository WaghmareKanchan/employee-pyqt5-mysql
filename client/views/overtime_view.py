from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QDateEdit, QDoubleSpinBox,
    QPushButton, QLabel, QTableWidget, QGroupBox, QTabWidget,
)

from controllers import overtime_controller
from controllers.api_client import APIError, api_client
from views.common import show_error, show_info, populate_table, selected_row_data


class MyOvertimeTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        apply_box = QGroupBox("Apply for overtime")
        form = QFormLayout(apply_box)
        self.work_date_input = QDateEdit()
        self.work_date_input.setCalendarPopup(True)
        self.work_date_input.setDate(QDate.currentDate())
        self.hours_input = QDoubleSpinBox()
        self.hours_input.setRange(0.5, 12)
        self.hours_input.setSingleStep(0.5)
        self.hours_input.setValue(1)
        form.addRow("Work date", self.work_date_input)
        form.addRow("Hours", self.hours_input)
        apply_button = QPushButton("Submit request")
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self._apply)
        form.addRow("", apply_button)
        layout.addWidget(apply_box)

        refresh_button = QPushButton("Refresh my requests")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)

        self.table = QTableWidget()
        layout.addWidget(self.table)

    def _apply(self):
        work_date = self.work_date_input.date().toString("yyyy-MM-dd")
        hours = self.hours_input.value()
        try:
            overtime_controller.apply_overtime(work_date, hours)
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Overtime request submitted. Note: hours are automatically\ncapped at your shift's daily overtime limit.")
        self.refresh()

    def refresh(self):
        try:
            rows = overtime_controller.my_overtime()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [("Date", "work_date"), ("Hours", "hours"), ("Status", "status")]
        populate_table(self.table, rows, columns)


class AllOvertimeTab(QWidget):
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
            self._rows = overtime_controller.all_overtime()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [
            ("Overtime ID", "overtime_id"), ("Employee ID", "employee_id"),
            ("Date", "work_date"), ("Hours", "hours"), ("Status", "status"),
        ]
        populate_table(self.table, self._rows, columns)

    def _decide(self, approve: bool):
        row = selected_row_data(self.table, self._rows)
        if not row:
            show_error(self, Exception("Select a request first."))
            return
        try:
            overtime_controller.decide_overtime(row["overtime_id"], approve)
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, f"Overtime request #{row['overtime_id']} {'approved' if approve else 'rejected'}.")
        self.refresh()


class OvertimeView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Overtime")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        self.my_tab = MyOvertimeTab()
        tabs.addTab(self.my_tab, "My Overtime")

        self.can_view_all = api_client.has_role("Admin", "HR", "Manager")
        if self.can_view_all:
            self.all_tab = AllOvertimeTab()
            tabs.addTab(self.all_tab, "All Requests / Approvals")

        layout.addWidget(tabs)

    def refresh(self):
        self.my_tab.refresh()
        if self.can_view_all:
            self.all_tab.refresh()
