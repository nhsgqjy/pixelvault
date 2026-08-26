"""Reproducible local HTTP benchmark for PixelVault.

Uses only the Python standard library so the benchmark can run in CI or on a
fresh machine without installing a load-testing package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sqlite3
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener


@dataclass
class Sample:
    latency_ms: float
    status: int
    error: str | None = None


class Client:
    def __init__(self, base_url: str, password: str):
        self.base_url = base_url.rstrip("/") + "/api"
        self.password = password
        self.local = threading.local()
        self.cookie_header = self._login()

    def _login(self) -> str:
        jar = CookieJar()
        opener = build_opener(HTTPCookieProcessor(jar))
        body = json.dumps({"password": self.password}).encode()
        request = Request(self.base_url + "/auth/login", data=body, method="POST",
                          headers={"Content-Type": "application/json"})
        with opener.open(request, timeout=10) as response:
            json.load(response)
        return "; ".join(f"{cookie.name}={cookie.value}" for cookie in jar)

    def request(self, path: str, method: str = "GET", body: dict | None = None) -> Sample:
        sample, _ = self.request_data(path, method, body)
        return sample

    def request_data(self, path: str, method: str = "GET", body: dict | None = None) -> tuple[Sample, dict | None]:
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Cookie": self.cookie_header}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=payload, method=method, headers=headers)
        started = time.perf_counter()
        status = 0
        error_text = None
        response_data = None
        try:
            with build_opener().open(request, timeout=15) as response:
                raw = response.read()
                status = response.status
                if response.headers.get_content_type() == "application/json":
                    response_data = json.loads(raw)
        except HTTPError as error:
            status = error.code
            error_text = f"HTTP {error.code}"
        except (URLError, TimeoutError, OSError) as error:
            error_text = type(error).__name__
        return Sample((time.perf_counter() - started) * 1000, status, error_text), response_data

    def json(self, path: str) -> dict:
        request = Request(self.base_url + path, headers={"Cookie": self.cookie_header})
        with build_opener().open(request, timeout=10) as response:
            return json.load(response)


def cleanup_local_performance_uploads(base_url: str) -> int:
    """Remove only upload sessions created by this benchmark on local runs."""
    if base_url.rstrip("/") not in {"http://127.0.0.1:8000", "http://localhost:8000"}:
        return 0
    data_dir = Path(__file__).resolve().parent / "data"
    database = data_dir / "pixelvault.db"
    chunks = (data_dir / "chunks").resolve()
    if not database.is_file() or not chunks.is_dir():
        return 0
    with sqlite3.connect(database, timeout=10) as db:
        rows = db.execute("SELECT id FROM upload_sessions WHERE filename='perf.jpg'").fetchall()
        db.execute("DELETE FROM upload_sessions WHERE filename='perf.jpg'")
    for (upload_id,) in rows:
        folder = (chunks / upload_id).resolve()
        if folder.parent == chunks and folder.is_dir():
            shutil.rmtree(folder)
    return len(rows)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def summarize(name: str, concurrency: int, samples: list[Sample], duration: float) -> dict:
    latencies = [sample.latency_ms for sample in samples]
    errors = [sample for sample in samples if sample.error or not 200 <= sample.status < 400]
    return {
        "name": name,
        "concurrency": concurrency,
        "requests": len(samples),
        "duration_seconds": round(duration, 3),
        "requests_per_second": round(len(samples) / duration, 2),
        "mean_ms": round(statistics.fmean(latencies), 2),
        "p50_ms": round(percentile(latencies, 0.50), 2),
        "p95_ms": round(percentile(latencies, 0.95), 2),
        "p99_ms": round(percentile(latencies, 0.99), 2),
        "max_ms": round(max(latencies), 2),
        "errors": len(errors),
        "error_rate_percent": round(len(errors) * 100 / len(samples), 2),
        "statuses": {str(code): sum(sample.status == code for sample in samples)
                     for code in sorted({sample.status for sample in samples})},
    }


def run_scenario(client: Client, name: str, concurrency: int, requests: int, operation) -> dict:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(operation, index) for index in range(requests)]
        samples = [future.result() for future in as_completed(futures)]
    result = summarize(name, concurrency, samples, time.perf_counter() - started)
    print(f"{name:18} {result['requests_per_second']:8.2f} req/s  "
          f"p95={result['p95_ms']:8.2f} ms  errors={result['errors']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", default="demo1234")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1.0,
                        help="Multiply request counts; use 0.2 for a fast check")
    args = parser.parse_args()
    removed = cleanup_local_performance_uploads(args.base_url)
    if removed:
        print(f"Cleaned {removed} stale benchmark upload sessions")
    client = Client(args.base_url, args.password)
    library = client.json("/photos?limit=24")
    photos = library.get("items", [])
    photo_id = photos[0]["id"] if photos else None

    def count(value: int) -> int:
        return max(1, round(value * args.scale))

    scenarios = [
        run_scenario(client, "photos_list", 20, count(300),
                     lambda _: client.request("/photos?limit=24")),
        run_scenario(client, "albums_list", 20, count(300),
                     lambda _: client.request("/albums")),
        run_scenario(client, "stats", 10, count(150),
                     lambda _: client.request("/stats")),
    ]
    if photo_id:
        scenarios.append(run_scenario(client, "thumbnail", 20, count(250),
                                      lambda _: client.request(f"/photos/{photo_id}/thumbnail")))

    mixed_paths = ["/photos?limit=24", "/albums", "/timeline", "/stats"]
    if photo_id:
        mixed_paths.extend([f"/photos/{photo_id}/thumbnail"] * 2)
    scenarios.append(run_scenario(client, "mixed_read", 30, count(500),
                                  lambda index: client.request(mixed_paths[index % len(mixed_paths)])))

    upload_ids: list[str] = []
    upload_ids_lock = threading.Lock()

    def upload_session(index: int) -> Sample:
        digest = hashlib.sha256(f"pixelvault-perf-{time.time_ns()}-{index}".encode()).hexdigest()
        path = ("/uploads/init?filename=perf.jpg&sha256=" + digest +
                "&size=2097152&content_type=" + quote("image/jpeg"))
        created, payload = client.request_data(path, "POST")
        if payload and payload.get("upload_id"):
            with upload_ids_lock:
                upload_ids.append(payload["upload_id"])
        return created

    scenarios.append(run_scenario(client, "upload_init", 10, count(60), upload_session))
    for upload_id in upload_ids:
        client.request(f"/uploads/{upload_id}", "DELETE")
    cleanup_local_performance_uploads(args.base_url)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "library_photo_count": library.get("total", 0),
        "scale": args.scale,
        "scenarios": scenarios,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
