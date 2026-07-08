"""Clean generated product noise without touching formal local data."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_DIRS = {
    ROOT / "data",
    ROOT / "kernel_pack",
    ROOT / ".git",
}
NOISE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    "test-results",
    "playwright-report",
    "dist",
    ".vite",
    ".turbo",
    "coverage",
}
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "data",
    "kernel_pack",
}
NOISE_SUFFIXES = {".pyc", ".pyo", ".log"}


def _is_protected(path: Path) -> bool:
    resolved = path.resolve()
    return any(resolved == protected.resolve() or protected.resolve() in resolved.parents for protected in PROTECTED_DIRS)


def find_noise() -> list[Path]:
    results: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES and not _is_protected(current / name)]
        for dirname in list(dirnames):
            candidate = current / dirname
            if dirname in NOISE_DIR_NAMES:
                results.append(candidate)
                dirnames.remove(dirname)
        for filename in filenames:
            candidate = current / filename
            if candidate.suffix.lower() in NOISE_SUFFIXES and not _is_protected(candidate):
                results.append(candidate)
    return sorted(set(results), key=lambda item: str(item).lower())


def write_report(paths: list[Path], *, applied: bool) -> Path:
    report = ROOT / "reports" / "product_noise_cleanup_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Product Noise Cleanup Report",
        "",
        f"- Mode: {'apply' if applied else 'dry-run'}",
        f"- Items: {len(paths)}",
        "- Protected: data/, kernel_pack/, .git/, .env files",
        "",
        "## Items",
    ]
    lines.extend(f"- {path.relative_to(ROOT)}" for path in paths)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="delete detected generated noise")
    args = parser.parse_args()
    paths = find_noise()
    if args.apply:
        for path in paths:
            if not path.exists() or _is_protected(path):
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    report = write_report(paths, applied=args.apply)
    print(f"{'applied' if args.apply else 'dry-run'} {len(paths)} item(s); report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
