from airflow import DAG
from datetime import datetime, timedelta
from src.api.weather_api import get_weather
from src.preprocessing.clean_data import clean_weather
from src.etl.load import load_data
from src.etl.compare import compare_with_db, print_report
from src.database.connection import get_engine
from airflow.providers.standard.operators.python import PythonOperator


def extract(**context):
    data = get_weather()
    context["ti"].xcom_push(key="raw_weather", value=data)


def transform(**context):
    data = context["ti"].xcom_pull(task_ids="EXT01", key="raw_weather")
    df = clean_weather(data)
    context["ti"].xcom_push(key="clean_df", value=df.to_json(date_format="iso"))


def pre_load(**context):
    import pandas as pd
    import io

    json_str = context["ti"].xcom_pull(task_ids="TRA01", key="clean_df")
    df = pd.read_json(io.StringIO(json_str))
    df["forecast_time"] = pd.to_datetime(df["forecast_time"], utc=True)

    report = compare_with_db(df, engine=get_engine())
    print_report(report)

    context["ti"].xcom_push(
        key="df_new", value=report.df_new.to_json(date_format="iso")
    )


def load(**context):
    import pandas as pd
    import io

    json_str = context["ti"].xcom_pull(task_ids="PRELOAD01", key="df_new")
    df = pd.read_json(io.StringIO(json_str))
    df["forecast_time"] = pd.to_datetime(df["forecast_time"], utc=True)

    load_data(df)


with DAG(
    dag_id="dag01",
    description="Fetch Open-Meteo forecast API and load into PostgreSQL — runs hourly at 00:30 UTC",
    start_date=datetime(2026, 6, 21, 0, 30),
    schedule="@hourly",
    catchup=False,
    dagrun_timeout=timedelta(minutes=25),
    tags=["Forecast", "Daily"],
    dag_display_name="Weather Forecast Pipeline",
) as dag:

    extract_weather_api = PythonOperator(
        task_id="EXT01",
        python_callable=extract,
    )

    transform_weather_api = PythonOperator(
        task_id="TRA01",
        python_callable=transform,
    )

    pre_load_task = PythonOperator(
        task_id="PRELOAD01",
        python_callable=pre_load,
    )

    load_weather_api = PythonOperator(
        task_id="LOAD01",
        python_callable=load,
    )

    extract_weather_api >> transform_weather_api >> pre_load_task >> load_weather_api  # type: ignore
