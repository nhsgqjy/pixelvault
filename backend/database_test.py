import os
import sys
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.database import Connection, _postgres_sql, backend_name
from app.db import (api_metrics, create_upload, get_photo, get_upload_by_hash,
                    initialize, recent_api_events, record_api_event,
                    set_photos_trashed, upsert)


class DatabaseCompatibilityTest(unittest.TestCase):
    def test_defaults_to_sqlite(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(backend_name(), "sqlite")

    def test_detects_render_postgres_url(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://example/db"}, clear=True):
            self.assertEqual(backend_name(), "postgresql")

    def test_converts_parameters_and_photo_order(self):
        converted = _postgres_sql("SELECT p.* FROM photos p WHERE p.id=? ORDER BY p.rowid DESC")
        self.assertIn("p.id=%s", converted)
        self.assertIn("p.sort_id DESC", converted)

    def test_converts_upload_session_positional_parameters(self):
        converted = _postgres_sql(
            "INSERT INTO upload_sessions(id,filename,sha256,size,content_type,created_at) "
            "VALUES(?,?,?,?,?,?)"
        )
        self.assertEqual(
            converted,
            "INSERT INTO upload_sessions(id,filename,sha256,size,content_type,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
        )

    def test_converts_sqlite_named_parameters_for_psycopg(self):
        converted = _postgres_sql(
            "INSERT INTO photos(id,name,sha256) VALUES(:id,:name,:sha256)"
        )
        self.assertEqual(
            converted,
            "INSERT INTO photos(id,name,sha256) VALUES(%(id)s,%(name)s,%(sha256)s)",
        )

    def test_converts_sqlite_insert_ignore(self):
        converted = _postgres_sql("INSERT OR IGNORE INTO tags(name) VALUES(?)")
        self.assertEqual(converted, "INSERT INTO tags(name) VALUES(%s) ON CONFLICT DO NOTHING")

    def test_converts_tag_aggregation(self):
        converted = _postgres_sql("SELECT GROUP_CONCAT(t.name, char(31)) FROM tags t")
        self.assertIn("STRING_AGG(t.name, CHR(31))", converted)

    def test_preserves_returning_clause(self):
        converted = _postgres_sql(
            "INSERT INTO api_events(method,path) VALUES(?,?) RETURNING id"
        )
        self.assertEqual(
            converted,
            "INSERT INTO api_events(method,path) VALUES(%s,%s) RETURNING id",
        )

    def test_metrics_use_rounding_sql_supported_by_both_databases(self):
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            initialize(data_dir, data_dir / "photos.json")
            record_api_event(data_dir, "POST", "/api/test", 201, 12.36,
                             "2026-08-28T00:00:00+00:00")
            self.assertEqual(api_metrics(data_dir)["average_ms"], 12.4)
            self.assertEqual(recent_api_events(data_dir)[0]["duration_ms"], 12.4)

    def test_replaces_stale_upload_session_with_the_same_hash(self):
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            initialize(data_dir, data_dir / "photos.json")
            first = {"id": "old", "filename": "old.jpg", "sha256": "a" * 64,
                     "size": 10, "content_type": "image/jpeg", "created_at": "old"}
            replacement = {**first, "id": "new", "filename": "new.jpg",
                           "size": 20, "created_at": "new"}
            create_upload(data_dir, first)
            create_upload(data_dir, replacement)
            saved = get_upload_by_hash(data_dir, first["sha256"])
            self.assertEqual(saved["id"], "new")
            self.assertEqual(saved["filename"], "new.jpg")
            self.assertEqual(saved["size"], 20)

    def test_postgres_executemany_uses_a_cursor(self):
        class FakeCursor:
            def __init__(self):
                self.call = None

            def executemany(self, sql, params):
                self.call = (sql, params)

        class FakePostgresConnection:
            def __init__(self):
                self.created_cursor = FakeCursor()

            def cursor(self):
                return self.created_cursor

        connection = Connection(Path("unused"))
        connection.postgres = True
        connection.raw = FakePostgresConnection()
        rows = [("album", "photo", "now")]
        cursor = connection.executemany(
            "INSERT OR IGNORE INTO album_photos(album_id,photo_id,added_at) VALUES(?,?,?)",
            rows,
        )
        self.assertIs(cursor, connection.raw.created_cursor)
        self.assertEqual(cursor.call, (
            "INSERT INTO album_photos(album_id,photo_id,added_at) VALUES(%s,%s,%s) "
            "ON CONFLICT DO NOTHING",
            rows,
        ))

    def test_batch_trash_and_restore_are_atomic_in_sqlite(self):
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            initialize(data_dir, data_dir / "photos.json")
            for photo_id in ("one", "two"):
                with Connection(data_dir) as db:
                    upsert(db, {"id": photo_id, "name": f"{photo_id}.jpg", "sha256": photo_id,
                                "object_name": f"{photo_id}.jpg", "content_type": "image/jpeg", "size": 1,
                                "favorite": False, "trashed": False, "share_token": None})
            self.assertEqual(set_photos_trashed(data_dir, ["one", "two"], True), 2)
            self.assertTrue(get_photo(data_dir, "one")["trashed"])
            self.assertTrue(get_photo(data_dir, "two")["trashed"])
            self.assertEqual(set_photos_trashed(data_dir, ["one", "two"], False), 2)
            self.assertFalse(get_photo(data_dir, "one")["trashed"])

    def test_postgres_integer_flags_are_normalized(self):
        class Result:
            def __init__(self, count=None, rowcount=0):
                self.count = count
                self.rowcount = rowcount

            def fetchone(self):
                return {"count": self.count}

        class FakeConnection:
            def __init__(self):
                self.calls = []

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params):
                self.calls.append((sql, params))
                return Result(count=2) if sql.startswith("SELECT") else Result(rowcount=2)

        fake = FakeConnection()
        with patch("app.db.connect", return_value=fake):
            self.assertEqual(set_photos_trashed(Path("unused"), ["one", "two"], True), 2)
        self.assertEqual(fake.calls[1][1][0], 1)

        fake.calls.clear()
        from app.db import update_fields
        with patch("app.db.connect", return_value=fake):
            update_fields(Path("unused"), "one", {"trashed": True, "favorite": False})
        self.assertEqual(fake.calls[0][1], (1, 0, "one"))


if __name__ == "__main__":
    unittest.main()
