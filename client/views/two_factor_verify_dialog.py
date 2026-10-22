"""
Second step of login for a 2FA-enabled account. Shown right after a
correct email/password, in place of going straight to the dashboard.
Takes the live 6-digit code from the user's authenticator app.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QDialogButtonBox,
)

from controllers import auth_controller
from controllers.api_client import APIError
from views.common import show_error


class TwoFactorVerifyDialog(QDialog):
    """exec_() returns QDialog.Accepted only once verify_2fa() has
    actually succeeded — the caller can then treat the session as
    fully logged in, same as a plain password-only login."""

    def __init__(self, parent, partial_token: str, email: str):
        super().__init__(parent)
        self.partial_token = partial_token
        self.email = email
        self.setWindowTitle("Two-Factor Authentication")
        self.setMinimumWidth(360)
        self.setModal(True)

        layout = QVBoxLayout(self)

        info = QLabel("Enter the 6-digit code from your authenticator app.")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("123456")
        self.code_input.setMaxLength(6)
        self.code_input.returnPressed.connect(self._submit)
        layout.addWidget(self.code_input)

        self.status_label = QLabel("")
        self.status_label.setObjectName("errorLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Verify")
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.code_input.setFocus()

    def _submit(self):
        code = self.code_input.text().strip()
        if not code:
            self.status_label.setText("Enter a code.")
            return
        try:
            auth_controller.verify_2fa(self.partial_token, code, self.email)
        except APIError as exc:
            self.status_label.setText(exc.message)
            return
        self.accept()
