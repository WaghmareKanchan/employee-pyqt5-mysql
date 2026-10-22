from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers import audit_controller
from app.models.leave import Holiday
from app.schemas.holiday import HolidayCreate


def create_holiday(db: Session, payload: HolidayCreate, acting_user_id: int) -> Holiday:
    holiday = Holiday(holiday_date=payload.holiday_date, name=payload.name)
    db.add(holiday)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A holiday already exists on this date.")
    db.refresh(holiday)
    audit_controller.log_action(db, acting_user_id, "CREATE", "holidays", holiday.holiday_id, holiday.name)
    return holiday


def list_holidays(db: Session, skip: int = 0, limit: int = 50) -> list[Holiday]:
    return db.query(Holiday).order_by(Holiday.holiday_date).offset(skip).limit(limit).all()
