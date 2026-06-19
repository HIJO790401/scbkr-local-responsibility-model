"""Runtime filesystem paths for P13-A local persistence.

This module only defines paths and creates the minimal runtime directories when
asked. It does not open SQLite, write JSONL, call models, or create any P13-B/C
storage directories.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SQLITE_PATH = DATA_DIR / "scbkr.sqlite3"
LEDGER_DIR = DATA_DIR / "ledger"
LEDGER_JSONL_PATH = LEDGER_DIR / "audit-log.jsonl"


def ensure_runtime_dirs() -> None:
    """Create only the P13-A runtime directories required for SQLite/JSONL."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
