"""Pure operation-to-permission and operation-to-risk mappings for P10."""

OPERATION_PERMISSION_REQUIREMENTS = {
    "model_generate": ["model_generate"],
    "external_api_call": ["external_api"],
    "web_search": ["web_search"],
    "local_file_read": ["local_file_access"],
    "storage_write": ["storage_write"],
    "ledger_append": ["ledger_write"],
    "sqlite_runtime": ["sqlite_runtime"],
    "chromadb_runtime": ["chromadb_runtime"],
    "embedding_create": ["embedding_runtime"],
    "memory_write": ["memory_write"],
    "high_risk_operation": ["dangerous_operation_confirmed"],
}

OPERATION_RISK_LEVELS = {
    "model_generate": "medium",
    "external_api_call": "high",
    "web_search": "high",
    "local_file_read": "high",
    "storage_write": "critical",
    "ledger_append": "critical",
    "sqlite_runtime": "critical",
    "chromadb_runtime": "critical",
    "embedding_create": "high",
    "memory_write": "critical",
    "high_risk_operation": "critical",
}

HIGH_RISK_OPERATIONS = frozenset(
    operation
    for operation, risk_level in OPERATION_RISK_LEVELS.items()
    if risk_level in {"high", "critical"}
)


def validate_operation(operation):
    """Validate that an operation is known to the P10 permission policy."""
    if operation not in OPERATION_PERMISSION_REQUIREMENTS:
        raise ValueError(f"Unsupported operation: {operation}")
    return True


def required_permissions_for_operation(operation):
    """Return required permission flags for an operation without executing it."""
    validate_operation(operation)
    return list(OPERATION_PERMISSION_REQUIREMENTS[operation])


def risk_level_for_operation(operation):
    """Return the configured risk level for an operation without executing it."""
    validate_operation(operation)
    return OPERATION_RISK_LEVELS[operation]


def operation_requires_confirmation(operation):
    """Return whether an operation requires explicit high-risk confirmation."""
    validate_operation(operation)
    return operation in HIGH_RISK_OPERATIONS
