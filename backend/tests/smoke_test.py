import json
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def call(method, path, token=None, data=None, form=False):
    url = BASE + path
    headers = {}
    body = None
    if data is not None:
        if form:
            body = data.encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


print("=== HEALTH ===")
print(call("GET", "/health"))

print("=== LOGIN ===")
status, body = call("POST", "/auth/login", data="username=manager&password=manager123", form=True)
print(status, body)
token = body["access_token"]

print("=== MACHINES ===")
status, machines = call("GET", "/machines", token=token)
print(status, len(machines), "machines")

print("=== TRIGGER OPTIMIZE ===")
status, run = call("POST", "/schedule/optimize", token=token, data={"goal": "balanced"})
print(status, run)
run_id = run["run_id"]

print("=== POLL RUN STATUS ===")
final = None
for i in range(10):
    time.sleep(2)
    status, run_status = call("GET", f"/schedule/runs/{run_id}", token=token)
    print(f"poll {i}: {run_status['status']}")
    if run_status["status"] in ("completed", "failed"):
        final = run_status
        break
print("final run status:", final)

print("=== GANTT ===")
status, gantt = call("GET", "/schedule/gantt", token=token)
print(status, f"{len(gantt)} assignments")
for a in gantt[:6]:
    print(" -", a["job_code"], a["task_name"], "on", a["machine_code"], a["scheduled_start"], "->", a["scheduled_end"])

print("=== BREAKDOWN SIMULATOR: mark CNC-01 offline ===")
machine_id = next(m["machine_id"] for m in machines if m["machine_code"] == "CNC-01")
status, resp = call("POST", f"/breakdown/{machine_id}/offline", token=token, data={"reason": "unplanned_breakdown", "notes": "test"})
print(status, resp)

print("=== WAIT FOR RE-SOLVE ===")
time.sleep(8)
status, gantt2 = call("GET", "/schedule/gantt", token=token)
on_cnc1 = [a for a in gantt2 if a["machine_code"] == "CNC-01" and a["status"] in ("planned", "confirmed", "in_progress")]
print(f"Assignments still on CNC-01 after marking offline: {len(on_cnc1)} (should be 0)")

print("=== RESTORE CNC-01 ===")
status, resp = call("POST", f"/breakdown/{machine_id}/online", token=token)
print(status, resp)

print("=== MANUAL OVERRIDE ===")
if gantt2:
    target = gantt2[0]
    other_machine = next(m for m in machines if m["machine_id"] != target["machine_id"])
    status, override_resp = call("POST", "/schedule/override", token=token, data={
        "assignment_id": target["assignment_id"],
        "new_machine_id": other_machine["machine_id"],
        "new_start": target["scheduled_start"],
    })
    print(status, override_resp)

print("=== OPERATOR STATUS UPDATE ===")
if gantt2:
    aid = gantt2[0]["assignment_id"]
    status, resp = call("PATCH", f"/schedule/assignments/{aid}/status", token=token, data={"status": "in_progress"})
    print(status, resp.get("status"))

print("=== ANALYTICS: utilization ===")
status, util = call("GET", "/analytics/utilization", token=token)
print(status, util)

print("=== ANALYTICS: audit log ===")
status, audit = call("GET", "/analytics/audit-log?limit=10", token=token)
print(status, f"{len(audit)} entries")
for entry in audit[:5]:
    print(" -", entry["entity_type"], entry["action"], entry["changed_by_name"])

print("=== ADMIN: login as admin ===")
status, admin_login = call("POST", "/auth/login", data="username=admin&password=admin123", form=True)
print(status, admin_login.get("role"))
admin_token = admin_login["access_token"]

print("=== ADMIN: manager should be forbidden from /admin/users ===")
status, resp = call("GET", "/admin/users", token=token)
print(status, "(expect 403)", resp)

print("=== ADMIN: list users ===")
status, users_list = call("GET", "/admin/users", token=admin_token)
print(status, f"{len(users_list)} users")

print("=== ADMIN: create a new operator account ===")
new_username = f"night_shift_operator_{int(time.time())}"
status, new_user = call("POST", "/admin/users", token=admin_token, data={
    "username": new_username,
    "password": "nightshift123",
    "full_name": "Test Night Operator",
    "role": "machine_operator",
})
print(status, new_user)

print("=== ADMIN: deactivate the new account ===")
if status == 201:
    status, updated = call("PATCH", f"/admin/users/{new_user['user_id']}", token=admin_token, data={"is_active": False})
    print(status, updated)

print("\nALL SMOKE TESTS COMPLETED")
