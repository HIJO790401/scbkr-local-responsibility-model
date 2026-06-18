"""Connection-test request structures for P5 model gateway.

The helpers in this module never execute network requests. Callers must pass
responses explicitly if they want to parse a test result.
"""

from datetime import UTC, datetime

from core.model_gateway.openai_compatible import build_chat_completion_payload
from core.model_gateway.response_parser import parse_chat_completion_response


def build_model_test_request(settings):
    """Build a model test request dictionary without sending it."""
    payload = build_chat_completion_payload(
        [{"role": "user", "content": "請回覆 SCBKR model gateway test。"}],
        settings,
    )
    return {
        "method": "POST",
        "url": settings.get("base_url", "").rstrip("/") + "/chat/completions",
        "payload": payload,
        "timeout": settings.get("timeout"),
    }


def parse_model_test_result(response):
    """Parse a caller-supplied test response without making a connection."""
    content = parse_chat_completion_response(response)
    return make_test_status(True, content)


def make_test_status(success, message):
    """Create a model test status dictionary."""
    return {
        "last_test_status": "success" if success else "failed",
        "last_test_message": message,
        "last_test_at": datetime.now(UTC).isoformat(),
    }
