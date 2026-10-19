import traceback
from app.database import SessionLocal
from app.models import User, Machine, Assignment, Task, Job
from app.routers.schedule import trigger_optimize, manual_override, OptimizeRequest, ManualOverrideRequest
from app.routers.breakdown import mark_machine_offline, MachineOfflineRequest
from fastapi import BackgroundTasks
import uuid

db = SessionLocal()
user = db.query(User).first()
print(f"Test user: {user.username}, id={user.user_id}")

bg = BackgroundTasks()

print("\n--- Testing trigger_optimize ---")
try:
    req = OptimizeRequest(goal="balanced")
    res = trigger_optimize(request=req, background_tasks=bg, db=db, user=user)
    print("trigger_optimize SUCCESS:", res)
except Exception as e:
    print("trigger_optimize FAILED:")
    traceback.print_exc()

print("\n--- Testing manual_override ---")
try:
    a = db.query(Assignment).first()
    if a:
        req = ManualOverrideRequest(assignment_id=a.assignment_id, new_machine_id=a.machine_id, new_start=a.scheduled_start)
        res = manual_override(request=req, db=db, user=user)
        print("manual_override SUCCESS:", res)
    else:
        print("No assignment found")
except Exception as e:
    print("manual_override FAILED:")
    traceback.print_exc()

print("\n--- Testing mark_machine_offline ---")
try:
    m = db.query(Machine).first()
    if m:
        req = MachineOfflineRequest(reason="unplanned_breakdown")
        res = mark_machine_offline(machine_id=m.machine_id, request=req, background_tasks=bg, db=db, user=user)
        print("mark_machine_offline SUCCESS:", res)
    else:
        print("No machine found")
except Exception as e:
    print("mark_machine_offline FAILED:")
    traceback.print_exc()

db.close()
