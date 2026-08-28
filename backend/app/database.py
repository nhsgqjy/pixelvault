"""Small DB-API compatibility layer for local SQLite and hosted PostgreSQL."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def is_postgres() -> bool:
    return database_url().startswith(("postgres://", "postgresql://"))


def backend_name() -> str:
    return "postgresql" if is_postgres() else "sqlite"


def _postgres_sql(sql: str) -> str:
    statement = sql.strip()
    insert_ignore = statement.upper().startswith("INSERT OR IGNORE INTO ")
    if insert_ignore:
        sql = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", sql, count=1, flags=re.IGNORECASE)
    sql = sql.replace("GROUP_CONCAT(t.name, char(31))", "STRING_AGG(t.name, CHR(31))")
    sql = sql.replace("p.rowid", "p.sort_id")
    sql = sql.replace(" COLLATE NOCASE", "")
    # SQLite accepts ``:name`` parameters while psycopg expects
    # ``%(name)s`` for a mapping. Keep this in the compatibility layer so
    # existing repository queries work with either database backend.
    sql = re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)
    sql = sql.replace("?", "%s")
    if insert_ignore:
        sql = f"{sql.rstrip().rstrip(';')} ON CONFLICT DO NOTHING"
    return sql


class Connection:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.postgres = is_postgres()
        self.raw = None

    def __enter__(self):
        if self.postgres:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as error:
                raise RuntimeError("PostgreSQL requires psycopg; install backend requirements") from error
            self.raw = psycopg.connect(database_url(), row_factory=dict_row,
                                       connect_timeout=10, application_name="pixelvault")
        else:
            self.raw = sqlite3.connect(self.data_dir / "pixelvault.db", timeout=10)
            self.raw.row_factory = sqlite3.Row
            self.raw.execute("PRAGMA busy_timeout=10000")
        return self

    def __exit__(self, error_type, error, traceback):
        if error_type is None:
            self.raw.commit()
        else:
            self.raw.rollback()
        self.raw.close()
        self.raw = None
        return False

    def execute(self, sql: str, params=()):
        return self.raw.execute(_postgres_sql(sql) if self.postgres else sql, params)

    def executemany(self, sql: str, params):
        return self.raw.executemany(_postgres_sql(sql) if self.postgres else sql, params)

    def executescript(self, sql: str):
        if self.postgres:
            raise RuntimeError("PostgreSQL schema must be executed as individual statements")
        return self.raw.executescript(sql)


def connect(data_dir: Path) -> Connection:
    return Connection(data_dir)
