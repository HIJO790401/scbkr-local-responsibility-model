"""Deterministic pure-Python fallback similarity for P13-C retrieval."""
from __future__ import annotations
import re
from collections import Counter
from math import sqrt
from typing import Any

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")

def build_token_fingerprint(text: str | None) -> dict[str, int]:
    if not text:
        return {}
    tokens = [t.lower() for t in _TOKEN_RE.findall(str(text)) if t.strip()]
    return dict(Counter(tokens))

def score_similarity(query_text: str | None, candidate_text: str | None) -> float:
    q = build_token_fingerprint(query_text)
    c = build_token_fingerprint(candidate_text)
    if not q or not c:
        return 0.0
    common = set(q) & set(c)
    dot = sum(q[t] * c[t] for t in common)
    qn = sqrt(sum(v*v for v in q.values()))
    cn = sqrt(sum(v*v for v in c.values()))
    cosine = dot / (qn * cn) if qn and cn else 0.0
    jaccard = len(common) / len(set(q) | set(c))
    return round((0.75 * cosine) + (0.25 * jaccard), 6)

def route_from_score(score: float) -> str:
    if score >= 0.75: return "A"
    if score >= 0.35: return "B"
    if score > 0: return "C"
    return "none"

def rank_candidates(query_text: str, candidates: list[dict[str, Any]], top_k: int = 3) -> list[dict[str, Any]]:
    ranked=[]
    for candidate in candidates:
        text = candidate.get("retrieval_text") or candidate.get("case_json", {}).get("retrieval_text") or ""
        score = score_similarity(query_text, text)
        ranked.append({**candidate, "score": score, "route": route_from_score(score)})
    ranked.sort(key=lambda x: (-x["score"], x.get("case_id", "")))
    return ranked[:max(0, int(top_k or 3))]


def _case_text(case: dict[str, Any]) -> str:
    parts=[case.get("task_summary"), case.get("raw_input"), case.get("task_type")]
    scbkr=case.get("scbkr_summary") or {}
    if isinstance(scbkr, dict): parts.extend(scbkr.values())
    parts.append(case.get("retrieval_text"))
    return "\n".join(str(p) for p in parts if p)


def score_case_similarity(query_text: str, task_type: str, scbkr: dict[str, Any], case: dict[str, Any]) -> float:
    query = "\n".join([query_text or "", task_type or "", *(str(v) for v in (scbkr or {}).values())])
    return score_similarity(query, _case_text(case))


def rank_candidate_cases(query_text: str, task_type: str, scbkr: dict[str, Any], cases: list[dict[str, Any]], top_k: int = 3) -> list[dict[str, Any]]:
    from core.retrieval.vector_case import assert_case_eligible_for_retrieval
    ranked=[]
    for case in cases:
        assert_case_eligible_for_retrieval(case)
        score=score_case_similarity(query_text, task_type, scbkr, case)
        ranked.append({**case, "score": score, "route": route_from_score(score)})
    ranked.sort(key=lambda x: (-x["score"], x.get("case_id", "")))
    return ranked[:top_k]
