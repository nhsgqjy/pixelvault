"""Provider-neutral media storage for local development and S3-compatible clouds."""

from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required when STORAGE_BACKEND=s3")
    return value


class LocalStorage:
    name = "local"

    def __init__(self, root: Path):
        self.root = root
        for namespace in ("objects", "thumbnails", "quarantine"):
            (root / namespace).mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        root = self.root.resolve()
        if target != root and root not in target.parents:
            raise ValueError("Storage key escapes its root")
        return target

    def put_file(self, key: str, source: Path, content_type: str | None = None):
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    def exists(self, key: str) -> bool:
        return self.path(key).is_file()

    def size(self, key: str) -> int:
        return self.path(key).stat().st_size

    def delete(self, key: str):
        self.path(key).unlink(missing_ok=True)

    def open(self, key: str):
        return self.path(key).open("rb")

    def list(self, prefix: str) -> list[str]:
        base = self.path(prefix)
        if not base.exists():
            return []
        return [path.relative_to(self.root).as_posix() for path in base.rglob("*") if path.is_file()]

    def list_sizes(self, prefix: str) -> dict[str, int]:
        return {key: self.size(key) for key in self.list(prefix)}

    def move(self, source_key: str, target_key: str):
        target = self.path(target_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.path(source_key)), str(target))

    @contextmanager
    def local_file(self, key: str):
        path = self.path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        yield path


class S3Storage:
    name = "s3"

    def __init__(self):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as error:
            raise RuntimeError("S3 storage requires boto3; install backend requirements") from error
        self.bucket = _required("S3_BUCKET")
        self.client = boto3.client(
            "s3",
            endpoint_url=_required("S3_ENDPOINT_URL"),
            aws_access_key_id=_required("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=_required("S3_SECRET_ACCESS_KEY"),
            region_name=os.getenv("S3_REGION", "auto"),
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
        )

    def put_file(self, key: str, source: Path, content_type: str | None = None):
        extra = {"ContentType": content_type} if content_type else None
        self.client.upload_file(str(source), self.bucket, key, ExtraArgs=extra or {})

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as error:
            if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise

    def size(self, key: str) -> int:
        return int(self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])

    def delete(self, key: str):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def open(self, key: str):
        from botocore.exceptions import ClientError
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        except ClientError as error:
            if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                raise FileNotFoundError(key) from error
            raise

    def list(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix.rstrip("/") + "/"):
            keys.extend(item["Key"] for item in page.get("Contents", []))
        return keys

    def list_sizes(self, prefix: str) -> dict[str, int]:
        sizes: dict[str, int] = {}
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix.rstrip("/") + "/"):
            sizes.update({item["Key"]: int(item["Size"]) for item in page.get("Contents", [])})
        return sizes

    def move(self, source_key: str, target_key: str):
        self.client.copy_object(Bucket=self.bucket, Key=target_key,
                                CopySource={"Bucket": self.bucket, "Key": source_key})
        self.delete(source_key)

    @contextmanager
    def local_file(self, key: str):
        handle = NamedTemporaryFile(prefix="pixelvault-media-", delete=False)
        path = Path(handle.name)
        handle.close()
        try:
            self.client.download_file(self.bucket, key, str(path))
            yield path
        finally:
            path.unlink(missing_ok=True)


def create_storage(data_dir: Path):
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    if backend == "local":
        return LocalStorage(data_dir)
    if backend == "s3":
        return S3Storage()
    raise RuntimeError("STORAGE_BACKEND must be 'local' or 's3'")
