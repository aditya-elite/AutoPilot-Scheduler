import os
from dotenv import load_dotenv
load_dotenv()

from app.database import engine, SessionLocal
from app.models import Base
import seed_data

def fix():
    print("Dropping all existing tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Recreating tables from SQLAlchemy models...")
    Base.metadata.create_all(bind=engine)
    
    print("Seeding database...")
    seed_data.seed()

if __name__ == "__main__":
    fix()
