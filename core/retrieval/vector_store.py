"""Optional local ChromaDB adapter for P13-C retrieval.

ChromaDB is strictly local and optional. This adapter supplies deterministic
local numeric fingerprints to ChromaDB so no default embedding model, download,
or external embedding API is needed.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any

from core.storage.runtime_paths import REPO_ROOT
from core.storage.sqlite_runtime import list_retrieval_cases
from core.retrieval.similarity import build_token_fingerprint, rank_candidates, route_from_score, score_similarity

EMBEDDING_STATUS_FALLBACK = "fallback_keyword"
EMBEDDING_STATUS_NOT_CREATED = "not_created"
EMBEDDING_STATUS_LOCAL_CHROMADB = "local_chromadb_no_external_embedding"


def _vector_dir() -> Path:
    import os

    return Path(os.environ.get("SCBKR_DATA_DIR", REPO_ROOT / "data")).expanduser() / "vector_db" / "chroma"


def _local_fingerprint_embedding(text: str, dimensions: int = 32) -> list[float]:
    """Return a deterministic local vector without models or external APIs."""
    vector = [0.0] * dimensions
    for token, count in build_token_fingerprint(text).items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign * float(count)
    norm = sum(value * value for value in vector) ** 0.5
    if norm:
        vector = [round(value / norm, 8) for value in vector]
    return vector


def is_chromadb_available() -> bool:
    try:
        import chromadb  # noqa: F401
        return True
    except Exception:
        return False


def get_vector_store_status() -> dict[str, Any]:
    available = is_chromadb_available()
    return {
        "available": available,
        "backend": "chromadb" if available else "deterministic_fallback",
        "path": str(_vector_dir()),
        "cloud": False,
        "embedding_status": EMBEDDING_STATUS_LOCAL_CHROMADB if available else EMBEDDING_STATUS_FALLBACK,
    }


def ensure_vector_store():
    if not is_chromadb_available():
        return None
    import chromadb

    path = _vector_dir()
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def _collection(client: Any):
    return client.get_or_create_collection("scbkr_retrieval_cases", embedding_function=None)


def upsert_retrieval_case(case: dict[str, Any]) -> dict[str, Any]:
    client = ensure_vector_store()
    if client is None:
        return {"backend": "deterministic_fallback", "status": "unavailable", "embedding_status": EMBEDDING_STATUS_FALLBACK}
    collection = _collection(client)
    retrieval_text = case.get("retrieval_text", "")
    collection.upsert(
        ids=[case["case_id"]],
        documents=[retrieval_text],
        embeddings=[_local_fingerprint_embedding(retrieval_text)],
        metadatas=[{"case_type": case.get("case_type", ""), "task_id": case.get("task_id", "")}],
    )
    return {"backend": "chromadb", "status": "upserted", "embedding_status": EMBEDDING_STATUS_LOCAL_CHROMADB}


def _score_chromadb_candidates(query_text: str, ids: list[str], docs: list[str], top_k: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for case_id, document in zip(ids, docs):
        if not document:
            continue
        score = score_similarity(query_text, document)
        candidates.append(
            {
                "case_id": case_id,
                "retrieval_text": document,
                "score": score,
                "route": route_from_score(score),
                "backend": "chromadb",
                "similarity_source": "deterministic_rescore_after_chromadb",
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["case_id"]))
    return candidates[:top_k]


def query_similar_cases(query_text: str, top_k: int = 3, case_type: str | None = None) -> dict[str, Any]:
    if not is_chromadb_available():
        return {"backend": "deterministic_fallback", "status": "unavailable", "candidates": [], "embedding_status": EMBEDDING_STATUS_FALLBACK}
    try:
        client = ensure_vector_store()
        collection = _collection(client)
        where = {"case_type": case_type} if case_type and case_type != "any" else None
        data = collection.query(query_embeddings=[_local_fingerprint_embedding(query_text)], n_results=top_k, where=where)
        ids = (data.get("ids") or [[]])[0]
        docs = (data.get("documents") or [[]])[0]
        candidates = _score_chromadb_candidates(query_text, ids, docs, top_k)
        if not candidates:
            return {"backend": "deterministic_fallback", "status": "fallback", "candidates": [], "embedding_status": EMBEDDING_STATUS_FALLBACK}
        return {"backend": "chromadb", "status": "ok", "candidates": candidates, "embedding_status": EMBEDDING_STATUS_LOCAL_CHROMADB}
    except Exception as exc:
        candidates = rank_candidates(query_text, list_retrieval_cases(case_type=case_type, limit=200), top_k)
        for candidate in candidates:
            candidate.setdefault("backend", "deterministic_fallback")
            candidate.setdefault("similarity_source", "deterministic_fallback")
        return {"backend": "deterministic_fallback", "status": "fallback", "error_message": str(exc), "candidates": candidates, "embedding_status": EMBEDDING_STATUS_FALLBACK}
