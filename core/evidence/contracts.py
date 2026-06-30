"""Build strict evidence packets from four-store retrieval results.

Vector search is discovery-only. A citation becomes authoritative only when it
resolves to a reviewed, owner-signed, active source in corpus, logic, or memory.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

FORMAL_STORES = ("vector", "corpus", "logic", "memory")
AUTHORITATIVE_STORES = ("corpus", "logic", "memory")
INACTIVE_STATUSES = {"revoked", "archived", "superseded", "deleted"}
SIGNED_STATUSES = {"owner_signed", "verified", "valid"}


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _source_id(hit: dict[str, Any]) -> str:
    return str(
        hit.get("storage_item_id")
        or hit.get("memory_rule_id")
        or hit.get("source_id")
        or hit.get("case_id")
        or f"evidence:{_hash(hit)[:16]}"
    )


def _canonical_store(value: Any) -> str:
    store = str(value or "vector")
    return "vector" if store == "vector_db" else store


def _citation_from_hit(hit: dict[str, Any]) -> dict[str, Any]:
    store = _canonical_store(hit.get("source_store"))
    status = str(hit.get("governance_status") or hit.get("item_status") or hit.get("status") or "active")
    signature_status = str(hit.get("signature_status") or "unsigned")
    review_passed = hit.get("review_passed") is True
    signed = signature_status in SIGNED_STATUSES
    active = status not in INACTIVE_STATUSES
    authoritative = bool(
        hit.get("adopted") is True
        and store in AUTHORITATIVE_STORES
        and review_passed
        and signed
        and active
    )
    source_id = _source_id(hit)
    excerpt = str(hit.get("rule") or hit.get("summary") or "")[:800]
    return {
        "citation_id": f"cite:{_hash([store, source_id, excerpt])[:20]}",
        "source_store": store,
        "source_id": source_id,
        "content_hash": str(hit.get("content_hash") or hit.get("hash") or _hash(excerpt)),
        "author_id": str(hit.get("author_id") or hit.get("confirmed_by") or "owner"),
        "version": str(hit.get("version") or "1"),
        "status": "active" if active else status,
        "signature_status": signature_status,
        "review_passed": review_passed,
        "adoption_scope": str(hit.get("adoption_scope") or "none"),
        "authority": authoritative,
        "must_cite": bool(hit.get("must_cite")),
        "excerpt": excerpt,
    }


def build_evidence_packet(context: dict[str, Any] | None) -> dict[str, Any]:
    context = context or {}
    raw_hits = list(context.get("adopted_hits") or context.get("hits") or [])
    citations = [_citation_from_hit(hit) for hit in raw_hits]
    authoritative = [item for item in citations if item["authority"]]
    candidates = [item for item in citations if not item["authority"]]
    packet = {
        "contract_version": "scbkr.evidence.v2",
        "formal_stores": list(FORMAL_STORES),
        "citations": authoritative,
        "candidates": candidates,
        "must_cite_ids": [item["citation_id"] for item in authoritative if item["must_cite"]],
        "authority_count": len(authoritative),
        "candidate_count": len(candidates),
        "vector_is_discovery_only": True,
    }
    validate_evidence_packet(packet)
    return packet


def validate_evidence_packet(packet: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(packet, dict):
        raise ValueError("evidence packet must be an object")
    for citation in packet.get("citations", []):
        if citation.get("source_store") not in AUTHORITATIVE_STORES:
            raise ValueError("authoritative citation must come from corpus, logic, or memory")
        if citation.get("authority") is not True:
            raise ValueError("citation authority must be true")
        if citation.get("review_passed") is not True:
            raise ValueError("authoritative citation must be reviewed")
        if citation.get("signature_status") not in SIGNED_STATUSES:
            raise ValueError("authoritative citation must be owner-signed or verified")
        if citation.get("status") in INACTIVE_STATUSES:
            raise ValueError("inactive citation cannot be authoritative")
        for key in ("citation_id", "source_id", "content_hash", "version", "excerpt"):
            if not str(citation.get(key) or "").strip():
                raise ValueError(f"citation.{key} is required")
    if any(item.get("authority") is True for item in packet.get("candidates", [])):
        raise ValueError("candidate evidence cannot carry authority")
    return packet
