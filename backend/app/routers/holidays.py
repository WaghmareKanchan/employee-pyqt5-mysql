from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.controllers import holiday_controller
from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.schemas.holiday import HolidayCreate, HolidayOut

router = APIRouter(prefix="/api/holidays", tags=["holidays"])


@router.get("", response_model=list[HolidayOut])
def list_holidays(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return holiday_controller.list_holidays(db, skip, limit)


@router.post("", response_model=HolidayOut, status_code=201)
def create_holiday(
    payload: HolidayCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_holidays")),
):
    return holiday_controller.create_holiday(db, payload, current_user.user_id)
