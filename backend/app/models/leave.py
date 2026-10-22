from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class LeaveType(Base):
    __tablename__ = "leave_types"

    leave_type_id = Column(Integer, primary_key=True)
    type_name = Column(String, unique=True, nullable=False)
    max_days_per_year = Column(Integer)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    leave_request_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.leave_type_id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String)
    status = Column(String, default="Pending")  # Pending / Approved / Rejected
    approved_by = Column(Integer, ForeignKey("users.user_id"))
    applied_at = Column(DateTime, server_default=func.now())   # DB default CURRENT_TIMESTAMP (column already in schema.sql)
    decided_at = Column(DateTime)
    last_reminded_at = Column(DateTime)

    employee = relationship("Employee")
    leave_type = relationship("LeaveType")


class LeaveBalance(Base):
    __tablename__ = "leave_balance"

    leave_balance_id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.leave_type_id"), nullable=False)
    year = Column(Integer, nullable=False)
    allocated_days = Column(Numeric, nullable=False)
    used_days = Column(Numeric, default=0)

    leave_type = relationship("LeaveType")


class Holiday(Base):
    __tablename__ = "holidays"

    holiday_id = Column(Integer, primary_key=True)
    holiday_date = Column(Date, unique=True, nullable=False)
    name = Column(String, nullable=False)
