"""
Seed script: adds 2 demo jobs with tasks and triggers optimization.
Uses only Python stdlib (urllib) — no external packages needed.
Run with: python seed_demo.py
"""
import urllib.request, urllib.parse, json, sys

BASE = "http://localhost:8000"

def call(method, path, data=None, headers=None):
    url = BASE + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# 1. Login (form-encoded)
form = urllib.parse.urlencode({"username": "manager", "password": "manager123"}).encode()
req = urllib.request.Request(BASE + "/auth/login", data=form, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    with urllib.request.urlopen(req) as r:
        tok = json.loads(r.read())
except Exception as e:
    print("Login failed:", e); sys.exit(1)

auth = {"Authorization": f"Bearer {tok['access_token']}"}
print(f"✅ Logged in as {tok['role']}")

# 2. Fetch machines
status, machines = call("GET", "/machines", headers=auth)
print(f"✅ {len(machines)} machines found:")
for m in machines:
    print(f"   [{m['machine_id']}] {m['machine_code']} ({m['status']})")

# 3. Figure out machine IDs by type
cnc_ids   = [m["machine_id"] for m in machines if "CNC"   in m["machine_code"]]
lathe_ids = [m["machine_id"] for m in machines if "LATHE" in m["machine_code"]]
weld_ids  = [m["machine_id"] for m in machines if "WELD"  in m["machine_code"]]
asm_ids   = [m["machine_id"] for m in machines if "ASM"   in m["machine_code"]]
all_ids   = [m["machine_id"] for m in machines]

def pick(*lists):
    for lst in lists:
        if lst: return lst[:2]
    return all_ids[:2]

# 4. Create Job A
s, r = call("POST", "/jobs", headers=auth, data={
    "job_code": "SO-DEMO-001",
    "customer_name": "Bharat Forge Ltd",
    "priority": 1,
    "due_date": "2026-07-15T18:00:00",
    "tasks": [
        {"task_name": "Rough Turning",  "sequence_order": 1, "duration_minutes": 45, "eligible_machine_ids": pick(lathe_ids, cnc_ids)},
        {"task_name": "Finish Milling", "sequence_order": 2, "duration_minutes": 60, "eligible_machine_ids": pick(cnc_ids)},
        {"task_name": "Final Assembly", "sequence_order": 3, "duration_minutes": 30, "eligible_machine_ids": pick(asm_ids, all_ids[-1:])},
    ]
})
if s in (200, 201):
    print(f"✅ Created Job A: {r['job_code']} (id={r['job_id']})")
else:
    print(f"⚠️  Job A: {s} — {r}")

# 5. Create Job B
s, r = call("POST", "/jobs", headers=auth, data={
    "job_code": "SO-DEMO-002",
    "customer_name": "Tata Motors",
    "priority": 2,
    "due_date": "2026-07-14T17:00:00",
    "tasks": [
        {"task_name": "Lathe Prep",  "sequence_order": 1, "duration_minutes": 35, "eligible_machine_ids": pick(lathe_ids, cnc_ids)},
        {"task_name": "Weld Frame",  "sequence_order": 2, "duration_minutes": 50, "eligible_machine_ids": pick(weld_ids, all_ids)},
    ]
})
if s in (200, 201):
    print(f"✅ Created Job B: {r['job_code']} (id={r['job_id']})")
else:
    print(f"⚠️  Job B: {s} — {r}")

# 6. Trigger optimization
s, r = call("POST", "/schedule/optimize", headers=auth, data={"goal": "balanced"})
if s == 200:
    print(f"✅ Optimization Run #{r['run_id']} — status: {r['status']}")
else:
    print(f"⚠️  Optimize: {s} — {r}")

print("\n🎉 Done! Refresh the Master Schedule in your browser to see the Gantt chart.")
