"""Fail fast when the Render deployment contract drifts from the container."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(text: str, expected: str, source: str) -> None:
    if expected not in text:
        raise SystemExit(f"Missing {expected!r} in {source}")


def main() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    for expected in (
        "PORT=8000",
        "${PORT:-8000}",
        'CMD ["python", "-m", "app.healthcheck"]',
    ):
        require(dockerfile, expected, "Dockerfile")

    for expected in (
        "runtime: docker",
        "plan: free",
        "region: singapore",
        "healthCheckPath: /api/health",
        "autoDeployTrigger: commit",
        "key: PIXELVAULT_DEMO_PASSWORD",
        "sync: false",
        "key: PIXELVAULT_COOKIE_SECURE",
        'value: "true"',
        "key: DATA_DIR",
        "value: /app/data",
    ):
        require(blueprint, expected, "render.yaml")

    healthcheck = ROOT / "backend/app/healthcheck.py"
    if not healthcheck.is_file():
        raise SystemExit("Missing backend/app/healthcheck.py")
    print("Render deployment contract verification passed.")


if __name__ == "__main__":
    main()
