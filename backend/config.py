import os
from pathlib import Path

from dotenv import load_dotenv

# .env lives in the project root, one folder above "backend"
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60
    ALLOW_DEV_LOGIN = os.getenv("ALLOW_DEV_LOGIN", "false").lower() == "true"
    ATTENDANCE_CLOSING_TIME = os.getenv("ATTENDANCE_CLOSING_TIME", "17:00")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    COLLEGE_START_TIME = os.getenv("COLLEGE_START_TIME", "09:00")
    LATE_CUTOFF_TIME = os.getenv("LATE_CUTOFF_TIME", "11:00")
    FULL_DAY_HOURS = float(os.getenv("FULL_DAY_HOURS", "6"))
    HALF_DAY_HOURS = float(os.getenv("HALF_DAY_HOURS", "3"))
    WEEKLY_OFF_DAYS = [int(x) for x in os.getenv("WEEKLY_OFF_DAYS", "6").split(",") if x.strip()]

    @classmethod
    def validate(cls):
        """Stop early with a clear message if something is missing in .env."""
        required = ["SECRET_KEY", "DB_USER", "DB_PASSWORD", "DB_NAME"]
        missing = [name for name in required if not getattr(cls, name)]
        if missing:
            raise RuntimeError(
                "Missing values in .env file: " + ", ".join(missing)
            )