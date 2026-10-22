from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QLabel, QDialogButtonBox

from controllers import employee_controller
from controllers.api_client import APIError
from views.common import show_error, populate_table


class EmployeeHistoryDialog(QDialog):
    def __init__(self, parent, employee: dict):
        super().__init__(parent)
        self.employee = employee
        self.setWindowTitle(f"Change history — {employee.get('full_name', '')}")
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Change history for {employee.get('full_name', '')}"))

        self.table = QTableWidget()
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)

        self._load()

    def _load(self):
        try:
            history = employee_controller.get_employee_history(self.employee["employee_id"])
        except APIError as exc:
            show_error(self, exc)
            history = []

        columns = [
            ("Field changed", "field_changed"),
            ("Old value", "old_value"),
            ("New value", "new_value"),
            ("Changed by (user id)", "changed_by"),
            ("Changed at", "changed_at"),
        ]
        populate_table(self.table, history, columns)
