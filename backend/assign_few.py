"""
Assigns ONE task per machine — simple, clean, all ending before 10 PM IST.
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

        # Clean up old simple batch
        for j in db.query(Job).filter(Job.job_code.like("SO-SM-%")).all():
            db.delete(j)
        db.commit()

        aid = (db.query(func.max(Assignment.assignment_id)).scalar() or 0) + 1

        # 5 machines, 1 task each, all ending before 22:00 IST
        specs = [
            # (job_code,      desc,                    machine,             task_name,               dur, start_h, start_m)
            ("SO-SM-001", "Brake Disc — Hero Parts",   M["CNC-01"],  "Disc Face Milling",        90,  17, 30),
            ("SO-SM-002", "Drive Shaft — Bosch India", M["CNC-02"],  "Shaft Groove Cutting",     60,  18,  0),
            ("SO-SM-003", "Rotor Spindle — SKF",       M["LATHE-01"],"Spindle Finish Turn",      75,  18, 30),
            ("SO-SM-004", "Tank Frame — TAFE",         M["WELD-01"], "Frame Tack & Weld",       120,  19,  0),
            ("SO-SM-005", "Motor Mount — Siemens",     M["ASM-01"],  "Mount Assembly & Torque",  90,  20,  0),
        ]

        print("\nAssigning 1 task per machine:\n")
        for job_code, desc, machine, task_name, dur, sh, sm in specs:
            s = ist(sh, sm)
            e = s + timedelta(minutes=dur)
            end_ist = e.astimezone(IST)

            j = Job(job_code=job_code, description=desc, priority_weight=7,
                    profit_value=8000, due_date=ist(22), status=JobStatus.scheduled)
            db.add(j); db.commit(); db.refresh(j)

            t = Task(job_id=j.job_id, sequence_index=0, task_name=task_name,
                     base_duration_minutes=dur, status=TaskStatus.scheduled)
            db.add(t); db.commit(); db.refresh(t)

            db.add(TaskMachineEligibility(task_id=t.task_id, machine_id=machine.machine_id, processing_minutes=dur))
            db.add(Assignment(assignment_id=aid, task_id=t.task_id, machine_id=machine.machine_id,
                              scheduled_start=s, scheduled_end=e,
                              status=AssignmentStatus.planned, is_manual_override=True))
            db.commit()
            aid += 1

            flag = "OK" if end_ist.hour < 22 else "LATE!"
            print(f"  {machine.machine_code:<12} {task_name:<32} {sh:02d}:{sm:02d} -> {end_ist.strftime('%H:%M')} IST  [{flag}]")

        print("\nDone — 5 tasks assigned, one per machine.")
        print("View at: http://localhost:5173  (login: manager / manager123)")
    finally:
        db.close()

if __name__ == "__main__":
    main()
