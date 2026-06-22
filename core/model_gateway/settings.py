"""Pure model gateway settings validation and safety helpers."""

MODEL_PROVIDERS = ("lm_studio", "ollama", "openai_compatible", "custom", "sandbox_mock_model")
MODEL_MODES = ("local", "external", "hybrid", "sandbox")
MODEL_TEST_STATUSES = ("untested", "success", "failed")

DEFAULT_MODEL_SETTINGS = {
    "provider": "lm_studio",
    "mode": "local",
    "base_url": "http://localhost:1234/v1",
    "api_key": "local",
    "model_name": "",
    "temperature": 0.2,
    "max_tokens": 4096,
    "context_length": 8192,
    "timeout": 120,
    "enabled": False,
    "last_test_status": "untested",
    "last_test_message": "",
    "last_test_at": None,
    "updated_at": None,
}

REQUIRED_MODEL_SETTING_FIELDS = tuple(DEFAULT_MODEL_SETTINGS.keys())


def validate_model_settings(settings):
    """Validate model gateway settings fields without IO or network calls."""
    if not isinstance(settings, dict):
        raise ValueError("model settings must be an object")

    missing_fields = [field for field in REQUIRED_MODEL_SETTING_FIELDS if field not in settings]
    if missing_fields:
        raise ValueError(f"model settings missing required fields: {', '.join(missing_fields)}")

    if settings["provider"] not in MODEL_PROVIDERS:
        raise ValueError(f"provider must be one of: {', '.join(MODEL_PROVIDERS)}")
    if settings["mode"] not in MODEL_MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODEL_MODES)}")
    if settings["last_test_status"] not in MODEL_TEST_STATUSES:
        raise ValueError(f"last_test_status must be one of: {', '.join(MODEL_TEST_STATUSES)}")

    if not isinstance(settings["base_url"], str):
        raise ValueError("base_url must be a string")
    if not isinstance(settings["api_key"], str):
        raise ValueError("api_key must be a string")
    if not isinstance(settings["model_name"], str):
        raise ValueError("model_name must be a string")
    if not isinstance(settings["temperature"], (int, float)):
        raise ValueError("temperature must be a number")
    if not isinstance(settings["max_tokens"], int) or settings["max_tokens"] < 1:
        raise ValueError("max_tokens must be a positive integer")
    if not isinstance(settings["context_length"], int) or settings["context_length"] < 1:
        raise ValueError("context_length must be a positive integer")
    if not isinstance(settings["timeout"], int) or settings["timeout"] < 1:
        raise ValueError("timeout must be a positive integer")
    if not isinstance(settings["enabled"], bool):
        raise ValueError("enabled must be a boolean")
    if settings["last_test_at"] is not None and not isinstance(settings["last_test_at"], str):
        raise ValueError("last_test_at must be a string or null")
    if settings["updated_at"] is not None and not isinstance(settings["updated_at"], str):
        raise ValueError("updated_at must be a string or null")

    return True


def mask_api_key(api_key):
    """Return a masked API key that never exposes the complete original key."""
    if not api_key:
        return ""
    if len(api_key) <= 4:
        return "****"
    return f"{api_key[:2]}****{api_key[-2:]}"


def can_enable_generate(settings, permissions):
    """Return whether future generation may be enabled by model settings and permissions."""
    validate_model_settings(settings)
    if settings["mode"] == "sandbox":
        return settings["provider"] == "sandbox_mock_model" and permissions.get("model_generate", False) is True
    if not settings["enabled"]:
        return False
    if not settings["model_name"].strip():
        return False
    if settings["last_test_status"] != "success":
        return False
    if settings["mode"] in ("external", "hybrid") and not permissions.get("external_api", False):
        return False
    return True
