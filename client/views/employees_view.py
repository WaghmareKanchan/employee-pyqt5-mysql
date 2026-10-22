from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QPushButton, QLabel,
)

from controllers import employee_controller
from controllers.api_client import APIError, api_client
from views.common import show_error, show_info, confirm, populate_table_with_actions, selected_row_data
from views.employee_form_dialog import EmployeeFormDialog
from views.employee_history_dialog import EmployeeHistoryDialog
from views.change_role_dialog import ChangeRoleDialog


class EmployeesView(QWidget):
    """
    Who sees what here (mirrors the backend permission matrix exactly):
      - Admin:   everything — create, edit assignment, change role
                 (any role), suspend/reactivate, delete, view history.
      - HR:      create employees and edit their assignment; change role,
                 but only into/out of Manager or Employee (never
                 Admin/HR — the backend enforces this too); suspend/
                 reactivate; delete; view history.
      - Manager: edit assignment (department/position/employment type/
                 shift/manager) only — no create, no role change, no
                 suspend/reactivate, no delete, no history. (Delete is a
                 destructive, account-management action reserved for
                 Admin/HR, same as suspend/reactivate always were.)

    Edit and Delete live directly on each row (Actions column) instead
    of a separate "select a row, then click a button below" flow.
    """
    def __init__(self):
        super().__init__()
        self._employees = []
        self.is_admin = api_client.has_role("Admin")
        self.is_hr = api_client.has_role("HR")
        self.is_manager = api_client.has_role("Manager")
        self.can_manage = self.is_admin or self.is_hr  # create / suspend / reactivate / history / role / delete
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Employees")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        if self.can_manage:
            # Creating an employee means choosing its role (backend
            # permission 'assign_roles') — Admin and HR both have it;
            # HR is limited server-side to Manager/Employee roles only.
            self.create_button = QPushButton("+ New Employee")
            self.create_button.setObjectName("primaryButton")
            self.create_button.clicked.connect(self._create_employee)
            header.addWidget(self.create_button)
        layout.addLayout(header)

        self.table = QTableWidget()
        layout.addWidget(self.table)

        # Change Role / View History / Suspend / Reactivate stay as a
        # "select a row, then click" row of buttons below the table —
        # only Edit and Delete moved into the per-row Actions column.
        actions = QHBoxLayout()
        if self.can_manage:
            self.change_role_button = QPushButton("Change Role")
            self.change_role_button.clicked.connect(self._change_role)
            actions.addWidget(self.change_role_button)
            self.history_button = QPushButton("View History")
            self.history_button.clicked.connect(self._view_history)
            actions.addWidget(self.history_button)
            self.suspend_button = QPushButton("Suspend")
            self.suspend_button.clicked.connect(self._suspend_employee)
            actions.addWidget(self.suspend_button)
            self.reactivate_button = QPushButton("Reactivate")
            self.reactivate_button.clicked.connect(self._reactivate_employee)
            actions.addWidget(self.reactivate_button)
            self.resend_button = QPushButton("Resend Invitation")
            self.resend_button.clicked.connect(self._resend_invitation)
            actions.addWidget(self.resend_button)
        actions.addStretch()
        layout.addLayout(actions)

    def refresh(self):
        try:
            self._employees = employee_controller.list_employees()
        except APIError as exc:
            show_error(self, exc)
            return

        columns = [
            ("ID", "employee_id"),
            ("Full name", "full_name"),
            ("Email", "email"),
            ("Role", lambda e: e.get("role_name") or "-"),
            ("Department ID", "department_id"),
            ("Position ID", "position_id"),
            ("Shift ID", "shift_id"),
            ("Status", "status"),
        ]

        # Edit (department/position/employment type/shift/manager) is
        # available to Admin, HR, AND Manager — backend permission
        # 'edit_employee_assignment' covers Manager here. Delete is
        # Admin/HR only, matching 'manage_employees' on the backend.
        row_actions = [("Edit", self._edit_employee)]
        if self.can_manage:
            row_actions.append(("Delete", self._delete_employee))

        populate_table_with_actions(self.table, self._employees, columns, row_actions)

    def _selected(self) -> dict | None:
        return selected_row_data(self.table, self._employees)

    def _create_employee(self):
        dialog = EmployeeFormDialog(self, employee=None, employees=self._employees,
                                     allowed_roles=self._selectable_roles())
        if dialog.exec_():
            self.refresh()

    def _edit_employee(self, employee: dict):
        dialog = EmployeeFormDialog(self, employee=employee, employees=self._employees)
        if dialog.exec_():
            self.refresh()

    def _delete_employee(self, employee: dict):
        if not confirm(
            self,
            f"Permanently delete {employee['full_name']}? This also removes their "
            "login account, attendance, leave, and overtime history. This cannot be undone.",
            title="Delete employee",
        ):
            return
        try:
            employee_controller.delete_employee(employee["employee_id"])
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Employee deleted.")
        self.refresh()

    def _change_role(self):
        employee = self._selected()
        if not employee:
            show_error(self, Exception("Select an employee first."))
            return
        if ChangeRoleDialog(self, employee, allowed_roles=self._selectable_roles()).exec_():
            self.refresh()

    def _selectable_roles(self) -> list:
        """HR only ever offers Manager/Employee (matches the backend's
        HR scoping in employee_controller._assert_role_assignment_allowed);
        Admin still sees every role."""
        if self.is_admin:
            return employee_controller.ALL_ROLES
        return ["Employee", "Manager"]

    def _view_history(self):
        employee = self._selected()
        if not employee:
            show_error(self, Exception("Select an employee first."))
            return
        EmployeeHistoryDialog(self, employee).exec_()

    def _resend_invitation(self):
        employee = self._selected()
        if not employee:
            show_error(self, Exception("Select an employee first."))
            return
        try:
            employee_controller.resend_invitation(employee["employee_id"])
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "A new invitation was queued. The old link no longer works.")

    def _suspend_employee(self):
        employee = self._selected()
        if not employee:
            show_error(self, Exception("Select an employee first."))
            return
        if not confirm(self, f"Suspend {employee['full_name']}'s account?"):
            return
        try:
            employee_controller.suspend_employee(employee["employee_id"])
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Employee account suspended.")
        self.refresh()

    def _reactivate_employee(self):
        employee = self._selected()
        if not employee:
            show_error(self, Exception("Select an employee first."))
            return
        try:
            employee_controller.reactivate_employee(employee["employee_id"])
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Employee account reactivated.")
        self.refresh()
