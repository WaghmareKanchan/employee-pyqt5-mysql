"""Leave requests: apply, approve/reject, balance."""
from controllers.api_client import api_client

# Fixed reference from database/schema.sql seed data. There's no
# GET /api/leave-types endpoint, so this mirrors the API_REFERENCE.md note:
# "1=Sick, 2=Casual, 3=Earned, 4=Unpaid, 5=Maternity/Paternity".
LEAVE_TYPES = [
    {"leave_type_id": 1, "type_name": "Sick Leave"},
    {"leave_type_id": 2, "type_name": "Casual Leave"},
    {"leave_type_id": 3, "type_name": "Earned Leave"},
    {"leave_type_id": 4, "type_name": "Unpaid Leave"},
    {"leave_type_id": 5, "type_name": "Maternity/Paternity Leave"},
]


def leave_type_name(leave_type_id: int) -> str:
    for lt in LEAVE_TYPES:
        if lt["leave_type_id"] == leave_type_id:
            return lt["type_name"]
    return f"Type #{leave_type_id}"


def apply_leave(leave_type_id: int, start_date: str, end_date: str, reason: str | None = None) -> dict:
    payload = {
        "leave_type_id": leave_type_id,
        "start_date": start_date,
        "end_date": end_date,
        "reason": reason,
    }
    return api_client.post("/api/leave-requests", payload)


def decide_leave(leave_request_id: int, approve: bool) -> dict:
    return api_client.put(f"/api/leave-requests/{leave_request_id}/decision", {"approve": approve})


def my_leave_balance() -> list:
    return api_client.get("/api/leave-requests/me/balance") or []


def my_leave_requests() -> list:
    return api_client.get("/api/leave-requests/me") or []


def all_leave_requests(skip: int = 0, limit: int = 200) -> list:
    return api_client.get("/api/leave-requests", params={"skip": skip, "limit": limit}) or []
