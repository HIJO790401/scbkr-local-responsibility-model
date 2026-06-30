from types import SimpleNamespace

from apps.api import main


def request(host="127.0.0.1", token=""):
    return SimpleNamespace(
        client=SimpleNamespace(host=host),
        headers={"X-SCBKR-Companion-Token": token} if token else {},
        query_params={},
    )


def test_pairing_code_is_one_time_and_generated_token_can_be_revoked(monkeypatch):
    monkeypatch.setenv("SCBKR_LAN_COMPANION_ENABLED", "1")
    main.COMPANION_PAIRINGS.clear()
    main.COMPANION_TOKENS.clear()

    started = main.companion_pairing_start(request())
    assert len(started["pairing_code"]) == 6
    assert started["pairing_code"].isdigit()
    redeemed = main.companion_pairing_redeem({"pairing_code": started["pairing_code"], "device_name": "phone"})
    assert main._companion_token_valid(request(host="192.168.1.9", token=redeemed["companion_token"])) is True

    try:
        main.companion_pairing_redeem({"pairing_code": started["pairing_code"]})
        assert False, "pairing code must be one-time"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401

    revoked = main.companion_pairing_revoke_all(request())
    assert revoked["revoked"] is True
    assert main._companion_token_valid(request(host="192.168.1.9", token=redeemed["companion_token"])) is False


def test_pairing_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SCBKR_LAN_COMPANION_ENABLED", raising=False)
    try:
        main.companion_pairing_start(request())
        assert False, "pairing must not start while LAN mode is disabled"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
