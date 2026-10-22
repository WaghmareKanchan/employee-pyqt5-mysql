"""
FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import config
from app.routers import (
    attendance, audit, auth, email, employees, holidays, leave, notifications, org, overtime, setup_page,
)
from app.services.email_worker import EmailWorker

email_worker = EmailWorker()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Starts the background email sender with the app and stops it on shutdown."""
    if config.EMAIL_WORKER_ENABLED:
        email_worker.start()
    yield
    email_worker.stop()


app = FastAPI(
    title="Meridian Systems — Employee Management API",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the PyQt5 desktop client (running locally) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(leave.router)
app.include_router(org.router)
app.include_router(attendance.router)
app.include_router(overtime.router)
app.include_router(holidays.router)
app.include_router(notifications.router)
app.include_router(audit.router)
app.include_router(email.router)
app.include_router(setup_page.router)


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "Meridian Systems API"}
