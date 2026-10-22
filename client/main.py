#!/usr/bin/env python3
"""
Meridian Systems — Employee Management System
PyQt5 desktop client entry point.

Run with:
    python main.py
(from inside the client/ directory, with the FastAPI backend already
running at http://127.0.0.1:8000 — see the project README.)
"""
import os
import sys

# Make `controllers` and `views` importable as top-level packages
# regardless of the current working directory this script is launched from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication

from views.login_view import LoginWindow
from views.main_window import MainWindow


class Application:
    """Owns the login <-> main-window lifecycle so logging out returns
    the user cleanly to a fresh login screen instead of exiting."""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self._load_stylesheet()
        self.login_window = None
        self.main_window = None
        self._show_login()

    def _load_stylesheet(self):
        style_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "resources", "styles", "style.qss",
        )
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.app.setStyleSheet(f.read())

    def _show_login(self):
        if self.main_window is not None:
            self.main_window.hide()
            self.main_window.deleteLater()
            self.main_window = None
        self.login_window = LoginWindow(on_login_success=self._show_main_window)
        self.login_window.resize(420, 480)
        self.login_window.show()

    def _show_main_window(self):
        self.login_window.hide()
        self.main_window = MainWindow(on_logout=self._show_login)
        self.main_window.show()

    def run(self):
        return self.app.exec_()


def main():
    application = Application()
    sys.exit(application.run())


if __name__ == "__main__":
    main()
