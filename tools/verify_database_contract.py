from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
database = (ROOT / "backend/app/database.py").read_text(encoding="utf-8")
schema = (ROOT / "backend/app/db.py").read_text(encoding="utf-8")
migration = (ROOT / "tools/migrate_sqlite_to_postgres.py").read_text(encoding="utf-8")

assert "DATABASE_URL" in database
assert 'return "postgresql" if is_postgres() else "sqlite"' in database
assert "BIGSERIAL" in schema and "idx_tags_name_lower" in schema
assert "Target is not empty; migration refused" in migration
assert "Row-count verification failed" in migration
assert "--apply" in migration
print("PixelVault database contract verification passed.")
