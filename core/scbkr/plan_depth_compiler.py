"""Plan depth compiler for SCBKR drafts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PLAN_LEVELS = {"FREE"}


def _plan(plan_level: str | None) -> str:
    return "FREE"


def apply_plan_depth(draft: dict[str, Any], plan_level: str = "FREE") -> dict[str, Any]:
    plan = _plan(plan_level)
    result = deepcopy(draft)
    result.setdefault("meta", {})["plan_level"] = plan
    result.setdefault("plan_depth", {"plan_level": plan, "adds": []})
    result["plan_depth"]["adds"] = [
        "basic_five_dimensions",
        "user_self_signature",
        "local_storage",
        "local_citation",
        "not_full_closure",
    ]
    return result
