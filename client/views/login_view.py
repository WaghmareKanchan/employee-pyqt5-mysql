"""Login screen — the first thing the user sees. Matches the module
flow doc: sign in, handle wrong password / lockout, then either force
a password reset (first login) or go straight to the dashboard."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy,
)

from controllers import auth_controller
from controllers.api_client import APIError, api_client
from views.common import show_error
from views.change_password_dialog import ChangePasswordDialog
from views.forgot_password_dialog import ForgotPasswordDialog
from views.two_factor_verify_dialog import TwoFactorVerifyDialog
from views.two_factor_setup_dialog import TwoFactorSetupDialog, TwoFactorPromptDialog


class LoginWindow(QWidget):
    """Emits `login_succeeded` (via callback set by main.py) once the
    user is fully authenticated and any forced password reset is done."""

    def __init__(self, on_login_success):
        super().__init__()
        self.on_login_success = on_login_success
        self.setWindowTitle("Meridian Systems — Sign In")
        self.setMinimumSize(420, 480)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(360)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)

        title = QLabel("Meridian Systems")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Employee Management System")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        form = QFormLayout()
        form.setSpacing(10)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("you@meridian.com")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self._attempt_login)
        form.addRow("Email", self.email_input)
        form.addRow("Password", self.password_input)

        self.status_label = QLabel("")
        self.status_label.setObjectName("errorLabel")
        self.status_label.setWordWrap(True)

        self.login_button = QPushButton("Sign In")
        self.login_button.setObjectName("primaryButton")
        self.login_button.clicked.connect(self._attempt_login)

        forgot_row = QHBoxLayout()
        forgot_row.addStretch()
        self.forgot_button = QPushButton("Forgot password?")
        self.forgot_button.setObjectName("linkButton")
        self.forgot_button.setCursor(Qt.PointingHandCursor)
        self.forgot_button.clicked.connect(self._open_forgot_password)
        forgot_row.addWidget(self.forgot_button)

        server_row = QHBoxLayout()
        server_label = QLabel("Server:")
        self.server_input = QLineEdit(api_client.base_url)
        self.server_input.setPlaceholderText("http://127.0.0.1:8000")
        server_row.addWidget(server_label)
        server_row.addWidget(self.server_input)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(10)
        card_layout.addLayout(form)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.login_button)
        card_layout.addLayout(forgot_row)
        card_layout.addSpacing(10)
        card_layout.addLayout(server_row)

        outer.addWidget(card)
        self.email_input.setFocus()

    def _attempt_login(self):
        email = self.email_input.text().strip()
        password = self.password_input.text()
        self.status_label.setText("")

        if not email or not password:
            self.status_label.setText("Please enter both email and password.")
            return

        api_client.set_base_url(self.server_input.text().strip() or api_client.base_url)

        self.login_button.setEnabled(False)
        self.login_button.setText("Signing in...")
        try:
            result = auth_controller.login(email, password)
        except APIError as exc:
            self.status_label.setText(exc.message)
            return
        finally:
            self.login_button.setEnabled(True)
            self.login_button.setText("Sign In")

        if result.get("requires_2fa"):
            # Password was correct, but the account has 2FA enabled —
            # api_client.token is NOT set yet at this point (see
            # auth_controller.login), so nothing beyond this dialog can
            # proceed until a valid code is verified.
            dialog = TwoFactorVerifyDialog(self, result["partial_token"], email)
            if dialog.exec_():
                self._after_full_login()
            else:
                self.status_label.setText("Two-factor verification was cancelled.")
            return

        self._after_full_login()

    def _after_full_login(self):
        if api_client.must_reset_password:
            self._force_password_reset()
        else:
            self._finish_login()

    def _force_password_reset(self):
        dialog = ChangePasswordDialog(
            self,
            title="Set a new password",
            message="This is your first login. Please set a new password to continue.",
            mandatory=True,
        )
        if dialog.exec_():
            self._finish_login()
        else:
            # User closed the mandatory dialog without setting a password —
            # they cannot proceed, so log them out client-side.
            auth_controller.logout()
            self.status_label.setText("You must set a new password to continue.")

    def _offer_2fa_enrollment(self):
        """Shown at login (not from Profile) to anyone who hasn't turned
        2FA on yet. Once enabled it is permanent — there is no disable."""
        if api_client.two_fa_enabled:
            return
        if TwoFactorPromptDialog(self).exec_():
            TwoFactorSetupDialog(self).exec_()

    def _finish_login(self):
        self._offer_2fa_enrollment()
        try:
            auth_controller.me()
        except APIError as exc:
            show_error(self, exc)
            return
        self.password_input.clear()
        self.on_login_success()

    def _open_forgot_password(self):
        api_client.set_base_url(self.server_input.text().strip() or api_client.base_url)
        dialog = ForgotPasswordDialog(self)
        dialog.exec_()

    def reset_form(self):
        self.password_input.clear()
        self.status_label.setText("")
