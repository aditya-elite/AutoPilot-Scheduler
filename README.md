# AutoPilot Scheduler
### AI-Powered Production Scheduling for the Modern Factory Floor
> **Constraint Solving &bull; Predictive Maintenance &bull; Real-Time Re-Optimization**

[![CI](https://github.com/aditya-elite/AutoPilot-Scheduler/actions/workflows/ci.yml/badge.svg)](https://github.com/aditya-elite/AutoPilot-Scheduler/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB.svg?logo=react&logoColor=black)](https://vitejs.dev)
[![Google OR-Tools](https://img.shields.io/badge/Solver-OR--Tools%20CP--SAT-4285F4.svg?logo=google&logoColor=white)](https://developers.google.com/optimization)
[![scikit-learn](https://img.shields.io/badge/ML-scikit--learn-F7931E.svg?logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Container-Docker%20Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)

---

## 📌 The Problem: The Whiteboard Doesn't Scale

Manual production scheduling breaks down as factories grow:
* ⚠️ **Late Orders:** Due dates missed because schedules are built on gut feel, spreadsheets, and whiteboard estimates rather than mathematical optimization.
* ⏳ **Idle Machines:** Uneven workloads leave expensive equipment sitting unused while bottlenecks pile up elsewhere.
* 📉 **No Financial Visibility:** Factory leadership cannot see the true labor costs or profit risks of delays until it is too late to react.
* 🚨 **Reactive Chaos:** When a key machine breaks down, rescheduling takes hours of manual recalculation, stalling the entire shop floor.

---

## 🚀 The Solution: AutoPilot Scheduler

**AutoPilot Scheduler** is an intelligent production scheduling and operations platform designed for discrete manufacturers. Tell it what needs to be made and by when, and AutoPilot Scheduler:
1. **Computes the optimal schedule** across all available machines using Google OR-Tools CP-SAT.
2. **Predicts realistic job durations and equipment failures** using custom scikit-learn ML models.
3. **Pushes live adjustments** in real-time over WebSockets whenever disruptions occur.
4. **Calculates financial impact** (labor costs, profit at risk vs. profit on-time) live.

```
       [ Production Jobs & Due Dates ]
                      │
                      ▼
 ┌─────────────────────────────────────────┐
 │       Google OR-Tools CP-SAT            │ ◄─── [ ML Model 1: Realistic Job Durations ]
 │      Constraint Programming             │
 └────────────────────┬────────────────────┘
                      │ Optimal Assignments
                      ▼
 ┌─────────────────────────────────────────┐
 │          Live Gantt Schedule            │ ◄─── [ ML Model 2: Breakdown Risk Scoring ]
 │   (WebSocket Broadcast to All Roles)    │
 └────────────────────┬────────────────────┘
                      │
       ┌──────────────┴──────────────┐
       ▼                             ▼
[ Manager View ]             [ Operator View ]
• Full schedule & overrides  • Shift checklist & tasks
• Financial analytics        • Machine execution status
• Predictive maintenance
```

---

## ✨ Key Capabilities

### 1. Flexible Job-Shop Constraint Solver (Google OR-Tools CP-SAT)
* Mathematically evaluates all valid permutations to optimize machine utilization and order delivery.
* Simultaneously solves **machine allocation** and **precise start/end timings**.
* Balances multi-criteria objectives: minimizing makespan (total completion time) and tardiness penalties.

### 2. Machine Learning: Realistic Timing & Predictive Maintenance
* **Duration Predictor:** Learns from historical factory runs to predict realistic job durations based on machine characteristics and priority weights, feeding accurate inputs to the solver.
* **Failure Risk Scorer:** Continuously monitors machine runtime hours, days since last service, daily utilization %, and historical breakdown records.
* **Proactive Maintenance Window:** Flags high-risk machines (e.g., Press #4 at 82% risk) and lets managers schedule maintenance with one click, proactively re-optimizing the schedule before an unplanned breakdown occurs.

### 3. Real-Time Disruption Handling & WebSockets
* Click **"Mark Offline"** on any broken machine to simulate or report an outage.
* The system re-allocates affected jobs to alternate compatible machines within seconds and streams the new schedule live to all connected screens without requiring a page refresh.

### 4. Interactive Gantt Chart with Safe Manual Adjustments
* Drag and drop tasks directly on the interactive timeline.
* Automatic constraint and conflict verification: if a manager's manual move creates a collision or violates order precedence, the app immediately flags the issue.

### 5. Financial Impact & Executive Analytics
* Quantifies schedule performance in dollars:
  * **Profit On-Time:** Secured revenue from orders delivered before deadlines (e.g., $186K).
  * **Profit at Risk:** Potential penalties and revenue jeopardy from late orders (e.g., $24K).
  * **On-Time Completion Rate:** Real-time percentage indicator (e.g., 94%).
  * **Labor & Machine Cost Rollup:** Aggregated operational expenditures.

### 6. Role-Based Access Control (RBAC) & Audit Logging
* **Factory Manager:** Full schedule control, AI optimization triggers, financial analytics, manual task adjustments.
* **Shop-Floor Operator:** Clean, focused shift checklist of what job is next on each machine.
* **Administrator:** Complete user management, credential controls, and full audit logs of every automated optimization and manual override.
* **Reporting & Export:** Instant download of schedules and assignment matrices as CSV or PDF.

---

## 🛠️ Architecture & Tech Stack

| Layer | Technologies | Role / Responsibility |
|---|---|---|
| **Frontend** | React 18, Vite, Lucide Icons, Recharts | Interactive Gantt chart, live dashboard, dark UI |
| **Backend** | Python 3.11+, FastAPI, WebSockets | Async REST API, WebSocket pub/sub, auth, business logic |
| **Solver** | Google OR-Tools (CP-SAT) | Mathematical constraint programming engine |
| **Machine Learning** | scikit-learn, joblib, numpy, pandas | Duration estimation & predictive failure risk models |
| **Database** | PostgreSQL, SQLAlchemy 2.0 | Relational data persistence, foreign key constraints |
| **Containerization** | Docker, Docker Compose | One-command full-stack containerized deployment |
| **CI/CD** | GitHub Actions | Automated linting, schema validation, and smoke tests |

---

## 🚀 Quick Start Guide

### Option A: Running with Docker (Recommended)

Make sure you have [Docker](https://www.docker.com/) and Docker Compose installed.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aditya-elite/AutoPilot-Scheduler.git
   cd AutoPilot-Scheduler
   ```

2. **Start all services (Database, Backend, Frontend):**
   ```bash
   docker compose up --build
   ```

3. **In a separate terminal, seed demo data:**
   ```bash
   docker compose exec backend python seed_data.py
   ```

4. **Open in your browser:**
   * **Web App:** [http://localhost:5173](http://localhost:5173)
   * **Interactive API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option B: Local Manual Setup (Without Docker)

For detailed step-by-step local setup, see [`docs/SETUP.md`](docs/SETUP.md).

#### 1. Database (PostgreSQL)
```bash
createdb autopilot_scheduler
psql -d autopilot_scheduler -f schema.sql
```

#### 2. Backend (FastAPI)
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python seed_data.py
uvicorn app.main:app --reload --port 8000
```

#### 3. Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
Visit **http://localhost:5173** in your browser.

---

## 🔑 Pre-Configured Demo Accounts

Log in to explore the customized interface for each factory role:

| Username | Password | Role | Features Available |
|---|---|---|---|
| `manager` | `manager123` | **Factory Manager** | Full Gantt timeline, AI optimizer, predictive maintenance, financial metrics |
| `operator` | `operator123` | **Machine Operator** | Focused shift checklist, job step execution status |
| `admin` | `admin123` | **Administrator** | Manager access + user access control, audit logs, account creation |

---

## 💼 Business & Commercial Model

AutoPilot Scheduler is packaged for modern discrete manufacturing environments:
* **Business Model:** Tiered B2B SaaS subscription per factory line.
* **Starter Tier (₹1,200/mo):** Up to 10 machines, basic optimization, single site.
* **Growth Tier (₹3,500/mo):** Up to 40 machines, full ML predictive maintenance, WebSocket push, financial analytics.
* **Enterprise Tier (Custom):** Multi-site support, ERP/MES integrations (SAP, Siemens, Rockwell), custom SLAs, SSO, on-premise deployment.

---

## 👥 Team — Hack Forge

Developed by **Team Hack Forge**:
* **I ADITYA ANNAMALAI**
* **AAKASH B**
* **JEEVAN SAI V**
* **KAVIYA E**
* **JYOSHITHA D**
* **ASHWINKUMAR DHANASEKARAN**

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
