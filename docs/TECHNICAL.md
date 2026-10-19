# Technical reference

For the plain-language overview, see the main [README](../README.md).
This document is for anyone working on the codebase.

## Stack

- **Backend**: FastAPI + SQLAlchemy (PostgreSQL), JWT auth with
  role-based access, WebSockets for live schedule push.
- **Scheduling engine**: Google OR-Tools CP-SAT, modeling a flexible
  job-shop problem (each task can run on more than one eligible
  machine, each with its own processing time).
- **ML**: two scikit-learn models —
  - `duration_model.py` predicts realistic task durations per
    (task, machine) pair from `base_duration_minutes`, `machine_type`,
    `job_priority_weight`, and the target machine's
    `failure_risk_score`.
  - `failure_model.py` predicts each machine's probability of
    breaking down soon, from `hours_since_last_maintenance`,
    `average_daily_utilization_pct`, `age_years`, and
    `historical_breakdown_count`.
  Both are trained on synthetic data on first use and cached to
  `backend/app/ml/artifacts/` (gitignored) — see "ML models" below for
  how to point them at real data instead.
- **Frontend**: React + Vite, Fluent/Aurora dark UI, drag-and-drop
  Gantt chart, recharts for gauges.

## Project layout

```
autopilot-scheduler/
├── .github/workflows/ci.yml    # CI: backend smoke test + frontend lint/build
├── schema.sql                  # PostgreSQL schema (run once)
├── docker-compose.yml          # One-command local stack
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app entrypoint
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   ├── schemas.py          # Pydantic request/response shapes
│   │   ├── security.py         # JWT auth + role-based access
│   │   ├── config.py           # Settings (env-driven)
│   │   ├── database.py         # DB session management
│   │   ├── websocket_manager.py
│   │   ├── ml/
│   │   │   ├── duration_model.py    # Predicts realistic task durations
│   │   │   ├── failure_model.py     # Predicts machine breakdown risk
│   │   │   └── feature_builder.py   # DB rows -> model feature dicts
│   │   ├── solver/
│   │   │   └── job_shop_solver.py   # OR-Tools CP-SAT flexible job-shop engine
│   │   ├── repositories/
│   │   │   ├── scheduling_repo.py   # DB <-> solver data bridge
│   │   │   └── analytics_repo.py    # Utilization % and financial summary (GET /analytics/financials)
│   │   └── routers/
│   │       ├── auth.py, machines.py, jobs.py, schedule.py,
│   │       │ breakdown.py, analytics.py, live.py, users.py (admin)
│   ├── tests/
│   │   └── smoke_test.py        # Live end-to-end integration test
│   ├── seed_data.py             # Populates demo users/machines/jobs
│   ├── migrate_v2.py            # Adds Google sign-in / forgot-password support
│   ├── migrate_v3.py            # Adds machines.age_years (predictive maintenance)
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx, main.jsx
    │   ├── pages/               # Login, ManagerDashboard, OperatorView,
    │   │                          Analytics, Admin, ...
    │   ├── components/          # GanttChart, AIControlCenter, BreakdownSimulator, ...
    │   ├── context/AuthContext.jsx
    │   ├── hooks/useScheduleSocket.js
    │   ├── api/client.js
    │   └── styles/global.css    # Fluent + Aurora dark theme
    └── package.json
```

## Roles

- `factory_manager` — full schedule control: run optimizations,
  override assignments, apply demo presets, manage jobs/machines.
- `machine_operator` — read-only schedule, can update their own
  assignment status (`in_progress` / `completed`).
- `admin` — everything a manager has, plus `/admin/users` (create,
  deactivate, change roles).

## ML models: how they're wired in

- `scheduling_repo.build_scheduling_problem()` batches a duration
  prediction for every (task, eligible machine) pair before each solve
  and feeds those predictions to the CP-SAT solver instead of the raw
  eligibility-table estimate.
- `scheduling_repo.persist_solution()` writes the predicted duration
  for whichever machine was actually chosen back onto
  `tasks.predicted_duration_minutes`.
- `GET /breakdown/risk` returns the currently stored
  `failure_risk_score` per machine plus the raw signals behind it.
  `POST /breakdown/risk/recompute` (factory_manager only) re-runs the
  model over live machine data and persists fresh scores.
- `POST /breakdown/{machine_id}/schedule-maintenance` (factory_manager
  only) is the proactive follow-up action: takes a machine offline for
  a bounded window (default 4h, `MachineDowntime.reason =
  predicted_failure_risk`) instead of the breakdown simulator's
  indefinite outage, then triggers the same bounded re-optimization.
  Ending it early reuses the existing `POST /breakdown/{machine_id}/online`.
- Both models currently train on synthetic data
  (`generate_synthetic_training_data()` in each `ml/*.py` file). To use
  real data instead, replace that function's output with a query
  against completed `assignments` (actual vs. scheduled duration) for
  the duration model, and real breakdown history for the failure
  model, then delete `backend/app/ml/artifacts/*.joblib` so the next
  call retrains.

## Live updates (WebSocket)

`backend/app/websocket_manager.py` broadcasts to every connected
`/ws/schedule` client whenever a re-optimization completes *or fails*,
a manual override is validated, or a machine's status changes. Because these
events are fired from synchronous route handlers and `BackgroundTasks`
jobs (which run in worker threads, not the main asyncio event loop),
`broadcast_sync()` schedules the actual send onto the real serving
loop via `asyncio.run_coroutine_threadsafe` — the main loop reference
is captured once at startup (`main.py`'s `startup_capture_event_loop`).
Using `asyncio.run()` there instead would silently create a disconnected
throwaway loop and no client would ever receive the message.

Event types currently emitted: `schedule_updated` (with `reason` of
`optimization_complete` / `manual_override` / `status_update`),
`optimization_failed` (carries `error_message` + `blockers`), and
`machine_status_changed` (carries `machine_code` + `status`).

`optimization_failed` matters more than it looks: a re-solve triggered
by a breakdown or scheduled maintenance has no caller polling for its
result, so if that solve fails (e.g. taking a machine offline leaves a
task with no eligible machine), nothing would otherwise tell the user
the schedule is now stale — they'd only find out by digging through
run history.

On the frontend, `frontend/src/context/NotificationContext.jsx` keeps
its own subscription via `useScheduleSocket` so the notification bell
updates app-wide regardless of which page is open, in addition to
`ManagerDashboard.jsx`/`OperatorView.jsx`'s own page-level reactions to
the same events. Those two pages only react to `schedule_updated` and
`machine_status_changed`, so adding new event types is backward-safe —
unknown types are ignored rather than mishandled.

## Continuous Integration

`.github/workflows/ci.yml` runs on every push/PR:
- **backend job**: spins up a real Postgres service container, applies
  `schema.sql`, seeds demo data, boots the actual FastAPI server, and
  runs `tests/smoke_test.py` against it — a live end-to-end test, not
  just an import check.
- **frontend job**: `npm run lint` (eslint) and `npm run build`.

## Known limitations / follow-ups

- `POST /schedule/preset`'s demo-reset branches do multi-step
  delete/recreate across several separate commits with no enclosing
  transaction — a failure mid-sequence can leave the database
  half-reset. Low risk in normal demo use, but not production-safe.
- `BackgroundTasks` is used for the solver run instead of a real task
  queue (Celery/RQ/arq) — a solve won't survive a backend restart or
  be cancellable mid-run.
- The in-memory `ConnectionManager` (`websocket_manager.py`) only
  works with a single backend process; move it to Redis pub/sub before
  scaling out.
- `JWT_SECRET_KEY` and other secrets live in `.env` — use a real
  secrets manager before any production deployment.
- `npm audit` flags transitive vulnerabilities in `dompurify` (via
  `jspdf`) and `esbuild` (via Vite's dev server). Neither is
  exploitable as this app uses them today (jsPDF only renders data
  this app already trusts; the esbuild advisory only affects the local
  dev server, not the production build), but both only resolve via
  major-version bumps that haven't been regression-tested here.
