"""Get exact 500 error tracebacks from backend."""
import urllib.request, urllib.parse, json, urllib.error

BASE = "http://localhost:8000"

form = urllib.parse.urlencode({"username": "manager", "password": "manager123"}).encode()
req = urllib.request.Request(BASE + "/auth/login", data=form, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
with urllib.request.urlopen(req) as r:
    tok = json.loads(r.read())
token = tok["access_token"]

tests = [
    ("POST", "/schedule/optimize", {"goal": "balanced"}),
    ("POST", "/schedule/override", {"assignment_id": 1, "new_machine_id": 1, "new_start": "2026-08-10T11:00:00"}),
    ("POST", "/breakdown/1/offline", {"reason": "unplanned_breakdown"}),
    ("DELETE", "/machines/6", None),
]

for method, path, body in tests:
    try:
        data = json.dumps(body).encode() if body else None
        req2 = urllib.request.Request(BASE + path, data=data, method=method)
        req2.add_header("Authorization", f"Bearer {token}")
        if body:
            req2.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req2) as r2:
            print(f"{method} {path}: OK")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f"\n{method} {path}: HTTP {e.code}")
        print(body_text[:1000])
