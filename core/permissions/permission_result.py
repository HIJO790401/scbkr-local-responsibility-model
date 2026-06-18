"""Pure permission result builders for P10 authorization decisions."""


def build_permission_allowed_result(operation, required_permissions, risk_level):
    return {
        "operation": operation,
        "allowed": True,
        "requires_confirmation": False,
        "risk_level": risk_level,
        "required_permissions": list(required_permissions),
        "missing_permissions": [],
        "reason": "operation_authorized_not_executed",
        "next_required_action": "proceed_with_authorized_operation",
    }


def build_permission_denied_result(
    operation,
    required_permissions,
    missing_permissions,
    reason,
    risk_level="medium",
):
    return {
        "operation": operation,
        "allowed": False,
        "requires_confirmation": False,
        "risk_level": risk_level,
        "required_permissions": list(required_permissions),
        "missing_permissions": list(missing_permissions),
        "reason": reason,
        "next_required_action": "user_enable_required_permissions",
    }


def build_permission_confirmation_required_result(operation, required_permissions, risk_level, reason):
    return {
        "operation": operation,
        "allowed": False,
        "requires_confirmation": True,
        "risk_level": risk_level,
        "required_permissions": list(required_permissions),
        "missing_permissions": [],
        "reason": reason,
        "next_required_action": "user_confirm_high_risk_operation",
    }
