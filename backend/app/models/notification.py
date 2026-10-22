from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"))  # which employee this is ABOUT
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    reference_table = Column(String)
    reference_id = Column(Integer)
    is_read = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
