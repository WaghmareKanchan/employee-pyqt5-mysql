"""Set/change password dialog. Used both for the mandatory first-login
reset and for a logged-in user voluntarily changing their password."""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QDialogButtonBox,
)

from controllers import auth_controller
from controllers.api_client import APIError
from views.common import show_error, show_info


class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None, title="Change password", message="", mandatory=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        self.mandatory = mandatory
        if mandatory:
            self.setModal(True)

        layout = QVBoxLayout(self)

        if message:
            info = QLabel(message)
            info.setWordWrap(True)
            layout.addWidget(info)

        hint = QLabel("Password must be 8+ characters with at least one uppercase\n"
                      "letter, one number, and one special character.")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        form.addRow("New password", self.new_password_input)
        form.addRow("Confirm password", self.confirm_password_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        new_password = self.new_password_input.text()
        confirm_password = self.confirm_password_input.text()

        if new_password != confirm_password:
            show_error(self, Exception("Passwords do not match."))
            return

        try:
            auth_controller.set_password(new_password, confirm_password)
        except APIError as exc:
            show_error(self, exc)
            return

        show_info(self, "Password updated successfully.")
        self.accept()
