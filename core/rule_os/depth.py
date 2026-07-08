"""Compatibility wrapper for SCBKR plan-depth compilation."""

from __future__ import annotations

from typing import Any

from core.scbkr.plan_depth_compiler import apply_plan_depth


def apply_plan_depth_to_draft(raw_input: str, draft: dict[str, Any], plan_level: str = "FREE") -> dict[str, Any]:
    """Apply generic plan depth without scenario-specific branches."""
    result = apply_plan_depth(draft, plan_level)
    result.setdefault("meta", {})["source_input"] = raw_input
    return result

