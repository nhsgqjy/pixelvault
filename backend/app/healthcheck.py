"""Container health probe that follows the platform-provided HTTP port."""

from __future__ import annotations

import os
from urllib.request import urlopen


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as response:
        if response.status != 200:
            raise SystemExit(f"Unexpected health status: {response.status}")


if __name__ == "__main__":
    main()
