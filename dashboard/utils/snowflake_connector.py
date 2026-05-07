from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import pandas as pd


REQUIRED_ENV_VARS = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "SNOWFLAKE_WAREHOUSE",
]


def snowflake_configured() -> bool:
    return all(os.getenv(name) for name in REQUIRED_ENV_VARS)


@contextmanager
def snowflake_connection() -> Iterator[object]:
    """Create a Snowflake connection when the optional connector is installed."""
    if not snowflake_configured():
        missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
        raise RuntimeError(f"Missing Snowflake environment variables: {', '.join(missing)}")

    try:
        import snowflake.connector
    except ImportError as exc:
        raise RuntimeError(
            "snowflake-connector-python is not installed. Install requirements or use the local CSV dashboard."
        ) from exc

    connection = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.getenv("SNOWFLAKE_ROLE"),
    )
    try:
        yield connection
    finally:
        connection.close()


def query_dataframe(sql: str) -> pd.DataFrame:
    with snowflake_connection() as connection:
        return pd.read_sql(sql, connection)
