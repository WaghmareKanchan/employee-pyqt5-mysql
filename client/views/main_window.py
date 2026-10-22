"""Main application shell shown after login. Tabs are added based on
the logged-in user's role, matching the module-flow docs:
  - Admin:    everything
  - HR:       everything except org structure (departments/positions/shifts)
  - Manager:  approvals + reports + self-service
  - Employee: self-service only
"""
from PyQt5.QtWidgets import QMainWindow, QTabWidget, QAction, QMessageBox

from controllers import auth_controller
from controllers.api_client import api_client
from views.dashboard_view import DashboardView
from views.profile_view import ProfileView
from views.employees_view import EmployeesView
from views.org_view import OrgView
from views.leave_view import LeaveView
from views.attendance_view import AttendanceView
from views.overtime_view import OvertimeView
from views.holidays_view import HolidaysView
from views.notifications_view import NotificationsView
from views.audit_view import AuditView


class MainWindow(QMainWindow):
    def __init__(self, on_logout):
        super().__init__()
        self.on_logout = on_logout
        self.setWindowTitle(f"Meridian Systems — {api_client.role or 'Dashboard'}")
        self.resize(1080, 680)

        self._build_menu()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self._refreshable_views = []
        self._build_tabs()

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.refresh_all()

    def _build_menu(self):
        menu = self.menuBar().addMenu("&Account")
        logout_action = QAction("Log out", self)
        logout_action.triggered.connect(self._logout)
        menu.addAction(logout_action)

    def _add_tab(self, widget, label):
        self.tabs.addTab(widget, label)
        self._refreshable_views.append(widget)

    def _build_tabs(self):
        role = api_client.role

        self.dashboard_view = DashboardView()
        self._add_tab(self.dashboard_view, "Dashboard")

        # Employees: Admin/HR get full management; Manager gets it too,
        # but only to edit their team's department/position/shift/manager
        # (see employees_view.py, gated by the 'edit_employee_assignment'
        # permission on the backend).
        if role in ("Admin", "HR", "Manager"):
            self.employees_view = EmployeesView()
            self._add_tab(self.employees_view, "Employees")

        if role in ("Admin", "HR", "Manager"):
            # OrgView itself decides Edit-only (HR/Manager) vs Add/Edit/
            # Delete (Admin) from the role string — see org_view.py.
            self.org_view = OrgView(role=role)
            self._add_tab(self.org_view, "Organization")

        self.leave_view = LeaveView()
        self._add_tab(self.leave_view, "Leave")

        self.attendance_view = AttendanceView()
        self._add_tab(self.attendance_view, "Attendance")

        self.overtime_view = OvertimeView()
        self._add_tab(self.overtime_view, "Overtime")

        self.holidays_view = HolidaysView()
        self._add_tab(self.holidays_view, "Holidays")

        self.notifications_view = NotificationsView()
        self._add_tab(self.notifications_view, "Notifications")

        # Audit Log is now open to every role — each account only ever
        # sees its OWN actions (never another user's), so there's no
        # reason to restrict the tab itself to Admin/HR any more.
        self.audit_view = AuditView()
        self._add_tab(self.audit_view, "Audit Log")

        # Check In / Check Out / Log out live ONLY here, on the My
        # Account page — not duplicated on every tab.
        self.profile_view = ProfileView(on_logout=self._logout)
        self._add_tab(self.profile_view, "My Account")

    def _on_tab_changed(self, index):
        widget = self.tabs.widget(index)
        if widget is not None and hasattr(widget, "refresh"):
            widget.refresh()

    def refresh_all(self):
        for view in self._refreshable_views:
            if hasattr(view, "refresh"):
                try:
                    view.refresh()
                except Exception:
                    # A single tab failing to load shouldn't take down the
                    # whole window; each view already shows its own error.
                    pass

    def _logout(self):
        confirm = QMessageBox.question(
            self, "Log out", "Are you sure you want to log out?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        auth_controller.logout()
        self.close()
        self.on_logout()
