from datetime import date, datetime

from pydantic import BaseModel


class AttendanceOut(BaseModel):
    attendance_id: int
    employee_id: int
    shift_id: int | None
    work_date: date
    check_in: datetime | None
    check_out: datetime | None
    total_hours: float | None
    status: str
    status_reason: str | None
    is_late: int

    class Config:
        from_attributes = True
