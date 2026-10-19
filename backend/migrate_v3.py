"""
V3 Migration — Predictive Maintenance (failure-risk model) support.

Adds:
  * machines.age_years   (NUMERIC(4,1), NOT NULL, default 5)

Idempotent: safe to run more than once.

Usage:
    python migrate_v3.py
"""
from sqlalchemy import text
from app.database import engine


MIGRATION_SQL = """
-- Add age_years column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'machines' AND column_name = 'age_years'
    ) THEN
        ALTER TABLE machines ADD COLUMN age_years NUMERIC(4,1) NOT NULL DEFAULT 5;
    END IF;
END $$;
"""


def migrate():
    with engine.begin() as conn:
        conn.execute(text(MIGRATION_SQL))
    print("V3 migration complete:")
    print("   machines.age_years added")


if __name__ == "__main__":
    migrate()
