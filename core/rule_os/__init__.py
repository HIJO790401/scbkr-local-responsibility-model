"""Local SCBKR rule operating-system helpers."""

from .classifier import classify_user_input
from .compiler import compile_executable_rule
from .depth import apply_plan_depth_to_draft
from .i18n import rule_os_text
from .post_check import check_model_answer_against_rule_package, downgrade_answer_to_draft
from .rule_package import (
    build_current_rule_package,
    build_rule_package_messages,
    build_rule_package_local_reply,
)

__all__ = [
    "apply_plan_depth_to_draft",
    "build_current_rule_package",
    "build_rule_package_local_reply",
    "build_rule_package_messages",
    "check_model_answer_against_rule_package",
    "classify_user_input",
    "compile_executable_rule",
    "downgrade_answer_to_draft",
    "rule_os_text",
]
