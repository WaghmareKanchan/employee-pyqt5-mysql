"""Company holidays."""
from controllers.api_client import api_client


def list_holidays(skip: int = 0, limit: int = 200) -> list:
    return api_client.get("/api/holidays", params={"skip": skip, "limit": limit}) or []


def create_holiday(holiday_date: str, name: str) -> dict:
    return api_client.post("/api/holidays", {"holiday_date": holiday_date, "name": name})
