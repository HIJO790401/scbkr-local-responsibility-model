import json
from pathlib import Path

import pytest

from core.permissions.permission_checker import (
    assert_permission_allowed,
    check_permission_for_operation,
    validate_permission_settings,
)
from core.permissions.permission_flags import DEFAULT_PERMISSION_SETTINGS, PERMISSION_FLAGS
from core.permissions.risk_policy import validate_operation

SCHEMA_PATH = Path("schemas/permission_settings.schema.json")

EXPECTED_PERMISSION_FLAGS = (
    "model_generate",
    "external_api",
    "web_search",
    "local_file_access",
    "storage_write",
    "ledger_write",
    "sqlite_runtime",
    "chromadb_runtime",
    "embedding_runtime",
    "memory_write",
    "dangerous_operation_confirmed",
)

DENIED_OPERATION_CASES = (
    ("external_api", "external_api_call"),
    ("web_search", "web_search"),
    ("local_file_access", "local_file_read"),
    ("storage_write", "storage_write"),
    ("ledger_write", "ledger_append"),
    ("sqlite_runtime", "sqlite_runtime"),
    ("chromadb_runtime", "chromadb_runtime"),
    ("embedding_runtime", "embedding_create"),
    ("memory_write", "memory_write"),
    ("model_generate", "model_generate"),
)

CONFIRMATION_OPERATION_CASES = (
    ("external_api", "external_api_call"),
    ("storage_write", "storage_write"),
    ("memory_write", "memory_write"),
    ("chromadb_runtime", "chromadb_runtime"),
    ("sqlite_runtime", "sqlite_runtime"),
)


def permission_settings(**overrides):
    settings = dict(DEFAULT_PERMISSION_SETTINGS)
    settings.update(overrides)
    return settings


def test_permission_settings_schema_is_valid_json():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    assert set(EXPECTED_PERMISSION_FLAGS).issubset(schema["properties"])
    assert "updated_at" in schema["properties"]


def test_permission_settings_schema_defaults_all_permissions_false():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    for flag in EXPECTED_PERMISSION_FLAGS:
        assert schema["properties"][flag]["type"] == "boolean"
        assert schema["properties"][flag]["default"] is False


def test_permission_flags_are_complete():
    assert PERMISSION_FLAGS == EXPECTED_PERMISSION_FLAGS


def test_default_permission_settings_are_all_false():
    for flag in EXPECTED_PERMISSION_FLAGS:
        assert DEFAULT_PERMISSION_SETTINGS[flag] is False
    assert DEFAULT_PERMISSION_SETTINGS["updated_at"] is None


def test_validate_permission_settings_rejects_missing_flag():
    permissions = permission_settings()
    permissions.pop("web_search")

    with pytest.raises(ValueError, match="Missing permission flag"):
        validate_permission_settings(permissions)


def test_validate_permission_settings_rejects_non_boolean_flag():
    permissions = permission_settings(web_search="false")

    with pytest.raises(ValueError, match="must be boolean"):
        validate_permission_settings(permissions)


def test_invalid_operation_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported operation"):
        validate_operation("unknown_operation")

    with pytest.raises(ValueError, match="Unsupported operation"):
        check_permission_for_operation(permission_settings(), "unknown_operation")


@pytest.mark.parametrize(("flag", "operation"), DENIED_OPERATION_CASES)
def test_permission_false_denies_operation(flag, operation):
    permissions = permission_settings(**{flag: False})

    result = check_permission_for_operation(permissions, operation)

    assert result["operation"] == operation
    assert result["allowed"] is False
    assert result["requires_confirmation"] is False
    assert flag in result["missing_permissions"]
    assert result["next_required_action"] == "user_enable_required_permissions"


@pytest.mark.parametrize(("flag", "operation"), CONFIRMATION_OPERATION_CASES)
def test_high_risk_operation_requires_confirmation_when_permission_enabled(flag, operation):
    permissions = permission_settings(**{flag: True, "dangerous_operation_confirmed": False})

    result = check_permission_for_operation(permissions, operation)

    assert result["allowed"] is False
    assert result["requires_confirmation"] is True
    assert result["missing_permissions"] == []
    assert result["next_required_action"] == "user_confirm_high_risk_operation"


def test_required_permission_and_high_risk_confirmation_allows_operation_without_execution_claim():
    permissions = permission_settings(
        external_api=True,
        dangerous_operation_confirmed=True,
    )

    result = check_permission_for_operation(permissions, "external_api_call")

    assert result["allowed"] is True
    assert result["requires_confirmation"] is False
    assert result["reason"] == "operation_authorized_not_executed"
    assert "executed" not in result
    assert "runtime_result" not in result
    assert "storage_written" not in result
    assert "ledger_written" not in result
    assert "model_generated" not in result


def test_assert_permission_allowed_raises_for_denied_and_confirmation_required():
    denied_permissions = permission_settings()
    confirmation_permissions = permission_settings(
        external_api=True,
        dangerous_operation_confirmed=False,
    )

    with pytest.raises(PermissionError):
        assert_permission_allowed(denied_permissions, "external_api_call")

    with pytest.raises(PermissionError):
        assert_permission_allowed(confirmation_permissions, "external_api_call")


def test_assert_permission_allowed_returns_true_for_allowed():
    permissions = permission_settings(model_generate=True)

    assert assert_permission_allowed(permissions, "model_generate") is True
