"""Pure P9 retrieval result builders."""

from core.retrieval.similarity import route_from_score

ROUTE_REASONS = {
    "A": "高度相似，但不得跳過 SCBKR 使用者確認。",
    "B": "部分相似，僅供調整參考，仍需使用者確認。",
    "C": "低相似，只能輔助參考，仍需使用者確認。",
    "none": "無可用相似案例，需全新生成 SCBKR 草案，仍需使用者確認。",
}


def build_empty_retrieval_result(query):
    """Build an empty retrieval result with no vector runtime access."""
    return {
        "query_summary": str(query),
        "top_cases": [],
        "similarity_route": "none",
        "route_reason": ROUTE_REASONS["none"],
        "usable_as_reference": False,
        "requires_user_confirmation": True,
        "physical_vector_search_performed": False,
        "embedding_created": False,
        "next_required_action": "user_review_retrieval_suggestions",
    }


def build_retrieval_result(query, ranked_cases):
    """Build a retrieval result from already-ranked caller-supplied cases."""
    if not ranked_cases:
        return build_empty_retrieval_result(query)
    best_route = route_from_score(ranked_cases[0]["score"])
    return {
        "query_summary": str(query),
        "top_cases": ranked_cases[:3],
        "similarity_route": best_route,
        "route_reason": ROUTE_REASONS[best_route],
        "usable_as_reference": best_route != "none",
        "requires_user_confirmation": True,
        "physical_vector_search_performed": False,
        "embedding_created": False,
        "next_required_action": "user_review_retrieval_suggestions",
    }
