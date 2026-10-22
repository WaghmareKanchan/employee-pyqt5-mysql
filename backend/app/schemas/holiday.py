from datetime import date

from pydantic import BaseModel, field_validator


class HolidayCreate(BaseModel):
    holiday_date: date
    name: str

    @field_validator("name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Holiday name must be at least 2 characters.")
        return v


class HolidayOut(BaseModel):
    holiday_id: int
    holiday_date: date
    name: str

    class Config:
        from_attributes = True
