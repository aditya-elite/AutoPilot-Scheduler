"""
Schedule tasks for today, all ending before 10:00 PM (22:00) local time (IST).
Current local time: ~3:43 PM (15:43) IST = 10:13 UTC.
Window available: ~16:00-22:00 local = 10:30-16:30 UTC.

Jobs:
  SO-EVE-001  | Valve Body CNC    | 3 tasks  | 16:00-19:30 local
  SO-EVE-002  | Shaft & Bearings  | 2 tasks  | 17:00-19:45 local
  SO-EVE-003  | Bracket Weld      | 2 tasks  | 18:00-21:30 local
  SO-EVE-004  | Control Panel Asm | 2 tasks  | 19:30-21:45 local
  SO-EVE-005  | Hydraulic Manifold| 3 tasks  | 16:30-21:30 local

All tasks end on or before 21:45 (9:45 PM) -- safely before 10 PM.
"""
import sys
from datetime import datetime, timezone, timedelta

from app.database import SessionLocal
from app.models import (
    Job, Task, TaskMachineEligibility, Machine, Assignment,
    JobStatus, TaskStatus, AssignmentStatus
)

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


def dt_ist(hour, minute=0):
    """Return a UTC datetime for today at the given IST hour:minute."""
    d = datetime(2026, 8, 10, hour, minute, 0, tzinfo=IST)
    return d.astimezone(UTC)


def main():
    db = SessionLocal()
    try:
        machines = {m.machine_code: m for m in db.query(Machine).all()}
        if not machines:
            print("ERROR: No machines found. Run seed_data.py first.")
            return

        print("Available machines:")
        for code, m in machines.items():
            print(f"  [{m.machine_id}] {m.machine_code} - {m.machine_name}")

        # Clean up any previous evening demo jobs so this script is idempotent
        to_clean = db.query(Job).filter(Job.job_code.like("SO-EVE-%")).all()
        for j in to_clean:
            db.delete(j)
        db.commit()

        # Find next safe assignment_id
        from sqlalchemy import func
        max_id = db.query(func.max(Assignment.assignment_id)).scalar() or 0
        aid = max_id + 1  # incrementing counter

        cnc1 = machines.get("CNC-01")
        cnc2 = machines.get("CNC-02")
        lathe = machines.get("LATHE-01")
        weld = machines.get("WELD-01")
        asm = machines.get("ASM-01")

        # ─────────────────────────────────────────────────────────────────────
        # Helper: create job + tasks + eligibility + assignments in one go
        # ─────────────────────────────────────────────────────────────────────
        def make_job(job_code, description, priority, profit, due_local_h, due_local_m, task_specs):
            """
            task_specs: list of (task_name, duration_min, machine_obj, start_local_h, start_local_m)
            """
            nonlocal aid

            due = dt_ist(due_local_h, due_local_m)
            job = Job(
                job_code=job_code,
                description=description,
                priority_weight=priority,
                profit_value=profit,
                due_date=due,
                status=JobStatus.scheduled
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            for seq, (tname, dur, machine, sh, sm) in enumerate(task_specs):
                task = Task(
                    job_id=job.job_id,
                    sequence_index=seq,
                    task_name=tname,
                    base_duration_minutes=dur,
                    status=TaskStatus.scheduled
                )
                db.add(task)
                db.commit()
                db.refresh(task)

                db.add(TaskMachineEligibility(
                    task_id=task.task_id,
                    machine_id=machine.machine_id,
                    processing_minutes=dur
                ))
                db.commit()

                s = dt_ist(sh, sm)
                e = s + timedelta(minutes=dur)
                assign = Assignment(
                    assignment_id=aid,
                    task_id=task.task_id,
                    machine_id=machine.machine_id,
                    scheduled_start=s,
                    scheduled_end=e,
                    status=AssignmentStatus.planned,
                    is_manual_override=True
                )
                db.add(assign)
                db.commit()
                aid += 1
                print(f"    Assigned: {tname} on {machine.machine_code}  {sh:02d}:{sm:02d} -> {e.astimezone(IST).strftime('%H:%M')} IST")

            print(f"  [+] Job {job_code} created ({len(task_specs)} tasks)")
            return job

        print("\n--- Scheduling evening jobs (all end before 10:00 PM IST) ---\n")

        # SO-EVE-001  Valve Body CNC  (16:00 - 19:30)
        # CNC-01: 16:00-17:15 (75 min Rough Mill)
        # CNC-02: 17:15-18:30 (75 min Finish Mill)
        # LATHE:  18:30-19:30 (60 min Precision Turn)
        make_job(
            "SO-EVE-001", "Valve Body Machining — Tata Industrial", 9, 18000.00, 22, 0,
            [
                ("Rough Milling",           75,  cnc1,  16,  0),
                ("Finish Milling",          75,  cnc2,  17, 15),
                ("Precision Turning",       60,  lathe, 18, 30),
            ]
        )

        # SO-EVE-002  Shaft & Bearings  (17:00 - 19:45)
        # LATHE:  17:00-18:30 (90 min Shaft Turn)
        # CNC-01: 18:30-19:45 (75 min Bearing Seat)
        make_job(
            "SO-EVE-002", "Shaft & Bearing Batch — Mahindra Parts", 7, 11500.00, 21, 45,
            [
                ("Shaft Turning",           90,  lathe, 17,  0),
                ("Bearing Seat Milling",    75,  cnc1,  18, 30),
            ]
        )

        # SO-EVE-003  Bracket Weld  (18:00 - 21:30)
        # CNC-02: 18:00-19:00 (60 min Bracket Prep)
        # WELD:   19:00-21:30 (150 min Frame Welding)
        make_job(
            "SO-EVE-003", "Heavy Bracket Weld Run — Bharat Forge", 8, 22000.00, 21, 59,
            [
                ("Bracket Prep & Drilling", 60,  cnc2,  18,  0),
                ("Full Frame Welding",     150,  weld,  19,  0),
            ]
        )

        # SO-EVE-004  Control Panel Assembly  (19:30 - 21:45)
        # ASM: 19:30-20:45 (75 min Sub-Assembly)
        # ASM: 20:45-21:45 (60 min Final Fit & Test)
        make_job(
            "SO-EVE-004", "Control Panel Assembly — Siemens India", 6, 9500.00, 21, 55,
            [
                ("Sub-Assembly Build",      75,  asm,   19, 30),
                ("Final Fit & Functional Test", 60, asm, 20, 45),
            ]
        )

        # SO-EVE-005  Hydraulic Manifold  (16:30 - 21:30)
        # CNC-01: 16:30-18:00 (90 min Bore Drilling)
        # CNC-02: 18:00-19:30 (90 min Port Milling)
        # WELD:   NA — Assembly 19:45-21:30 (105 min)
        make_job(
            "SO-EVE-005", "Hydraulic Manifold Block — BEML", 10, 31000.00, 21, 59,
            [
                ("Manifold Bore Drilling",  90,  cnc1,  16, 30),
                ("Port Channel Milling",    90,  cnc2,  18,  0),
                ("Manifold Final Assembly", 105, asm,   19, 45),
            ]
        )

        print("\n=== SUMMARY ===")
        jobs = db.query(Job).filter(Job.job_code.like("SO-EVE-%")).all()
        total_tasks = 0
        for j in jobs:
            tasks = db.query(Task).filter(Task.job_id == j.job_id).all()
            total_tasks += len(tasks)
            latest = None
            for t in tasks:
                a = db.query(Assignment).filter(Assignment.task_id == t.task_id).first()
                if a:
                    end_ist = a.scheduled_end.astimezone(IST)
                    if latest is None or end_ist > latest:
                        latest = end_ist
            print(f"  {j.job_code}  |  {j.description[:40]:<40} |  latest end: {latest.strftime('%H:%M') if latest else 'N/A'} IST")

        print(f"\nTotal jobs created: {len(jobs)}")
        print(f"Total tasks created: {total_tasks}")
        print("\nAll tasks scheduled to finish before 22:00 (10:00 PM) IST.")
        print("Open http://localhost:5173 -> Manager Dashboard to see the Gantt chart.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
