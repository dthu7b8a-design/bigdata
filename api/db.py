"""MySQL storage; no JSON-file fallback and no writes during API reads."""
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path

import pymysql
from dotenv import load_dotenv

CHART_NAMES = ("daily", "hourly", "weekday", "stations", "locations", "facility", "platform", "vehicle", "users", "duration", "station_hour", "platform_daytype")


class DatabaseUnavailable(Exception):
    pass


class NoResults(Exception):
    pass


class InvalidStoredResults(Exception):
    pass


def settings():
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    name = os.getenv("MYSQL_DATABASE", "bigdata_dashboard")
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise DatabaseUnavailable("Invalid database identifier")
    try:
        port = int(os.getenv("MYSQL_PORT", "3307"))
    except ValueError:
        raise DatabaseUnavailable("Invalid database port") from None
    return dict(host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=port,
                user=os.getenv("MYSQL_USER", "bigdata_api"), password=os.getenv("MYSQL_PASSWORD", ""),
                database=name, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=5, read_timeout=15, write_timeout=30, autocommit=False)


@contextmanager
def connect():
    conn = None
    try:
        conn = pymysql.connect(**settings())
        # Each request sees its active version and charts in one consistent transaction.
        with conn.cursor() as cur:
            cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        yield conn
    except pymysql.MySQLError:
        raise DatabaseUnavailable("MySQL operation failed") from None
    finally:
        if conn is not None:
            conn.close()


def initialize_schema(conn):
    statements = (
        """CREATE TABLE IF NOT EXISTS dashboard_runs (
            run_id CHAR(36) CHARACTER SET ascii PRIMARY KEY,
            imported_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            source_sha256 CHAR(64) CHARACTER SET ascii NOT NULL,
            meta JSON NOT NULL, kpis JSON NOT NULL, quality JSON NOT NULL, model JSON NOT NULL
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS dashboard_charts (
            run_id CHAR(36) CHARACTER SET ascii NOT NULL,
            chart_name VARCHAR(64) CHARACTER SET ascii NOT NULL,
            chart_data JSON NOT NULL,
            PRIMARY KEY (run_id, chart_name),
            FOREIGN KEY (run_id) REFERENCES dashboard_runs(run_id)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS dashboard_active (
            singleton TINYINT PRIMARY KEY,
            run_id CHAR(36) CHARACTER SET ascii NOT NULL,
            CONSTRAINT dashboard_singleton CHECK (singleton = 1),
            FOREIGN KEY (run_id) REFERENCES dashboard_runs(run_id)
        ) ENGINE=InnoDB""",
    )
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    conn.commit()


def active_run(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT run_id FROM dashboard_active WHERE singleton = 1")
        row = cur.fetchone()
    return row["run_id"] if row else None


def load_snapshot():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT r.run_id, r.meta, r.kpis, r.quality, r.model
                FROM dashboard_active a JOIN dashboard_runs r ON r.run_id = a.run_id
                WHERE a.singleton = 1""")
            row = cur.fetchone()
            if row is None:
                raise NoResults()
            cur.execute("SELECT chart_name, chart_data FROM dashboard_charts WHERE run_id = %s", (row["run_id"],))
            charts = cur.fetchall()
    try:
        result = {key: json.loads(row[key]) for key in ("meta", "kpis", "quality", "model")}
        result["charts"] = {chart["chart_name"]: json.loads(chart["chart_data"]) for chart in charts}
        validate_snapshot(result)
        return result
    except (ValueError, TypeError, KeyError):
        raise InvalidStoredResults() from None


def validate_snapshot(value):
    if not isinstance(value, dict) or set(value) != {"meta", "kpis", "charts", "quality", "model"}:
        raise ValueError("Expected exactly meta, kpis, charts, quality, model")
    for key in ("meta", "kpis", "quality", "model", "charts"):
        if not isinstance(value[key], dict):
            raise ValueError(f"{key} must be an object")
    if not set(CHART_NAMES).issubset(value["charts"]):
        raise ValueError("Missing required chart arrays")
    for name, rows in value["charts"].items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name) or not isinstance(rows, list):
            raise ValueError("Chart names must be safe identifiers and chart values must be arrays")
    # Reject NaN / Infinity before submitting any SQL.
    json.dumps(value, ensure_ascii=False, allow_nan=False)
