from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QPushButton, QLabel,
    QTabWidget, QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox,
    QTimeEdit, QDoubleSpinBox, QSpinBox, QCheckBox,
)
from PyQt5.QtCore import QTime

from controllers import org_controller
from controllers.api_client import APIError
from views.common import show_error, show_info, confirm, populate_table, selected_row_data


# ------------------------------------------------------------------ Departments
class DepartmentDialog(QDialog):
    def __init__(self, parent=None, department: dict | None = None):
        super().__init__(parent)
        self.department = department
        self.setWindowTitle("Edit Department" if department else "New Department")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit(department["department_name"] if department else "")
        self.description_input = QLineEdit(department.get("description") or "" if department else "")
        form.addRow("Name", self.name_input)
        form.addRow("Description", self.description_input)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        name = self.name_input.text().strip()
        description = self.description_input.text().strip() or None
        if not name:
            show_error(self, Exception("Department name is required."))
            return
        try:
            if self.department:
                org_controller.update_department(self.department["department_id"], name, description)
            else:
                org_controller.create_department(name, description)
        except APIError as exc:
            show_error(self, exc)
            return
        self.accept()


class DepartmentsTab(QWidget):
    def __init__(self, can_edit: bool, can_manage: bool):
        super().__init__()
        # can_manage (Admin only) => Add + Delete. can_edit (Admin/HR/
        # Manager) => Edit existing rows. can_manage implies can_edit.
        self.can_edit = can_edit
        self.can_manage = can_manage
        self._rows = []
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Departments"))
        header.addStretch()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        if can_manage:
            self.add_button = QPushButton("+ Add")
            self.add_button.clicked.connect(self._add)
            header.addWidget(self.add_button)
        layout.addLayout(header)

        self.table = QTableWidget()
        layout.addWidget(self.table)

        if can_edit or can_manage:
            actions = QHBoxLayout()
            if can_edit:
                self.edit_button = QPushButton("Edit")
                self.edit_button.clicked.connect(self._edit)
                actions.addWidget(self.edit_button)
            if can_manage:
                self.delete_button = QPushButton("Delete")
                self.delete_button.clicked.connect(self._delete)
                actions.addWidget(self.delete_button)
            actions.addStretch()
            layout.addLayout(actions)

    def refresh(self):
        try:
            self._rows = org_controller.list_departments()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [("ID", "department_id"), ("Name", "department_name"), ("Description", "description")]
        populate_table(self.table, self._rows, columns)

    def _add(self):
        if DepartmentDialog(self).exec_():
            self.refresh()

    def _edit(self):
        row = selected_row_data(self.table, self._rows)
        if not row:
            show_error(self, Exception("Select a department first."))
            return
        if DepartmentDialog(self, row).exec_():
            self.refresh()

    def _delete(self):
        row = selected_row_data(self.table, self._rows)
        if not row:
            show_error(self, Exception("Select a department first."))
            return
        if not confirm(self, f"Delete department '{row['department_name']}'?"):
            return
        try:
            org_controller.delete_department(row["department_id"])
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Department deleted.")
        self.refresh()


# ------------------------------------------------------------------ Positions
class PositionDialog(QDialog):
    def __init__(self, parent=None, position: dict | None = None, departments: list | None = None):
        super().__init__(parent)
        self.position = position
        self.setWindowTitle("Edit Position" if position else "New Position")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.department_combo = QComboBox()
        for d in departments or []:
            self.department_combo.addItem(d["department_name"], d["department_id"])
        if position:
            index = self.department_combo.findData(position.get("department_id"))
            if index >= 0:
                self.department_combo.setCurrentIndex(index)

        self.title_input = QLineEdit(position["title"] if position else "")
        self.level_input = QLineEdit((position.get("level") or "") if position else "")
        self.level_input.setPlaceholderText("Junior / Senior / Lead / Manager")

        form.addRow("Department", self.department_combo)
        form.addRow("Title", self.title_input)
        form.addRow("Level", self.level_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        department_id = self.department_combo.currentData()
        title = self.title_input.text().strip()
        level = self.level_input.text().strip() or None
        if department_id is None or not title:
            show_error(self, Exception("Department and title are required."))
            return
        try:
            if self.position:
                org_controller.update_position(self.position["position_id"], department_id, title, level)
            else:
                org_controller.create_position(department_id, title, level)
        except APIError as exc:
            show_error(self, exc)
            return
        self.accept()


class PositionsTab(QWidget):
    def __init__(self, can_edit: bool, can_manage: bool):
        super().__init__()
        self.can_edit = can_edit
        self.can_manage = can_manage
        self._rows = []
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Positions"))
        header.addStretch()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        if can_manage:
            self.add_button = QPushButton("+ Add")
            self.add_button.clicked.connect(self._add)
            header.addWidget(self.add_button)
        layout.addLayout(header)

        self.table = QTableWidget()
        layout.addWidget(self.table)

        if can_edit or can_manage:
            actions = QHBoxLayout()
            if can_edit:
                self.edit_button = QPushButton("Edit")
                self.edit_button.clicked.connect(self._edit)
                actions.addWidget(self.edit_button)
            if can_manage:
                self.delete_button = QPushButton("Delete")
                self.delete_button.clicked.connect(self._delete)
                actions.addWidget(self.delete_button)
            actions.addStretch()
            layout.addLayout(actions)

    def refresh(self):
        try:
            self._rows = org_controller.list_positions()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [
            ("ID", "position_id"), ("Department ID", "department_id"),
            ("Title", "title"), ("Level", "level"),
        ]
        populate_table(self.table, self._rows, columns)

    def _departments(self):
        try:
            return org_controller.list_departments()
        except APIError as exc:
            show_error(self, exc)
            return []

    def _add(self):
        if PositionDialog(self, departments=self._departments()).exec_():
            self.refresh()

    def _edit(self):
        row = selected_row_data(self.table, self._rows)
        if not row:
            show_error(self, Exception("Select a position first."))
            return
        if PositionDialog(self, row, departments=self._departments()).exec_():
            self.refresh()

    def _delete(self):
        row = selected_row_data(self.table, self._rows)
        if not row:
            show_error(self, Exception("Select a position first."))
            return
        if not confirm(self, f"Delete position '{row['title']}'?"):
            return
        try:
            org_controller.delete_position(row["position_id"])
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Position deleted.")
        self.refresh()


# ------------------------------------------------------------------ Shifts
class ShiftDialog(QDialog):
    def __init__(self, parent=None, shift: dict | None = None):
        super().__init__(parent)
        self.shift = shift
        self.setWindowTitle("Edit Shift" if shift else "New Shift")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit(shift["shift_name"] if shift else "")

        self.start_time_input = QTimeEdit()
        self.start_time_input.setDisplayFormat("HH:mm")
        self.end_time_input = QTimeEdit()
        self.end_time_input.setDisplayFormat("HH:mm")
        self.late_cutoff_input = QTimeEdit()
        self.late_cutoff_input.setDisplayFormat("HH:mm")

        if shift:
            self.start_time_input.setTime(QTime.fromString(str(shift["start_time"])[:5], "HH:mm"))
            self.end_time_input.setTime(QTime.fromString(str(shift["end_time"])[:5], "HH:mm"))
            if shift.get("late_cutoff"):
                self.late_cutoff_input.setTime(QTime.fromString(str(shift["late_cutoff"])[:5], "HH:mm"))
        else:
            self.start_time_input.setTime(QTime(9, 0))
            self.end_time_input.setTime(QTime(18, 0))
            self.late_cutoff_input.setTime(QTime(13, 0))

        self.grace_minutes_input = QSpinBox()
        self.grace_minutes_input.setRange(0, 240)
        self.grace_minutes_input.setValue(shift.get("grace_minutes", 15) if shift else 15)

        self.min_half_day_input = QDoubleSpinBox()
        self.min_half_day_input.setRange(0, 24)
        self.min_half_day_input.setValue(shift.get("min_half_day_hours", 4.0) if shift else 4.0)

        self.max_ot_input = QDoubleSpinBox()
        self.max_ot_input.setRange(0, 12)
        self.max_ot_input.setValue(shift.get("max_ot_hours_per_day", 2.0) if shift else 2.0)

        self.requires_ot_approval_input = QCheckBox("Overtime requires approval")
        self.requires_ot_approval_input.setChecked(
            bool(shift.get("requires_ot_approval", 1)) if shift else True
        )

        form.addRow("Shift name", self.name_input)
        form.addRow("Start time", self.start_time_input)
        form.addRow("End time", self.end_time_input)
        form.addRow("Grace minutes", self.grace_minutes_input)
        form.addRow("Late cutoff", self.late_cutoff_input)
        form.addRow("Min half-day hours", self.min_half_day_input)
        form.addRow("Max OT hours/day", self.max_ot_input)
        form.addRow("", self.requires_ot_approval_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        name = self.name_input.text().strip()
        if not name:
            show_error(self, Exception("Shift name is required."))
            return
        payload = dict(
            shift_name=name,
            start_time=self.start_time_input.time().toString("HH:mm:ss"),
            end_time=self.end_time_input.time().toString("HH:mm:ss"),
            grace_minutes=self.grace_minutes_input.value(),
            late_cutoff=self.late_cutoff_input.time().toString("HH:mm:ss"),
            min_half_day_hours=self.min_half_day_input.value(),
            max_ot_hours_per_day=self.max_ot_input.value(),
            requires_ot_approval=self.requires_ot_approval_input.isChecked(),
        )
        try:
            if self.shift:
                org_controller.update_shift(self.shift["shift_id"], **payload)
            else:
                org_controller.create_shift(**payload)
        except APIError as exc:
            show_error(self, exc)
            return
        self.accept()


class ShiftsTab(QWidget):
    def __init__(self, can_edit: bool, can_manage: bool):
        super().__init__()
        self.can_edit = can_edit
        self.can_manage = can_manage
        self._rows = []
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Shifts"))
        header.addStretch()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        if can_manage:
            self.add_button = QPushButton("+ Add")
            self.add_button.clicked.connect(self._add)
            header.addWidget(self.add_button)
        layout.addLayout(header)

        self.table = QTableWidget()
        layout.addWidget(self.table)

        if can_edit or can_manage:
            actions = QHBoxLayout()
            if can_edit:
                self.edit_button = QPushButton("Edit")
                self.edit_button.clicked.connect(self._edit)
                actions.addWidget(self.edit_button)
            if can_manage:
                self.delete_button = QPushButton("Delete")
                self.delete_button.clicked.connect(self._delete)
                actions.addWidget(self.delete_button)
            actions.addStretch()
            layout.addLayout(actions)

    def refresh(self):
        try:
            self._rows = org_controller.list_shifts()
        except APIError as exc:
            show_error(self, exc)
            return
        columns = [
            ("ID", "shift_id"), ("Name", "shift_name"), ("Start", "start_time"),
            ("End", "end_time"), ("Grace (min)", "grace_minutes"),
            ("Late cutoff", "late_cutoff"), ("Min half-day hrs", "min_half_day_hours"),
            ("Max OT hrs/day", "max_ot_hours_per_day"),
        ]
        populate_table(self.table, self._rows, columns)

    def _add(self):
        if ShiftDialog(self).exec_():
            self.refresh()

    def _edit(self):
        row = selected_row_data(self.table, self._rows)
        if not row:
            show_error(self, Exception("Select a shift first."))
            return
        if ShiftDialog(self, row).exec_():
            self.refresh()

    def _delete(self):
        row = selected_row_data(self.table, self._rows)
        if not row:
            show_error(self, Exception("Select a shift first."))
            return
        if not confirm(self, f"Delete shift '{row['shift_name']}'?"):
            return
        try:
            org_controller.delete_shift(row["shift_id"])
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Shift deleted.")
        self.refresh()


# ------------------------------------------------------------------ Container
class OrgView(QWidget):
    """
    Tabbed container: Departments / Positions / Shifts.

      - Admin:            Add, Edit, Delete on all three (can_edit=True,
                           can_manage=True — matches 'manage_departments'/
                           'manage_shifts').
      - HR / Manager:      Edit only (can_edit=True, can_manage=False —
                           matches the new 'edit_org_structure'
                           permission). No Add, no Delete.
      - Anything else that reaches this tab: read-only.
    """

    def __init__(self, role: str):
        super().__init__()
        can_manage = role == "Admin"
        can_edit = role in ("Admin", "HR", "Manager")
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self.departments_tab = DepartmentsTab(can_edit, can_manage)
        self.positions_tab = PositionsTab(can_edit, can_manage)
        self.shifts_tab = ShiftsTab(can_edit, can_manage)
        tabs.addTab(self.departments_tab, "Departments")
        tabs.addTab(self.positions_tab, "Positions")
        tabs.addTab(self.shifts_tab, "Shifts")
        layout.addWidget(tabs)

    def refresh(self):
        self.departments_tab.refresh()
        self.positions_tab.refresh()
        self.shifts_tab.refresh()
