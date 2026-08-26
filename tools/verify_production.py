"""Build-independent production entrypoint verification.

Starts the backend exactly as the production container does, but with an
isolated temporary data directory, then checks static hosting and auth.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
STATIC = ROOT / "frontend" / "dist"
PASSWORD = "production-verification-only"


def wait_for_server(url: str, process: subprocess.Popen) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Production server exited before becoming healthy")
        try:
            with urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Production server did not become healthy")


def main() -> None:
    if not (STATIC / "index.html").is_file():
        raise RuntimeError("frontend/dist is missing; run the production build first")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="pixelvault-production-") as data_dir:
        environment = os.environ.copy()
        environment.update({
            "PIXELVAULT_ENV": "production",
            "PIXELVAULT_DEMO_PASSWORD": PASSWORD,
            "PIXELVAULT_COOKIE_SECURE": "false",
            "PIXELVAULT_STATIC_DIR": str(STATIC),
            "DATA_DIR": data_dir,
        })
        command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                   "--port", str(port), "--proxy-headers", "--forwarded-allow-ips=*"]
        process = subprocess.Popen(command, cwd=BACKEND, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            base = f"http://127.0.0.1:{port}"
            wait_for_server(base + "/api/health", process)
            with urlopen(base + "/", timeout=3) as response:
                assert response.status == 200 and b'<div id="root">' in response.read()
            with urlopen(base + "/album-share/client-route", timeout=3) as response:
                assert response.status == 200 and b'<div id="root">' in response.read()
            asset = next((STATIC / "assets").iterdir()).name
            with urlopen(base + "/assets/" + asset, timeout=3) as response:
                assert response.status == 200 and response.read(1)
            try:
                urlopen(base + "/api/photos", timeout=3)
                raise AssertionError("Private API accepted an anonymous request")
            except HTTPError as error:
                assert error.code == 401
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            payload = json.dumps({"password": PASSWORD}).encode()
            request = Request(base + "/api/auth/login", data=payload, method="POST",
                              headers={"Content-Type": "application/json"})
            with opener.open(request, timeout=3) as response:
                assert json.load(response)["authenticated"] is True
            with opener.open(base + "/api/photos?limit=1", timeout=3) as response:
                assert json.load(response)["total"] == 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        print("PixelVault production entrypoint verification passed.")


if __name__ == "__main__":
    main()
