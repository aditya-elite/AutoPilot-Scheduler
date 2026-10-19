"""
Centralized app configuration. All values are overridable via
environment variables or a `.env` file, so nothing sensitive is
hardcoded — this is the FIRST thing to check in a security review.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    database_url: str = "postgresql://autopilot:autopilot@localhost:5432/autopilot_scheduler"

    # --- Auth ---
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_A_LONG_RANDOM_STRING"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8  # 8 hour shifts

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173"

    # --- Solver ---
    default_solve_time_limit_seconds: float = 20.0


settings = Settings()
