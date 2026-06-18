"""SCBKR P1 five-dimension constants.

This module contains pure data structures only. It performs no IO and does
not call files, databases, models, APIs, or external tools.
"""

SCBKR_DIMENSIONS = ["S", "C", "B", "K", "R"]

SCBKR_REQUIRED_FIELDS = {
    "S": [
        "task_name",
        "user_instruction",
        "task_subject",
        "input_content",
        "output_format",
        "interface_type",
        "platform_type",
        "confirmation_status",
        "pending_questions",
    ],
    "C": [
        "flow_steps",
        "execution_order",
        "data_flow",
        "event_flow",
        "core_logic",
        "dependencies",
        "failure_impact",
        "test_conditions",
        "pending_questions",
    ],
    "B": [
        "data_read_scope",
        "data_write_scope",
        "local_scope",
        "external_scope",
        "permission_switches",
        "stop_conditions",
        "error_handling",
        "sensitive_operation_confirm",
        "storage_conditions",
        "pending_questions",
    ],
    "K": [
        "references",
        "technical_docs",
        "corpus_sources",
        "style_settings",
        "framework_choice",
        "model_basis",
        "history_cases",
        "source_credibility",
        "pending_questions",
    ],
    "R": [
        "expected_outputs",
        "acceptance_criteria",
        "ledger_requirements",
        "storage_options",
        "signature_status",
        "review_status",
        "replay_requirements",
        "memory_rule_generated",
        "pending_questions",
    ],
}
