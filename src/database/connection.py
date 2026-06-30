import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import logging

load_dotenv()

logger = logging.getLogger(__name__)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")


def get_engine():
    """Create and return a SQLAlchemy engine for the weather PostgreSQL database."""

    missing = [k for k, v in {
        "DB_USER": DB_USER, "DB_PASSWORD": DB_PASSWORD,
        "DB_HOST": DB_HOST, "DB_PORT": DB_PORT, "DB_NAME": DB_NAME
    }.items() if not v]

    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")

    url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(url, pool_pre_ping=True)

    # Validate connectivity at engine creation time
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully.")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to database: {e}")

    return engine
