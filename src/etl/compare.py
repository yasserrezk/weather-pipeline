"""
compare.py
----------
Compares the current weather_forecasts table in PostgreSQL against a freshly
transformed DataFrame (output of clean_weather) and produces a structured
diff report covering:

  - New rows      : in df_new but not in DB  → will be inserted
  - Existing rows : already in DB, no action needed
  - Changed rows  : same key (lat, lon, forecast_time) but different values
  - Stale rows    : in DB but missing from df_new (old forecasts no longer returned)

Usage (standalone):
    python -m src.etl.compare

Usage (in DAG / other modules):
    from src.etl.compare import compare_with_db, print_report
    report = compare_with_db(df_transformed)
    print_report(report)
"""

import logging
import os
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import text

from src.database.connection import get_engine

logger = logging.getLogger(__name__)

TABLE_NAME = "weather_forecasts"

# Composite key that uniquely identifies a forecast row
KEY_COLS = ["latitude", "longitude", "forecast_time"]

# Numeric columns to check for value drift
NUMERIC_COLS = [
    "temperature_2m",
    "apparent_temperature",
    "dew_point_2m",
    "relative_humidity_2m",
    "rain",
    "precipitation_probability",
    "surface_pressure",
    "cloud_cover",
    "visibility",
    "uv_index",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "sunshine_duration",
]

# Tolerance for floating-point comparisons (e.g. 0.1 °C difference is noise)
NUMERIC_TOLERANCE = 0.05


# ── Result dataclass ──────────────────────────────────────────────────────────


@dataclass
class CompareReport:
    total_new_rows: int = 0
    total_db_rows: int = 0

    new_count: int = 0  # to be inserted
    existing_count: int = 0  # identical, no action
    changed_count: int = 0  # same key, different values
    stale_count: int = 0  # in DB but not in new batch

    new_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    existing_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    changed_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    stale_rows: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Per-column drift summary for changed rows
    column_drift: dict = field(default_factory=dict)

    # The normalised df_new — ready to pass directly to load_data()
    df_new: pd.DataFrame = field(default_factory=pd.DataFrame)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalise_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce key columns to exact types required for merging.

    API JSON attaches lat/lon as Python floats but pandas may infer them
    as object dtype when the column is built via df[col] = scalar.
    pd.to_numeric + explicit float64 cast avoids the merge type-mismatch.
    """
    df = df.copy()
    df["latitude"] = (
        pd.to_numeric(df["latitude"], errors="coerce").astype("float64").round(5)
    )
    df["longitude"] = (
        pd.to_numeric(df["longitude"], errors="coerce").astype("float64").round(5)
    )
    df["forecast_time"] = pd.to_datetime(df["forecast_time"], utc=True)
    return df


def _table_exists(engine) -> bool:
    """Return True if weather_forecasts exists in the public schema."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name   = :tname
            )
        """),
            {"tname": TABLE_NAME},
        )
        return result.scalar()


def _create_table(engine) -> None:
    """Create weather_forecasts from schema.sql if it doesn't exist."""
    schema_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")
    )
    with open(schema_path, "r") as f:
        ddl = f.read()

    with engine.begin() as conn:
        conn.execute(text(ddl))

    logger.info("%s table created from schema.sql.", TABLE_NAME)


def _load_db_slice(
    engine, lat: float, lon: float, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """
    Pull only the rows from DB that overlap with the new batch's
    time window and location. If the table doesn't exist, create it
    and return an empty DataFrame so the pipeline continues cleanly.
    """
    if not _table_exists(engine):
        logger.warning(
            "%s table not found — creating it now from schema.sql.", TABLE_NAME
        )
        _create_table(engine)
        return pd.DataFrame()

    query = text(f"""
        SELECT *
        FROM {TABLE_NAME}
        WHERE latitude      = :lat
          AND longitude     = :lon
          AND forecast_time BETWEEN :start AND :end
        ORDER BY forecast_time
    """)
    with engine.connect() as conn:
        df_db = pd.read_sql(
            query,
            conn,
            params={
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "start": start,
                "end": end,
            },
        )

    if not df_db.empty:
        df_db["forecast_time"] = pd.to_datetime(df_db["forecast_time"], utc=True)
        df_db["latitude"] = (
            pd.to_numeric(df_db["latitude"], errors="coerce").astype("float64").round(5)
        )
        df_db["longitude"] = (
            pd.to_numeric(df_db["longitude"], errors="coerce")
            .astype("float64")
            .round(5)
        )

    return df_db


def _column_drift(df_changed: pd.DataFrame) -> dict:
    """
    For each numeric column in changed rows compute:
      - how many rows differ beyond tolerance
      - mean absolute difference
      - max absolute difference
    """
    drift = {}
    for col in NUMERIC_COLS:
        old_col = f"{col}_db"
        new_col = f"{col}_new"
        if old_col not in df_changed.columns or new_col not in df_changed.columns:
            continue
        diff = (df_changed[new_col] - df_changed[old_col]).abs().dropna()
        changed_in_col = (diff > NUMERIC_TOLERANCE).sum()
        if changed_in_col > 0:
            drift[col] = {
                "rows_changed": int(changed_in_col),
                "mean_abs_diff": round(float(diff[diff > NUMERIC_TOLERANCE].mean()), 4),
                "max_abs_diff": round(float(diff.max()), 4),
            }
    return drift


# ── Main comparison ───────────────────────────────────────────────────────────


def compare_with_db(df_new: pd.DataFrame, engine=None) -> CompareReport:
    """
    Compare a transformed DataFrame against weather_forecasts and return
    a CompareReport.

    Parameters
    ----------
    df_new : pd.DataFrame
        Output of clean_weather() — the freshly transformed batch.
    engine : SQLAlchemy engine, optional
        Uses get_engine() if not provided.

    Returns
    -------
    CompareReport
    """
    if df_new is None or df_new.empty:
        raise ValueError("df_new is empty — nothing to compare.")

    engine = engine or get_engine()
    df_new = _normalise_keys(df_new)
    report = CompareReport(total_new_rows=len(df_new))

    lat = float(df_new["latitude"].iloc[0])
    lon = float(df_new["longitude"].iloc[0])
    start = df_new["forecast_time"].min()
    end = df_new["forecast_time"].max()

    logger.info(
        "Comparing %d new rows against %s for (lat=%.5f, lon=%.5f) from %s to %s",
        len(df_new),
        TABLE_NAME,
        lat,
        lon,
        start,
        end,
    )

    df_db = _load_db_slice(engine, lat, lon, start, end)
    report.total_db_rows = len(df_db)

    # ── DB window is empty — everything is new ────────────────────────────
    if df_db.empty:
        logger.info(
            "No existing rows in DB for this window — all %d rows are new.", len(df_new)
        )
        report.new_count = len(df_new)
        report.new_rows = df_new
        report.df_new = df_new
        return report

    # ── Merge on composite key ────────────────────────────────────────────
    merged = df_new.merge(
        df_db,
        on=KEY_COLS,
        how="outer",
        indicator=True,
        suffixes=("_new", "_db"),
    )

    # New rows — in df_new only
    mask_new = merged["_merge"] == "left_only"
    report.new_rows = df_new[
        df_new.set_index(KEY_COLS).index.isin(
            merged.loc[mask_new].set_index(KEY_COLS).index
        )
    ].reset_index(drop=True)
    report.new_count = len(report.new_rows)

    # Stale rows — in DB only
    mask_stale = merged["_merge"] == "right_only"
    stale_keys = merged.loc[mask_stale, KEY_COLS]
    report.stale_rows = df_db.merge(stale_keys, on=KEY_COLS, how="inner").reset_index(
        drop=True
    )
    report.stale_count = len(report.stale_rows)

    # Matched rows — check for value drift
    matched = merged[merged["_merge"] == "both"].copy()
    if matched.empty:
        return report

    any_changed = pd.Series(False, index=matched.index)
    for col in NUMERIC_COLS:
        old_col = f"{col}_db"
        new_col = f"{col}_new"
        if old_col in matched.columns and new_col in matched.columns:
            diff = (matched[new_col] - matched[old_col]).abs()
            any_changed = any_changed | (diff > NUMERIC_TOLERANCE).fillna(False)

    if "is_day_new" in matched.columns and "is_day_db" in matched.columns:
        any_changed = any_changed | (
            matched["is_day_new"] != matched["is_day_db"]
        ).fillna(False)

    report.changed_rows = matched[any_changed].reset_index(drop=True)
    report.changed_count = len(report.changed_rows)
    report.existing_rows = matched[~any_changed].reset_index(drop=True)
    report.existing_count = len(report.existing_rows)

    if not report.changed_rows.empty:
        report.column_drift = _column_drift(report.changed_rows)

    logger.info(
        "Compare complete: %d new | %d existing | %d changed | %d stale",
        report.new_count,
        report.existing_count,
        report.changed_count,
        report.stale_count,
    )
    report.df_new = df_new
    return report


# ── Pretty printer ────────────────────────────────────────────────────────────


def print_report(report: CompareReport, show_rows: int = 5) -> None:
    """Print a human-readable summary of a CompareReport."""
    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  {TABLE_NAME.upper()} — COMPARE REPORT")
    print(bar)
    print(f"  New batch rows   : {report.total_new_rows:>6,}")
    print(f"  DB rows (window) : {report.total_db_rows:>6,}")
    print(bar)
    print(f"  🟢 New (to insert)  : {report.new_count:>6,}")
    print(f"  ✅ Existing (match) : {report.existing_count:>6,}")
    print(f"  🟡 Changed (drift)  : {report.changed_count:>6,}")
    print(f"  🔴 Stale (DB only)  : {report.stale_count:>6,}")
    print(bar)

    if report.new_count > 0:
        print(f"\n── New rows (first {show_rows}) ──")
        print(
            report.new_rows[KEY_COLS + ["temperature_2m", "rain", "uv_index"]]
            .head(show_rows)
            .to_string(index=False)
        )

    if report.changed_count > 0:
        print(f"\n── Changed rows (first {show_rows}) ──")
        key_plus = KEY_COLS + [
            c
            for c in report.changed_rows.columns
            if c.endswith("_new") or c.endswith("_db")
        ]
        print(report.changed_rows[key_plus].head(show_rows).to_string(index=False))

        print("\n── Column drift summary ──")
        if report.column_drift:
            for col, stats in report.column_drift.items():
                print(
                    f"  {col:<30} "
                    f"rows={stats['rows_changed']:>4}  "
                    f"mean_Δ={stats['mean_abs_diff']:>7}  "
                    f"max_Δ={stats['max_abs_diff']:>7}"
                )
        else:
            print("  (no numeric drift detected)")

    if report.stale_count > 0:
        print(f"\n── Stale rows in DB not in new batch (first {show_rows}) ──")
        print(
            report.stale_rows[KEY_COLS + ["temperature_2m"]]
            .head(show_rows)
            .to_string(index=False)
        )

    print(f"\n{bar}\n")


# ── Standalone demo ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    from src.api.weather_api import get_weather
    from src.preprocessing.clean_data import clean_weather

    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    print("Fetching fresh data from API...")
    raw = get_weather()
    df_fresh = clean_weather(raw)

    print(f"Transformed {len(df_fresh)} rows. Running comparison...")
    report = compare_with_db(df_fresh)
    print_report(report)
