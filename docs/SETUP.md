# Manual setup (no Docker)

This walks through starting the database, the server, and the website
one at a time, in three separate terminal windows.

## 1. Database

Install PostgreSQL locally, then create the database and load the
blueprint (`schema.sql`) into it:

```bash
createdb autopilot_scheduler
psql -d autopilot_scheduler -f schema.sql
```

## 2. Server (backend)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # edit DATABASE_URL if needed
python seed_data.py              # loads example jobs/machines/users
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** to confirm the server is running —
you should see an interactive API documentation page.

If you're using VS Code: open the `backend` folder, select the `venv`
interpreter (`Ctrl+Shift+P` → "Python: Select Interpreter"), then run
the command above from the integrated terminal.

## 3. Website (frontend)

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The website talks to the server
running on port 8000, so both need to be running at the same time.

## Keeping the database schema up to date

Occasionally a new feature needs a small addition to the database. If
you already have data you don't want to lose, run the matching
migration script instead of recreating the database from scratch, e.g.:

```bash
cd backend
python migrate_v2.py
python migrate_v3.py
```

These are safe to run more than once — they only add what's missing.
