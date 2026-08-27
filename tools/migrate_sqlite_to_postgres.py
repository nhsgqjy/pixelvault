"""Copy PixelVault metadata from SQLite into an empty PostgreSQL database.

The command is deliberately read-only unless --apply is supplied. DATABASE_URL
must point at PostgreSQL; credentials are never accepted as command arguments.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import connect, is_postgres  # noqa: E402
from app.db import initialize  # noqa: E402


TABLES = {
    "photos": ("id", "name", "sha256", "object_name", "content_type", "size", "favorite", "trashed",
               "share_token", "thumbnail_name", "width", "height", "captured_at", "share_expires_at",
               "share_views", "caption", "perceptual_hash", "sort_id"),
    "albums": ("id", "name", "created_at", "share_token", "share_expires_at", "share_views",
               "description", "cover_photo_id"),
    "upload_sessions": ("id", "filename", "sha256", "size", "content_type", "created_at"),
    "auth_sessions": ("token", "created_at", "expires_at"),
    "api_events": ("id", "method", "path", "status", "duration_ms", "created_at"),
    "tags": ("id", "name"),
    "login_attempts": ("id", "client_key", "attempted_at"),
    "integrity_jobs": ("id", "status", "total", "completed", "current_name", "result_json", "error",
                       "created_at", "updated_at"),
    "photo_processing_jobs": ("photo_id", "status", "error", "created_at", "updated_at"),
    "album_photos": ("album_id", "photo_id", "added_at"),
    "photo_tags": ("photo_id", "tag_id"),
}


def source_rows(source: sqlite3.Connection, table: str, columns: tuple[str, ...]):
    selected = ",".join("rowid AS sort_id" if table == "photos" and name == "sort_id" else name
                        for name in columns)
    return [dict(row) for row in source.execute(f"SELECT {selected} FROM {table}")]


def target_count(target, table: str) -> int:
    return target.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]


def migrate(source_path: Path, apply: bool):
    if not source_path.is_file():
        raise SystemExit(f"SQLite source does not exist: {source_path}")
    if not is_postgres():
        raise SystemExit("DATABASE_URL must be a postgresql:// or postgres:// URL")

    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row
    try:
        snapshot = {table: source_rows(source, table, columns) for table, columns in TABLES.items()}
    finally:
        source.close()

    summary = ", ".join(f"{table}={len(rows)}" for table, rows in snapshot.items())
    print(f"Source snapshot: {summary}")
    if not apply:
        print("Dry run only. Re-run with --apply to initialize and write the PostgreSQL target.")
        return

    initialize(ROOT / "backend" / "data", ROOT / "backend" / "data" / "photos.json")
    with connect(ROOT / "backend" / "data") as target:
        populated = {table: target_count(target, table) for table in TABLES}
        populated = {table: count for table, count in populated.items() if count}
        if populated:
            raise SystemExit(f"Target is not empty; migration refused: {populated}")

        for table, columns in TABLES.items():
            rows = snapshot[table]
            if not rows:
                continue
            names = ",".join(columns)
            placeholders = ",".join("?" for _ in columns)
            target.executemany(f"INSERT INTO {table}({names}) VALUES({placeholders})",
                               [tuple(row[name] for name in columns) for row in rows])

        for table, column, sequence in (
            ("photos", "sort_id", "photos_sort_id_seq"),
            ("api_events", "id", "api_events_id_seq"),
            ("tags", "id", "tags_id_seq"),
            ("login_attempts", "id", "login_attempts_id_seq"),
        ):
            target.execute(
                f"SELECT setval('{sequence}', COALESCE((SELECT MAX({column}) FROM {table}), 1), "
                f"EXISTS(SELECT 1 FROM {table}))"
            )

        mismatches = {}
        for table, rows in snapshot.items():
            actual = target_count(target, table)
            if actual != len(rows):
                mismatches[table] = {"source": len(rows), "target": actual}
        if mismatches:
            raise RuntimeError(f"Row-count verification failed: {mismatches}")
    print("Migration completed and all table row counts match.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "backend" / "data" / "pixelvault.db")
    parser.add_argument("--apply", action="store_true", help="write to the empty DATABASE_URL target")
    args = parser.parse_args()
    migrate(args.source.resolve(), args.apply)
