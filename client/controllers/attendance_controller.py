"""Attendance: check-in/out, own history, all-employees view."""
from controllers.api_client import api_client


def check_in() -> dict:
    return api_client.post("/api/attendance/check-in")


def check_out() -> dict:
    return api_client.post("/api/attendance/check-out")


def my_attendance() -> list:
    return api_client.get("/api/attendance/me") or []


def all_attendance(skip: int = 0, limit: int = 200) -> list:
    return api_client.get("/api/attendance", params={"skip": skip, "limit": limit}) or []
