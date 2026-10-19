"""
Run this ONCE against a freshly-migrated database (after applying
schema.sql) to populate demo data so the frontend has something real
to show immediately.

Usage:
    python seed_data.py
"""
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import (
    User, UserRole, Machine, MachineStatus, Job, JobStatus, Task,
    TaskMachineEligibility,
)
from app.security import hash_password


def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("Database already has data — skipping seed. Delete rows manually to reseed.")
            return

        # --- Users ---
        users = [
            User(username="admin", password_hash=hash_password("admin123"), full_name="System Admin", role=UserRole.admin),
            User(username="manager", password_hash=hash_password("manager123"), full_name="Factory Manager", role=UserRole.factory_manager),
            User(username="operator", password_hash=hash_password("operator123"), full_name="Dave Chen", role=UserRole.machine_operator),
        ]
        db.add_all(users)
        db.commit()

        # --- Machines ---
        now_ts = datetime.now(timezone.utc)
        machines = [
            Machine(machine_code="CNC-01", machine_name="CNC Mill #1", machine_type="CNC_MILL", status=MachineStatus.online, cost_per_hour=45.00, failure_risk_score=0.12, age_years=2.5, last_maintained_at=now_ts - timedelta(days=20)),
            Machine(machine_code="CNC-02", machine_name="CNC Mill #2", machine_type="CNC_MILL", status=MachineStatus.online, cost_per_hour=45.00, failure_risk_score=0.31, age_years=6.0, last_maintained_at=now_ts - timedelta(days=90)),
            Machine(machine_code="LATHE-01", machine_name="Lathe Station #1", machine_type="LATHE", status=MachineStatus.online, cost_per_hour=38.00, failure_risk_score=0.08, age_years=1.5, last_maintained_at=now_ts - timedelta(days=10)),
            Machine(machine_code="WELD-01", machine_name="Welding Robot #1", machine_type="WELDING_STATION", status=MachineStatus.online, cost_per_hour=52.00, failure_risk_score=0.44, age_years=9.0, last_maintained_at=now_ts - timedelta(days=150)),
            Machine(machine_code="ASM-01", machine_name="Assembly Line A", machine_type="ASSEMBLY_LINE", status=MachineStatus.online, cost_per_hour=30.00, failure_risk_score=0.05, age_years=3.0, last_maintained_at=now_ts - timedelta(days=30)),
        ]
        db.add_all(machines)
        db.commit()
        for m in machines:
            db.refresh(m)

        cnc1, cnc2, lathe1, weld1, asm1 = machines

        # --- Jobs + tasks ---
        now = datetime.now(timezone.utc)
        job_specs = [
            {
                "job_code": "SO-2026-1001", "description": "Bracket assembly — Acme Corp",
                "priority_weight": 9, "profit_value": 12000, "due_date": now + timedelta(hours=10),
                "tasks": [
                    ("Rough mill housing", 45, [(cnc1, 45), (cnc2, 50)]),
                    ("Lathe finish shaft", 30, [(lathe1, 30)]),
                    ("Weld sub-assembly", 40, [(weld1, 40)]),
                ],
            },
            {
                "job_code": "SO-2026-1002", "description": "Gearbox housing — Nordic Industries",
                "priority_weight": 6, "profit_value": 6500, "due_date": now + timedelta(hours=18),
                "tasks": [
                    ("Mill housing", 60, [(cnc2, 60), (cnc1, 65)]),
                    ("Assemble unit", 35, [(asm1, 35)]),
                ],
            },
            {
                "job_code": "SO-2026-1003", "description": "Custom fixture — rapid turnaround",
                "priority_weight": 10, "profit_value": 20000, "due_date": now + timedelta(hours=6),
                "tasks": [
                    ("Lathe prep", 25, [(lathe1, 25)]),
                    ("Weld frame", 50, [(weld1, 50)]),
                    ("Final assembly", 20, [(asm1, 20)]),
                ],
            },
            {
                "job_code": "SO-2026-1004", "description": "Standard bracket batch",
                "priority_weight": 3, "profit_value": 1800, "due_date": now + timedelta(hours=30),
                "tasks": [
                    ("Mill batch", 90, [(cnc1, 90), (cnc2, 95)]),
                ],
            },
        ]

        for spec in job_specs:
            job = Job(
                job_code=spec["job_code"], description=spec["description"],
                priority_weight=spec["priority_weight"], profit_value=spec["profit_value"],
                due_date=spec["due_date"], status=JobStatus.pending,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            for idx, (task_name, base_duration, machine_options) in enumerate(spec["tasks"]):
                task = Task(job_id=job.job_id, sequence_index=idx, task_name=task_name, base_duration_minutes=base_duration)
                db.add(task)
                db.commit()
                db.refresh(task)

                for machine, minutes in machine_options:
                    db.add(TaskMachineEligibility(task_id=task.task_id, machine_id=machine.machine_id, processing_minutes=minutes))
            db.commit()

        print("Seed complete: 3 users, 5 machines, 4 jobs with tasks.")
        print("Login as: manager / manager123  (Factory Manager)")
        print("          operator / operator123 (Machine Operator)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
