"""Airflow DAG: fetch daily stock data and store it in Postgres.

Two tasks so that the failure boundary is visible in the UI: an API problem and
a database problem light up different tasks.
"""

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator

from core.stock_fetcher import StockFetcher
from core.storage import Storage
from utils import read_json

CONFIG = read_json("config.json")

logger = logging.getLogger("marketpipe")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    # A fixed date on purpose. datetime.now() is re-evaluated on every DAG
    # parse, which makes the schedule drift and backfills unpredictable.
    "start_date": datetime(2024, 1, 1),
    "retries": CONFIG.get("retries", 2),
    "retry_delay": timedelta(minutes=CONFIG.get("retry_delay_minutes", 5)),
}


def fetch_stock_data() -> dict:
    """Fetch every configured symbol.

    Returns:
        A dict with the fetched `data` and any `failures`, passed to the next
        task via XCom.
    """
    fetcher = StockFetcher(logger)
    data, failures = fetcher.fetch()
    return {"data": data, "failures": failures}


def store_stock_data(result: dict) -> None:
    """Store the fetched rows, then surface any failures.

    Successful symbols are committed BEFORE the failure is raised, so a partial
    outage still lands the data it managed to collect while the task itself goes
    red with the reason. Raising first would discard good rows on retry.

    Fetch failures fail the task WITHOUT retrying it. A retry of this task only
    re-reads the same XCom -- it cannot re-fetch -- so it would wait out every
    retry delay and fail identically. Database errors still raise normally and
    do get Airflow's retries, since a store retry can fix those.

    Raises:
        AirflowFailException: If any symbol failed to fetch.
    """
    data = result.get("data", {})
    failures = result.get("failures", [])

    written = Storage(logger).store_data(data)

    if failures:
        raise AirflowFailException(
            f"Stored {written} row(s), but {len(failures)} symbol(s) failed: "
            + "; ".join(failures)
        )

    logger.info(f"All symbols stored successfully ({written} row(s)).")


with DAG(
    dag_id="stock_data_pipeline",
    default_args=default_args,
    description="Fetch daily stock data from Alpha Vantage and store it in Postgres",
    schedule=CONFIG["schedule"],
    catchup=False,
    max_active_runs=1,
    tags=["stocks", "marketpipe"],
) as dag:
    fetch_task = PythonOperator(
        task_id="fetch_stock_data",
        python_callable=fetch_stock_data,
    )

    store_task = PythonOperator(
        task_id="store_stock_data",
        python_callable=store_stock_data,
        op_args=[fetch_task.output],
    )

    fetch_task >> store_task
