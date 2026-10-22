"""Departments / Positions / Shifts (master data) calls."""
from controllers.api_client import api_client

# ---- Employment types --------------------------------------------------
# NOTE: the backend does not currently expose a GET /api/employment-types
# endpoint (there is no employment_types router), even though
# EmployeeCreateRequest requires an employment_type_id. We fall back to
# the fixed seed data inserted by database/schema.sql so the employee
# creation form still has something to select from. If the backend adds
# a real endpoint later, replace this with an api_client.get() call.
EMPLOYMENT_TYPES_FALLBACK = [
    {"employment_type_id": 1, "type_name": "Full-time"},
    {"employment_type_id": 2, "type_name": "Part-time"},
    {"employment_type_id": 3, "type_name": "Contract"},
    {"employment_type_id": 4, "type_name": "Intern"},
    {"employment_type_id": 5, "type_name": "Probation"},
]


def list_employment_types() -> list:
    return list(EMPLOYMENT_TYPES_FALLBACK)


# ---- Departments --------------------------------------------------------
def list_departments(skip: int = 0, limit: int = 200) -> list:
    return api_client.get("/api/departments", params={"skip": skip, "limit": limit}) or []


def create_department(department_name: str, description: str | None = None) -> dict:
    return api_client.post("/api/departments", {"department_name": department_name, "description": description})


def update_department(department_id: int, department_name: str, description: str | None = None) -> dict:
    return api_client.patch(
        f"/api/departments/{department_id}",
        {"department_name": department_name, "description": description},
    )


def delete_department(department_id: int) -> dict:
    return api_client.delete(f"/api/departments/{department_id}")


# ---- Positions ------------------------------------------------------------
def list_positions(skip: int = 0, limit: int = 200) -> list:
    return api_client.get("/api/positions", params={"skip": skip, "limit": limit}) or []


def create_position(department_id: int, title: str, level: str | None = None) -> dict:
    return api_client.post("/api/positions", {"department_id": department_id, "title": title, "level": level})


def update_position(position_id: int, department_id: int, title: str, level: str | None = None) -> dict:
    return api_client.patch(
        f"/api/positions/{position_id}",
        {"department_id": department_id, "title": title, "level": level},
    )


def delete_position(position_id: int) -> dict:
    return api_client.delete(f"/api/positions/{position_id}")


# ---- Shifts ------------------------------------------------------------
def list_shifts(skip: int = 0, limit: int = 200) -> list:
    return api_client.get("/api/shifts", params={"skip": skip, "limit": limit}) or []


def create_shift(shift_name: str, start_time: str, end_time: str, grace_minutes: int = 15,
                  late_cutoff: str | None = None, min_half_day_hours: float = 4.0,
                  max_ot_hours_per_day: float = 2.0, requires_ot_approval: bool = True) -> dict:
    payload = {
        "shift_name": shift_name,
        "start_time": start_time,
        "end_time": end_time,
        "grace_minutes": grace_minutes,
        "late_cutoff": late_cutoff,
        "min_half_day_hours": min_half_day_hours,
        "max_ot_hours_per_day": max_ot_hours_per_day,
        "requires_ot_approval": requires_ot_approval,
    }
    return api_client.post("/api/shifts", payload)


def update_shift(shift_id: int, **fields) -> dict:
    return api_client.patch(f"/api/shifts/{shift_id}", fields)


def delete_shift(shift_id: int) -> dict:
    return api_client.delete(f"/api/shifts/{shift_id}")
