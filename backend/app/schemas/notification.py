from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    notification_id: int
    employee_id: int | None
    title: str
    message: str
    reference_table: str | None
    reference_id: int | None
    is_read: int
    created_at: datetime

    class Config:
        from_attributes = True
