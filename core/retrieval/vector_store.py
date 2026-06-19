"""Optional local ChromaDB adapter for P13-C retrieval."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from core.storage.runtime_paths import REPO_ROOT
from core.storage.sqlite_runtime import list_retrieval_cases
from core.retrieval.similarity import rank_candidates

def _vector_dir() -> Path:
    import os
    return Path(os.environ.get("SCBKR_DATA_DIR", REPO_ROOT / "data")).expanduser() / "vector_db" / "chroma"

def is_chromadb_available() -> bool:
    try:
        import chromadb  # noqa: F401
        return True
    except Exception:
        return False

def get_vector_store_status() -> dict[str, Any]:
    return {"available": is_chromadb_available(), "backend": "chromadb" if is_chromadb_available() else "deterministic_fallback", "path": str(_vector_dir()), "cloud": False}

def ensure_vector_store():
    if not is_chromadb_available():
        return None
    import chromadb
    path = _vector_dir(); path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))

def upsert_retrieval_case(case: dict[str, Any]) -> dict[str, Any]:
    client = ensure_vector_store()
    if client is None:
        return {"backend": "deterministic_fallback", "status": "unavailable", "embedding_status": "fallback_keyword"}
    collection = client.get_or_create_collection("scbkr_retrieval_cases")
    collection.upsert(ids=[case["case_id"]], documents=[case.get("retrieval_text", "")], metadatas=[{"case_type": case.get("case_type", ""), "task_id": case.get("task_id", "")}])
    return {"backend": "chromadb", "status": "upserted", "embedding_status": "not_created"}

def query_similar_cases(query_text: str, top_k: int = 3, case_type: str | None = None) -> dict[str, Any]:
    if not is_chromadb_available():
        return {"backend": "deterministic_fallback", "status": "unavailable", "candidates": []}
    try:
        client = ensure_vector_store(); collection = client.get_or_create_collection("scbkr_retrieval_cases")
        where = {"case_type": case_type} if case_type and case_type != "any" else None
        data = collection.query(query_texts=[query_text], n_results=top_k, where=where)
        ids = (data.get("ids") or [[]])[0]
        docs = (data.get("documents") or [[]])[0]
        return {"backend": "chromadb", "status": "ok", "candidates": [{"case_id": i, "retrieval_text": d} for i,d in zip(ids, docs)]}
    except Exception as exc:
        candidates = rank_candidates(query_text, list_retrieval_cases(case_type=case_type, limit=200), top_k)
        return {"backend": "deterministic_fallback", "status": "fallback", "error_message": str(exc), "candidates": candidates}
