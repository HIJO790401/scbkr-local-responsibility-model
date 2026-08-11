"""OpenAI-compatible request builders for the P5 model gateway.

These helpers only build dictionaries. They do not perform network calls.
"""


def build_chat_completion_payload(messages, settings, response_format=None):
    """Build an OpenAI-compatible chat completion payload without sending it."""
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")
    model_name = settings.get("model_name", "")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("model_name must be a non-empty string")
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": settings.get("temperature"),
        "max_tokens": settings.get("max_tokens"),
    }
    chat_template_kwargs = settings.get("chat_template_kwargs")
    if isinstance(chat_template_kwargs, dict):
        payload["chat_template_kwargs"] = dict(chat_template_kwargs)
    elif _uses_local_qwen35(settings):
        # Qwen3.5 thinks by default. For bounded desktop authoring calls that
        # can consume the whole output budget before a user-visible answer.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    explicit_thinking = isinstance(chat_template_kwargs, dict) and chat_template_kwargs.get("enable_thinking") is True
    if (
        _uses_local_qwen35(settings)
        and str(settings.get("provider") or "").lower() == "lm_studio"
        and not explicit_thinking
    ):
        # LM Studio exposes the model's public reasoning switch through the
        # OpenAI-compatible reasoning_effort field.
        payload["reasoning_effort"] = "none"
    if response_format is not None:
        payload["response_format"] = response_format
    return payload


def _uses_local_qwen35(settings):
    model_name = str(settings.get("model_name") or "").lower().replace("_", "").replace("-", "")
    base_url = str(settings.get("base_url") or "").lower()
    loopback = any(host in base_url for host in ("127.0.0.1", "localhost", "[::1]"))
    return loopback and "qwen3.5".replace(".", "") in model_name.replace(".", "")


def build_headers(settings):
    """Build authorization headers without printing or logging the API key."""
    return {
        "Authorization": f"Bearer {settings.get('api_key', '')}",
        "Content-Type": "application/json",
    }
