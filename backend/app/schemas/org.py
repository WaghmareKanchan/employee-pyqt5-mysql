from datetime import time

from pydantic import BaseModel, field_validator


class DepartmentCreate(BaseModel):
    department_name: str
    description: str | None = None

    @field_validator("department_name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Department name must be at least 2 characters.")
        return v


class DepartmentOut(BaseModel):
    department_id: int
    department_name: str
    description: str | None

    class Config:
        from_attributes = True


class PositionCreate(BaseModel):
    department_id: int
    title: str
    level: str | None = None

    @field_validator("title")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Position title must be at least 2 characters.")
        return v


class PositionOut(BaseModel):
    position_id: int
    department_id: int
    title: str
    level: str | None

    class Config:
        from_attributes = True


class ShiftCreate(BaseModel):
    shift_name: str
    start_time: time
    end_time: time
    grace_minutes: int = 15
    late_cutoff: time | None = None
    min_half_day_hours: float = 4.0
    max_ot_hours_per_day: float = 2.0
    requires_ot_approval: bool = True

    @field_validator("grace_minutes", "min_half_day_hours", "max_ot_hours_per_day")
    @classmethod
    def not_negative(cls, v):
        if v < 0:
            raise ValueError("This value cannot be negative.")
        return v


class ShiftOut(BaseModel):
    shift_id: int
    shift_name: str
    start_time: time
    end_time: time
    grace_minutes: int
    late_cutoff: time | None
    min_half_day_hours: float
    max_ot_hours_per_day: float
    requires_ot_approval: int

    class Config:
        from_attributes = True
