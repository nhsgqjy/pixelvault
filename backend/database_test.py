import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.database import _postgres_sql, backend_name


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


if __name__ == "__main__":
    unittest.main()
