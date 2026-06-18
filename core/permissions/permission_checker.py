"""Pure permission checker helpers for P10 authorization decisions."""

from core.permissions.permission_flags import PERMISSION_FLAGS
from core.permissions.permission_result import (
    build_permission_allowed_result,
    build_permission_confirmation_required_result,
    build_permission_denied_result,
)
from core.permissions.risk_policy import (
    operation_requires_confirmation,
    required_permissions_for_operation,
    risk_level_for_operation,
    validate_operation,
)


def validate_permission_settings(permissions):
    """Validate that every permission flag exists and is boolean."""
    for flag in PERMISSION_FLAGS:
        if flag not in permissions:
            raise ValueError(f"Missing permission flag: {flag}")
        if not isinstance(permissions[flag], bool):
            raise ValueError(f"Permission flag must be boolean: {flag}")
    return True


def missing_permissions_for_operation(permissions, operation):
    """Return required flags that are not explicitly enabled for an operation."""
    validate_operation(operation)
    required_permissions = required_permissions_for_operation(operation)
    return [flag for flag in required_permissions if permissions.get(flag) is not True]


def check_permission_for_operation(permissions, operation, context=None):
    """Return a permission_result dict without executing the requested operation."""
    _ = context
    validate_permission_settings(permissions)
    validate_operation(operation)
    required_permissions = required_permissions_for_operation(operation)
    risk_level = risk_level_for_operation(operation)
    missing_permissions = missing_permissions_for_operation(permissions, operation)

    if missing_permissions:
        return build_permission_denied_result(
            operation=operation,
            required_permissions=required_permissions,
            missing_permissions=missing_permissions,
            reason="required_permissions_not_enabled",
            risk_level=risk_level,
        )

    if (
        operation_requires_confirmation(operation)
        and permissions["dangerous_operation_confirmed"] is not True
    ):
        return build_permission_confirmation_required_result(
            operation=operation,
            required_permissions=required_permissions,
            risk_level=risk_level,
            reason="high_risk_operation_requires_user_confirmation",
        )

    return build_permission_allowed_result(
        operation=operation,
        required_permissions=required_permissions,
        risk_level=risk_level,
    )


def assert_permission_allowed(permissions, operation, context=None):
    """Raise PermissionError unless the operation is authorized by P10."""
    result = check_permission_for_operation(permissions, operation, context=context)
    if result["allowed"] is not True:
        raise PermissionError(result["reason"])
    return True
