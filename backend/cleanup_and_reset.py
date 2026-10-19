"""
CLEANUP + light schedule: removes all batch/demo jobs, then adds
just 3 well-spaced tasks so the Gantt chart is clean and readable.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

from app.database import SessionLocal
from app.models import Job, Task, TaskMachineEligibility, Machine, Assignment, JobStatus, TaskStatus, AssignmentStatus

IST = timezone(timedelta(hours=5, minutes=30))

def ist(h, m=0):
    return datetime(2026, 8, 10, h, m, 0, tzinfo=IST).astimezone(timezone.utc)

def main():
    db = SessionLocal()
    try:
        M = {m.machine_code: m for m in db.query(Machine).all()}

        # ── Delete all previous demo/batch jobs ───────────────────────────────
        patterns = ["SO-EVE-%", "SO-B2-%", "SO-SM-%", "SO-2026-900%"]
        deleted = 0
        for pat in patterns:
            for j in db.query(Job).filter(Job.job_code.like(pat)).all():
                db.delete(j)
                deleted += 1
        db.commit()
        print(f"Removed {deleted} old batch jobs.\n")

        # ── Add 3 clean, well-spaced tasks ────────────────────────────────────
        aid = (db.query(func.max(Assignment.assignment_id)).scalar() or 0) + 1

        tasks = [
            # (code,        desc,                    machine,           task_name,          dur, sh, sm)
            ("SO-CLN-001", "Valve Cover — MRF",      M["CNC-01"],  "CNC Milling",          60, 17,  0),
            ("SO-CLN-002", "Drive Shaft — Bosch",    M["LATHE-01"],"Shaft Turning",         75, 18, 30),
            ("SO-CLN-003", "Chassis Frame — Tata",   M["WELD-01"], "Frame Welding",        90, 19, 30),
        ]

        print("New schedule (3 tasks, well spaced):\n")
        for code, desc, machine, tname, dur, sh, sm in tasks:
            s = ist(sh, sm)
            e = s + timedelta(minutes=dur)
            end_ist = e.astimezone(IST)

            j = Job(job_code=code, description=desc, priority_weight=6,
                    profit_value=5000, due_date=ist(22), status=JobStatus.scheduled)
            db.add(j); db.commit(); db.refresh(j)

            t = Task(job_id=j.job_id, sequence_index=0, task_name=tname,
                     base_duration_minutes=dur, status=TaskStatus.scheduled)
            db.add(t); db.commit(); db.refresh(t)

            db.add(TaskMachineEligibility(task_id=t.task_id, machine_id=machine.machine_id, processing_minutes=dur))
            db.add(Assignment(
                assignment_id=aid, task_id=t.task_id, machine_id=machine.machine_id,
                scheduled_start=s, scheduled_end=e,
                status=AssignmentStatus.planned, is_manual_override=True
            ))
            db.commit()
            aid += 1

            print(f"  {machine.machine_code:<12}  {tname:<22}  {sh:02d}:{sm:02d} -> {end_ist.strftime('%H:%M')} IST  ({dur}m)")

        print("\nGantt should now be clean. Refresh http://localhost:5173")
    finally:
        db.close()

if __name__ == "__main__":
    main()
