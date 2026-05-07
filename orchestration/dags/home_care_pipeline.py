from __future__ import annotations

from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


try:
    from airflow import DAG  # pyright: ignore[reportMissingImports]
    from airflow.operators.bash import BashOperator  # pyright: ignore[reportMissingImports]
    from airflow.operators.empty import EmptyOperator  # pyright: ignore[reportMissingImports]
except ImportError:
    DAG = None
    BashOperator = None
    EmptyOperator = None


if DAG is not None:
    with DAG(
        dag_id="home_care_daily_pipeline",
        description="Generate synthetic home care data, run dbt, and refresh dashboard-ready marts.",
        start_date=datetime(2026, 1, 1),
        schedule="@daily",
        catchup=False,
        tags=["home-care", "dbt", "streamlit"],
    ) as dag:
        start = EmptyOperator(task_id="start")

        generate_synthetic_data = BashOperator(
            task_id="generate_synthetic_data",
            bash_command=f"cd {REPO_ROOT} && python scripts/generate_synthetic_data.py",
        )

        dbt_run = BashOperator(
            task_id="dbt_run",
            bash_command=(
                f"cd {REPO_ROOT / 'dbt'} && "
                "dbt run --profiles-dir ."
            ),
        )

        dbt_test = BashOperator(
            task_id="dbt_test",
            bash_command=(
                f"cd {REPO_ROOT / 'dbt'} && "
                "dbt test --profiles-dir ."
            ),
        )

        dashboard_ready = EmptyOperator(task_id="dashboard_ready")

        start >> generate_synthetic_data >> dbt_run >> dbt_test >> dashboard_ready
else:
    dag = None
