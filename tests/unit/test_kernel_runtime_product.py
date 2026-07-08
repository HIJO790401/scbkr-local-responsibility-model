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


def test_plan_depth_adds_paid_depth_without_changing_rule_owner():
    free = compile_rule_from_input(RULE_INPUT, plan_level="FREE")["draft"]
    nt690 = apply_plan_depth(free, "NT690")
    nt3300 = apply_plan_depth(free, "NT3300")
    assert "responsibility_boundary" in nt690["plan_depth"]["adds"]
    assert "rulebook_audit_record" in nt3300
    assert "dual_signature_conditions" in nt3300["R"]
    assert nt3300["meta"]["user_rule_owner"] == "local_user"


def test_signature_policy_blocks_model_signature_and_marks_paid_dual_lock():
    free = signature_policy("FREE")
    paid = signature_policy("NT3300")
    record = build_signature_record("owner-signature", plan_level="FREE")
    assert free["model_signature_allowed"] is False
    assert free["user_signature_required"] is True
    assert paid["dual_signature"]["locked"] is False
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
