"""Copy an existing local PixelVault media tree to configured S3 storage."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.storage import S3Storage


def media_files(source: Path):
    for namespace in ("objects", "thumbnails"):
        base = source / namespace
        if base.exists():
            yield from (path for path in base.rglob("*") if path.is_file())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "backend" / "data")
    parser.add_argument("--apply", action="store_true", help="upload and verify files")
    args = parser.parse_args()
    source = args.source.resolve()
    files = list(media_files(source))
    total_bytes = sum(path.stat().st_size for path in files)
    print(f"Source: {source}")
    print(f"Files: {len(files)}, bytes: {total_bytes}")
    if not args.apply:
        print("Dry run only. Set S3_* variables and add --apply to upload.")
        return

    target = S3Storage()
    uploaded = 0
    for path in files:
        key = path.relative_to(source).as_posix()
        target.put_file(key, path)
        if not target.exists(key) or target.size(key) != path.stat().st_size:
            raise RuntimeError(f"Object verification failed: {key}")
        uploaded += 1
    print(f"Uploaded and verified: {uploaded} objects")


if __name__ == "__main__":
    main()
