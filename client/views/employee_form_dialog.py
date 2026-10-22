"""Dialog for creating a new employee (Admin/HR), or editing department/
position/employment type/shift/manager for an existing one (Admin/HR/
Manager). Matches EmployeeCreateRequest / EmployeeUpdateRequest on the
backend."""
from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDateEdit,
    QDialogButtonBox, QLabel,
)

from controllers import employee_controller, org_controller
from controllers.api_client import APIError
from views.common import show_error, show_info


class EmployeeFormDialog(QDialog):
    def __init__(self, parent=None, employee: dict | None = None, employees: list | None = None,
                 allowed_roles: list | None = None):
        """
        employee=None            -> "create employee" mode
        employee={...} (dict)    -> "edit employee" mode (department/position/
                                     employment type/shift/manager only)
        employees                -> full employee list, used to populate the
                                     "manager" dropdown
        allowed_roles             -> roles offered in the Role dropdown when
                                     creating. Admin sees all four; HR sees
                                     only Manager/Employee (the backend
                                     enforces this too either way).
        """
        super().__init__(parent)
        self.employee = employee
        self.employees = employees or []
        self.allowed_roles = allowed_roles or employee_controller.ALL_ROLES
        self.is_edit = employee is not None
        self.setWindowTitle("Edit Employee" if self.is_edit else "Create Employee")
        self.setMinimumWidth(420)
        self._build_ui()
        self._load_lookups()
        if self.is_edit:
            self._prefill()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        if not self.is_edit:
            self.full_name_input = QLineEdit()
            self.full_name_input.setPlaceholderText("Letters and spaces only")
            form.addRow("Full name", self.full_name_input)
            
            # Personal email field
            self.personal_email_input = QLineEdit()
            self.personal_email_input.setPlaceholderText(
                "Enter employee's personal email"
            )
            form.addRow("Personal Email", self.personal_email_input)

            self.date_joined_input = QDateEdit()
            self.date_joined_input.setCalendarPopup(True)
            self.date_joined_input.setDate(QDate.currentDate())
            form.addRow("Date joined", self.date_joined_input)

            self.role_combo = QComboBox()
            # Admin/HR both reach this dialog now. Admin sees every role;
            # HR only sees Manager/Employee (self.allowed_roles), matching
            # what the backend will actually accept from an HR account.
            for role_name in self.allowed_roles:
                self.role_combo.addItem(role_name, role_name)
            form.addRow("Role", self.role_combo)
        else:
            name_label = QLabel(self.employee.get("full_name", ""))
            form.addRow("Full name", name_label)

        self.department_combo = QComboBox()
        self.position_combo = QComboBox()
        self.employment_type_combo = QComboBox()
        self.shift_combo = QComboBox()
        self.manager_combo = QComboBox()

        form.addRow("Department", self.department_combo)
        form.addRow("Position", self.position_combo)
        form.addRow("Employment type", self.employment_type_combo)
        form.addRow("Shift", self.shift_combo)
        form.addRow("Manager (optional)", self.manager_combo)

        layout.addLayout(form)

        if not self.is_edit:
            note = QLabel(
                "A company login ID is generated automatically. The employee gets an\n"
                "invitation link at their personal email to choose their own password."
            )
            note.setObjectName("hintLabel")
            note.setWordWrap(True)
            layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_lookups(self):
        try:
            departments = org_controller.list_departments()
            positions = org_controller.list_positions()
            shifts = org_controller.list_shifts()
        except APIError as exc:
            show_error(self, exc)
            departments, positions, shifts = [], [], []
        employment_types = org_controller.list_employment_types()

        self._departments = departments
        self._positions = positions
        self._shifts = shifts
        self._employment_types = employment_types

        self.department_combo.addItem("Select...", None)
        for d in departments:
            self.department_combo.addItem(d["department_name"], d["department_id"])

        self.position_combo.addItem("Select...", None)
        for p in positions:
            self.position_combo.addItem(p["title"], p["position_id"])

        self.employment_type_combo.addItem("Select...", None)
        for et in employment_types:
            self.employment_type_combo.addItem(et["type_name"], et["employment_type_id"])

        self.shift_combo.addItem("Select...", None)
        for s in shifts:
            self.shift_combo.addItem(s["shift_name"], s["shift_id"])

        self.manager_combo.addItem("No manager", None)
        for e in self.employees:
            if self.is_edit and e.get("employee_id") == self.employee.get("employee_id"):
                continue  # can't be your own manager
            self.manager_combo.addItem(f"{e['full_name']} ({e['email']})", e["employee_id"])

    def _prefill(self):
        self._select_combo_value(self.department_combo, self.employee.get("department_id"))
        self._select_combo_value(self.position_combo, self.employee.get("position_id"))
        self._select_combo_value(self.shift_combo, self.employee.get("shift_id"))
        # employment_type_id and manager_id are not part of EmployeeOut, so
        # they default to "Select..." / "No manager" — the admin re-picks
        # them explicitly only if they want to change that field.

    @staticmethod
    def _select_combo_value(combo: QComboBox, value):
        if value is None:
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _submit(self):
        department_id = self.department_combo.currentData()
        position_id = self.position_combo.currentData()
        employment_type_id = self.employment_type_combo.currentData()
        shift_id = self.shift_combo.currentData()
        manager_id = self.manager_combo.currentData()

        try:
            if self.is_edit:
                employee_controller.update_employee(
                    self.employee["employee_id"],
                    department_id=department_id,
                    position_id=position_id,
                    employment_type_id=employment_type_id,
                    shift_id=shift_id,
                    manager_id=manager_id,
                )
                show_info(self, "Employee updated successfully.")
            else:
                full_name = self.full_name_input.text().strip()
                
                personal_email = self.personal_email_input.text().strip()

                if not personal_email:
                    show_error(self, Exception("Personal email is required."))
                    return
                if "@" not in personal_email or "." not in personal_email.split("@")[-1]:
                    show_error(self, Exception("Enter a valid personal email address."))
                    return
                
                if not full_name:
                    show_error(self, Exception("Full name is required."))
                    return
                if None in (department_id, position_id, employment_type_id, shift_id):
                    show_error(self, Exception("Department, position, employment type, and shift are all required."))
                    return
                date_joined = self.date_joined_input.date().toString("yyyy-MM-dd")
                role_name = self.role_combo.currentData()
                result = employee_controller.create_employee(
                    full_name=full_name,
                    personal_email=personal_email,
                    department_id=department_id,
                    position_id=position_id,
                    employment_type_id=employment_type_id,
                    shift_id=shift_id,
                    date_joined=date_joined,
                    manager_id=manager_id,
                    role_name=role_name,
                )
                show_info(
                    self,
                    f"{result['message']}\n\n"
                    f"Login ID: {result['email']}\n"
                    "The employee must open the link in the email to choose a password.\n"
                    "(Link lost or expired? Select the employee and click Resend Invitation.)",
                    title="Employee Created",
                )
        except APIError as exc:
            show_error(self, exc)
            return

        self.accept()
