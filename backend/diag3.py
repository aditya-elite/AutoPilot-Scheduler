"""Intercept the actual 500 exception by calling the route logic directly."""
import sys
sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models import Machine, MachineDowntime, MachineStatus, DowntimeReason
from app.repositories.scheduling_repo import build_scheduling_problem, diagnose_scheduling_blockers
from app.solver.job_shop_solver import FlexibleJobShopScheduler, OptimizationConfig, OptimizationGoal
from datetime import datetime, timezone, timedelta
import traceback

db = SessionLocal()

print("=== 1. Checking scheduling blockers ===")
try:
    blockers = diagnose_scheduling_blockers(db)
    print(f"Blockers: {blockers}")
except Exception as e:
    print(f"ERROR in diagnose_scheduling_blockers: {e}")
    traceback.print_exc()

print("\n=== 2. Building scheduling problem ===")
try:
    problem = build_scheduling_problem(db)
    print(f"Jobs in problem: {len(problem['jobs'])}")
    print(f"Machines in problem: {len(problem['machines'])}")
except Exception as e:
    print(f"ERROR in build_scheduling_problem: {e}")
    traceback.print_exc()

print("\n=== 3. Testing mark offline ===")
try:
    m = db.query(Machine).filter(Machine.machine_id == 1).first()
    print(f"Machine 1: {m.machine_code}, status={m.status}")
    now = datetime.now(timezone.utc)
    downtime = MachineDowntime(
        machine_id=1,
        reason=DowntimeReason.unplanned_breakdown,
        start_time=now,
        end_time=now + timedelta(days=3650),
    )
    db.add(downtime)
    m.status = MachineStatus.offline
    db.commit()
    print("Mark offline: OK")
    # Restore
    m.status = MachineStatus.online
    db.query(MachineDowntime).filter(MachineDowntime.machine_id == 1).delete()
    db.commit()
    print("Restored")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
    db.rollback()

print("\n=== 4. Testing solver directly ===")
try:
    problem = build_scheduling_problem(db)
    if problem["jobs"]:
        config = OptimizationConfig(makespan_weight=2, tardiness_weight=4, max_solve_seconds=10.0)
        scheduler = FlexibleJobShopScheduler(problem, config)
        result = scheduler.solve()
        print(f"Solver result: status={result.status}, assignments={len(result.assignments)}")
    else:
        print("No jobs to solve")
except Exception as e:
    print(f"ERROR in solver: {e}")
    traceback.print_exc()

db.close()
