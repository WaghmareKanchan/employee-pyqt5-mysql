"""
Organization structure models: roles, permissions, departments,
positions, employment types, shifts.

These map directly to the tables in database/schema.sql — column
names must stay in sync with that file.
"""
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Table, Time
from sqlalchemy.orm import relationship

from app.database import Base

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.role_id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.permission_id"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True)
    role_name = Column(String, unique=True, nullable=False)
    description = Column(String)

    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")


class Permission(Base):
    __tablename__ = "permissions"

    permission_id = Column(Integer, primary_key=True)
    permission_name = Column(String, unique=True, nullable=False)
    description = Column(String)

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class Department(Base):
    __tablename__ = "departments"

    department_id = Column(Integer, primary_key=True)
    department_name = Column(String, unique=True, nullable=False)
    description = Column(String)

    # passive_deletes=True: same reasoning as Employee.user_account in
    # people.py — let the DB's ON DELETE CASCADE (positions.department_id,
    # schema.sql) do the deleting instead of SQLAlchemy trying to NULL out
    # position.department_id first (which fails: that column is NOT NULL).
    positions = relationship("Position", back_populates="department", passive_deletes=True)


class Position(Base):
    __tablename__ = "positions"

    position_id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey("departments.department_id"), nullable=False)
    title = Column(String, nullable=False)
    level = Column(String)

    department = relationship("Department", back_populates="positions")


class EmploymentType(Base):
    __tablename__ = "employment_types"

    employment_type_id = Column(Integer, primary_key=True)
    type_name = Column(String, unique=True, nullable=False)


class Shift(Base):
    __tablename__ = "shifts"

    shift_id = Column(Integer, primary_key=True)
    shift_name = Column(String, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    grace_minutes = Column(Integer, default=15)
    late_cutoff = Column(Time)
    min_half_day_hours = Column(Numeric, default=4.0)
    max_ot_hours_per_day = Column(Numeric, default=2.0)
    requires_ot_approval = Column(Integer, default=1)
