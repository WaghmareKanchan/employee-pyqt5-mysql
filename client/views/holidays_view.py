from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QDateEdit, QLineEdit,
    QPushButton, QLabel, QTableWidget, QGroupBox,
)

from controllers import holiday_controller
from controllers.api_client import APIError, api_client
from views.common import show_error, show_info, populate_table


class HolidaysView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Holidays")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # Admin and HR can both add holidays now (backend permission
        # 'manage_holidays' — see database/schema.sql).
        if api_client.has_role("Admin", "HR"):
            add_box = QGroupBox("Add a holiday")
            form = QFormLayout(add_box)
            self.date_input = QDateEdit()
            self.date_input.setCalendarPopup(True)
            self.date_input.setDate(QDate.currentDate())
            self.name_input = QLineEdit()
            form.addRow("Date", self.date_input)
            form.addRow("Name", self.name_input)
            add_button = QPushButton("Add holiday")
            add_button.setObjectName("primaryButton")
            add_button.clicked.connect(self._add_holiday)
            form.addRow("", add_button)
            layout.addWidget(add_box)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)

        self.table = QTableWidget()
        layout.addWidget(self.table)

    def _add_holiday(self):
        name = self.name_input.text().strip()
        if not name:
            show_error(self, Exception("Holiday name is required."))
            return
        holiday_date = self.date_input.date().toString("yyyy-MM-dd")
        try:
            holiday_controller.create_holiday(holiday_date, name)
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Holiday added.")
        self.name_input.clear()
        self.refresh()

    def refresh(self):
        try:
            rows = holiday_controller.list_holidays()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [("Date", "holiday_date"), ("Name", "name")]
        populate_table(self.table, rows, columns)
