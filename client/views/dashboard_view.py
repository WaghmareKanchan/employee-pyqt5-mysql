from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QFrame

from controllers import notification_controller
from controllers.api_client import APIError, api_client


class StatCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        self.value_label = QLabel("—")
        self.value_label.setObjectName("statValue")
        title_label = QLabel(title)
        title_label.setObjectName("statTitle")
        layout.addWidget(self.value_label)
        layout.addWidget(title_label)

    def set_value(self, value):
        self.value_label.setText(str(value))


class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        # Check In / Check Out and Log out live only on the My Account
        # tab now (see profile_view.py) — Dashboard is read-only stats.

        self.welcome_label = QLabel("Welcome")
        self.welcome_label.setObjectName("pageTitle")
        layout.addWidget(self.welcome_label)

        stats_grid = QGridLayout()
        self.notifications_card = StatCard("Unread notifications")
        self.role_card = StatCard("Your role")
        stats_grid.addWidget(self.notifications_card, 0, 0)
        stats_grid.addWidget(self.role_card, 0, 1)
        layout.addLayout(stats_grid)

        layout.addStretch()

    def refresh(self):
        name = api_client.full_name or "there"
        self.welcome_label.setText(f"Welcome, {name}")
        self.role_card.set_value(api_client.role or "-")

        try:
            notifications = notification_controller.my_notifications()
            unread = sum(1 for n in notifications if not n.get("is_read"))
            self.notifications_card.set_value(unread)
        except APIError:
            self.notifications_card.set_value("-")
