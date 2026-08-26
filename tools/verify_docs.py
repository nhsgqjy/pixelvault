"""Validate local Markdown links used by the public project documentation."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DOCS = {
    ROOT / "docs/portfolio/interview-guide.md",
    ROOT / "docs/portfolio/resume-copy.md",
    ROOT / "docs/portfolio/PUBLISHING.md",
}
FILES = [*sorted(ROOT.glob("README*.md")),
         *(path for path in sorted((ROOT / "docs").rglob("*.md"))
           if path not in PRIVATE_DOCS)]
LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def main() -> None:
    failures: list[str] = []
    checked = 0
    for document in FILES:
        text = document.read_text(encoding="utf-8")
        for raw_target in LINK.findall(text):
            target = raw_target.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            checked += 1
            resolved = (document.parent / target).resolve()
            if not resolved.exists():
                failures.append(f"{document.relative_to(ROOT)} -> {raw_target}")
    if failures:
        raise SystemExit("Broken local documentation links:\n" + "\n".join(failures))
    required = [
        ROOT / "docs/portfolio/README.md",
        ROOT / "docs/portfolio/evidence-index.md",
        ROOT / "docs/performance-report.md",
        ROOT / "artifacts/performance/baseline.json",
        ROOT / "artifacts/performance/optimized.json",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing portfolio artifacts:\n" + "\n".join(missing))
    print(f"Portfolio documentation verification passed ({len(FILES)} documents, {checked} local links).")


if __name__ == "__main__":
    main()
