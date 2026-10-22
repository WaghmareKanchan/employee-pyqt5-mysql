"""Forgot-password flow for logged-out users: request an OTP, then
enter the OTP + new password to reset. The OTP itself is emailed if
SMTP is configured on the backend, otherwise it is printed to the
backend's console (see README) — this dialog just collects it."""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton,
    QDialogButtonBox, QStackedWidget, QWidget,
)

from controllers import auth_controller
from controllers.api_client import APIError
from views.common import show_error, show_info


class ForgotPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Forgot password")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.stack.addWidget(self._build_request_page())
        self.stack.addWidget(self._build_reset_page())

    # ---- Page 1: request OTP ------------------------------------------
    def _build_request_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel("Enter your account email. If it exists, a one-time code\n"
                      "will be sent (or printed to the server console in dev mode).")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.email_input = QLineEdit()
        form.addRow("Email", self.email_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        send_button = QPushButton("Send code")
        send_button.setObjectName("primaryButton")
        send_button.clicked.connect(self._request_otp)
        buttons.addButton(send_button, QDialogButtonBox.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        return page

    def _request_otp(self):
        email = self.email_input.text().strip()
        if not email:
            show_error(self, Exception("Please enter your email."))
            return
        try:
            auth_controller.forgot_password(email)
        except APIError as exc:
            show_error(self, exc)
            return
        show_info(self, "If that email exists, an OTP has been sent (valid 10 minutes).")
        self.stack.setCurrentIndex(1)

    # ---- Page 2: enter OTP + new password ------------------------------
    def _build_reset_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form = QFormLayout()
        self.otp_input = QLineEdit()
        self.otp_input.setPlaceholderText("6-digit code")
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        form.addRow("OTP code", self.otp_input)
        form.addRow("New password", self.new_password_input)
        form.addRow("Confirm password", self.confirm_password_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        reset_button = QPushButton("Reset password")
        reset_button.setObjectName("primaryButton")
        reset_button.clicked.connect(self._reset_password)
        buttons.addButton(reset_button, QDialogButtonBox.AcceptRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        return page

    def _reset_password(self):
        email = self.email_input.text().strip()
        otp = self.otp_input.text().strip()
        new_password = self.new_password_input.text()
        confirm_password = self.confirm_password_input.text()

        if new_password != confirm_password:
            show_error(self, Exception("Passwords do not match."))
            return

        try:
            auth_controller.reset_password_with_otp(email, otp, new_password, confirm_password)
        except APIError as exc:
            show_error(self, exc)
            return

        show_info(self, "Password reset successfully. You can now log in.")
        self.accept()
