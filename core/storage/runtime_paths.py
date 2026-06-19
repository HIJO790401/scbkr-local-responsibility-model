"""Runtime filesystem paths for SCBKR local persistence and storage.

This module only defines paths and creates the minimal runtime directories when
asked. It does not open SQLite, write JSONL, call models, or eagerly create optional vector storage directories.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("SCBKR_DATA_DIR", REPO_ROOT / "data")).expanduser()
SQLITE_PATH = DATA_DIR / "scbkr.sqlite3"
LEDGER_DIR = DATA_DIR / "ledger"
LEDGER_JSONL_PATH = LEDGER_DIR / "audit-log.jsonl"
CORPUS_DIR = DATA_DIR / "corpus"
LOGIC_DIR = DATA_DIR / "logic"
EXPORTS_DIR = DATA_DIR / "exports"
MEMORY_DIR = DATA_DIR / "memory"
VECTOR_DB_DIR = DATA_DIR / "vector_db"


def ensure_runtime_dirs() -> None:
    """Create P13-A/B runtime directories; vector_db is lazy-created by retrieval runtime only."""
    for directory in (DATA_DIR, LEDGER_DIR, CORPUS_DIR, LOGIC_DIR, EXPORTS_DIR, MEMORY_DIR):
        directory.mkdir(parents=True, exist_ok=True)
