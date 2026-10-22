"""In-app notifications."""
from controllers.api_client import api_client


def my_notifications() -> list:
    return api_client.get("/api/notifications/me") or []


def mark_as_read(notification_id: int) -> dict:
    return api_client.patch(f"/api/notifications/{notification_id}/read")
