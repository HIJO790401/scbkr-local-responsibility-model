from core.audit.signature_policy import build_signature_record, signature_policy
from core.kernel.scbkr_kernel_compiler import compile_kernel_pack
from core.runtime.local_scbkr_runtime import compile_rule_from_input
from core.rule_os.rule_package import build_current_rule_package
from core.scbkr.plan_depth_compiler import apply_plan_depth


RULE_INPUT = "以後凡是朋友要求我先墊錢，我要先判斷這是不是風險轉嫁，把這個寫成我的本地規則。"


def test_kernel_pack_contains_required_product_sections(tmp_path):
    pack = compile_kernel_pack(tmp_path / "kernel_pack.json")
    assert pack["meta"]["source_role"] == "AUTHOR_KERNEL_SOURCE"
    for key in (
        "L0_ZEROTH_THEOREM",
        "SCBKR_CORE",
        "VALIDITY_FAILURE_GATE",
        "OWNER_RECALL",
        "FOUR_STORE_POLICY",
        "USER_RESPONSIBILITY_RULES",
    ):
        assert key in pack


def test_direct_runtime_generates_signable_scbkr_without_model_authority():
    result = compile_rule_from_input(RULE_INPUT, plan_level="FREE", locale="zh-TW")
    draft = result["draft"]
    assert result["route"] == "generate_rule"
    assert result["validator"]["passed"] is True
    assert all(layer in draft for layer in ("S", "C", "B", "K", "R"))
    assert draft["meta"]["model_cannot_sign"] is True
    assert draft["R"]["signature_status"] == "waiting_owner_signature"
    assert "VECTOR" in draft["K"]["four_store_policy"]


def test_plan_depth_is_always_public_free_without_changing_rule_owner():
    free = compile_rule_from_input(RULE_INPUT, plan_level="FREE")["draft"]
    unknown = apply_plan_depth(free, "PRIVATE")
    assert unknown["meta"]["plan_level"] == "FREE"
    assert unknown["plan_depth"]["adds"] == [
        "basic_five_dimensions",
        "user_self_signature",
        "local_storage",
        "local_citation",
        "not_full_closure",
    ]
    assert unknown["meta"]["user_rule_owner"] == "local_user"


def test_signature_policy_blocks_model_signature_and_requires_local_user():
    free = signature_policy("FREE")
    unknown = signature_policy("PRIVATE")
    record = build_signature_record("owner-signature", plan_level="FREE")
    assert free["model_signature_allowed"] is False
    assert free["user_signature_required"] is True
    assert unknown["signature_mode"] == "local_user_only"
    assert record["signature_status"] == "owner_signed"


def test_current_rule_package_only_promotes_signed_active_formal_sources():
    context = {
        "hits": [
            {
                "source_store": "logic",
                "rule": "朋友要求先墊錢時，先判斷是否為風險轉嫁。",
                "adopted": True,
                "review_passed": True,
                "signature_status": "owner_signed",
                "status": "active",
            },
            {
                "source_store": "vector",
                "rule": "向量召回候選",
                "adopted": True,
                "review_passed": True,
                "signature_status": "owner_signed",
                "status": "active",
            },
        ]
    }
    package = build_current_rule_package("朋友說月底還我，要我今天先墊三萬，可以嗎？", context)
    assert package["chat_context_used"] is False
    assert package["matched_rules"][0]["source_store"] == "logic"
    assert package["matched_rules"][0]["active"] is True
    assert not package["citable_data"]
    assert package["retrieval_candidates"][0]["source_store"] == "vector"


def test_owner_signed_local_rule_takes_priority_over_an_adopted_external_rulepack():
    context = {
        "hits": [
            {
                "source_store": "logic",
                "rule": "使用者已簽名規則：未確認金額與證據前不得墊款。",
                "adopted": True,
                "review_passed": True,
                "signature_status": "owner_signed",
                "status": "active",
                "source_id": "local-owner-rule",
            },
            {
                "source_store": "logic",
                "rule": "外部普遍說法：朋友之間應互相墊款。",
                "adopted": True,
                "review_passed": True,
                "signature_status": "verified",
                "status": "active",
                "source_id": "external-pack-rule",
            },
        ]
    }

    package = build_current_rule_package("朋友要我先墊三萬，可以嗎？", context)

    assert [item["source_id"] for item in package["matched_rules"]] == ["local-owner-rule"]
    assert any(item["source_id"] == "external-pack-rule" for item in package["non_citable_data"])
    assert package["external_generalizations_override_active_rule_state"] is False
    assert package["rule_authority_precedence"][0] == "owner_signed_local_rule"


def test_explicitly_adopted_verified_pack_can_be_used_when_no_local_rule_conflicts():
    context = {
        "hits": [
            {
                "source_store": "logic",
                "rule": "使用者已明確採用的外部規則包條文。",
                "adopted": True,
                "review_passed": True,
                "signature_status": "verified",
                "status": "active",
                "source_id": "adopted-pack-rule",
            }
        ]
    }

    package = build_current_rule_package("依我採用的規則判斷", context)

    assert package["matched_rules"][0]["source_id"] == "adopted-pack-rule"
    assert package["matched_rules"][0]["authority_origin"] == "explicitly_adopted_verified_rulepack"
