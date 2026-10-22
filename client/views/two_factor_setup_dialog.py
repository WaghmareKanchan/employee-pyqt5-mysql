"""
Enable 2FA (TOTP) for the logged-in user's own account. Opened from the
prompt shown at login (see login_view._offer_2fa_enrollment).

Scan the QR code with an authenticator app, then enter the 6-digit code
it shows to prove the enrollment worked. That's it — no secret text and
no recovery codes are shown.
"""
import base64

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDialogButtonBox,
)

from controllers import auth_controller
from controllers.api_client import APIError
from views.common import show_error, show_info


class TwoFactorSetupDialog(QDialog):
    """exec_() returns QDialog.Accepted only once the user has confirmed
    a working code, i.e. only once 2FA is actually turned on."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Set Up Two-Factor Authentication")
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)

        instructions = QLabel(
            "1. Scan this QR code with your authenticator app (Google Authenticator, "
            "Microsoft Authenticator, Authy, etc.)\n"
            "2. Then type the 6-digit code it shows to confirm."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setMinimumHeight(200)
        layout.addWidget(self.qr_label)

        code_row = QHBoxLayout()
        code_row.addWidget(QLabel("Code:"))
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("123456")
        self.code_input.setMaxLength(6)
        self.code_input.returnPressed.connect(self._confirm_code)
        code_row.addWidget(self.code_input)
        layout.addLayout(code_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("errorLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Confirm")
        buttons.accepted.connect(self._confirm_code)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.code_input.setFocus()
        self._load_setup()

    def _load_setup(self):
        try:
            data = auth_controller.start_2fa_setup()
        except APIError as exc:
            show_error(self, exc)
            self.reject()
            return
        pixmap = QPixmap()
        pixmap.loadFromData(base64.b64decode(data["qr_code_base64"]))
        self.qr_label.setPixmap(pixmap.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _confirm_code(self):
        code = self.code_input.text().strip()
        if len(code) != 6 or not code.isdigit():
            self.status_label.setText("Enter the 6-digit code from your app.")
            return
        try:
            auth_controller.confirm_2fa_setup(code)
        except APIError as exc:
            self.status_label.setText(exc.message)
            return
        show_info(self, "Two-factor authentication is now enabled on your account.")
        self.accept()


class TwoFactorPromptDialog(QDialog):
    """The 'enable 2FA' ask shown at login. exec_() is Accepted when the
    user clicks Enable, Rejected when they choose to skip for now."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Secure your account")
        self.setMinimumWidth(380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        title = QLabel("Enable two-factor authentication?")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        info = QLabel(
            "Add a second step to your sign-in using an authenticator app. "
            "Once enabled it stays on and a code will be required every time you sign in."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        skip = QPushButton("Not now")
        skip.clicked.connect(self.reject)
        enable = QPushButton("Enable 2FA")
        enable.setObjectName("primaryButton")
        enable.setDefault(True)
        enable.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(skip)
        row.addWidget(enable)
        layout.addLayout(row)
