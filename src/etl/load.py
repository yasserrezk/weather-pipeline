from src.database.connection import get_engine
import logging
from sqlalchemy import engine, text

logger = logging.getLogger(__name__)


def load_data(df):
    """Load a cleaned DataFrame into the weather_forecasts PostgreSQL table."""

    if df is None or df.empty:
        raise ValueError("Cannot load empty or None DataFrame into the database.")

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE weather_forecasts"))
        conn.commit()
    
    df.to_sql("weather_forecasts", engine, if_exists="append", index=False)
    logger.info("Loaded %d rows into 'weather_forecasts' table.", len(df))
