"""Pure P9 responsibility-chain similarity scoring placeholders."""

from core.retrieval.vector_case import assert_case_eligible_for_retrieval

SIMILARITY_ROUTES = ("A", "B", "C", "none")


def _tokens(text):
    return {token for token in str(text).lower().replace("｜", " ").replace("/", " ").split() if token}


def score_task_type_match(query_task_type, case_task_type):
    """Score exact task type match."""
    return 1.0 if query_task_type == case_task_type else 0.0


def score_text_overlap(query_text, case_text):
    """Score simple caller-supplied text overlap without embeddings."""
    query_tokens = _tokens(query_text)
    case_tokens = _tokens(case_text)
    if not query_tokens or not case_tokens:
        return 0.0
    return len(query_tokens & case_tokens) / len(query_tokens | case_tokens)


def score_scbkr_dimension_overlap(scbkr_draft, case_scbkr_summary):
    """Score overlap across S/C/B/K/R responsibility-chain dimensions."""
    scores = []
    for dimension in ("S", "C", "B", "K", "R"):
        scores.append(score_text_overlap(scbkr_draft.get(dimension, ""), case_scbkr_summary.get(dimension, "")))
    return sum(scores) / len(scores)


def score_case_similarity(query, task_type, scbkr_draft, case):
    """Score a candidate case using task type, query text, and SCBKR dimensions."""
    assert_case_eligible_for_retrieval(case)
    task_score = score_task_type_match(task_type, case.get("task_type"))
    text_score = score_text_overlap(query, case.get("task_summary", ""))
    dimension_score = score_scbkr_dimension_overlap(scbkr_draft, case.get("scbkr_summary", {}))
    return round((task_score * 0.35) + (text_score * 0.25) + (dimension_score * 0.40), 6)


def route_from_score(score):
    """Map a numeric similarity score to A/B/C/none route."""
    if score >= 0.75:
        return "A"
    if score >= 0.45:
        return "B"
    if score > 0:
        return "C"
    return "none"


def rank_candidate_cases(query, task_type, scbkr_draft, candidate_cases, top_k=3):
    """Rank caller-supplied eligible candidate cases without vector runtime access."""
    ranked_cases = []
    for case in candidate_cases:
        assert_case_eligible_for_retrieval(case)
        score = score_case_similarity(query, task_type, scbkr_draft, case)
        ranked_cases.append(
            {
                "case_id": case.get("case_id"),
                "task_id": case.get("task_id"),
                "task_type": case.get("task_type"),
                "task_summary": case.get("task_summary"),
                "score": score,
                "similarity_route": route_from_score(score),
                "scbkr_summary": case.get("scbkr_summary"),
            }
        )
    ranked_cases.sort(key=lambda item: item["score"], reverse=True)
    return ranked_cases[:top_k]
