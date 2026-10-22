"""Overtime: apply, approve/reject, own/all history."""
from controllers.api_client import api_client


def apply_overtime(work_date: str, hours: float) -> dict:
    return api_client.post("/api/overtime", {"work_date": work_date, "hours": hours})


def decide_overtime(overtime_id: int, approve: bool) -> dict:
    return api_client.put(f"/api/overtime/{overtime_id}/decision", {"approve": approve})


def my_overtime() -> list:
    return api_client.get("/api/overtime/me") or []


def all_overtime(skip: int = 0, limit: int = 200) -> list:
    return api_client.get("/api/overtime", params={"skip": skip, "limit": limit}) or []
