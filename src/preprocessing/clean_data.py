import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Updated to match the API keys we are saving into the database
REQUIRED_COLUMNS = {
    "time",
    "temperature_2m",
    "relative_humidity_2m",
    "rain",
    "uv_index",
    "is_day",
    "sunshine_duration",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation_probability",
    "surface_pressure",
    "cloud_cover",
    "visibility",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
}

# Mapping API names to your exact PostgreSQL column names
RENAME_MAP = {"time": "forecast_time"}


def clean_weather(data):
    """Parse, validate, add location metadata, and clean the raw API payload

    to fit the single-table PostgreSQL schema.
    """
    if not data or "hourly" not in data:
        raise ValueError("Input data is missing the 'hourly' key.")

    hourly = data["hourly"]

    # 1. Validate required hourly time-series columns
    missing = REQUIRED_COLUMNS - set(hourly.keys())
    if missing:
        raise ValueError(f"API response is missing expected columns: {missing}")

    # 2. Build the initial DataFrame from hourly array data
    df = pd.DataFrame(hourly)
    df.rename(columns=RENAME_MAP, inplace=True)

    # 3. Inject the root-level location metadata into every row
    df["latitude"] = data.get("latitude")
    df["longitude"] = data.get("longitude")
    df["timezone"] = data.get("timezone", "Africa/Cairo")
    df["elevation"] = data.get("elevation")

    # Optional: Hardcode or extract the model if necessary
    df["model_used"] = "best_match"

    # 4. Handle Data Types for PostgreSQL compatibility
    df["forecast_time"] = pd.to_datetime(df["forecast_time"])

    # Convert 1/0 to true native Booleans for PostgreSQL BOOLEAN column
    if "is_day" in df.columns:
        df["is_day"] = df["is_day"].astype(bool)

    # 5. Clean missing values
    before = len(df)
    df.dropna(
        subset=["forecast_time", "latitude", "longitude"], inplace=True
    )  # Keep rows unless critical composite keys are missing
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d rows with null key values.", dropped)

    logger.info("Cleaned weather data: %d rows retained.", len(df))
    return df
