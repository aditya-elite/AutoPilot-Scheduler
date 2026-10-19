import csv
import io
from typing import List

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Assignment, Machine, AuditLog, User, AssignmentStatus, Task
from app.schemas import UtilizationOut, AuditLogOut, FinancialSummaryOut
from app.security import get_current_user
from app.repositories.analytics_repo import compute_busy_minutes, compute_financial_summary, UTILIZATION_WINDOW_HOURS

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/financials", response_model=FinancialSummaryOut)
def get_financial_summary(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return FinancialSummaryOut(**compute_financial_summary(db))


@router.get("/utilization", response_model=List[UtilizationOut])
def get_utilization(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    horizon_minutes = UTILIZATION_WINDOW_HOURS * 60

    machines = db.query(Machine).all()
    results = []
    for machine in machines:
        busy_minutes = compute_busy_minutes(db, machine.machine_id)
        utilization_pct = round(min(100.0, (busy_minutes / horizon_minutes) * 100), 1) if horizon_minutes else 0.0
        results.append(UtilizationOut(
            machine_id=machine.machine_id,
            machine_code=machine.machine_code,
            utilization_pct=utilization_pct,
            busy_minutes=busy_minutes,
            horizon_minutes=horizon_minutes,
        ))
    return results


@router.get("/audit-log", response_model=List[AuditLogOut])
def get_audit_log(limit: int = 100, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.changed_at.desc())
        .limit(limit)
        .all()
    )
    output = []
    for log in logs:
        user = db.query(User).filter(User.user_id == log.changed_by).first() if log.changed_by else None
        output.append(AuditLogOut(
            log_id=log.log_id,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            changed_at=log.changed_at,
            changed_by_name=user.full_name if user else "System (AI Engine)",
        ))
    return output


@router.get("/export/schedule.csv")
def export_schedule_csv(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    assignments = (
        db.query(Assignment)
        .options(joinedload(Assignment.task).joinedload(Task.job), joinedload(Assignment.machine))
        .filter(Assignment.status.in_([AssignmentStatus.planned, AssignmentStatus.confirmed, AssignmentStatus.in_progress]))
        .order_by(Assignment.scheduled_start)
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Job Code", "Task", "Machine", "Start", "End", "Status", "Manual Override", "Violation"])
    for a in assignments:
        writer.writerow([
            a.task.job.job_code,
            a.task.task_name,
            a.machine.machine_code,
            a.scheduled_start.isoformat(),
            a.scheduled_end.isoformat(),
            a.status.value,
            "Yes" if a.is_manual_override else "No",
            a.violation_reason or "",
        ])
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=autopilot_schedule.csv"},
    )
