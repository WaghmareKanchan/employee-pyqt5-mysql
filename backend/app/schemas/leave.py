from datetime import date

from pydantic import BaseModel, field_validator


class LeaveRequestCreate(BaseModel):
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str | None = None

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("End date cannot be before start date.")
        return v


class LeaveRequestOut(BaseModel):
    leave_request_id: int
    employee_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    status: str

    class Config:
        from_attributes = True


class LeaveDecisionRequest(BaseModel):
    approve: bool


class LeaveBalanceOut(BaseModel):
    leave_type_id: int
    year: int
    allocated_days: float
    used_days: float

    class Config:
        from_attributes = True
