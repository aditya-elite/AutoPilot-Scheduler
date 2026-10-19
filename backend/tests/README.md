# Testing

`smoke_test.py` is a live end-to-end integration test — it exercises
the real running API against a real database: login, machine listing,
triggering an OR-Tools optimization, polling it to completion,
reading the resulting Gantt data, the breakdown simulator (mark a
machine offline and confirm the AI rerouted its tasks), restoring the
machine, a manual override, the operator status-update endpoint, both
analytics endpoints, and the admin user-management endpoints
(including confirming a non-admin gets a 403).

Run it against a live local instance:

```bash
# In one terminal:
uvicorn app.main:app --port 8000

# In another, from backend/:
python tests/smoke_test.py
```

It expects `seed_data.py` to have been run first so `manager` /
`manager123` exists and there are pending jobs to schedule.

This was used to catch and confirm the fix for two real bugs during
development: a passlib/bcrypt version incompatibility, and a
naive-vs-timezone-aware datetime crash in the scheduling repository.
For a CI pipeline, wrap this in pytest and point it at a disposable
test database rather than running it manually.
