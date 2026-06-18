"""OpenAI-compatible response parser for P5 model gateway."""


def parse_chat_completion_response(response):
    """Parse text content from an OpenAI-compatible response dictionary."""
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("response missing chat completion content") from exc
    if not isinstance(content, str):
        raise ValueError("response chat completion content must be a string")
    return content
