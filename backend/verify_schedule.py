from app.database import SessionLocal
from app.models import Assignment, Task, Job, Machine
from datetime import timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
db = SessionLocal()

jobs = db.query(Job).filter(Job.job_code.like("SO-EVE-%")).all()
print("Jobs scheduled today (times in IST):\n")
for j in jobs:
    print(f"  {j.job_code}: {j.description}")
    for t in sorted(j.tasks, key=lambda x: x.sequence_index):
        for a in t.assignments:
            m = db.query(Machine).get(a.machine_id)
            s = a.scheduled_start.replace(tzinfo=timezone.utc).astimezone(IST)
            e = a.scheduled_end.replace(tzinfo=timezone.utc).astimezone(IST)
            dur = int((a.scheduled_end - a.scheduled_start).total_seconds() // 60)
            flag = "OK" if e.hour < 22 else "LATE!"
            print(f"    [{t.sequence_index+1}] {t.task_name:<36} {m.machine_code:<12} {s.strftime('%H:%M')} -> {e.strftime('%H:%M')} IST  ({dur}m) [{flag}]")
    print()

db.close()
