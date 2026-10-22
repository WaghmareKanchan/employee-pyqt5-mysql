"""Small shared helpers used across most views, to avoid repeating
table-population and error-dialog boilerplate in every tab."""
from PyQt5.QtWidgets import (
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QHBoxLayout, QPushButton,
)
from PyQt5.QtCore import Qt, pyqtSignal

from controllers import attendance_controller
from controllers.api_client import APIError


def show_error(parent, error: Exception, title: str = "Something went wrong") -> None:
    message = error.message if isinstance(error, APIError) else str(error)
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle(title)
    box.setText(message)
    box.exec_()


def show_info(parent, message: str, title: str = "Success") -> None:
    QMessageBox.information(parent, title, message)


def confirm(parent, message: str, title: str = "Please confirm") -> bool:
    result = QMessageBox.question(
        parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    return result == QMessageBox.Yes


def populate_table(table: QTableWidget, rows: list, columns: list) -> None:
    """
    columns: list of (header_label, key_or_callable) tuples.
    `key_or_callable` is either a dict key (str) or a function(row) -> str.
    """
    table.clear()
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels([c[0] for c in columns])
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, (_, accessor) in enumerate(columns):
            if callable(accessor):
                value = accessor(row)
            else:
                value = row.get(accessor, "")
            item = QTableWidgetItem("" if value is None else str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, c, item)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setAlternatingRowColors(True)


def populate_table_with_actions(table: QTableWidget, rows: list, columns: list, actions: list) -> None:
    """
    Same as populate_table, but appends one "Actions" column of buttons
    per row instead of relying on a separate "select a row, then click a
    button below the table" flow.

    `actions`: list of (label, callback) tuples, where callback takes the
    row's dict as its only argument, e.g.:
        [("Edit", lambda row: open_edit_dialog(row)),
         ("Delete", lambda row: delete_row(row))]
    Every row gets every action in this list — to hide an action for some
    rows (e.g. role-gated buttons), build a shorter `actions` list before
    calling this, or add per-row filtering here if that's ever needed.
    """
    table.clear()
    table.setColumnCount(len(columns) + (1 if actions else 0))
    headers = [c[0] for c in columns] + (["Actions"] if actions else [])
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, (_, accessor) in enumerate(columns):
            value = accessor(row) if callable(accessor) else row.get(accessor, "")
            item = QTableWidgetItem("" if value is None else str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, c, item)

        if actions:
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(4, 2, 4, 2)
            cell_layout.setSpacing(6)
            for label, callback in actions:
                button = QPushButton(label)
                # Default-arg trick: binds THIS row, not whatever `row`
                # is by the time the button is actually clicked.
                button.clicked.connect(lambda _checked=False, cb=callback, rw=row: cb(rw))
                cell_layout.addWidget(button)
            cell_layout.addStretch()
            table.setCellWidget(r, len(columns), cell)

    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setAlternatingRowColors(True)


class ModuleToolbar(QWidget):
    """
    Check In / Check Out / Log out bar. Lives ONLY on the My Account tab
    (see profile_view.py) — every other module/tab is check-in/out- and
    logout-free, so these actions live in exactly one place instead of
    being duplicated across every tab.
    """
    logout_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)

        self.checkin_button = QPushButton("Check In")
        self.checkin_button.setObjectName("primaryButton")
        self.checkin_button.clicked.connect(self._check_in)
        layout.addWidget(self.checkin_button)

        self.checkout_button = QPushButton("Check Out")
        self.checkout_button.clicked.connect(self._check_out)
        layout.addWidget(self.checkout_button)

        layout.addStretch()

        self.logout_button = QPushButton("Log out")
        self.logout_button.setObjectName("dangerButton")
        self.logout_button.clicked.connect(self.logout_requested.emit)
        layout.addWidget(self.logout_button)

    def _check_in(self):
        try:
            attendance_controller.check_in()
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Checked in successfully.")

    def _check_out(self):
        try:
            attendance_controller.check_out()
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "Checked out successfully.")


def attach_module_toolbar(layout, on_logout) -> "ModuleToolbar | None":
    """
    Inserts a ModuleToolbar at the top of `layout` (a QVBoxLayout) and
    wires its Log out button to `on_logout`. Call this as the first
    line inside a view's __init__, right after `layout = QVBoxLayout(self)`.

    `on_logout` is optional (defaults to None) so every view keeps
    working standalone (e.g. in isolated tests) even without a real
    MainWindow behind it — in that case no toolbar is added at all.
    """
    if on_logout is None:
        return None
    toolbar = ModuleToolbar()
    toolbar.logout_requested.connect(on_logout)
    layout.addWidget(toolbar)
    return toolbar


def selected_row_data(table: QTableWidget, rows: list) -> dict | None:
    """Returns the underlying dict for the currently selected table row, or None."""
    selected = table.selectionModel().selectedRows()
    if not selected:
        return None
    index = selected[0].row()
    if index < 0 or index >= len(rows):
        return None
    return rows[index]
