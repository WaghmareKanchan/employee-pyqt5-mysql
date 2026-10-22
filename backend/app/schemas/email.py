from datetime import datetime

from pydantic import BaseModel, field_validator

from app.services.email_service import PREFERENCE_CATEGORIES


class EmailLogOut(BaseModel):
    """Deliberately has NO body field: bodies can contain setup links/codes."""
    email_id: int
    to_address: str
    category: str
    template: str
    subject: str
    status: str
    attempts: int
    last_error: str | None
    next_attempt_at: datetime | None
    created_at: datetime
    sent_at: datetime | None

    class Config:
        from_attributes = True


class EmailPreferenceItem(BaseModel):
    category: str
    label: str
    enabled: bool


class EmailPreferencesUpdate(BaseModel):
    # e.g. {"leave_overtime": false, "attendance": true}
    preferences: dict[str, bool]

    @field_validator("preferences")
    @classmethod
    def known_categories(cls, v: dict[str, bool]) -> dict[str, bool]:
        unknown = set(v) - set(PREFERENCE_CATEGORIES)
        if unknown:
            raise ValueError(f"Unknown categories: {sorted(unknown)}. Allowed: {sorted(PREFERENCE_CATEGORIES)}")
        return v
