"""Fail closed when private runtime data could enter the public repository."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = (
    "backend/data/",
    "frontend/node_modules/",
    "frontend/dist/",
)
FORBIDDEN_PATHS = {
    "docs/portfolio/interview-guide.md",
    "docs/portfolio/resume-copy.md",
    "docs/portfolio/PUBLISHING.md",
}
PRIVATE_MARKERS = (
    "156024" + "07001",
    "812097204" + "@qq.com",
    "C:/Users/" + "qjy",
    "C:\\Users\\" + "qjy",
    "D:/" + "求职",
    "D:\\" + "求职",
)
REQUIRED_PUBLIC_FILES = (
    "README.md",
    "README.zh-CN.md",
    ".env.example",
    "Dockerfile",
    "docker-compose.yml",
    "docs/portfolio/README.md",
    "docs/portfolio/evidence-index.md",
    "docs/portfolio/assets/pixelvault-desktop.png",
    "docs/portfolio/assets/pixelvault-albums.png",
    "docs/portfolio/assets/pixelvault-insights.png",
    "docs/portfolio/assets/pixelvault-mobile.png",
    "artifacts/performance/baseline.json",
    "artifacts/performance/optimized.json",
)


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True, errors="replace")


def main() -> None:
    if not (ROOT / ".git").exists():
        raise SystemExit("Git repository is not initialized")
    candidates = [line.replace("\\", "/") for line in git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()]
    leaked = [path for path in candidates
              if path == ".env" or path in FORBIDDEN_PATHS
              or any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)]
    if leaked:
        raise SystemExit("Private or generated paths would be published:\n" + "\n".join(leaked))
    exposed: list[str] = []
    text_suffixes = {".md", ".py", ".ts", ".tsx", ".json", ".yml", ".yaml", ".txt", ".html", ".css"}
    for path in candidates:
        file = ROOT / path
        if file.is_file() and (file.suffix.lower() in text_suffixes or file.name in {"Dockerfile", ".env.example"}):
            content = file.read_text(encoding="utf-8", errors="replace")
            for marker in PRIVATE_MARKERS:
                if marker.casefold() in content.casefold():
                    exposed.append(f"{path}: {marker}")
    if exposed:
        raise SystemExit("Personal markers found in publishable files:\n" + "\n".join(exposed))
    missing = [path for path in REQUIRED_PUBLIC_FILES if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit("Required public evidence is missing:\n" + "\n".join(missing))
    ignored_checks = ["backend/data/pixelvault.db", ".env", "frontend/node_modules/example"]
    for path in ignored_checks:
        result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
        if result.returncode != 0:
            raise SystemExit(f"Expected private path is not ignored: {path}")
    print(f"Public release verification passed ({len(candidates)} publishable paths, no private runtime data).")


if __name__ == "__main__":
    main()
