"""Pure permission flag constants for the P10 permission lock."""

PERMISSION_FLAGS = (
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

DEFAULT_PERMISSION_SETTINGS = {
    "model_generate": False,
    "external_api": False,
    "web_search": False,
    "local_file_access": False,
    "storage_write": False,
    "ledger_write": False,
    "sqlite_runtime": False,
    "chromadb_runtime": False,
    "embedding_runtime": False,
    "memory_write": False,
    "dangerous_operation_confirmed": False,
    "updated_at": None,
}

HIGH_RISK_PERMISSION_FLAGS = (
    "external_api",
    "web_search",
    "local_file_access",
    "storage_write",
    "ledger_write",
    "sqlite_runtime",
    "chromadb_runtime",
    "embedding_runtime",
    "memory_write",
)
