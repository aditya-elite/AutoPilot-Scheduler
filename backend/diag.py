"""Quick diagnostic: test optimize and override API endpoints."""
import urllib.request, urllib.parse, json, urllib.error

BASE = "http://localhost:8000"

# Login
form = urllib.parse.urlencode({"username": "manager", "password": "manager123"}).encode()
req = urllib.request.Request(BASE + "/auth/login", data=form, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
with urllib.request.urlopen(req) as r:
    tok = json.loads(r.read())
token = tok["access_token"]
auth = {"Authorization": f"Bearer {token}"}
print("Logged in OK")

# 1. Test optimize
try:
    req2 = urllib.request.Request(BASE + "/schedule/optimize",
                                   data=json.dumps({"goal": "balanced"}).encode(), method="POST")
    req2.add_header("Content-Type", "application/json")
    req2.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req2) as r2:
        print("Optimize OK:", json.loads(r2.read()))
except urllib.error.HTTPError as e:
    print("Optimize ERROR:", e.code, e.read().decode()[:600])

# 2. Get gantt & test override
try:
    req3 = urllib.request.Request(BASE + "/schedule/gantt", method="GET")
    req3.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req3) as r3:
        gantt = json.loads(r3.read())
    print(f"Gantt: {len(gantt)} assignments")
    if gantt:
        a = gantt[0]
        print(f"First: id={a['assignment_id']} machine={a['machine_id']} start={a['scheduled_start']}")
        payload = {
            "assignment_id": a["assignment_id"],
            "new_machine_id": a["machine_id"],
            "new_start": a["scheduled_start"]
        }
        req4 = urllib.request.Request(BASE + "/schedule/override",
                                       data=json.dumps(payload).encode(), method="POST")
        req4.add_header("Content-Type", "application/json")
        req4.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req4) as r4:
            print("Override OK:", json.loads(r4.read()).get("task_name"))
except urllib.error.HTTPError as e:
    print("Override ERROR:", e.code, e.read().decode()[:800])

# 3. Test mark offline (machine 1)
try:
    payload = {"reason": "unplanned_breakdown"}
    req5 = urllib.request.Request(BASE + "/breakdown/1/offline",
                                   data=json.dumps(payload).encode(), method="POST")
    req5.add_header("Content-Type", "application/json")
    req5.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req5) as r5:
        print("Mark offline OK:", json.loads(r5.read()).get("machine_code"))
except urllib.error.HTTPError as e:
    print("Mark offline ERROR:", e.code, e.read().decode()[:600])

# 4. Test delete machine (look for a deletable one first)
try:
    req6 = urllib.request.Request(BASE + "/machines", method="GET")
    req6.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req6) as r6:
        machines = json.loads(r6.read())
    print(f"Machines: {[m['machine_code'] for m in machines]}")
except urllib.error.HTTPError as e:
    print("Machines ERROR:", e.code, e.read().decode()[:300])
