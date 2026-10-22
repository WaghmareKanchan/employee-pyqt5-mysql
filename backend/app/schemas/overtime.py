from datetime import date

from pydantic import BaseModel, field_validator


class OvertimeCreate(BaseModel):
    work_date: date
    hours: float

    @field_validator("hours")
    @classmethod
    def reasonable_hours(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Overtime hours must be greater than 0.")
        if v > 12:
            raise ValueError("Overtime hours cannot exceed 12 in a single request.")
        return v


class OvertimeOut(BaseModel):
    overtime_id: int
    employee_id: int
    work_date: date
    hours: float
    status: str

    class Config:
        from_attributes = True


class OvertimeDecision(BaseModel):
    approve: bool
