"""OpenAI-compatible request builders for the P5 model gateway.

These helpers only build dictionaries. They do not perform network calls.
"""


def build_chat_completion_payload(messages, settings):
    """Build an OpenAI-compatible chat completion payload without sending it."""
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")
    model_name = settings.get("model_name", "")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("model_name must be a non-empty string")
    return {
        "model": model_name,
        "messages": messages,
        "temperature": settings.get("temperature"),
        "max_tokens": settings.get("max_tokens"),
    }


def build_headers(settings):
    """Build authorization headers without printing or logging the API key."""
    return {
        "Authorization": f"Bearer {settings.get('api_key', '')}",
        "Content-Type": "application/json",
    }
