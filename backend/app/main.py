import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import auth, machines, jobs, schedule, breakdown, analytics, live, users
from app.websocket_manager import set_main_loop
from seed_data import seed

logger = logging.getLogger("autopilot.main")

app = FastAPI(
    title="AutoPilot Scheduler API",
    description="AI-driven production scheduling engine — OR-Tools CP-SAT + ML duration/failure prediction.",
    version="0.1.0",
)

@app.on_event("startup")
def startup_db_init():
    try:
        logger.info("Initializing database schema...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized.")
        seed()
    except Exception as e:
        logger.error(f"Error during DB startup initialization: {e}")


@app.on_event("startup")
async def startup_capture_event_loop():
    # Must be an ASYNC startup handler so this runs ON the real
    # serving event loop (sync `def` startup handlers run in a worker
    # thread instead) — see websocket_manager.broadcast_sync.
    set_main_loop(asyncio.get_running_loop())

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(machines.router)
app.include_router(jobs.router)
app.include_router(schedule.router)
app.include_router(breakdown.router)
app.include_router(analytics.router)
app.include_router(live.router)
app.include_router(users.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "autopilot-scheduler-api", "db_connected": True}

