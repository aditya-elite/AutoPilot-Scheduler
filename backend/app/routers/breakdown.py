"""
The Breakdown Simulator.

Marking a machine offline does three things in one transaction:
  1. Flips `machines.status` to 'offline'.
  2. Inserts a `machine_downtime` row spanning now -> far future (so
     the solver's forbidden-interval mechanism excludes it entirely
     until someone brings it back online).
  3. Writes an audit log entry.

It then immediately kicks off a re-optimization run (same code path
as the AI Control Center's manual trigger) so the Gantt chart
reflects the disruption without the manager needing a second click.
"""
from typing import List
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Machine, MachineDowntime, AuditLog, MachineStatus, DowntimeReason, OptimizationRun, OptimizationStatus, OptimizationGoal
from app.schemas import MachineOfflineRequest, MachineOut, MachineRiskOut, ScheduleMaintenanceRequest
from app.security import require_role, get_current_user
from app.routers.schedule import _run_optimization_job, _GOAL_WEIGHTS
from app.solver.job_shop_solver import OptimizationConfig
from app.websocket_manager import broadcast_sync
from app.ml.feature_builder import build_failure_risk_features, recompute_all_failure_risk

router = APIRouter(prefix="/breakdown", tags=["breakdown"])

FAR_FUTURE_DAYS = 3650  # "until manually restored" — effectively indefinite


def _risk_level(score: float) -> str:
    if score >= 0.5:
        return "high"
    if score >= 0.2:
        return "medium"
    return "low"


@router.get("/risk", response_model=List[MachineRiskOut])
def get_predicted_risk(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """
    Predictive Maintenance panel data source. Returns the CURRENT
    stored failure_risk_score per machine (fast, no model inference)
    alongside the raw signals that feed it. Use POST /breakdown/risk/recompute
    to actually re-run the ML model and refresh the scores.
    """
    machines = db.query(Machine).order_by(Machine.failure_risk_score.desc()).all()
    results = []
    for machine in machines:
        features = build_failure_risk_features(db, machine)
        score = float(machine.failure_risk_score or 0.0)
        results.append(MachineRiskOut(
            machine_id=machine.machine_id,
            machine_code=machine.machine_code,
            machine_type=machine.machine_type,
            status=machine.status.value,
            failure_risk_score=score,
            hours_since_last_maintenance=round(features["hours_since_last_maintenance"], 1),
            age_years=features["age_years"],
            historical_breakdown_count=features["historical_breakdown_count"],
            risk_level=_risk_level(score),
        ))
    return results


@router.post("/risk/recompute", response_model=List[MachineRiskOut])
def recompute_predicted_risk(
    db: Session = Depends(get_db),
    _user=Depends(require_role("factory_manager")),
):
    """Re-runs the failure-risk ML model over live machine data and persists the results."""
    recompute_all_failure_risk(db)
    return get_predicted_risk(db=db, _user=_user)


@router.post("/{machine_id}/offline", response_model=MachineOut)
def mark_machine_offline(
    machine_id: int,
    request: MachineOfflineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_role("factory_manager")),
):
    machine = db.query(Machine).filter(Machine.machine_id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    old_status = machine.status.value
    machine.status = MachineStatus.offline

    now = datetime.now(timezone.utc)
    db.add(MachineDowntime(
        machine_id=machine_id,
        reason=DowntimeReason(request.reason) if request.reason in DowntimeReason._value2member_map_ else DowntimeReason.unplanned_breakdown,
        start_time=now,
        end_time=now + timedelta(days=FAR_FUTURE_DAYS),
        notes=request.notes,
        created_by=user.user_id,
    ))
    db.add(AuditLog(
        entity_type="machine",
        entity_id=machine_id,
        action="update",
        old_value={"status": old_status},
        new_value={"status": "offline", "reason": request.reason},
        changed_by=user.user_id,
    ))
    db.commit()
    db.refresh(machine)

    broadcast_sync("machine_status_changed", {"machine_id": machine_id, "machine_code": machine.machine_code, "status": "offline"})

    # Immediately trigger a fast re-optimization scoped to a short
    # time budget, since this is a live-disruption response, not a
    # leisurely nightly re-plan.
    goal = OptimizationGoal.balanced
    mw, tw = _GOAL_WEIGHTS[goal]
    config = OptimizationConfig(makespan_weight=mw, tardiness_weight=tw, max_solve_seconds=10.0)

    run = OptimizationRun(
        triggered_by=user.user_id,
        goal=goal,
        status=OptimizationStatus.queued,
        solver_config={"trigger": "breakdown_simulator", "machine_id": machine_id},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))

    return machine


@router.post("/{machine_id}/schedule-maintenance", response_model=MachineOut)
def schedule_maintenance(
    machine_id: int,
    request: ScheduleMaintenanceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_role("factory_manager")),
):
    """
    The action behind the Predictive Maintenance panel's "Schedule
    Maintenance" button. Unlike the breakdown simulator's deliberately
    indefinite outage, this takes the machine offline for a BOUNDED
    window (default 4 hours) since it's a proactive, planned response
    to elevated failure_risk_score rather than an actual breakdown.
    Ending early works the same way as restoring from a breakdown:
    POST /breakdown/{machine_id}/online.
    """
    machine = db.query(Machine).filter(Machine.machine_id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    old_status = machine.status.value
    machine.status = MachineStatus.offline

    now = datetime.now(timezone.utc)
    default_notes = f"Proactive maintenance — predicted failure risk {float(machine.failure_risk_score or 0.0) * 100:.0f}%"
    db.add(MachineDowntime(
        machine_id=machine_id,
        reason=DowntimeReason.predicted_failure_risk,
        start_time=now,
        end_time=now + timedelta(hours=request.duration_hours),
        notes=request.notes or default_notes,
        created_by=user.user_id,
    ))
    db.add(AuditLog(
        entity_type="machine",
        entity_id=machine_id,
        action="update",
        old_value={"status": old_status},
        new_value={"status": "offline", "reason": "predicted_failure_risk"},
        changed_by=user.user_id,
    ))
    db.commit()
    db.refresh(machine)

    broadcast_sync("machine_status_changed", {"machine_id": machine_id, "machine_code": machine.machine_code, "status": "offline"})

    goal = OptimizationGoal.balanced
    mw, tw = _GOAL_WEIGHTS[goal]
    config = OptimizationConfig(makespan_weight=mw, tardiness_weight=tw, max_solve_seconds=10.0)

    run = OptimizationRun(
        triggered_by=user.user_id,
        goal=goal,
        status=OptimizationStatus.queued,
        solver_config={"trigger": "scheduled_maintenance", "machine_id": machine_id},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_run_optimization_job, run.run_id, goal, config, str(user.user_id))

    return machine


@router.post("/{machine_id}/online", response_model=MachineOut)
def restore_machine_online(
    machine_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("factory_manager")),
):
    machine = db.query(Machine).filter(Machine.machine_id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    old_status = machine.status.value
    machine.status = MachineStatus.online

    # Close out any open-ended downtime windows for this machine.
    open_downtimes = (
        db.query(MachineDowntime)
        .filter(MachineDowntime.machine_id == machine_id, MachineDowntime.end_time > datetime.now(timezone.utc))
        .all()
    )
    for dt in open_downtimes:
        dt.end_time = datetime.now(timezone.utc)

    db.add(AuditLog(
        entity_type="machine",
        entity_id=machine_id,
        action="update",
        old_value={"status": old_status},
        new_value={"status": "online"},
        changed_by=user.user_id,
    ))
    db.commit()
    db.refresh(machine)
    broadcast_sync("machine_status_changed", {"machine_id": machine_id, "machine_code": machine.machine_code, "status": "online"})
    return machine
