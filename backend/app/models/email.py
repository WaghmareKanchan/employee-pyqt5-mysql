"""Email service tables: the queue/delivery-history and per-user preferences."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class EmailQueue(Base):
    """One row per email. The same table is the queue (Pending rows the
    worker picks up) AND the delivery history (Sent / Failed rows shown
    in the Email Log)."""
    __tablename__ = "email_queue"

    email_id = Column(Integer, primary_key=True)
    to_address = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    category = Column(String, nullable=False)    # invitation / password_reset / security / leave_overtime / attendance / reminder
    template = Column(String, nullable=False)    # which template produced it
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)          # plain text
    body_html = Column(Text)                     # optional HTML version
    status = Column(String, nullable=False, default="Pending")  # Pending / Sent / Failed
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String)
    next_attempt_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime)


class EmailPreference(Base):
    """One row per (user, non-essential category). No row = enabled."""
    __tablename__ = "email_preferences"

    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    category = Column(String, primary_key=True)
    enabled = Column(Integer, nullable=False, default=1)
