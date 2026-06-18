import json
from pathlib import Path

import pytest

from core.model_gateway.connection_test import (
    build_model_test_request,
    make_test_status,
    parse_model_test_result,
)
from core.model_gateway.openai_compatible import build_chat_completion_payload, build_headers
from core.model_gateway.response_parser import parse_chat_completion_response
from core.model_gateway.settings import (
    DEFAULT_MODEL_SETTINGS,
    MODEL_MODES,
    MODEL_PROVIDERS,
    MODEL_TEST_STATUSES,
    can_enable_generate,
    mask_api_key,
    validate_model_settings,
)


def enabled_settings(**overrides):
    settings = dict(DEFAULT_MODEL_SETTINGS)
    settings.update(
        {
            "enabled": True,
            "model_name": "local-model",
            "last_test_status": "success",
        }
    )
    settings.update(overrides)
    return settings


def test_model_settings_schema_is_valid_json_schema_shape():
    schema = json.loads(Path("schemas/model_settings.schema.json").read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert tuple(schema["properties"]["provider"]["enum"]) == MODEL_PROVIDERS
    assert tuple(schema["properties"]["mode"]["enum"]) == MODEL_MODES
    assert tuple(schema["properties"]["last_test_status"]["enum"]) == MODEL_TEST_STATUSES


def test_default_model_settings_enabled_false_and_valid():
    assert DEFAULT_MODEL_SETTINGS["enabled"] is False
    assert DEFAULT_MODEL_SETTINGS["provider"] == "lm_studio"
    assert DEFAULT_MODEL_SETTINGS["mode"] == "local"
    assert DEFAULT_MODEL_SETTINGS["last_test_status"] == "untested"
    assert validate_model_settings(dict(DEFAULT_MODEL_SETTINGS)) is True


def test_validate_model_settings_rejects_invalid_provider_and_mode():
    invalid_provider = dict(DEFAULT_MODEL_SETTINGS)
    invalid_provider["provider"] = "unknown"
    with pytest.raises(ValueError):
        validate_model_settings(invalid_provider)

    invalid_mode = dict(DEFAULT_MODEL_SETTINGS)
    invalid_mode["mode"] = "cloud"
    with pytest.raises(ValueError):
        validate_model_settings(invalid_mode)


def test_mask_api_key_does_not_expose_full_key():
    api_key = "sk-test-secret-key"
    masked = mask_api_key(api_key)

    assert masked != api_key
    assert api_key not in masked
    assert "****" in masked
    assert mask_api_key("abc") == "****"


def test_can_enable_generate_locks_disabled_model_name_and_test_status():
    permissions = {"external_api": True}

    assert can_enable_generate(enabled_settings(enabled=False), permissions) is False
    assert can_enable_generate(enabled_settings(model_name="  "), permissions) is False
    assert can_enable_generate(enabled_settings(last_test_status="failed"), permissions) is False
    assert can_enable_generate(enabled_settings(last_test_status="untested"), permissions) is False


def test_can_enable_generate_requires_external_api_permission_for_external_or_hybrid():
    assert can_enable_generate(enabled_settings(mode="external"), {"external_api": False}) is False
    assert can_enable_generate(enabled_settings(mode="hybrid"), {"external_api": False}) is False
    assert can_enable_generate(enabled_settings(mode="external"), {"external_api": True}) is True
    assert can_enable_generate(enabled_settings(mode="local"), {"external_api": False}) is True


def test_build_chat_completion_payload_only_builds_payload():
    messages = [{"role": "user", "content": "測試"}]
    payload = build_chat_completion_payload(messages, enabled_settings())

    assert payload == {
        "model": "local-model",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 4096,
    }

    with pytest.raises(ValueError):
        build_chat_completion_payload("not-list", enabled_settings())

    with pytest.raises(ValueError):
        build_chat_completion_payload(messages, enabled_settings(model_name=""))


def test_build_headers_does_not_print_or_log_api_key(capsys):
    api_key = "sk-test-secret-key"
    headers = build_headers(enabled_settings(api_key=api_key))
    captured = capsys.readouterr()

    assert headers["Authorization"] == f"Bearer {api_key}"
    assert api_key not in captured.out
    assert api_key not in captured.err


def test_parse_chat_completion_response_content_and_missing_content():
    response = {"choices": [{"message": {"content": "模型測試內容"}}]}

    assert parse_chat_completion_response(response) == "模型測試內容"

    with pytest.raises(ValueError):
        parse_chat_completion_response({"choices": [{"message": {}}]})


def test_connection_test_helpers_do_not_execute_real_connection():
    settings = enabled_settings(base_url="http://localhost:1234/v1")
    request = build_model_test_request(settings)
    response = {"choices": [{"message": {"content": "ok"}}]}
    status = parse_model_test_result(response)
    failed_status = make_test_status(False, "not connected")

    assert request["method"] == "POST"
    assert request["url"] == "http://localhost:1234/v1/chat/completions"
    assert request["payload"]["model"] == "local-model"
    assert request["timeout"] == 120
    assert status["last_test_status"] == "success"
    assert status["last_test_message"] == "ok"
    assert failed_status["last_test_status"] == "failed"
