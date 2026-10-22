from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.controllers import notification_controller
from app.database import get_db
from app.dependencies import get_current_user
from app.models.people import User
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/me", response_model=list[NotificationOut])
def my_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return notification_controller.list_my_notifications(db, current_user.user_id)


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_controller.mark_as_read(db, notification_id, current_user.user_id)
