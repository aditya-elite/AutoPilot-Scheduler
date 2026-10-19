import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

logger = logging.getLogger("autopilot.database")

def init_engine():
    db_url = settings.database_url
    try:
        if "postgresql" in db_url:
            eng = create_engine(db_url, pool_pre_ping=True)
            with eng.connect() as conn:
                logger.info(f"Connected to primary database successfully ({db_url.split('@')[-1]}).")
            return eng
    except Exception as e:
        logger.warning(f"Could not connect to configured database ({e}). Falling back to SQLite database.")
    
    sqlite_url = "sqlite:///./autopilot_scheduler.db"
    eng = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    logger.info(f"Using fallback SQLite database: {sqlite_url}")
    return eng

engine = init_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

