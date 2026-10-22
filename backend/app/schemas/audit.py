from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    log_id: int
    user_id: int | None
    username: str | None = None
    role_name: str | None = None
    action: str
    table_name: str
    record_id: int | None
    details: str | None
    timestamp: datetime

    class Config:
        from_attributes = True
