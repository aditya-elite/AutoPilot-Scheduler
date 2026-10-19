"""
Adds exactly 2 tasks per machine (10 tasks total), well-spaced, all before 10 PM IST.
Cleans up previous CLN jobs first so it's safe to re-run.
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

        # Clean up old CLN jobs
        for j in db.query(Job).filter(Job.job_code.like("SO-CLN-%")).all():
            db.delete(j)
        db.commit()

        aid = (db.query(func.max(Assignment.assignment_id)).scalar() or 0) + 1

        #  2 tasks per machine — spaced ~1.5 hrs apart so the Gantt stays clean
        # Format: (code, desc, machine_key, task_name, duration_min, start_h, start_m)
        specs = [
            # CNC-01
            ("SO-CLN-001", "Valve Cover — MRF",         "CNC-01",   "Rough Face Milling",    50, 16, 30),
            ("SO-CLN-002", "Pump Housing — KSB",        "CNC-01",   "Bore & Thread Mill",    45, 18, 30),

            # CNC-02
            ("SO-CLN-003", "Turbine Disc — BHEL",       "CNC-02",   "Profile Rough Cut",     60, 17,  0),
            ("SO-CLN-004", "Gear Blank — Elecon",       "CNC-02",   "Finish Contour Mill",   45, 19, 15),

            # LATHE-01
            ("SO-CLN-005", "Drive Shaft — Bosch",       "LATHE-01", "Shaft Rough Turn",      55, 16, 45),
            ("SO-CLN-006", "Rotor Pin — SKF",           "LATHE-01", "Pin Finish Turn",       40, 18, 45),

            # WELD-01
            ("SO-CLN-007", "Chassis Frame — Tata",      "WELD-01",  "Tack & Fixture Weld",   60, 17, 30),
            ("SO-CLN-008", "Exhaust Bracket — Hero",    "WELD-01",  "Full Seam Weld",        75, 19, 45),

            # ASM-01
            ("SO-CLN-009", "Control Panel — Siemens",   "ASM-01",   "Sub-Assembly Build",    60, 17, 15),
            ("SO-CLN-010", "Motor Mount — L&T",         "ASM-01",   "Final Fit & QC",        55, 20,  0),
        ]

        print(f"\n2 tasks per machine — 10 tasks total:\n")
        prev_machine = None
        for code, desc, mkey, tname, dur, sh, sm in specs:
            if prev_machine != mkey:
                print(f"  [{mkey}]")
                prev_machine = mkey

            machine = M[mkey]
            s = ist(sh, sm)
            e = s + timedelta(minutes=dur)
            end_ist = e.astimezone(IST)

            j = Job(job_code=code, description=desc, priority_weight=6,
                    profit_value=6000, due_date=ist(22), status=JobStatus.scheduled)
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

            flag = "OK" if end_ist.hour < 22 else "LATE!"
            print(f"    {tname:<28}  {sh:02d}:{sm:02d} -> {end_ist.strftime('%H:%M')} IST  ({dur}m)  [{flag}]")

        print("\nAll 10 tasks assigned. Refresh http://localhost:5173")
    finally:
        db.close()

if __name__ == "__main__":
    main()
