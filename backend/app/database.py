"""
SQLAlchemy engine + session setup (MySQL).

Coding standard: routers/controllers always go through get_db() so the
connection is managed in one place (opened per-request, always closed).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core import config

# pool_pre_ping: transparently replaces connections MySQL has closed
# after its idle timeout. pool_recycle: refresh before that timeout.
engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session, always closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
