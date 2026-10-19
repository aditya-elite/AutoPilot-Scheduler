"""
Scheduling Repository
=======================

This is THE seam between Postgres and the pure-Python solver in
`app/solver/job_shop_solver.py`. It has two jobs:

  1. build_scheduling_problem(db) — reads jobs/tasks/eligibility/
     downtime out of Postgres and shapes them into the exact
     `SchedulingProblem` TypedDict the solver expects. The solver
     never touches SQLAlchemy directly.

  2. persist_solution(db, result, run_id) — writes the solver's
     output back as `assignments` rows, tied to the `optimization_runs`
     row that produced them, and writes an audit log entry.

Time handling: the solver works in integer MINUTES from a horizon
origin (kept deliberately simple/fast for CP-SAT). This repository is
the only place that converts between wall-clock TIMESTAMPTZ values in
Postgres and those integer minute offsets.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    Job, Task, TaskMachineEligibility, Machine, MachineDowntime,
    Assignment, AuditLog, JobStatus, AssignmentStatus, MachineStatus,
)
from app.solver.job_shop_solver import SchedulingProblem, SolveResult
from app.ml.duration_model import predict_durations
from app.ml.feature_builder import build_duration_features

HORIZON_ORIGIN = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _as_aware(dt: datetime) -> datetime:
    """Postgres TIMESTAMPTZ columns should already come back tz-aware
    via psycopg2, but we normalize defensively in case a naive
    datetime slips in from elsewhere (e.g. test fixtures)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _minutes_from_origin(dt: datetime) -> int:
    return max(0, int((_as_aware(dt) - HORIZON_ORIGIN).total_seconds() // 60))


def _datetime_from_minutes(minutes: int) -> datetime:
    return HORIZON_ORIGIN + timedelta(minutes=minutes)


def diagnose_scheduling_blockers(db: Session) -> list[str]:
    """
    Returns concrete, user-facing blockers that make optimization
    impossible or very likely to fail.
    """
    blockers: list[str] = []

    jobs = (
        db.query(Job)
        .filter(Job.status.in_([JobStatus.pending, JobStatus.scheduled]))
        .all()
    )
    if not jobs:
        return ["No pending/scheduled jobs are available to optimize."]

    machines = db.query(Machine).all()
    machine_by_id = {m.machine_id: m for m in machines}

    for job in jobs:
        tasks = sorted(job.tasks, key=lambda t: t.sequence_index)
        if not tasks:
            blockers.append(f"Job {job.job_code} has no tasks configured.")
            continue

        for task in tasks:
            eligible = (
                db.query(TaskMachineEligibility)
                .filter(TaskMachineEligibility.task_id == task.task_id)
                .all()
            )
            if not eligible:
                blockers.append(
                    f"Job {job.job_code} task '{task.task_name}' has no eligible machines."
                )
                continue

            if task.predicted_duration_minutes is not None and task.predicted_duration_minutes <= 0:
                blockers.append(
                    f"Job {job.job_code} task '{task.task_name}' has invalid predicted duration "
                    f"{task.predicted_duration_minutes}."
                )
            for option in eligible:
                if option.processing_minutes <= 0:
                    machine = machine_by_id.get(option.machine_id)
                    machine_code = machine.machine_code if machine else f"machine:{option.machine_id}"
                    blockers.append(
                        f"Job {job.job_code} task '{task.task_name}' has invalid processing time "
                        f"{option.processing_minutes} on {machine_code}."
                    )

    # Keep output concise in UI toasts while still actionable.
    return blockers[:6]


def build_scheduling_problem(db: Session) -> SchedulingProblem:
    """
    Pulls all pending/scheduled jobs (with their tasks and machine
    eligibility) and all active machine downtime windows, and shapes
    them into the solver's input contract.
    """
    jobs = (
        db.query(Job)
        .filter(Job.status.in_([JobStatus.pending, JobStatus.scheduled]))
        .all()
    )
    machines = db.query(Machine).all()
    machine_by_id = {m.machine_id: m for m in machines}

    # Pass 1: gather every (task, eligible machine) pair that needs a
    # predicted duration, so the ML model runs ONCE in a batch instead
    # of once per pair.
    pending_specs = []  # list of (job, [(task, eligibility rows)])
    feature_rows = []
    pair_index = []  # parallel to feature_rows: (task_id, machine_id)

    for job in jobs:
        task_specs_raw = []
        for task in sorted(job.tasks, key=lambda t: t.sequence_index):
            eligible = (
                db.query(TaskMachineEligibility)
                .filter(TaskMachineEligibility.task_id == task.task_id)
                .all()
            )
            if not eligible:
                # A task with no eligible machines can't be scheduled —
                # skip the whole job rather than silently dropping one
                # task and corrupting the precedence chain.
                task_specs_raw = []
                break
            task_specs_raw.append((task, eligible))

        if not task_specs_raw:
            continue

        pending_specs.append((job, task_specs_raw))
        for task, eligible in task_specs_raw:
            for e in eligible:
                machine = machine_by_id.get(e.machine_id)
                if machine is None:
                    continue
                feature_rows.append(build_duration_features(
                    base_duration_minutes=e.processing_minutes,
                    machine=machine,
                    job_priority_weight=job.priority_weight,
                ))
                pair_index.append((task.task_id, e.machine_id))

    predicted = predict_durations(feature_rows) if feature_rows else []
    predicted_by_pair = dict(zip(pair_index, predicted))

    # Pass 2: assemble the solver's input, using the predicted duration
    # for each (task, machine) pair (falling back to the engineering
    # estimate if the model somehow didn't return a value for it).
    problem_jobs = []
    for job, task_specs_raw in pending_specs:
        task_specs = []
        for task, eligible in task_specs_raw:
            task_specs.append({
                "task_id": task.task_id,
                "sequence_index": task.sequence_index,
                "eligible_machines": [
                    {
                        "machine_id": e.machine_id,
                        "processing_minutes": predicted_by_pair.get(
                            (task.task_id, e.machine_id), e.processing_minutes
                        ),
                    }
                    for e in eligible
                ],
            })

        problem_jobs.append({
            "job_id": job.job_id,
            "due_date_minute": _minutes_from_origin(job.due_date),
            "priority_weight": job.priority_weight,
            "profit_value": float(job.profit_value),
            "material_available_minute": job.material_available_minutes,
            "tasks": task_specs,
        })

    now = datetime.now(timezone.utc)
    # Only include downtime for machines that are currently offline.
    # This prevents restored machines from having leftover downtime
    # windows that block the solver.
    from app.models import MachineStatus as _MS
    offline_machine_ids = {m.machine_id for m in machines if m.status == _MS.offline}
    
    machine_downtime: dict[int, list] = {m.machine_id: [] for m in machines}
    downtimes = (
        db.query(MachineDowntime)
        .filter(
            MachineDowntime.machine_id.in_(offline_machine_ids),
            MachineDowntime.end_time >= now,
        )
        .all()
    ) if offline_machine_ids else []
    for dt in downtimes:
        machine_downtime.setdefault(dt.machine_id, []).append({
            "start_minute": _minutes_from_origin(dt.start_time),
            "end_minute": _minutes_from_origin(dt.end_time),
        })

    return {
        "jobs": problem_jobs,
        "machine_ids": [m.machine_id for m in machines if m.status != _MS.offline],
        "machine_downtime": machine_downtime,
    }


def persist_solution(db: Session, result: SolveResult, run_id: int, triggered_by: Optional[str] = None) -> None:
    """
    Writes the solver's assignments as new `assignments` rows.
    Existing 'planned' assignments for the same tasks are superseded
    (not deleted) so the audit trail stays intact.
    """
    # Supersede prior planned assignments for tasks we're re-scheduling.
    task_ids = [a.task_id for a in result.assignments]
    if task_ids:
        (
            db.query(Assignment)
            .filter(Assignment.task_id.in_(task_ids), Assignment.status == AssignmentStatus.planned)
            .update({Assignment.status: AssignmentStatus.superseded}, synchronize_session=False)
        )

    # The processing_minutes fed to the solver for each (task, machine)
    # pair was already the ML-predicted duration (see
    # build_scheduling_problem), so the chosen machine's actual slot
    # length IS that prediction — persist it onto the task so it's
    # visible instead of permanently null.
    tasks_by_id = {
        t.task_id: t
        for t in db.query(Task).filter(Task.task_id.in_(task_ids)).all()
    } if task_ids else {}

    for a in result.assignments:
        assignment = Assignment(
            task_id=a.task_id,
            machine_id=a.machine_id,
            scheduled_start=_datetime_from_minutes(a.start_minute),
            scheduled_end=_datetime_from_minutes(a.end_minute),
            status=AssignmentStatus.planned,
            is_manual_override=False,
            optimization_run_id=run_id,
        )
        db.add(assignment)

        task = tasks_by_id.get(a.task_id)
        if task is not None:
            task.predicted_duration_minutes = a.end_minute - a.start_minute

    db.add(AuditLog(
        entity_type="optimization_run",
        entity_id=run_id,
        action="ai_reschedule",
        new_value={"assignments_written": len(result.assignments), "status": result.status},
        changed_by=triggered_by,
    ))

    db.commit()
