"""P13-C retrieval result helpers."""
from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4
import hashlib

def query_hash(text: str) -> str: return hashlib.sha256(text.encode('utf-8')).hexdigest()
def new_query_id() -> str: return f"retrieval-query-{uuid4().hex[:12]}"
def now() -> str: return datetime.now(UTC).isoformat()


def build_retrieval_result(query_text: str, ranked_cases: list[dict]) -> dict:
    route = ranked_cases[0].get("route", "none") if ranked_cases else "none"
    return {
        "query_text_hash": query_hash(query_text),
        "similarity_route": route,
        "usable_as_reference": route in ("A", "B", "C"),
        "candidates": ranked_cases,
        "requires_user_confirmation": True,
        "physical_vector_search_performed": False,
        "embedding_created": False,
        "route_reason": "相似案例只作參考，不得跳過 SCBKR 使用者確認。",
    }


def build_empty_retrieval_result(query_text: str) -> dict:
    return build_retrieval_result(query_text, [])
