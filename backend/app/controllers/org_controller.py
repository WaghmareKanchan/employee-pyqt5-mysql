from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.controllers import audit_controller
from app.models.org import Department, Position, Shift
from app.schemas.org import DepartmentCreate, PositionCreate, ShiftCreate


def create_department(db: Session, payload: DepartmentCreate, acting_user_id: int) -> Department:
    department = Department(department_name=payload.department_name, description=payload.description)
    db.add(department)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A department with this name already exists.")
    db.refresh(department)
    audit_controller.log_action(db, acting_user_id, "CREATE", "departments", department.department_id, department.department_name)
    return department


def list_departments(db: Session, skip: int = 0, limit: int = 50) -> list[Department]:
    return db.query(Department).offset(skip).limit(limit).all()


def update_department(db: Session, department_id: int, payload: DepartmentCreate, acting_user_id: int) -> Department:
    department = db.query(Department).filter(Department.department_id == department_id).first()
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found.")
    department.department_name = payload.department_name
    department.description = payload.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A department with this name already exists.")
    db.refresh(department)
    audit_controller.log_action(db, acting_user_id, "UPDATE", "departments", department_id)
    return department


def delete_department(db: Session, department_id: int, acting_user_id: int) -> None:
    department = db.query(Department).filter(Department.department_id == department_id).first()
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found.")
    try:
        db.delete(department)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete: employees or positions are still assigned to this department.",
        )
    audit_controller.log_action(db, acting_user_id, "DELETE", "departments", department_id)


def create_position(db: Session, payload: PositionCreate, acting_user_id: int) -> Position:
    department = db.query(Department).filter(Department.department_id == payload.department_id).first()
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found.")

    position = Position(department_id=payload.department_id, title=payload.title, level=payload.level)
    db.add(position)
    db.commit()
    db.refresh(position)
    audit_controller.log_action(db, acting_user_id, "CREATE", "positions", position.position_id, position.title)
    return position


def list_positions(db: Session, skip: int = 0, limit: int = 50) -> list[Position]:
    return db.query(Position).offset(skip).limit(limit).all()


def update_position(db: Session, position_id: int, payload: PositionCreate, acting_user_id: int) -> Position:
    position = db.query(Position).filter(Position.position_id == position_id).first()
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found.")
    department = db.query(Department).filter(Department.department_id == payload.department_id).first()
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found.")

    position.department_id = payload.department_id
    position.title = payload.title
    position.level = payload.level
    db.commit()
    db.refresh(position)
    audit_controller.log_action(db, acting_user_id, "UPDATE", "positions", position_id)
    return position


def delete_position(db: Session, position_id: int, acting_user_id: int) -> None:
    position = db.query(Position).filter(Position.position_id == position_id).first()
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found.")
    try:
        db.delete(position)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cannot delete: employees are still assigned to this position.")
    audit_controller.log_action(db, acting_user_id, "DELETE", "positions", position_id)


def create_shift(db: Session, payload: ShiftCreate, acting_user_id: int) -> Shift:
    shift = Shift(
        shift_name=payload.shift_name,
        start_time=payload.start_time,
        end_time=payload.end_time,
        grace_minutes=payload.grace_minutes,
        late_cutoff=payload.late_cutoff,
        min_half_day_hours=payload.min_half_day_hours,
        max_ot_hours_per_day=payload.max_ot_hours_per_day,
        requires_ot_approval=1 if payload.requires_ot_approval else 0,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    audit_controller.log_action(db, acting_user_id, "CREATE", "shifts", shift.shift_id, shift.shift_name)
    return shift


def list_shifts(db: Session, skip: int = 0, limit: int = 50) -> list[Shift]:
    return db.query(Shift).offset(skip).limit(limit).all()


def update_shift(db: Session, shift_id: int, payload: ShiftCreate, acting_user_id: int) -> Shift:
    shift = db.query(Shift).filter(Shift.shift_id == shift_id).first()
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found.")

    shift.shift_name = payload.shift_name
    shift.start_time = payload.start_time
    shift.end_time = payload.end_time
    shift.grace_minutes = payload.grace_minutes
    shift.late_cutoff = payload.late_cutoff
    shift.min_half_day_hours = payload.min_half_day_hours
    shift.max_ot_hours_per_day = payload.max_ot_hours_per_day
    shift.requires_ot_approval = 1 if payload.requires_ot_approval else 0
    db.commit()
    db.refresh(shift)
    audit_controller.log_action(db, acting_user_id, "UPDATE", "shifts", shift_id)
    return shift


def delete_shift(db: Session, shift_id: int, acting_user_id: int) -> None:
    shift = db.query(Shift).filter(Shift.shift_id == shift_id).first()
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found.")
    try:
        db.delete(shift)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete: employees or attendance records still reference this shift.",
        )
    audit_controller.log_action(db, acting_user_id, "DELETE", "shifts", shift_id)
