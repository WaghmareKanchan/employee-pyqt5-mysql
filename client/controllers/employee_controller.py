"""Employee management calls.

- list_employees / update_employee (dept/position/employment type/shift/
  manager only): Admin, HR, and Manager.
- create_employee / change_role: Admin and HR (HR is limited server-side
  to granting/holding Manager or Employee — see employees_view.py and
  backend/app/controllers/employee_controller.py).
- suspend_employee / reactivate_employee / get_employee_history: Admin
  and HR only.
"""
from controllers.api_client import api_client

# Mirrors backend/app/schemas/employee.py VALID_ROLE_NAMES.
ALL_ROLES = ["Employee", "Manager", "HR", "Admin"]


def list_employees(skip: int = 0, limit: int = 200) -> list:
    return api_client.get("/api/employees", params={"skip": skip, "limit": limit}) or []


def create_employee(full_name: str,  personal_email: str, department_id: int, position_id: int, employment_type_id: int,
                     shift_id: int, date_joined: str, manager_id: int | None = None,
                     role_name: str = "Employee") -> dict:
    payload = {
        "full_name": full_name,
        "personal_email": personal_email,
        "department_id": department_id,
        "position_id": position_id,
        "employment_type_id": employment_type_id,
        "shift_id": shift_id,
        "manager_id": manager_id,
        "date_joined": date_joined,
        "role_name": role_name,
    }
    return api_client.post("/api/employees", payload)

def resend_invitation(employee_id: int) -> dict:
    """Admin/HR: new setup link for someone who has not set a password yet."""
    return api_client.post(f"/api/employees/{employee_id}/resend-invitation")

def change_personal_email(employee_id: int, personal_email: str) -> dict:
    """Admin/HR only."""
    return api_client.patch(f"/api/employees/{employee_id}/personal-email", {"personal_email": personal_email})


def change_role(employee_id: int, role_name: str) -> dict:
    return api_client.patch(f"/api/employees/{employee_id}/role", {"role_name": role_name})


def update_employee(employee_id: int, **fields) -> dict:
    """Only non-None fields are sent, matching the backend's partial-update contract."""
    payload = {k: v for k, v in fields.items() if v is not None}
    return api_client.patch(f"/api/employees/{employee_id}", payload)


def suspend_employee(employee_id: int) -> dict:
    return api_client.patch(f"/api/employees/{employee_id}/suspend")


def reactivate_employee(employee_id: int) -> dict:
    return api_client.patch(f"/api/employees/{employee_id}/reactivate")


def get_employee_history(employee_id: int) -> list:
    return api_client.get(f"/api/employees/{employee_id}/history") or []


def delete_employee(employee_id: int) -> dict:
    """Admin/HR only (backend permission 'manage_employees') — hard-deletes
    the employee and cascades to their user account, attendance, leave,
    overtime, and history rows."""
    return api_client.delete(f"/api/employees/{employee_id}")
