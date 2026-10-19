"""
V2 Migration — Google Sign-In + Forgot Password support.

Adds:
  * users.email            (VARCHAR 255, UNIQUE, nullable)
  * users.email_verified   (BOOLEAN, default FALSE)
  * users.google_id        (VARCHAR 128, UNIQUE, nullable)
  * password_reset_otps    (new table)

Idempotent: safe to run more than once.

Usage:
    python migrate_v2.py
"""
from sqlalchemy import text
from app.database import engine


MIGRATION_SQL = """
-- Add email column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'email'
    ) THEN
        ALTER TABLE users ADD COLUMN email VARCHAR(255) UNIQUE;
    END IF;
END $$;

-- Add email_verified column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'email_verified'
    ) THEN
        ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END $$;

-- Add google_id column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'google_id'
    ) THEN
        ALTER TABLE users ADD COLUMN google_id VARCHAR(128) UNIQUE;
    END IF;
END $$;

-- Make password_hash nullable for Google-only users
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;

-- Create OTP table if not exists
CREATE TABLE IF NOT EXISTS password_reset_otps (
    otp_id      BIGSERIAL PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    otp_code    VARCHAR(6) NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_otp_user ON password_reset_otps (user_id, expires_at);
"""


def migrate():
    with engine.begin() as conn:
        conn.execute(text(MIGRATION_SQL))
    print("V2 migration complete:")
    print("   users.email, users.email_verified, users.google_id added")
    print("   password_reset_otps table created")


if __name__ == "__main__":
    migrate()
