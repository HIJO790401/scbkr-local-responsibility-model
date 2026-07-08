"""L0 gate for direct SCBKR compilation."""

from __future__ import annotations

from typing import Any


def evaluate_l0_gate(user_input: str, kernel_pack: dict[str, Any]) -> dict[str, Any]:
    text = (user_input or "").strip()
    wants_rule = any(token in text.lower() for token in ("規則", "以後凡是", "以後都", "rule", "rulebook", "local rule"))
    passed = bool(text) and wants_rule and bool(kernel_pack.get("L0_ZEROTH_THEOREM"))
    return {
        "passed": passed,
        "gate": "L0_ZEROTH_THEOREM",
        "route": "generate_rule" if passed else "normal_chat",
        "reason": "reusable_judgement_requires_direct_scbkr" if passed else "not_a_rule_generation_request",
    }

