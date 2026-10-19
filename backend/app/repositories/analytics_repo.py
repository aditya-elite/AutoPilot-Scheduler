"""
Shared analytics computations used by both the /analytics router and
the ML feature builder, so "utilization %" has exactly one definition
instead of drifting between two call sites.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Assignment, AssignmentStatus, Task

UTILIZATION_WINDOW_HOURS = 24 * 7  # rolling 7-day utilization window

_ACTIVE_ASSIGNMENT_STATUSES = [
    AssignmentStatus.planned, AssignmentStatus.confirmed,
    AssignmentStatus.in_progress, AssignmentStatus.completed,
]


def compute_busy_minutes(db: Session, machine_id: int) -> int:
    window_start = datetime.now(timezone.utc) - timedelta(hours=UTILIZATION_WINDOW_HOURS)

    assignments = (
        db.query(Assignment)
        .filter(
            Assignment.machine_id == machine_id,
            Assignment.scheduled_start >= window_start,
            Assignment.status.in_([AssignmentStatus.planned, AssignmentStatus.confirmed, AssignmentStatus.completed]),
        )
        .all()
    )
    return sum(
        int((a.scheduled_end - a.scheduled_start).total_seconds() // 60) for a in assignments
    )


def compute_utilization_pct(db: Session, machine_id: int) -> float:
    horizon_minutes = UTILIZATION_WINDOW_HOURS * 60
    busy_minutes = compute_busy_minutes(db, machine_id)
    return round(min(100.0, (busy_minutes / horizon_minutes) * 100), 1) if horizon_minutes else 0.0


def _as_aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def compute_financial_summary(db: Session) -> dict:
    """
    Rolls up the schedule's real dollar impact from data that's
    already there (Machine.cost_per_hour, Job.profit_value) but never
    surfaced anywhere: what the currently scheduled work costs in
    machine-hours, and how much of each job's profit is riding on an
    on-time vs. late completion.
    """
    assignments = (
        db.query(Assignment)
        .options(joinedload(Assignment.machine), joinedload(Assignment.task).joinedload(Task.job))
        .filter(Assignment.status.in_(_ACTIVE_ASSIGNMENT_STATUSES))
        .all()
    )

    total_labor_cost = 0.0
    latest_end_by_job: dict = {}
    job_by_id: dict = {}

    for a in assignments:
        duration_hours = (a.scheduled_end - a.scheduled_start).total_seconds() / 3600
        total_labor_cost += float(a.machine.cost_per_hour or 0) * duration_hours

        job = a.task.job
        job_by_id[job.job_id] = job
        end = _as_aware(a.scheduled_end)
        if job.job_id not in latest_end_by_job or end > latest_end_by_job[job.job_id]:
            latest_end_by_job[job.job_id] = end

    profit_on_time = 0.0
    profit_at_risk = 0.0
    jobs_on_time_count = 0
    jobs_at_risk_count = 0

    for job_id, latest_end in latest_end_by_job.items():
        job = job_by_id[job_id]
        due_date = _as_aware(job.due_date)
        if latest_end <= due_date:
            profit_on_time += float(job.profit_value or 0)
            jobs_on_time_count += 1
        else:
            profit_at_risk += float(job.profit_value or 0)
            jobs_at_risk_count += 1

    return {
        "total_labor_cost": round(total_labor_cost, 2),
        "profit_on_time": round(profit_on_time, 2),
        "profit_at_risk": round(profit_at_risk, 2),
        "jobs_on_time_count": jobs_on_time_count,
        "jobs_at_risk_count": jobs_at_risk_count,
    }
