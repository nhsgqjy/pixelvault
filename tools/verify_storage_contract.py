from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
storage = (ROOT / "backend/app/storage.py").read_text(encoding="utf-8")
main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
migration = (ROOT / "tools/migrate_files_to_object_storage.py").read_text(encoding="utf-8")

for expected in ("class LocalStorage", "class S3Storage", "S3_ENDPOINT_URL", "list_sizes",
                 "download_file", "upload_file", "copy_object"):
    assert expected in storage, expected
for expected in ("STORAGE.put_file", "STORAGE.local_file", "STORAGE.open", "STORAGE.delete",
                 '"storage": STORAGE.name'):
    assert expected in main, expected
assert "OBJECTS /" not in main and "THUMBS /" not in main
assert "Dry run only" in migration and "Uploaded and verified" in migration
print("PixelVault object-storage contract verification passed.")
