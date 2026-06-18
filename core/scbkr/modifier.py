"""Pure SCBKR P4 draft modification helpers."""

from copy import deepcopy

ALLOWED_CONFIRMATION_STATUSES = ("draft", "waiting_user_confirm", "confirmed", "modified")


def apply_scbkr_modifications(scbkr_draft, modifications):
    """Return a modified copy of a SCBKR draft without mutating the original."""
    updated_draft = deepcopy(scbkr_draft)
    for key, value in modifications.items():
        if isinstance(value, dict) and isinstance(updated_draft.get(key), dict):
            updated_draft[key].update(deepcopy(value))
        else:
            updated_draft[key] = deepcopy(value)
    return updated_draft


def set_confirmation_status(scbkr_draft, confirmation_status):
    """Return a copy with only the SCBKR confirmation_status field changed."""
    if confirmation_status not in ALLOWED_CONFIRMATION_STATUSES:
        raise ValueError(
            "confirmation_status must be one of: "
            + ", ".join(ALLOWED_CONFIRMATION_STATUSES)
        )
    updated_draft = deepcopy(scbkr_draft)
    updated_draft["confirmation_status"] = confirmation_status
    return updated_draft
