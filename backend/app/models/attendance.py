from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Attendance(Base):
    __tablename__ = "attendance"

    attendance_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    shift_id = Column(Integer, ForeignKey("shifts.shift_id"))
    work_date = Column(Date, nullable=False)
    check_in = Column(DateTime)
    check_out = Column(DateTime)
    total_hours = Column(Numeric)
    status = Column(String, default="Pending")  # Pending / Present / Half Day / Absent
    status_reason = Column(String)
    is_late = Column(Integer, default=0)

    employee = relationship("Employee")
    shift = relationship("Shift")


class Overtime(Base):
    __tablename__ = "overtime"

    overtime_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    attendance_id = Column(Integer, ForeignKey("attendance.attendance_id"))
    work_date = Column(Date, nullable=False)
    hours = Column(Numeric, nullable=False)
    status = Column(String, default="Pending")  # Pending / Approved / Rejected
    approved_by = Column(Integer, ForeignKey("users.user_id"))
    applied_at = Column(DateTime, server_default=func.now())   # DB default CURRENT_TIMESTAMP (column already in schema.sql)
    last_reminded_at = Column(DateTime)

    employee = relationship("Employee")
