"""Promote/demote an existing employee between Employee / Manager / HR /
Admin. Admin and HR both see this (see employees_view.py); Admin can pick
any role, HR is offered only Manager/Employee — the backend rejects an
HR account trying to grant (or touch) Admin/HR either way, this just
keeps the dropdown from offering choices HR can't actually use."""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QLabel, QDialogButtonBox

from controllers import employee_controller
from controllers.api_client import APIError
from views.common import show_error, show_info


class ChangeRoleDialog(QDialog):
    def __init__(self, parent, employee: dict, allowed_roles: list | None = None):
        super().__init__(parent)
        self.employee = employee
        self.setWindowTitle(f"Change role — {employee.get('full_name', '')}")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        current_role = employee.get("role_name") or "Employee"
        layout.addWidget(QLabel(f"Current role: {current_role}"))

        form = QFormLayout()
        self.role_combo = QComboBox()
        for role_name in (allowed_roles or employee_controller.ALL_ROLES):
            self.role_combo.addItem(role_name, role_name)
        index = self.role_combo.findData(current_role)
        if index >= 0:
            self.role_combo.setCurrentIndex(index)
        form.addRow("New role", self.role_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        new_role = self.role_combo.currentData()
        try:
            employee_controller.change_role(self.employee["employee_id"], new_role)
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, f"Role updated to {new_role}.")
        self.accept()
