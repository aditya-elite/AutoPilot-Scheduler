"""
Pydantic schemas — the API's public contract. These are deliberately
separate from the SQLAlchemy models: clients should never see raw DB
rows, only validated, explicit shapes.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- Auth
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    email: Optional[str] = None


class GoogleAuthRequest(BaseModel):
    id_token: str
    role: Optional[str] = None  # factory_manager or machine_operator for new user registration


class GoogleAuthResponse(BaseModel):
    is_new_user: bool = False
    access_token: Optional[str] = None
    token_type: str = "bearer"
    role: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    google_id: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: str


class VerifyOTPRequest(BaseModel):
    email: str
    otp_code: str = Field(min_length=6, max_length=6)


class ResetPasswordRequest(BaseModel):
    email: str
    otp_code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)



# ---------------------------------------------------------------- Machines
class MachineOut(BaseModel):
    machine_id: int
    machine_code: str
    machine_name: str
    machine_type: str
    status: str
    cost_per_hour: float
    failure_risk_score: float

    class Config:
        from_attributes = True


class MachineOfflineRequest(BaseModel):
    reason: str = Field(default="unplanned_breakdown")
    notes: Optional[str] = None
    estimated_downtime_minutes: int = Field(default=240, ge=1)


class ScheduleMaintenanceRequest(BaseModel):
    notes: Optional[str] = None
    duration_hours: float = Field(default=4.0, gt=0)


# ---------------------------------------------------------------- Jobs / Tasks
class TaskMachineEligibilityOut(BaseModel):
    machine_id: int
    processing_minutes: int

    class Config:
        from_attributes = True


class TaskOut(BaseModel):
    task_id: int
    sequence_index: int
    task_name: str
    base_duration_minutes: int
    predicted_duration_minutes: Optional[int]
    status: str
    eligible_machines: List[TaskMachineEligibilityOut] = []

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    job_id: int
    job_code: str
    description: Optional[str]
    priority_weight: int
    profit_value: float
    due_date: datetime
    material_available_minutes: int = 0
    status: str
    tasks: List[TaskOut] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------- Gantt / Assignments
class AssignmentOut(BaseModel):
    assignment_id: int
    task_id: int
    job_id: int
    job_code: str
    task_name: str
    machine_id: int
    machine_code: str
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    is_manual_override: bool
    violates_constraint: bool
    violation_reason: Optional[str]
    eligible_machine_ids: List[int] = []

    class Config:
        from_attributes = True


class ManualOverrideRequest(BaseModel):
    assignment_id: int
    new_machine_id: int
    new_start: datetime


class AssignmentStatusUpdate(BaseModel):
    status: str  # 'in_progress' | 'completed'


# ---------------------------------------------------------------- Optimization
class OptimizeRequest(BaseModel):
    goal: str = Field(default="balanced")  # minimize_makespan | minimize_tardiness | maximize_profit | balanced
    makespan_weight: Optional[float] = None
    tardiness_weight: Optional[float] = None
    max_solve_seconds: Optional[float] = None


class OptimizationRunOut(BaseModel):
    run_id: int
    goal: str
    status: str
    objective_value: Optional[float]
    makespan_minutes: Optional[int]
    total_tardiness_minutes: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: Optional[datetime] = None
    error_message: Optional[str]
    solver_config: Optional[dict] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------- Analytics
class UtilizationOut(BaseModel):
    machine_id: int
    machine_code: str
    utilization_pct: float
    busy_minutes: int
    horizon_minutes: int


class FinancialSummaryOut(BaseModel):
    total_labor_cost: float
    profit_on_time: float
    profit_at_risk: float
    jobs_on_time_count: int
    jobs_at_risk_count: int


class MachineRiskOut(BaseModel):
    machine_id: int
    machine_code: str
    machine_type: str
    status: str
    failure_risk_score: float
    hours_since_last_maintenance: float
    age_years: float
    historical_breakdown_count: int
    risk_level: str  # "low" | "medium" | "high"


class AuditLogOut(BaseModel):
    log_id: int
    entity_type: str
    entity_id: int
    action: str
    changed_at: datetime
    changed_by_name: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------- Admin: users
class UserOut(BaseModel):
    user_id: str
    username: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=128)
    role: str = Field(default="machine_operator")


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------- Machines CRUD
class MachineCreate(BaseModel):
    machine_code: str = Field(min_length=2, max_length=32)
    machine_name: str = Field(min_length=1, max_length=128)
    machine_type: str = Field(min_length=1, max_length=64)
    cost_per_hour: float = Field(default=0.0, ge=0.0)
    status: Optional[str] = "online"


class MachineUpdate(BaseModel):
    machine_code: Optional[str] = Field(default=None, min_length=2, max_length=32)
    machine_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    machine_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    cost_per_hour: Optional[float] = Field(default=None, ge=0.0)
    status: Optional[str] = None


# ---------------------------------------------------------------- Jobs & Tasks CRUD
class TaskEligibilityCreate(BaseModel):
    machine_id: int
    processing_minutes: int


class TaskCreate(BaseModel):
    sequence_index: int = Field(ge=0)
    task_name: str = Field(min_length=1, max_length=128)
    base_duration_minutes: int = Field(ge=1)
    eligible_machines: List[TaskEligibilityCreate] = []


class JobCreate(BaseModel):
    job_code: str = Field(min_length=2, max_length=32)
    description: Optional[str] = None
    priority_weight: int = Field(default=5, ge=1, le=10)
    profit_value: float = Field(default=0.0, ge=0.0)
    due_date: datetime
    material_available_minutes: Optional[int] = Field(default=0, ge=0)
    tasks: Optional[List[TaskCreate]] = []


class JobUpdate(BaseModel):
    job_code: Optional[str] = Field(default=None, min_length=2, max_length=32)
    description: Optional[str] = None
    priority_weight: Optional[int] = Field(default=None, ge=1, le=10)
    profit_value: Optional[float] = Field(default=None, ge=0.0)
    due_date: Optional[datetime] = None
    material_available_minutes: Optional[int] = Field(default=None, ge=0)


class RunLabelUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=128)
