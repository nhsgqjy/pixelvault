import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.storage import LocalStorage, create_storage


class LocalStorageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.storage = LocalStorage(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_round_trip_list_size_and_delete(self):
        source = self.root / "source.bin"
        source.write_bytes(b"pixelvault")
        self.storage.put_file("objects/example.bin", source, "application/octet-stream")
        self.assertTrue(self.storage.exists("objects/example.bin"))
        self.assertEqual(self.storage.size("objects/example.bin"), 10)
        self.assertEqual(self.storage.list("objects"), ["objects/example.bin"])
        self.assertEqual(self.storage.list_sizes("objects"), {"objects/example.bin": 10})
        with self.storage.open("objects/example.bin") as handle:
            self.assertEqual(handle.read(), b"pixelvault")
        self.storage.delete("objects/example.bin")
        self.assertFalse(self.storage.exists("objects/example.bin"))

    def test_move_to_quarantine(self):
        source = self.root / "source.bin"
        source.write_bytes(b"orphan")
        self.storage.put_file("objects/orphan.bin", source)
        self.storage.move("objects/orphan.bin", "quarantine/run/orphan.bin")
        self.assertFalse(self.storage.exists("objects/orphan.bin"))
        self.assertTrue(self.storage.exists("quarantine/run/orphan.bin"))

    def test_rejects_path_escape(self):
        with self.assertRaises(ValueError):
            self.storage.path("../secret.txt")

    def test_factory_defaults_to_local(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(create_storage(self.root).name, "local")

    def test_factory_rejects_unknown_backend(self):
        with patch.dict(os.environ, {"STORAGE_BACKEND": "unknown"}, clear=True):
            with self.assertRaises(RuntimeError):
                create_storage(self.root)

    def test_s3_factory_loads_configuration_without_network(self):
        values = {
            "STORAGE_BACKEND": "s3",
            "S3_ENDPOINT_URL": "https://example.invalid",
            "S3_BUCKET": "pixelvault-test",
            "S3_ACCESS_KEY_ID": "test-key",
            "S3_SECRET_ACCESS_KEY": "test-secret",
            "S3_REGION": "us-west-004",
        }
        with patch.dict(os.environ, values, clear=True):
            storage = create_storage(self.root)
            self.assertEqual(storage.name, "s3")
            self.assertEqual(storage.bucket, "pixelvault-test")
            self.assertEqual(storage.client.meta.region_name, "us-west-004")

    def test_s3_lists_sizes_with_one_paginated_request(self):
        values = {
            "STORAGE_BACKEND": "s3",
            "S3_ENDPOINT_URL": "https://example.invalid",
            "S3_BUCKET": "pixelvault-test",
            "S3_ACCESS_KEY_ID": "test-key",
            "S3_SECRET_ACCESS_KEY": "test-secret",
            "S3_REGION": "us-west-004",
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [{"Contents": [
            {"Key": "thumbnails/a.webp", "Size": 12},
            {"Key": "thumbnails/b.webp", "Size": 34},
        ]}]
        client = MagicMock()
        client.get_paginator.return_value = paginator
        with patch.dict(os.environ, values, clear=True), patch("boto3.client", return_value=client):
            storage = create_storage(self.root)
            self.assertEqual(storage.list_sizes("thumbnails"), {
                "thumbnails/a.webp": 12,
                "thumbnails/b.webp": 34,
            })
        paginator.paginate.assert_called_once_with(Bucket="pixelvault-test", Prefix="thumbnails/")

    def test_s3_requires_explicit_region(self):
        values = {
            "STORAGE_BACKEND": "s3",
            "S3_ENDPOINT_URL": "https://s3.us-west-004.backblazeb2.com",
            "S3_BUCKET": "pixelvault-test",
            "S3_ACCESS_KEY_ID": "test-key",
            "S3_SECRET_ACCESS_KEY": "test-secret",
        }
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaisesRegex(RuntimeError, "S3_REGION"):
                create_storage(self.root)


if __name__ == "__main__":
    unittest.main()
