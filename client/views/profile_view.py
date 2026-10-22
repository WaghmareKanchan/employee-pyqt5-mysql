from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLabel, QPushButton, QGroupBox, QInputDialog, QLineEdit

from controllers import auth_controller
from controllers.api_client import APIError, api_client
from views.common import show_error, show_info, confirm, attach_module_toolbar
from views.change_password_dialog import ChangePasswordDialog
from views.two_factor_setup_dialog import TwoFactorSetupDialog


class ProfileView(QWidget):
    def __init__(self, on_logout=None):
        super().__init__()
        layout = QVBoxLayout(self)
        attach_module_toolbar(layout, on_logout)

        box = QGroupBox("My Account")
        form = QFormLayout(box)
        self.name_label = QLabel("-")
        self.email_label = QLabel("-")
        self.role_label = QLabel("-")
        form.addRow("Full name:", self.name_label)
        form.addRow("Email:", self.email_label)
        form.addRow("Role:", self.role_label)

        self.change_password_button = QPushButton("Change password")
        self.change_password_button.clicked.connect(self._open_change_password)

        security_box = QGroupBox("Two-Factor Authentication")
        security_layout = QVBoxLayout(security_box)
        self.twofa_status_label = QLabel("-")
        security_layout.addWidget(self.twofa_status_label)
        
        #enable
        self.twofa_button = QPushButton("Enable 2FA")
        self.twofa_button.clicked.connect(self._toggle_2fa)
        security_layout.addWidget(self.twofa_button)
        self._twofa_enabled = False
        
        layout.addWidget(box)
        layout.addWidget(self.change_password_button)
        layout.addWidget(security_box)
        layout.addStretch()

    def refresh(self):
        try:
            profile = auth_controller.me()
        except APIError as exc:
            show_error(self, exc)
            return
        self.name_label.setText(profile.get("full_name") or "-")
        self.email_label.setText(profile.get("email") or "-")
        self.role_label.setText(api_client.role or profile.get("role") or "-")
        self._refresh_2fa_status()

    def _refresh_2fa_status(self):
        try:
            status = auth_controller.get_2fa_status()
        except APIError as exc:
            show_error(self, exc)
            return
        enabled = status.get("enabled", False)
        
        #enable 
        enabled = status.get("enabled", False)
        self._twofa_enabled = bool(enabled)
        self.twofa_button.setText("Disable 2FA" if enabled else "Enable 2FA")
        self.twofa_status_label.setText(
            "Enabled — your account requires a code at login." if enabled
            else "Not enabled — you can enable it using the button below."
        )

    def _open_change_password(self):
        dialog = ChangePasswordDialog(self, title="Change password")
        dialog.exec_()
        
    #enable 
    def _toggle_2fa(self):
        if self._twofa_enabled:
            # DISABLE: confirm, ask for code, call API
            if not confirm(self, "Disable two-factor authentication?"):
                return
            code, ok = QInputDialog.getText(self, "Disable 2FA",
                                            "Enter the 6-digit code from your authenticator app:")
            if not ok or not code.strip():
                return
            try:
                auth_controller.disable_2fa(code.strip())
            except APIError as exc:
                show_error(self, exc)
                return
            show_info(self, "Two-factor authentication has been disabled.")
        else:
            # ENABLE: reuse the existing setup dialog (QR + confirm code)
            TwoFactorSetupDialog(self).exec_()
        self._refresh_2fa_status()
        
    