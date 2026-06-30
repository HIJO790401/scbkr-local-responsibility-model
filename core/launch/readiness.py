"""SCBKR 2.1 external-service configuration and launch checklist."""

from __future__ import annotations

from copy import deepcopy
import os
from typing import Any

from core.runtime_settings import load_runtime_section, save_runtime_section

DEFAULT_LAUNCH_SETTINGS = {
    "public_domain": "",
    "runtime_service_url": "",
    "supabase_url": "",
    "supabase_publishable_key": "",
    "stripe_publishable_key": "",
    "stripe_monthly_price_id": "",
    "stripe_annual_price_id": "",
    "stripe_customer_portal_url": "",
    "search_provider": "searxng",
    "searxng_url": "",
    "brave_api_key": "",
    "search_timeout": 15,
    "microsoft_partner_product_id": "",
    "code_signing_subject": "",
    "tauri_update_endpoint": "",
    "privacy_policy_url": "",
    "terms_of_service_url": "",
    "support_email": "ken0963521@gmail.com",
}

SECRET_FIELDS = {"brave_api_key"}


def load_launch_settings() -> dict[str, Any]:
    values = load_runtime_section("launch", DEFAULT_LAUNCH_SETTINGS)
    values["brave_api_key"] = os.environ.get("SCBKR_BRAVE_API_KEY", "")
    return values


def save_launch_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_runtime_section("launch", DEFAULT_LAUNCH_SETTINGS)
    update = deepcopy(payload)
    for field in SECRET_FIELDS:
        update.pop(field, None)
        current.pop(field, None)
    merged = {**current, **update}
    merged["search_timeout"] = max(3, min(int(merged.get("search_timeout") or 15), 60))
    save_runtime_section("launch", merged)
    return load_launch_settings()


def public_launch_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    values = deepcopy(settings or load_launch_settings())
    values["brave_api_key_configured"] = bool(values.get("brave_api_key"))
    for field in SECRET_FIELDS:
        values.pop(field, None)
    return values


def launch_readiness(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    values = settings or load_launch_settings()
    search_ready = (values.get("search_provider") == "searxng" and bool(values.get("searxng_url"))) or (values.get("search_provider") == "brave" and bool(values.get("brave_api_key")))
    checks = [
        {"id": "domain", "label": "正式網域", "ready": bool(values.get("public_domain")), "owner_action": True},
        {"id": "auth", "label": "Supabase Auth", "ready": bool(values.get("supabase_url") and values.get("supabase_publishable_key")), "owner_action": True},
        {"id": "billing", "label": "Stripe 月費／年費", "ready": bool(values.get("stripe_publishable_key") and values.get("stripe_monthly_price_id") and values.get("stripe_annual_price_id")), "owner_action": True},
        {"id": "search", "label": "網路搜尋服務", "ready": search_ready, "owner_action": True},
        {"id": "partner", "label": "Microsoft Partner Center", "ready": bool(values.get("microsoft_partner_product_id")), "owner_action": True},
        {"id": "signing", "label": "程式碼簽章", "ready": bool(values.get("code_signing_subject")), "owner_action": True},
        {"id": "updater", "label": "Tauri 更新端點", "ready": bool(values.get("tauri_update_endpoint")), "owner_action": False},
        {"id": "legal", "label": "隱私與服務條款", "ready": bool(values.get("privacy_policy_url") and values.get("terms_of_service_url")), "owner_action": True},
    ]
    ready_count = sum(1 for item in checks if item["ready"])
    return {"checks": checks, "ready_count": ready_count, "total_count": len(checks), "ready_for_private_beta": ready_count >= 5 and search_ready, "ready_for_store_submission": all(item["ready"] for item in checks), "blocked_by": [item["id"] for item in checks if not item["ready"]]}
