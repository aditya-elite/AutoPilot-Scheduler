"""
Feature Builder
================

The seam between live database state and the two ML models'
(`duration_model.py`, `failure_model.py`) expected input feature
dicts. Keeping this logic here (instead of scattering feature
assembly across the scheduling repo and routers) means both models'
feature contracts have exactly one place they're built from.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Machine, MachineDowntime, DowntimeReason
from app.repositories.analytics_repo import compute_utilization_pct
from app.ml.duration_model import predict_durations
from app.ml.failure_model import predict_failure_risk

DEFAULT_HOURS_SINCE_MAINTENANCE = 2000.0  # ~83 days; used when never maintained


def build_duration_features(base_duration_minutes: int, machine: Machine, job_priority_weight: int) -> dict:
    """
    Feature row for one (task, eligible machine) pair. base_duration_minutes
    comes from that pair's TaskMachineEligibility.processing_minutes, NOT
    task.base_duration_minutes, since it varies per eligible machine.
    """
    return {
        "base_duration_minutes": base_duration_minutes,
        "machine_type": machine.machine_type,
        "job_priority_weight": job_priority_weight,
        "machine_failure_risk_score": float(machine.failure_risk_score or 0.0),
    }


def build_failure_risk_features(db: Session, machine: Machine) -> dict:
    if machine.last_maintained_at:
        last_maintained = machine.last_maintained_at
        if last_maintained.tzinfo is None:
            last_maintained = last_maintained.replace(tzinfo=timezone.utc)
        hours_since_maintenance = max(
            0.0, (datetime.now(timezone.utc) - last_maintained).total_seconds() / 3600
        )
    else:
        hours_since_maintenance = DEFAULT_HOURS_SINCE_MAINTENANCE

    historical_breakdown_count = (
        db.query(MachineDowntime)
        .filter(
            MachineDowntime.machine_id == machine.machine_id,
            MachineDowntime.reason == DowntimeReason.unplanned_breakdown,
        )
        .count()
    )

    return {
        "hours_since_last_maintenance": hours_since_maintenance,
        "average_daily_utilization_pct": compute_utilization_pct(db, machine.machine_id),
        "age_years": float(machine.age_years or 0.0),
        "historical_breakdown_count": historical_breakdown_count,
    }


def recompute_all_failure_risk(db: Session) -> list[dict]:
    """
    Recomputes and persists failure_risk_score for every machine.
    Returns a summary list (used by the manual recompute endpoint).
    """
    machines = db.query(Machine).all()
    if not machines:
        return []

    feature_rows = [build_failure_risk_features(db, m) for m in machines]
    risk_scores = predict_failure_risk(feature_rows)

    summary = []
    for machine, features, score in zip(machines, feature_rows, risk_scores):
        machine.failure_risk_score = score
        summary.append({
            "machine_id": machine.machine_id,
            "machine_code": machine.machine_code,
            "failure_risk_score": score,
            **features,
        })

    db.commit()
    return summary
