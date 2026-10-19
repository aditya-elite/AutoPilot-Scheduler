"""
SQLAlchemy ORM models — a 1:1 mapping onto schema.sql. Keeping this
file mechanically aligned with the SQL schema means a DBA reading
schema.sql and a backend engineer reading models.py are always
looking at the same shape of data.
"""
import enum
import uuid

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, Numeric,
    SmallInteger, ForeignKey, TIMESTAMP, Enum as SAEnum, JSON, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type when on Postgres, otherwise CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(str(value)))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(str(value))
            else:
                return value


class UserRole(str, enum.Enum):
    admin = "admin"
    factory_manager = "factory_manager"
    machine_operator = "machine_operator"


class MachineStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    maintenance = "maintenance"
    degraded = "degraded"


class JobStatus(str, enum.Enum):
    pending = "pending"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    blocked = "blocked"


class AssignmentStatus(str, enum.Enum):
    planned = "planned"
    confirmed = "confirmed"
    in_progress = "in_progress"
    completed = "completed"
    violated = "violated"
    superseded = "superseded"


class OptimizationGoal(str, enum.Enum):
    minimize_makespan = "minimize_makespan"
    minimize_tardiness = "minimize_tardiness"
    maximize_profit = "maximize_profit"
    balanced = "balanced"


class OptimizationStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class DowntimeReason(str, enum.Enum):
    unplanned_breakdown = "unplanned_breakdown"
    planned_maintenance = "planned_maintenance"
    predicted_failure_risk = "predicted_failure_risk"


class User(Base):
    __tablename__ = "users"
    user_id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(Text, nullable=True)
    full_name = Column(String(128), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    google_id = Column(String(128), unique=True, nullable=True)
    role = Column(SAEnum(UserRole, name="user_role"), nullable=False, default=UserRole.machine_operator)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"
    otp_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(GUID(), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    otp_code = Column(String(6), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User")



class Machine(Base):
    __tablename__ = "machines"
    machine_id = Column(Integer, primary_key=True, autoincrement=True)
    machine_code = Column(String(32), unique=True, nullable=False)
    machine_name = Column(String(128), nullable=False)
    machine_type = Column(String(64), nullable=False)
    status = Column(SAEnum(MachineStatus, name="machine_status"), nullable=False, default=MachineStatus.online)
    cost_per_hour = Column(Numeric(10, 2), nullable=False, default=0)
    failure_risk_score = Column(Numeric(5, 4), nullable=False, default=0)
    age_years = Column(Numeric(4, 1), nullable=False, default=5)
    last_maintained_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    downtimes = relationship("MachineDowntime", back_populates="machine", cascade="all, delete-orphan")
    eligibility = relationship("TaskMachineEligibility", back_populates="machine", cascade="all, delete-orphan")


class MachineDowntime(Base):
    __tablename__ = "machine_downtime"
    downtime_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    machine_id = Column(Integer, ForeignKey("machines.machine_id", ondelete="CASCADE"), nullable=False)
    reason = Column(SAEnum(DowntimeReason, name="downtime_reason"), nullable=False)
    start_time = Column(TIMESTAMP(timezone=True), nullable=False)
    end_time = Column(TIMESTAMP(timezone=True), nullable=False)
    notes = Column(Text)
    created_by = Column(GUID(), ForeignKey("users.user_id"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    machine = relationship("Machine", back_populates="downtimes")


class Job(Base):
    __tablename__ = "jobs"
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    job_code = Column(String(32), unique=True, nullable=False)
    description = Column(Text)
    priority_weight = Column(SmallInteger, nullable=False, default=5)
    profit_value = Column(Numeric(12, 2), nullable=False, default=0)
    due_date = Column(TIMESTAMP(timezone=True), nullable=False)
    material_available_minutes = Column(Integer, nullable=False, default=0)
    status = Column(SAEnum(JobStatus, name="job_status"), nullable=False, default=JobStatus.pending)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    tasks = relationship("Task", back_populates="job", cascade="all, delete-orphan", order_by="Task.sequence_index")


class Task(Base):
    __tablename__ = "tasks"
    task_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False)
    sequence_index = Column(SmallInteger, nullable=False)
    task_name = Column(String(128), nullable=False)
    base_duration_minutes = Column(Integer, nullable=False)
    predicted_duration_minutes = Column(Integer)
    status = Column(SAEnum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.pending)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("job_id", "sequence_index"),)

    job = relationship("Job", back_populates="tasks")
    eligible_machines = relationship("TaskMachineEligibility", back_populates="task", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="task", cascade="all, delete-orphan")


class TaskMachineEligibility(Base):
    __tablename__ = "task_machine_eligibility"
    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), primary_key=True)
    machine_id = Column(Integer, ForeignKey("machines.machine_id", ondelete="CASCADE"), primary_key=True)
    processing_minutes = Column(Integer, nullable=False)

    task = relationship("Task", back_populates="eligible_machines")
    machine = relationship("Machine", back_populates="eligibility")


class Assignment(Base):
    __tablename__ = "assignments"
    assignment_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    machine_id = Column(Integer, ForeignKey("machines.machine_id"), nullable=False)
    scheduled_start = Column(TIMESTAMP(timezone=True), nullable=False)
    scheduled_end = Column(TIMESTAMP(timezone=True), nullable=False)
    actual_start = Column(TIMESTAMP(timezone=True))
    actual_end = Column(TIMESTAMP(timezone=True))
    status = Column(SAEnum(AssignmentStatus, name="assignment_status"), nullable=False, default=AssignmentStatus.planned)
    is_manual_override = Column(Boolean, nullable=False, default=False)
    violates_constraint = Column(Boolean, nullable=False, default=False)
    violation_reason = Column(Text)
    optimization_run_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("optimization_runs.run_id"))
    created_by = Column(GUID(), ForeignKey("users.user_id"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    task = relationship("Task", back_populates="assignments")
    machine = relationship("Machine")


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    run_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    triggered_by = Column(GUID(), ForeignKey("users.user_id"))
    goal = Column(SAEnum(OptimizationGoal, name="optimization_goal"), nullable=False, default=OptimizationGoal.balanced)
    status = Column(SAEnum(OptimizationStatus, name="optimization_status"), nullable=False, default=OptimizationStatus.queued)
    solver_config = Column(JSON, nullable=False, default=dict)
    objective_value = Column(Numeric)
    makespan_minutes = Column(Integer)
    total_tardiness_minutes = Column(Integer)
    started_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    log_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(BigInteger, nullable=False)
    action = Column(String(32), nullable=False)
    old_value = Column(JSON)
    new_value = Column(JSON)
    changed_by = Column(GUID(), ForeignKey("users.user_id"))
    changed_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
