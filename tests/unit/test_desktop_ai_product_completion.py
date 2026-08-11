import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from core.kernel.local_kernel_cache import ensure_local_kernel_cache
from core.scbkr.model_rulebook_author import (
    ModelRulebookAuthoringError,
    apply_model_dimension_patch,
    authoring_to_scbkr_draft,
    build_model_capability_assessment,
    build_model_basis_selection_messages,
    build_model_dimension_explanation_messages,
    build_model_dimension_patch_messages,
    build_model_rulebook_messages,
    compile_kernel_required_clauses,
    compile_model_basis_selection_candidate,
    enforce_kernel_authority_boundary,
    merge_model_dimension_explanation_candidate,
    model_dimension_repair_instruction,
    model_rulebook_repair_targets,
    model_rulebook_response_format,
    parse_model_basis_selection_output,
    parse_model_dimension_explanation_output,
    parse_model_dimension_patch_output,
    parse_model_rulebook_candidate,
    parse_model_rulebook_output,
    refresh_model_rulebook_support_fields,
    validate_model_rulebook_semantics,
)


RULE_REQUEST = "以後凡是朋友要求我先墊錢，我要先判斷這是不是風險轉嫁，把這個寫成我的本地規則。"
FOLLOWUP = "朋友說月底還我，要我今天先墊三萬，可以嗎？"


def test_small_model_prompt_hard_separates_causality_from_boundaries():
    messages = build_model_rulebook_messages(
        "建立美容院文案規則",
        kernel_pack={},
        locale="zh-TW",
    )
    system = messages[0]["content"]

    assert "多步驟用「先……再……」" in system
    assert "條件結果用「若……則……」" in system
    assert "不得把禁止事項當成 C" in system
    assert "K 必須使用「只可引用使用者已確認……；不可引用……」" in system
    assert "S_explanation" in system
    assert "所有值都是短字串" in system
    assert "原始規則需求中的「我／我的」永遠指人類使用者" in system

    english_system = build_model_rulebook_messages(
        "Create a publishing rule that requires my signature.",
        kernel_pack={},
        locale="en",
    )[0]["content"]
    assert "'I', 'me', and 'my' always refer to the human user" in english_system


def test_conditional_causality_is_a_complete_cross_domain_c_path():
    parsed = parse_model_rulebook_candidate(json.dumps({
        "S": "專案維護者在合併程式碼到 main 前檢查發布條件。",
        "S_explanation": "S 鎖定專案維護者、程式碼合併與 main 發布情境。",
        "C": "若自動測試、人工審查或安全掃描任一項失敗，則停止合併。",
        "C_explanation": "C 寫出檢查結果造成停止合併的條件因果。",
        "B": "不得自行部署或替維護者簽名；檢查未確認時必須停止。",
        "B_explanation": "B 限制未驗證部署與代簽。",
        "K": "只可引用使用者已確認的測試、審查與掃描結果；不可引用聊天猜測、未簽名草稿或 VECTOR 候選。",
        "K_explanation": "K 區分正式檢查紀錄與不可引用候選。",
        "R": "由使用者維護者驗收、承擔並簽名；模型不能簽名、入庫或啟用。",
        "R_explanation": "R 將驗收、責任與簽名留給維護者。",
        "rule_summary": "程式碼合併前的品質與責任檢查規則。",
        "missing_information": "各項檢查的實際結果",
        "user_confirmation_items": "維護者確認三項檢查是否通過",
        "model_cannot_decide": "是否正式合併或部署",
        "risk_reminders": "跳過任一檢查可能造成品質或安全問題",
        "next_actions": "維護者逐欄確認後簽名",
    }, ensure_ascii=False), user_input="合併到 main 前必須通過自動測試、人工審查與安全掃描；任何一項失敗就停止。")

    assert parsed["model_semantic_report"]["dimension_role_alignment"]["C"] is True
    assert parsed["model_semantic_valid"] is True


def test_flat_small_model_schema_rehydrates_model_authored_explanations():
    schema = model_rulebook_response_format()["json_schema"]["schema"]
    assert schema["properties"]["S"]["type"] == "string"
    assert schema["properties"]["S_explanation"]["type"] == "string"

    parsed = parse_model_rulebook_candidate(json.dumps({
        "S": "朋友要求使用者先墊錢時啟動風險轉嫁判斷。",
        "S_explanation": "S 鎖定使用者、墊款請求與觸發情境。",
        "C": "先查金額與書面證據，再查還款能力；若資料不足則停止判斷。",
        "C_explanation": "C 把判斷順序與條件結果分開寫清楚。",
        "B": "不得直接建議付款；資料不足時必須停止。",
        "B_explanation": "B 限制模型越權與無證據行動。",
        "K": "只可引用已確認紀錄；不可引用聊天猜測或 VECTOR 候選。",
        "K_explanation": "K 區分正式資料與不可引用內容。",
        "R": "由使用者驗收並簽名；模型不能簽名或替使用者承擔。",
        "R_explanation": "R 將確認、簽名與現實責任留給使用者。",
        "rule_summary": "朋友墊款風險轉嫁規則。",
        "missing_information": "金額上限；書面證據要求",
        "user_confirmation_items": "確認適用對象；確認停止條件",
        "model_cannot_decide": "是否實際付款",
        "risk_reminders": "無憑證付款可能無法回放",
        "next_actions": "使用者逐欄審閱後簽名",
    }, ensure_ascii=False), user_input=RULE_REQUEST)

    assert parsed["S"]["explanation"].startswith("S 鎖定")
    assert parsed["S"].get("schema_adapter_generated") is not True
    assert parsed["model_semantic_valid"] is True


def test_compact_model_explanations_complete_roles_and_expose_support_gaps():
    parsed = parse_model_rulebook_candidate(json.dumps({
        "S": "專案負責人建立程式部署規則，適用於測試與版本核對後的部署任務。",
        "S_explanation": "程式部署的主體與觸發情境。",
        "C": "先跑測試再檢查版本與環境；若測試失敗則停止部署判斷。",
        "C_explanation": "先檢查測試，再檢查環境；若缺資料則停在待確認。",
        "B": "不得在資料未確認時部署",
        "B_explanation": "測試報告或版本紀錄沒有確認時必須停止。",
        "K": "只可引用使用者已確認的測試報告；不可引用聊天猜測或 VECTOR 候選。",
        "K_explanation": "已確認紀錄才是正式依據。",
        "R": "專案負責人驗收簽名",
        "R_explanation": "由專案負責人驗收並簽名；模型不能簽名。",
        "rule_summary": "測試與版本核對完成後才可部署。",
        "missing_information": "",
        "user_confirmation_items": "測試報告與版本紀錄是否已確認",
        "model_cannot_decide": "",
        "risk_reminders": "錯誤版本可能造成部署事故",
        "next_actions": "專案負責人逐欄確認後簽名",
    }, ensure_ascii=False), user_input="建立程式部署規則：先跑測試並核對版本；未確認不得部署。")

    assert parsed["model_semantic_valid"] is True
    assert parsed["model_semantic_report"]["dimension_role_alignment"] == {
        "C": True,
        "B": True,
        "K": True,
        "R": True,
    }
    assert parsed["missing_information"] == ["驗收前待核對：測試報告與版本紀錄是否已確認"]
    assert parsed["model_cannot_decide"] == ["模型不能替使用者簽名、核准或取代使用者的最終判斷。"]
    assert parsed["model_support_fields_derived"] == {
        "model_cannot_decide": "model_R_plus_kernel_authority_boundary",
        "missing_information": "model_user_confirmation_item",
    }


def test_compact_small_model_output_exposes_missing_data_and_risk():
    parsed = parse_model_rulebook_candidate(json.dumps({
        "S": "朋友要求先墊錢的風險轉嫁規則",
        "C": "先查金額、還款條件與證據",
        "B": "資料不足時不得建議付款",
        "K": "只引用已簽名正式資料",
        "R": "使用者簽名並承擔決定",
    }, ensure_ascii=False), user_input=RULE_REQUEST)

    assert parsed["model_schema_repaired"] is True
    assert parsed["missing_information"]
    assert parsed["risk_reminders"]
    assert parsed["user_confirmation_items"]
    assert parsed["model_semantic_valid"] is False
    assert parsed["model_semantic_report"]["model_explanations_present"] is False
    assert parsed["model_semantic_report"]["model_explanation_alignment"] == {
        "S": False,
        "C": False,
        "B": False,
        "K": False,
        "R": False,
    }
    assert model_rulebook_repair_targets(parsed["model_semantic_report"]) == ["C", "K", "R"]


def test_dimension_repair_targets_missing_explanations_after_roles_are_valid():
    report = {
        "dimension_role_alignment": {"C": True, "B": True, "K": True, "R": True},
        "model_support_fields_useful": True,
        "model_explanation_alignment": {
            "S": False,
            "C": False,
            "B": True,
            "K": False,
            "R": True,
        },
    }

    assert model_rulebook_repair_targets(report, limit=5) == ["S", "C", "K"]
    assert "主體" in model_dimension_repair_instruction("S", locale="zh-TW")
    assert "subject" in model_dimension_repair_instruction("S", locale="en").lower()


def test_kernel_preserves_model_basis_and_adds_only_citation_invariant():
    candidate = parse_model_rulebook_candidate(json.dumps({
        "S": "專案負責人建立程式部署規則。適用於每次部署前。 ",
        "S_explanation": "S 鎖定專案負責人與部署前情境。",
        "C": "先跑測試，再檢查版本與環境；若測試失敗則停止部署。",
        "C_explanation": "C 寫出部署前的檢查順序與失敗結果。",
        "B": "沒有回滾方案時不得部署；資料未確認時必須停止。",
        "B_explanation": "B 限制缺少回滾與確認資料的部署。",
        "K": "只可引用已確認的測試報告與版本紀錄。",
        "K_explanation": "K 指定可核對的部署依據。",
        "R": "由專案負責人驗收、承擔並簽名；模型不能簽名。",
        "R_explanation": "R 將驗收與簽名留給專案負責人。",
        "rule_summary": "程式部署確認規則。",
        "missing_information": "實際測試結果",
        "user_confirmation_items": "確認測試與版本紀錄",
        "model_cannot_decide": "是否正式部署",
        "risk_reminders": "無回滾方案會放大部署風險",
        "next_actions": "專案負責人逐欄確認並簽名",
    }, ensure_ascii=False), user_input="部署前只能引用已確認的測試報告與版本紀錄。")

    compiled, audits = compile_kernel_required_clauses(
        candidate,
        user_input="部署前只能引用已確認的測試報告與版本紀錄。",
        locale="zh-TW",
    )

    assert compiled["K"]["content"].startswith("只可引用已確認的測試報告與版本紀錄")
    assert "未確認內容" in compiled["K"]["content"]
    assert "VECTOR 候選不可引用" in compiled["K"]["content"]
    assert any(item["code"] == "k_model_fragment_compiled_with_citation_boundary" for item in audits)


def test_english_citation_boundary_compilation_is_idempotent():
    candidate = {
        "K": {
            "content": "Owner-confirmed order and evidence may be cited; unconfirmed content, chat or model guesses, unsigned drafts, and VECTOR candidates may not be cited.",
            "explanation": "The basis is limited to user-confirmed records.",
        }
    }
    once, first_audit = compile_kernel_required_clauses(
        candidate,
        user_input="Verify the order and evidence before approving a refund.",
        locale="en",
    )
    twice, second_audit = compile_kernel_required_clauses(
        once,
        user_input="Verify the order and evidence before approving a refund.",
        locale="en",
    )

    assert once["K"]["content"] == twice["K"]["content"]
    assert once["K"]["content"].lower().count("may not be cited") == 1
    assert not any(item.get("layer") == "K" for item in first_audit + second_audit)


def test_explanation_only_repair_never_rewrites_accepted_dimension_content():
    content = "只可引用已確認的測試報告與版本紀錄；未確認內容與 VECTOR 候選不可引用。"
    messages = build_model_dimension_explanation_messages(
        "建立程式部署規則。",
        layer="K",
        current_content=content,
        locale="zh-TW",
    )
    explanation = parse_model_dimension_explanation_output(
        json.dumps({"explanation": "K 欄指定測試報告與版本紀錄是部署時可核對的正式依據。"}, ensure_ascii=False),
        layer="K",
        current_content=content,
        user_input="建立程式部署規則。",
        locale="zh-TW",
    )
    bare_explanation = parse_model_dimension_explanation_output(
        'explanation: "K 欄以測試報告與版本紀錄作為程式部署的可核對依據。"',
        layer="K",
        current_content=content,
        user_input="建立程式部署規則。",
        locale="zh-TW",
    )
    candidate = {"K": {"content": content, "explanation": "舊的自動解釋", "schema_adapter_generated": True}}
    merged = merge_model_dimension_explanation_candidate(
        candidate,
        layer="K",
        explanation=explanation,
    )

    assert "只能回傳 explanation" in messages[0]["content"]
    assert merged["K"]["content"] == content
    assert merged["K"]["explanation"] == explanation
    assert merged["K"]["model_explanation_repaired_by_model"] is True
    assert bare_explanation.startswith("K 欄以測試報告")


def test_schema_gap_repair_preserves_valid_dimensions_and_asks_model_for_explanation(tmp_path, monkeypatch):
    request = "建立文件發布規則：未核准不得發布，資料缺失就停止。"
    raw = {
        "S": "使用者準備公開文件時套用本規則。",
        "S_explanation": "S 鎖定使用者與公開文件的觸發情境。",
        "C": "先核對文件版本，再確認使用者已核准；若未核准則停止發布。",
        "C_explanation": "C 寫出版本核對、核准與停止發布的判斷順序。",
        "B": "未核准不得發布；資料缺失時必須停止。",
        "B_explanation": "無",
        "K": "只可引用使用者已確認的文件與版本紀錄；不可引用未確認內容或 VECTOR 候選。",
        "K_explanation": "K 區分正式文件紀錄與召回候選。",
        "R": "由使用者驗收、承擔並簽名；模型不能簽名。",
        "R_explanation": "R 把驗收、責任與簽名留給使用者。",
        "rule_summary": "公開文件前的核准與停止規則。",
        "missing_information": "文件版本與收件對象",
        "user_confirmation_items": "確認文件已核准",
        "model_cannot_decide": "是否正式發布",
        "risk_reminders": "未核准發布可能造成資訊外洩",
        "next_actions": "使用者逐欄確認並簽名",
    }
    try:
        parse_model_rulebook_candidate(
            json.dumps(raw, ensure_ascii=False),
            user_input=request,
        )
    except ModelRulebookAuthoringError as exc:
        parse_error = exc
    else:
        raise AssertionError("the incomplete model explanation must fail schema validation")

    assert parse_error.code == "B_missing_explanation"
    assert parse_error.candidate["B"] == raw["B"]

    repaired_explanation = "B 欄禁止未核准發布，並在資料缺失時停止文件流程。"
    expected_raw = dict(raw)
    expected_raw["B_explanation"] = repaired_explanation
    expected = parse_model_rulebook_candidate(
        json.dumps(expected_raw, ensure_ascii=False),
        user_input=request,
    )
    main = fresh_main(tmp_path, monkeypatch)
    monkeypatch.setattr(
        main,
        "_post_same_model_with_schema",
        lambda *_args, **_kwargs: {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "explanation": repaired_explanation
                    }, ensure_ascii=False)
                }
            }],
            "usage": {"prompt_tokens": 80, "completion_tokens": 24, "total_tokens": 104},
        },
    )
    repaired, audit, _messages = main._repair_model_rulebook_schema_gap(
        parse_error,
        raw_input=request,
        locale="zh-TW",
        settings={"max_tokens": 640},
        provider_usages=[],
    )

    assert repaired["S"]["content"] == expected["S"]["content"]
    assert repaired["B"]["content"] == expected["B"]["content"]
    assert repaired["B"]["explanation"].startswith("B 欄禁止未核准發布")
    assert repaired["B"]["model_explanation_repaired_by_model"] is True
    assert audit["repair_kind"] == "schema_explanation_only"
    assert repaired["model_schema_repaired"] is True


def test_model_repaired_explanation_provenance_survives_compiled_signing_view(tmp_path, monkeypatch):
    candidate = parse_model_rulebook_candidate(json.dumps({
        "S": "專案維護者在程式部署前套用本規則。",
        "S_explanation": "S 鎖定專案維護者與部署前情境。",
        "C": "先跑測試，再檢查版本與環境；若任一檢查失敗則停止部署。",
        "C_explanation": "C 寫出部署檢查順序與失敗結果。",
        "B": "不得略過檢查；資料不足或未確認時必須停止。",
        "B_explanation": "B 限制未驗證部署並設定停止條件。",
        "K": "只可引用使用者已確認的測試報告與版本紀錄；未確認內容與 VECTOR 候選不可引用。",
        "K_explanation": "K 區分正式部署紀錄與召回候選。",
        "R": "由使用者（專案維護者）驗收、承擔並簽名；模型不能簽名。",
        "R_explanation": "R 把驗收、責任與簽名留給使用者（專案維護者）。",
        "rule_summary": "程式部署前的檢查與責任規則。",
        "missing_information": "實際測試結果",
        "user_confirmation_items": "確認版本與環境",
        "model_cannot_decide": "是否正式部署",
        "risk_reminders": "略過檢查可能造成部署事故",
        "next_actions": "專案維護者逐欄確認並簽名",
    }, ensure_ascii=False), user_input="建立程式部署規則：部署前先跑測試並核對版本與環境。")
    for dim in ("S", "C", "B", "K", "R"):
        candidate[dim]["schema_adapter_generated"] = True
        candidate[dim]["model_explanation_preserved_from_alias"] = False
        candidate[dim]["model_explanation_repaired_by_model"] = True
    report = validate_model_rulebook_semantics(
        candidate,
        user_input="建立程式部署規則：部署前先跑測試並核對版本與環境。",
    )
    candidate["model_semantic_valid"] = report["passed"]
    candidate["model_semantic_report"] = report
    draft = authoring_to_scbkr_draft(
        user_input="建立程式部署規則：部署前先跑測試並核對版本與環境。",
        authoring=candidate,
        kernel_pack=ensure_local_kernel_cache(),
        model_provider="lm_studio",
        model_name="test-model",
    )
    main = fresh_main(tmp_path, monkeypatch)
    signing_view = main._compiled_scbkr_authoring_view(draft)

    assert report["passed"] is True, report
    assert all(signing_view[dim]["model_explanation_repaired_by_model"] for dim in ("S", "C", "B", "K", "R"))
    assert validate_model_rulebook_semantics(
        signing_view,
        user_input="建立程式部署規則：部署前先跑測試並核對版本與環境。",
    )["passed"] is True


def test_compact_english_output_keeps_human_explanations_in_english():
    parsed = parse_model_rulebook_candidate(json.dumps({
        "S": "A rule for approving customer refunds.",
        "C": "First check the order record, then decide the refund path.",
        "B": "Do not approve a refund when the order cannot be verified.",
        "K": "Use confirmed order records and the signed refund policy as evidence.",
        "R": "The user must review, sign, and accept responsibility for the rule.",
    }), user_input="Create a reusable customer refund approval rule.", locale="en")

    assert parsed["model_semantic_valid"] is False
    assert parsed["S"]["explanation"].startswith("The model filled")
    assert "模型" not in parsed["S"]["explanation"]


def test_english_prompt_skeleton_and_missing_human_signer_are_not_accepted():
    parsed = parse_model_rulebook_candidate(json.dumps({
        "S": "The user wants a reusable refund approval rule.",
        "S_explanation": "This applies to customer refund requests.",
        "C": "First verify the order, then check the evidence; if records are missing, then stop.",
        "C_explanation": "The checks run in order.",
        "B": "Must not/cannot",
        "B_explanation": "The rule stops when records are missing.",
        "K": "may cite owner-confirmed...; may not cite...",
        "K_explanation": "Only verified records may become formal evidence.",
        "R": "the model cannot sign",
        "R_explanation": "The model has no authority to approve the rule without user confirmation.",
        "rule_summary": "Refund approval draft.",
        "missing_information": "Order and evidence records",
        "user_confirmation_items": "Confirm the records",
        "model_cannot_decide": "Whether the owner signs",
        "risk_reminders": "Incomplete records can produce a wrong refund",
        "next_actions": "Owner review and signature",
    }), user_input="Create a refund rule. Verify the order and evidence, stop when records are missing, and require my signature.", locale="en")

    assert parsed["model_semantic_valid"] is False
    assert parsed["model_semantic_report"]["placeholder_dimensions"] == ["B", "K"]
    assert parsed["model_semantic_report"]["dimension_role_alignment"]["R"] is False


def test_model_claiming_no_boundary_does_not_pass_boundary_role():
    parsed = parse_model_rulebook_candidate(json.dumps({
        "S": "A customer refund approval rule.",
        "S_explanation": "This applies when a customer requests a refund.",
        "C": "First verify the order, then check the evidence; if records are missing, then stop.",
        "C_explanation": "The checks run in order.",
        "B": "No specific forbidden actions or stops are mentioned.",
        "B_explanation": "There are no explicit prohibitions.",
        "K": "Owner-confirmed order records may be cited; unconfirmed chat and VECTOR candidates may not be cited.",
        "K_explanation": "Only confirmed evidence is a formal basis.",
        "R": "The user accepts responsibility and signs; the model cannot sign.",
        "R_explanation": "The user is the accountable signer.",
        "rule_summary": "Refund approval draft.",
        "missing_information": "Order evidence",
        "user_confirmation_items": "Confirm the order evidence",
        "model_cannot_decide": "Whether the user approves the refund",
        "risk_reminders": "Missing records can produce a wrong approval",
        "next_actions": "Owner review and signature",
    }), user_input="Create a refund rule. Stop when order records are missing.", locale="en")

    assert parsed["model_semantic_report"]["dimension_role_alignment"]["B"] is False
    assert parsed["model_semantic_valid"] is False


def test_nested_small_model_fields_are_adapted_without_replacing_model_meaning():
    parsed = parse_model_rulebook_candidate(json.dumps({
        "S": {
            "subject": "使用者公開已核准文件",
            "situation": "每次文件發布前",
        },
        "C": {
            "why_the_rule_exists": "避免錯誤版本或錯誤對象收到文件",
            "causality": "先核對文件版本與收件對象，再確認使用者已核准，最後才判斷是否可發布",
        },
        "B": {
            "boundaries": "只有已核准文件可進入發布判斷",
            "forbidden_actions": ["未核准不得發布", "資料缺失就停止"],
        },
        "K": {
            "basis_policy": "只能引用使用者確認的文件與版本紀錄",
            "logic_corpus_memory_vector": "VECTOR 只能召回候選，不得作正式依據",
        },
        "R": {
            "responsibility": "由使用者驗收並簽名後才生效",
            "failure_replay": "發布失敗時保留版本、核准與輸出紀錄",
            "repair": "修正資料後重新送使用者確認",
        },
    }, ensure_ascii=False), user_input="建立可重用文件發布規則：先核對文件版本及收件對象，未核准不得發布。")

    assert parsed["model_schema_repaired"] is True
    assert parsed["model_semantic_valid"] is False
    assert "使用者公開已核准" in parsed["S"]["content"]
    assert "先核對" in parsed["C"]["content"] and "版本" in parsed["C"]["content"]
    assert "未核准不得發布" in parsed["B"]["content"]
    assert "只能引用使用者確認" in parsed["K"]["content"]
    assert "使用者驗收並簽名" in parsed["R"]["content"]
    assert parsed["S"]["model_original_fields"]["subject"] == "使用者公開已核准檔案"


def test_repeated_or_role_confused_dimensions_are_rejected():
    repeated = json.dumps({dim: "Handle the user's request." for dim in ("S", "C", "B", "K", "R")})
    try:
        parse_model_rulebook_output(repeated, user_input="Create a debt collection rule.", locale="en")
    except ModelRulebookAuthoringError as exc:
        assert str(exc) == "scbkr_semantic_roles_invalid"
    else:
        raise AssertionError("role-confused SCBKR output must be rejected")


def test_boundary_and_basis_swapped_are_rejected():
    swapped = json.dumps({
        "S": "債務民事案件資料整理",
        "C": "先核對當事人，再檢查金額與日期。",
        "B": "借款契約、匯款紀錄與對話資料。",
        "K": "不得替使用者判決勝敗。",
        "R": "使用者確認並簽名後自行承擔決定。",
    }, ensure_ascii=False)
    try:
        parse_model_rulebook_output(swapped, user_input="幫我建立債務民事案件資料整理規則。")
    except ModelRulebookAuthoringError as exc:
        assert str(exc) == "scbkr_semantic_roles_invalid"
    else:
        raise AssertionError("B/K-swapped output must be rejected")


def test_basis_rejects_named_source_restrictions_absent_from_owner_request():
    candidate = parse_model_rulebook_candidate(json.dumps({
        "S": "債務民事案件資料整理",
        "S_explanation": "處理使用者的債務資料整理需求。",
        "C": "先核對當事人與借款證據，再核對金額、日期與時效；若資料不足則停在待確認。",
        "C_explanation": "依序核對使用者點名的事實。",
        "B": "不得替使用者判決勝敗；資料不足時必須停止。",
        "B_explanation": "只整理資料，不代替使用者或法院判斷。",
        "K": "只可引用使用者已確認的資料；不可引用判決書、律師意見等官方文件。",
        "K_explanation": "模型自行增加了原始需求沒有指定的來源限制。",
        "R": "由使用者驗收、承擔並簽名；模型不能簽名。",
        "R_explanation": "最終責任與簽名留給使用者。",
        "rule_summary": "債務資料整理規則。",
        "missing_information": "當事人、證據、金額、日期與時效",
        "user_confirmation_items": "確認資料是否完整",
        "model_cannot_decide": "模型不能判決勝敗",
        "risk_reminders": "個人資料與時效判斷可能有風險",
        "next_actions": "使用者逐欄確認後簽名",
    }, ensure_ascii=False), user_input="整理債務民事案件資料：核對當事人、借款證據、金額、日期與時效；不得替我判決勝敗。")

    assert candidate["model_semantic_valid"] is False
    assert candidate["model_semantic_report"]["k_unrequested_non_citable_sources"] == [
        "判決書",
        "律師意見等官方檔案",
    ]


def test_author_identity_injection_and_signature_as_basis_are_rejected():
    bad = {
        "S": {"content": "許文耀 / 沈耀", "explanation": "產品作者被放成美容院規則主體。"},
        "C": {"content": "不得誇大療效；不得編造價格；若違反則先確認再判斷。", "explanation": "先確認再判斷。"},
        "B": {"content": "不得誇大療效；不得編造價格；若違反則停止。", "explanation": "限制文案內容。"},
        "K": {"content": "只可引用沈耀的審核與簽名；不可引用其他資料。", "explanation": "把簽名當成依據。"},
        "R": {"content": "由沈耀驗收簽名；模型不能簽名。", "explanation": "使用者需要簽名。"},
        "rule_summary": "美容院文案規則",
        "missing_information": [],
        "user_confirmation_items": ["確認規則內容"],
        "model_cannot_decide": ["模型不能簽名"],
        "risk_reminders": ["未確認內容可能誤導"],
        "next_actions": ["使用者審閱"],
    }
    candidate = parse_model_rulebook_candidate(
        json.dumps(bad, ensure_ascii=False),
        user_input="建立美容院文案規則，不得誇大療效或編造價格。",
    )

    report = candidate["model_semantic_report"]
    assert report["passed"] is False
    assert report["subject_request_alignment"] is False
    assert report["unrequested_identity_injection"] is True
    assert report["k_signature_as_basis"] is True


def test_model_dimension_patch_updates_executable_boundary_fields():
    patch = parse_model_dimension_patch_output(
        json.dumps({
            "content": "未取得使用者確認前不得發布，也不得編造價格；資料不足時必須停止。",
            "explanation": "這個修改把發布權限、價格真實性與停止條件寫入 B 層。",
            "missing_information": ["正式價格表"],
            "needs_user_confirmation": ["確認發布核准人"],
            "model_cannot_decide": ["是否核准發布"],
            "risk_notes": ["錯誤價格可能造成客訴"],
        }, ensure_ascii=False),
        layer="B",
        instruction="補上未確認不得發布與不得編造價格",
    )
    current = {
        "forbidden": ["模型不得簽名"],
        "stop_conditions": ["使用者未簽名"],
        "data_read_scope": ["使用者輸入"],
        "data_write_scope": ["草稿"],
    }
    edited = apply_model_dimension_patch(current, layer="B", patch=patch, model_provider="lm_studio", model_name="small-local")

    assert "不得發布" in edited["model_draft_content"]
    assert any("不得編造價格" in item for item in edited["forbidden"])
    assert any("正式價格表" in item for item in edited["stop_conditions"])
    assert edited["model_patch"]["model_used"] is True


def test_small_model_rule_content_alias_preserves_model_authored_explanation():
    request = (
        "Create a reusable customer refund approval rule. Verify the order and evidence, "
        "stop when records are missing, and require my signature."
    )
    patch = parse_model_dimension_patch_output(
        json.dumps({
            "rule_content": (
                "For each refund, the user reviews the evidence, accepts responsibility, "
                "and signs; after failure the user repairs and replays the decision, while "
                "the model cannot sign, store, or activate the rule."
            ),
            "explanation": "This keeps approval authority and the final signature with the user.",
            "missing_information": "Named approval owner",
            "needs_user_confirmation": "Confirm the approval owner",
            "model_cannot_decide": "Whether the owner signs",
            "risk_notes": "An unsigned rule cannot become active",
        }),
        layer="R",
        instruction="Repair the responsibility and signature field.",
        user_input=request,
        locale="en",
    )

    assert patch["content"].startswith("For each refund")
    assert patch["explanation"].startswith("This keeps approval authority")
    assert patch["model_schema_repaired"] is True


def test_dimension_repair_prompt_requires_flat_human_readable_contract():
    messages = build_model_dimension_patch_messages(
        user_input="建立任何領域都可用的規則。",
        layer="K",
        instruction="只修 K。",
        current_dimension={},
        locale="zh-TW",
        compact=True,
    )
    system = messages[0]["content"]
    payload = json.loads(messages[1]["content"])

    assert "一個扁平物件" in system
    assert "不得把 content 改名為 rule_content" in system
    assert payload["output_contract"]["content"].startswith("one complete")
    assert set(payload["output_contract"]) == {"content", "explanation"}


def test_small_model_basis_selection_compiles_request_terms_not_domain_template():
    request = (
        "Create a reusable customer refund approval rule. Verify the order and evidence, "
        "stop when records are missing, and require my signature."
    )
    messages = build_model_basis_selection_messages(request, locale="en")
    payload = json.loads(messages[1]["content"])
    selected = parse_model_basis_selection_output(
        "evidence, records, order",
        user_input=request,
        locale="en",
    )
    candidate = {
        "model_semantic_valid": False,
        "K": {
            "content": "The model's first K attempt.",
            "explanation": "The model identified evidence for the current refund approval request.",
        },
    }
    compiled, audit = compile_model_basis_selection_candidate(
        candidate,
        selected_terms=selected,
        raw_model_output="evidence, records, order",
        locale="en",
    )

    assert "evidence, records, order" in compiled["K"]["content"]
    assert "may not be cited" in compiled["K"]["content"]
    assert compiled["K"]["model_task_fragment"] == "evidence, records, order"
    assert compiled["K"]["kernel_structure_compiled"] is True
    assert audit["source"] == "model_fragment_plus_kernel_invariant"
    assert "evidence" in payload["candidate_terms"]


def test_chinese_basis_selection_preserves_readable_request_phrases():
    request = (
        "幫我生成債務民事案件資料整理規則書：先核對當事人、借款證據、金額、日期與時效；"
        "資料不足時只能列待確認，不得替我判決勝敗。"
    )
    messages = build_model_basis_selection_messages(request, locale="zh-TW")
    payload = json.loads(messages[1]["content"])
    selected = parse_model_basis_selection_output(
        "事人, 借款證據, 金額",
        user_input=request,
        locale="zh-TW",
    )

    assert "當事人" in payload["candidate_terms"]
    assert "借款證據" in payload["candidate_terms"]
    assert selected == ["當事人", "借款證據", "金額"]


def test_chinese_basis_selection_normalizes_terms_and_rejects_stop_clauses():
    request = (
        "建立可重用文件發布規則：先核對文件版本及收件對象，再確認我已核准；"
        "未核准不得發布，資料缺失就停止；只能引用我確認的文件與版本紀錄。"
    )
    selected = parse_model_basis_selection_output(
        "檔案版本, 收件物件, 資料缺失就停止",
        user_input=request,
        locale="zh-TW",
    )

    assert selected == ["文件版本", "收件對象"]


def test_kernel_compiles_only_authority_clause_after_model_names_human_signer():
    candidate = {
        "model_semantic_valid": False,
        "R": {
            "content": "The user reviews the refund evidence, accepts responsibility, and signs.",
            "explanation": "The user remains accountable.",
        },
    }
    compiled, audit = compile_kernel_required_clauses(candidate, locale="en")

    assert "model cannot sign" in compiled["R"]["content"].lower()
    assert "repairs and replays" in compiled["R"]["content"].lower()
    assert compiled["R"]["model_original_content_before_kernel_compile"].startswith("The user")
    assert audit[0]["source"] == "model_fragment_plus_kernel_invariant"


def test_support_fields_refresh_after_kernel_compiles_owner_boundary():
    candidate = {
        "S": {"content": "refund approval", "explanation": "subject"},
        "C": {"content": "first verify, then decide", "explanation": "sequence"},
        "B": {"content": "do not approve; stop if missing", "explanation": "boundary"},
        "K": {"content": "confirmed evidence may be cited; chat may not be cited", "explanation": "basis"},
        "R": {
            "content": "The user accepts responsibility and signs; the model cannot sign.",
            "explanation": "The user is accountable.",
        },
        "rule_summary": "refund rule",
        "missing_information": ["order evidence"],
        "user_confirmation_items": ["confirm the order"],
        "model_cannot_decide": [],
        "risk_reminders": ["wrong refund"],
        "next_actions": [],
    }
    refreshed = refresh_model_rulebook_support_fields(candidate, locale="en")

    assert refreshed["model_cannot_decide"]
    assert refreshed["model_support_fields_derived"]["model_cannot_decide"] == (
        "model_R_plus_kernel_authority_boundary"
    )
    assert refreshed["next_actions"] == [
        "The user reviews every field and signs; until then, keep the rule as a draft."
    ]
    assert refreshed["model_support_fields_derived"]["next_actions"] == (
        "model_R_owner_signature_workflow"
    )


def test_kernel_compiles_boundary_only_after_model_writes_task_stop_condition():
    request = "Create a refund rule. Verify the order and evidence; stop when records are missing."
    candidate = {
        "model_semantic_valid": False,
        "B": {
            "content": "Verify the order and evidence first; stop when records are missing.",
            "explanation": "The model identified the task-specific stop condition.",
        },
    }
    compiled, audit = compile_kernel_required_clauses(
        candidate,
        user_input=request,
        locale="en",
    )

    assert compiled["B"]["content"].startswith("Do not proceed")
    assert compiled["B"]["model_original_content_before_kernel_compile"].startswith("Verify")
    assert audit[0]["layer"] == "B"


def test_automatic_dimension_repair_rejects_role_incomplete_copy():
    try:
        parse_model_dimension_patch_output(
            json.dumps({
                "content": "Verify order and evidence first; stop when records are missing.",
                "explanation": "This is supposed to be the citable-source field.",
            }),
            layer="K",
            instruction="Repair the basis field.",
            user_input="Create a refund rule using the order and evidence.",
            locale="en",
            require_complete_role=True,
        )
    except ModelRulebookAuthoringError as exc:
        assert exc.code == "k_role_incomplete"
    else:
        raise AssertionError("an automatic repair must not accept copied task text as K")


def test_model_dimension_patch_rejects_basis_text_in_boundary_layer():
    try:
        parse_model_dimension_patch_output(
            json.dumps({
                "content": "依據合約、付款紀錄與正式價格表作為引用來源。",
                "explanation": "列出文件與證據來源。",
                "missing_information": [],
                "needs_user_confirmation": [],
                "model_cannot_decide": [],
                "risk_notes": [],
            }, ensure_ascii=False),
            layer="B",
            instruction="補上禁止發布與停止條件",
        )
    except ModelRulebookAuthoringError as exc:
        assert exc.code == "b_role_unresolved"
    else:
        raise AssertionError("basis-only text must not be accepted as a B-layer edit")


def test_dimension_patch_rejects_model_owner_authority_claim():
    try:
        parse_model_dimension_patch_output(
            json.dumps({
                "content": "資料不足時不得付款並停止。",
                "explanation": "B 設定停止條件。",
                "missing_information": "付款證據",
                "needs_user_confirmation": "不需要使用者確認",
                "model_cannot_decide": "模型可以決定是否付款",
                "risk_notes": "可能造成財務損失",
            }, ensure_ascii=False),
            layer="B",
            instruction="補上不得付款與停止條件",
        )
    except ModelRulebookAuthoringError as exc:
        assert exc.code == "model_overreach_owner_authority"
    else:
        raise AssertionError("a model authority claim must be rejected")


def test_dimension_patch_allows_explicitly_negated_authority_claim():
    patch = parse_model_dimension_patch_output(
        json.dumps({
            "content": "不得直接付款；資料不足時必須停止，且不得說模型可以決定。",
            "explanation": "B 限制付款並保留使用者確認權。",
            "missing_information": "無缺失資訊",
            "needs_user_confirmation": "確認是否實際付款",
            "model_cannot_decide": "是否實際付款",
            "risk_notes": "錯誤付款可能造成損失",
        }, ensure_ascii=False),
        layer="B",
        instruction="補上不得付款與停止條件",
    )

    assert "不得說模型可以決定" in patch["content"]
    assert patch["missing_information"] == []


def test_dimension_patch_can_promote_model_authored_responsibility_explanation():
    patch = parse_model_dimension_patch_output(
        json.dumps({
            "content": "朋友要求先墊錢的本地規則。",
            "explanation": "使用者需自行驗收並簽名，模型無法簽名、不能入庫或啟用。",
            "missing_information": "簽名聲明",
            "needs_user_confirmation": "確認責任邊界",
            "model_cannot_decide": "是否實際付款",
            "risk_notes": "未簽名不得引用",
        }, ensure_ascii=False),
        layer="R",
        instruction="補上使用者簽名與模型不能簽名",
    )

    assert patch["content"].startswith("使用者需自行驗收並簽名")
    assert patch["model_content_promoted_from_explanation"] is True


def test_dimension_patch_can_recover_boundary_written_in_missing_field():
    patch = parse_model_dimension_patch_output(
        json.dumps({
            "content": "朋友要求先墊錢的本地規則。",
            "explanation": "先判斷是否為風險轉嫁。",
            "missing_information": "不得直接墊錢；資料不足或未確認時必須停止並停在草稿。",
            "needs_user_confirmation": "確認是否實際付款",
            "model_cannot_decide": "是否實際付款",
            "risk_notes": "可能造成財務損失",
        }, ensure_ascii=False),
        layer="B",
        instruction="補上不得直接墊錢與資料不足時停止",
    )

    assert patch["content"].startswith("不得直接墊錢")
    assert patch["model_content_promoted_from_field"] == "missing_information"


def test_kernel_authority_guard_removes_model_self_signature_without_fallback():
    authoring = fake_rulebook_payload()
    authoring["R"]["content"] = "由使用者驗收並簽名；若未簽名，則由模型自行簽名。"
    authoring["model_semantic_valid"] = False

    guarded, repairs = enforce_kernel_authority_boundary(authoring)

    assert "模型自行簽名" not in guarded["R"]["content"]
    assert "模型不能簽名" in guarded["R"]["content"]
    assert guarded["R"]["kernel_authority_guard_applied"] is True
    assert repairs[0]["source"] == "kernel_authority_guard"


def test_authority_guard_blocks_and_repairs_model_signature_claims_outside_r():
    authoring = fake_rulebook_payload()
    authoring["rule_summary"] = "核對資料後發布文件；由模型驗收並簽名後才生效。"
    authoring["next_actions"] = ["由模型核准並啟用規則"]
    parsed = parse_model_rulebook_candidate(
        json.dumps(authoring, ensure_ascii=False),
        user_input="建立文件發布規則，核對資料後由我簽名。",
    )

    assert parsed["model_semantic_valid"] is False
    assert parsed["model_semantic_report"]["model_authority_overreach_paths"] == [
        "rule_summary",
        "next_actions",
    ]

    guarded, repairs = enforce_kernel_authority_boundary(parsed)
    report = validate_model_rulebook_semantics(
        guarded,
        user_input="建立文件發布規則，核對資料後由我簽名。",
    )

    assert "由模型驗收" not in guarded["rule_summary"]
    assert "使用者驗收並簽名" in guarded["rule_summary"]
    assert all("模型核准" not in item for item in guarded["next_actions"])
    assert {item["path"] for item in repairs} == {"rule_summary", "next_actions"}
    assert report["model_authority_overreach_paths"] == []


def test_authority_guard_does_not_misread_model_guesses_or_unsigned_drafts_as_model_signing():
    authoring = fake_rulebook_payload()
    authoring["K"]["content"] = (
        "使用者已確認的文件版本可引用；未確認內容、聊天或模型猜測、"
        "未簽名草稿與 VECTOR 候選不可引用。"
    )

    guarded, repairs = enforce_kernel_authority_boundary(authoring)

    assert repairs == []
    assert guarded["K"]["content"] == authoring["K"]["content"]
    assert validate_model_rulebook_semantics(
        guarded,
        user_input="建立文件發布規則，只引用已確認的文件版本。",
    )["model_authority_overreach_paths"] == []


def test_parseable_incomplete_output_is_preserved_as_candidate():
    candidate = parse_model_rulebook_candidate(json.dumps({
        "S": "主體與情境",
        "C": "因果與判斷順序",
        "B": "邊界、禁止與停止",
        "K": "依據與引用來源",
        "R": "責任、驗收與簽名",
    }, ensure_ascii=False), user_input=RULE_REQUEST)

    assert candidate["model_semantic_valid"] is False
    assert candidate["model_semantic_report"]["request_alignment"] is False
    assert candidate["S"]["content"] == "主體與情境"


def fresh_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main

    return importlib.reload(main)


def fake_rulebook_payload():
    return {
        "S": {
            "content": "朋友要求使用者先墊錢時，判斷這是否為風險轉嫁的本地規則。",
            "explanation": "S 層鎖定情境：朋友要求先墊錢，使用者需要先判斷主體、金額與還款承諾。",
            "missing_information": ["金額上限", "朋友關係與歷史紀錄"],
            "needs_user_confirmation": ["確認是否所有朋友借款都適用"],
            "model_cannot_decide": ["使用者是否願意承擔現實金錢風險"],
            "risk_notes": ["主體不清會導致錯誤套用"],
        },
        "C": {
            "content": "先確認墊款請求，再檢查還款時間、證據、對方是否把自身風險轉嫁給使用者，最後決定是否拒絕或要求補條件。",
            "explanation": "C 層定義判斷順序，避免模型只因朋友承諾月底還款就直接答應。",
            "missing_information": ["是否有書面紀錄", "是否有過往未還款紀錄"],
            "needs_user_confirmation": ["確認判斷順序是否符合使用者習慣"],
            "model_cannot_decide": ["最後是否答應墊款"],
            "risk_notes": ["跳過證據檢查會降低可回放性"],
        },
        "B": {
            "content": "未確認金額、還款日期、證據與對方責任前，不得建議直接墊款；模型不得替使用者做付款決定。",
            "explanation": "B 層設下禁止事項與停止條件，防止金錢風險被包成友情義務。",
            "missing_information": ["可接受金額", "是否要求借據"],
            "needs_user_confirmation": ["確認停止條件"],
            "model_cannot_decide": ["是否真的付款"],
            "risk_notes": ["直接墊款可能形成無憑證債務"],
        },
        "K": {
            "content": "正式依據只能使用使用者已簽名規則與已確認資料；VECTOR 只能召回相似案例，recall only，不能當正式依據。",
            "explanation": "K 層區分正式依據與候選資料，避免把聊天上下文或檢索候選當成判準。",
            "missing_information": ["使用者正式借款政策"],
            "needs_user_confirmation": ["確認可引用依據"],
            "model_cannot_decide": ["未確認資料是否可信"],
            "risk_notes": ["VECTOR 當依據會造成假引用"],
        },
        "R": {
            "content": "規則只有在使用者逐欄確認並簽名後才成立；模型不能簽名，使用者採用後自行承擔現實付款決定。",
            "explanation": "R 層定義成立、失效、回放、修復與使用者責任。",
            "missing_information": ["簽名聲明", "回放要求細節"],
            "needs_user_confirmation": ["使用者簽名"],
            "model_cannot_decide": ["現實付款責任"],
            "risk_notes": ["未簽名規則不得引用"],
        },
        "rule_summary": "朋友要求先墊錢時的風險轉嫁判斷規則。",
        "missing_information": ["金額上限", "證據要求", "例外條件"],
        "user_confirmation_items": ["S/C/B/K/R 全欄位", "停止條件", "簽名聲明"],
        "model_cannot_decide": ["是否答應付款", "是否承擔現實風險"],
        "risk_reminders": ["不得自動建議付款", "不得把 VECTOR 當正式依據"],
        "next_actions": ["owner_review_and_signature"],
    }


def configure_fake_local_model(main, monkeypatch, *, bad_output=False):
    main.MODEL_SETTINGS.update(
        {
            "provider": "lm_studio",
            "mode": "local",
            "base_url": "http://127.0.0.1:1234/v1",
            "api_key": "local",
            "model_name": "fake-local-scbkr",
            "enabled": True,
            "last_test_status": "success",
        }
    )
    main.PERMISSIONS["model_generate"] = True
    calls = []

    def fake_model(settings, messages, response_format=None):
        calls.append({"settings": dict(settings), "messages": messages, "response_format": response_format})
        if bad_output:
            return {"choices": [{"message": {"content": "not json"}}]}
        last = json.dumps(messages, ensure_ascii=False)
        if "owner_edit_instruction" in last:
            return {
                "choices": [{"message": {"content": json.dumps({
                    "content": "朋友要求先墊錢時，未確認金額、還款日期與書面證據前不得墊款；資料不足時必須停止。",
                    "explanation": "已把朋友墊錢情境、還款證據與停止條件寫入 B 層。",
                    "missing_information": ["書面借款證據"],
                    "needs_user_confirmation": ["確認可接受的墊款上限"],
                    "model_cannot_decide": ["是否答應墊款"],
                    "risk_notes": ["責任不清可能造成金錢損失"],
                }, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 260, "completion_tokens": 90},
            }
        if "scbkr_model_rulebook_authoring" in json.dumps(response_format or {}) or "Model-assisted SCBKR Rulebook Authoring" in last:
            return {"choices": [{"message": {"content": json.dumps(fake_rulebook_payload(), ensure_ascii=False)}}], "usage": {"prompt_tokens": 900, "completion_tokens": 400}}
        return {"choices": [{"message": {"content": "依照已簽名的墊錢風險轉嫁規則：先不要直接墊三萬。請先確認金額、還款日期、書面證據與對方責任；在缺少憑證前只能列為待確認草稿，不得把月底還款承諾當作正式依據。"}}], "usage": {"prompt_tokens": 500, "completion_tokens": 120}}

    monkeypatch.setattr(main, "_post_openai_compatible", fake_model)
    return calls


def test_no_signed_rule_still_uses_connected_model_for_normal_chat(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    configure_fake_local_model(main, monkeypatch)
    captured = {}

    def fake_general_chat(settings, messages, response_format=None):
        captured["messages"] = messages
        return {
            "choices": [{"message": {"content": "一、燕麥配水果；二、蛋配吐司；三、優格配堅果。"}}],
            "usage": {"prompt_tokens": 88, "completion_tokens": 24, "total_tokens": 112},
        }

    monkeypatch.setattr(main, "_post_openai_compatible", fake_general_chat)
    response = TestClient(main.app).post("/api/chat/general", json={
        "message": "請幫我想三種簡單早餐搭配，每種一句話。",
        "locale": "zh-TW",
        "chat_history": [{"role": "user", "content": "我不吃辣。"}],
    })

    assert response.status_code == 200
    result = response.json()
    assert result["route_mode"] == "answer_with_rules"
    assert result["reply_source"] == "model_gateway_general_no_rule"
    assert result["model_used"] is True
    assert result["current_rule_package"]["matched_rules"] == []
    assert result["task_created"] is False
    assert result["data_center_written"] is False
    assert result["chat_context_used"] is False
    assert result["token_cost_audit"]["actual_usage_verified"] is True
    assert result["token_cost_audit"]["actual_prompt_tokens"] == 88
    assert any(item.get("content") == "我不吃辣。" for item in captured["messages"])


def test_web_waits_for_slow_small_models_and_recovers_full_task_details():
    source = (
        Path(__file__).resolve().parents[2] / "apps" / "web" / "src" / "V2App.tsx"
    ).read_text(encoding="utf-8")

    assert source.count("1200000") >= 3
    assert "return await api<TaskSummary>(`/api/tasks/${encodeURIComponent(found.task_id)}`);" in source


def test_web_explains_stale_state_conflicts_and_offers_a_fresh_revision():
    source = (
        Path(__file__).resolve().parents[2] / "apps" / "web" / "src" / "V2App.tsx"
    ).read_text(encoding="utf-8")

    assert 'data-testid="storage-state-conflict"' in source
    assert "state_conflict_reconfirmation_required" in source
    assert "refreshConflictedRevision" in source
    assert "copy.stateConflict.noWrite" in source
    i18n_root = Path(__file__).resolve().parents[2] / "apps" / "web" / "src" / "i18n"
    assert "四庫未寫入" in (i18n_root / "zh-TW.ts").read_text(encoding="utf-8")
    assert "No four-store write" in (i18n_root / "en.ts").read_text(encoding="utf-8")


def complete_owner_signed_rule(client, raw_input=RULE_REQUEST):
    task = client.post(
        "/api/tasks/create",
        json={"raw_input": raw_input, "task_type": "general", "create_scbkr_draft": True, "object_type": "rule"},
    ).json()
    signed = client.post(
        f"/api/tasks/{task['task_id']}/confirm",
        json={"scbkr": task["scbkr"], "confirmed_by": "user", "signature": "owner-signature"},
    ).json()
    client.post(f"/api/tasks/{task['task_id']}/generate")
    client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "可入庫", "reviewer_signature": "owner-review"},
    )
    client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["logic", "corpus", "memory", "vector"], "user_decision": "custom", "signature": "storage-request"},
    )
    stored = client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={"storage_confirmed": True, "second_confirm": True, "confirmed_by": "user", "signature": "storage-signature", "selected_targets": ["logic", "corpus", "memory", "vector"]},
    ).json()
    assert signed["status"] == "confirmed"
    assert stored["storage_confirmed"] is True
    return stored


def prepare_rule_task_for_storage(client, task, signature_prefix):
    confirmed = client.post(
        f"/api/tasks/{task['task_id']}/confirm",
        json={"scbkr": task["scbkr"], "confirmed_by": "user", "signature": f"{signature_prefix}-owner"},
    )
    assert confirmed.status_code == 200, confirmed.text
    generated = client.post(f"/api/tasks/{task['task_id']}/generate")
    assert generated.status_code == 200, generated.text
    reviewed = client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "新版可入庫", "reviewer_signature": f"{signature_prefix}-review"},
    )
    assert reviewed.status_code == 200, reviewed.text
    requested = client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["logic", "corpus", "memory", "vector"], "user_decision": "custom", "signature": f"{signature_prefix}-request"},
    )
    assert requested.status_code == 200, requested.text
    return requested.json()


def test_model_unavailable_does_not_create_fallback_rulebook(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(main.app)

    response = client.post("/api/tasks/create", json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True})

    assert response.status_code == 200
    task = response.json()
    assert task["status"] == "model_unavailable"
    assert task["draft_source"] == "model_unavailable"
    assert task["fallback_used"] is False
    assert "scbkr" not in task
    assert task["next_required_action"] == "model_connection_required"


def test_model_bad_schema_does_not_create_fallback_rulebook(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    configure_fake_local_model(main, monkeypatch, bad_output=True)
    client = TestClient(main.app)

    task = client.post("/api/tasks/create", json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True}).json()

    assert task["status"] == "model_rulebook_schema_invalid"
    assert task["fallback_used"] is False
    assert "scbkr" not in task
    assert task["next_required_action"] == "retry_model_rulebook_authoring"


def test_connected_model_edits_real_dimension_and_never_auto_confirms(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    calls = configure_fake_local_model(main, monkeypatch)
    main.MODEL_SETTINGS["model_name"] = "qwen3.5-4b"
    client = TestClient(main.app)
    task = client.post(
        "/api/tasks/create",
        json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True},
    ).json()

    assert calls[0]["settings"]["timeout"] >= 900
    assert 960 <= calls[0]["settings"]["max_tokens"] <= 1200
    drafted = client.post(
        f"/api/tasks/{task['task_id']}/scbkr/patch-draft",
        json={"layer": "B", "instruction": "補上朋友要求先墊錢時，未確認金額與書面證據就不得墊款"},
    )
    assert drafted.status_code == 200
    patch = drafted.json()["patch"]
    assert patch["model_used"] is True
    assert patch["sandbox_used"] is False
    assert patch["provider_usage"]["prompt_tokens"] == 260
    assert "不得墊款" in patch["after_draft"]["model_draft_content"]

    applied = client.post(
        f"/api/tasks/{task['task_id']}/scbkr/apply-patch",
        json={"patch": patch},
    ).json()
    assert applied["confirmed"] is False
    assert applied["status"] == "waiting_user_confirm"
    assert any("不得墊款" in item for item in applied["scbkr"]["B"]["forbidden"])


def test_owner_edit_changes_compiled_dimension_not_just_a_note(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    configure_fake_local_model(main, monkeypatch)
    client = TestClient(main.app)
    task = client.post(
        "/api/tasks/create",
        json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True},
    ).json()

    response = client.post(
        f"/api/tasks/{task['task_id']}/scbkr/owner-edit",
        json={"layer": "C", "content": "先核對書面證據，再檢查金額與還款日，最後才判斷是否承擔風險。"},
    )
    assert response.status_code == 200
    edited = response.json()
    assert edited["confirmed"] is False
    assert "先核對書面證據" in edited["scbkr"]["C"]["core_logic"]
    assert edited["scbkr"]["C"]["owner_edit"]["owner_edited"] is True
    assert "user_edit_note" not in edited["scbkr"]["C"]


def test_semantic_role_failure_retries_same_model_without_fallback(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    calls = configure_fake_local_model(main, monkeypatch)
    valid_call = main._post_openai_compatible
    state = {"count": 0}

    def first_swapped_then_valid(settings, messages, response_format=None):
        state["count"] += 1
        if state["count"] == 1:
            return {"choices": [{"message": {"content": json.dumps({
                "S": "朋友墊款風險規則",
                "C": "先檢查請求，再判斷風險。",
                "B": "借款紀錄與轉帳資料。",
                "K": "不得直接答應付款。",
                "R": "使用者確認並簽名後自行承擔。",
            }, ensure_ascii=False)}}], "usage": {"prompt_tokens": 300, "completion_tokens": 90}}
        return valid_call(settings, messages, response_format=response_format)

    monkeypatch.setattr(main, "_post_openai_compatible", first_swapped_then_valid)
    task = TestClient(main.app).post("/api/tasks/create", json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True}).json()

    assert task["status"] == "waiting_user_confirm"
    assert task["fallback_used"] is False
    assert task["model_semantic_valid"] is True
    assert task["scbkr"]["compiler_report"]["attempts"] == 2
    assert task["scbkr"]["compiler_report"]["repairs"] == 1
    assert "scbkr_semantic_roles_invalid" in task["scbkr"]["compiler_report"]["errors"]


def test_repeated_semantic_gap_keeps_real_model_draft_and_locks_signature(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    configure_fake_local_model(main, monkeypatch)

    incomplete = json.dumps({
        "S": "主體與情境",
        "C": "因果與判斷順序",
        "B": "邊界、禁止與停止",
        "K": "依據與引用來源",
        "R": "責任、驗收與簽名",
    }, ensure_ascii=False)

    def always_incomplete(settings, messages, response_format=None):
        return {"choices": [{"message": {"content": incomplete}}], "usage": {"prompt_tokens": 200, "completion_tokens": 50}}

    monkeypatch.setattr(main, "_post_openai_compatible", always_incomplete)
    client = TestClient(main.app)
    task = client.post("/api/tasks/create", json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True}).json()

    assert task["status"] == "model_capability_limited"
    assert task["draft_source"] == "model_capability_limited"
    assert task["model_used"] is True
    assert task["model_schema_valid"] is True
    assert task["model_semantic_valid"] is False
    assert task["validator_passed"] is False
    assert task["fallback_used"] is False
    assert task["scbkr"]["S"]["model_draft_content"] == "主體與情境"
    capability = task["model_capability"]
    assert capability["model_baseline"] == "scbkr_draft_capable"
    assert capability["stronger_model_recommended"] is True
    assert capability["latency_triggered"] is False
    assert capability["automatic_cloud_escalation"] is False
    assert capability["signed_rule_small_model_reuse_supported"] is True
    assert len(task["attempt_audit"]) == 3

    blocked = client.post(
        f"/api/tasks/{task['task_id']}/confirm",
        json={"scbkr": task["scbkr"], "confirmed_by": "user", "signature": "owner-signature"},
    )
    assert blocked.status_code == 409


def test_targeted_small_model_repair_can_recommend_a_stronger_authoring_pass():
    capability = build_model_capability_assessment(
        {"passed": False, "model_support_fields_useful": False},
        attempts=1,
        targeted_repair_attempted=True,
        locale="en",
        model_name="qwen2.5-3b-instruct",
    )

    assert capability["stronger_model_recommended"] is True
    assert capability["targeted_repair_attempted"] is True
    assert capability["latency_triggered"] is False


def test_owner_can_repair_limited_model_draft_then_sign_without_fallback(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    configure_fake_local_model(main, monkeypatch)
    incomplete = json.dumps({
        "S": "主體與情境",
        "C": "因果與判斷順序",
        "B": "邊界、禁止與停止",
        "K": "依據與引用來源",
        "R": "責任、驗收與簽名",
    }, ensure_ascii=False)

    monkeypatch.setattr(
        main,
        "_post_openai_compatible",
        lambda settings, messages, response_format=None: {
            "choices": [{"message": {"content": incomplete}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 50},
        },
    )
    client = TestClient(main.app)
    task = client.post(
        "/api/tasks/create",
        json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True},
    ).json()
    assert task["status"] == "model_capability_limited"

    repairs = {
        "S": "朋友要求使用者先墊錢時，判斷是否把對方的金錢風險轉嫁給使用者。",
        "C": "先核對朋友的墊款金額與還款時間，再檢查書面證據；若責任不清，則停止並要求補資料。",
        "B": "未確認金額、還款日期與責任前不得墊款；資料不足或要求立即付款時必須停止。",
        "K": "只可引用使用者確認的借款紀錄與正式資料；不可引用聊天猜測，VECTOR recall only，不得作正式依據。",
        "R": "使用者負責驗收並簽名後規則才成立；模型不能代簽，錯誤時由使用者回放並修復。",
    }
    for layer, content in repairs.items():
        response = client.post(
            f"/api/tasks/{task['task_id']}/scbkr/owner-edit",
            json={"layer": layer, "content": content},
        )
        assert response.status_code == 200, response.text
        task = response.json()

    assert task["status"] == "waiting_user_confirm"
    assert task["draft_source"] == "owner_repaired_model_rulebook"
    assert task["compiled_semantic_valid"] is True
    assert task["validator_passed"] is True
    assert task["fallback_used"] is False
    assert task["model_semantic_valid"] is False

    signed = client.post(
        f"/api/tasks/{task['task_id']}/confirm",
        json={"confirmed_by": "user", "signature": "owner-signature"},
    )
    assert signed.status_code == 200
    assert signed.json()["status"] == "confirmed"


def test_model_assisted_rulebook_storage_and_followup_rule_package(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    calls = configure_fake_local_model(main, monkeypatch)
    client = TestClient(main.app)

    task = client.post("/api/tasks/create", json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True}).json()
    assert task["status"] == "waiting_user_confirm"
    assert task["draft_source"] == "model_assisted_rulebook"
    assert task["model_used"] is True
    assert task["model_schema_valid"] is True
    assert task["model_semantic_valid"] is True
    assert task["validator_passed"] is True
    assert task["fallback_used"] is False
    assert task["requires_user_signature"] is True
    assert task["model_signature_allowed"] is False
    assert task["scbkr"]["S"]["model_explanation"]
    assert task["scbkr"]["missing_information"]
    assert task["context_audit"]["chat_context_used"] is False

    signed = client.post(f"/api/tasks/{task['task_id']}/confirm", json={"scbkr": task["scbkr"], "confirmed_by": "user", "signature": "owner-signature"}).json()
    assert signed["status"] == "confirmed"
    generated = client.post(f"/api/tasks/{task['task_id']}/generate").json()
    assert generated["status"] == "waiting_review"
    reviewed = client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "可入庫", "reviewer_signature": "owner-review"},
    ).json()
    assert reviewed["review_passed"] is True
    client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["logic", "corpus", "memory", "vector"], "user_decision": "custom", "signature": "storage-request"},
    )
    stored = client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={"storage_confirmed": True, "second_confirm": True, "confirmed_by": "user", "signature": "storage-signature", "selected_targets": ["logic", "corpus", "memory", "vector"]},
    ).json()
    assert stored["storage_confirmed"] is True
    assert "logic" in stored["storage_result"]["written_targets"]

    answer = client.post("/api/chat/general", json={"message": FOLLOWUP}).json()
    assert answer["route_mode"] == "answer_with_rules"
    assert answer["chat_context_used"] is False
    assert answer["current_rule_package"]["matched_rules"]
    assert answer["current_rule_package"]["chat_context_used"] is False
    assert answer["rule_state"]["awareness_state"] == "RULE_ACTIVE"
    assert answer["token_cost_audit"]["compression_ratio"] >= 0
    assert answer["token_cost_audit"]["chat_context_used"] is False
    assert "VECTOR" not in json.dumps(answer["current_rule_package"].get("citable_data", []), ensure_ascii=False)
    assert answer["token_cost_audit"]["measurement_basis"] == "provider_usage"
    assert answer["token_cost_audit"]["actual_prompt_tokens"] == 500
    assert answer["token_cost_audit"]["actual_completion_tokens"] == 120
    assert answer["token_cost_audit"]["local_execution"] is True
    assert answer["token_cost_audit"]["api_cost"] == 0.0
    assert len(calls) >= 2


def test_rule_revision_keeps_old_active_until_new_signed_storage_then_supersedes(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    configure_fake_local_model(main, monkeypatch)
    client = TestClient(main.app)
    original = complete_owner_signed_rule(client)
    original_rule_id = original["compiled_rule"]["rule_id"]

    revision_response = client.post(
        f"/api/rules/{original_rule_id}/revision",
        json={"instruction": "增加停止條件：金額與書面證據未確認時不得建議墊款。", "locale": "zh-TW"},
    )
    assert revision_response.status_code == 200
    revision = revision_response.json()
    assert revision["status"] == "waiting_user_confirm"
    assert revision["supersedes_rule_id"] == original_rule_id
    assert revision["revision_number"] == 2
    before_storage = {item["rule_id"]: item for item in main.list_rules()["rules"]}
    assert before_storage[original_rule_id]["activation_status"] == "active"

    client.post(
        f"/api/tasks/{revision['task_id']}/confirm",
        json={"scbkr": revision["scbkr"], "confirmed_by": "user", "signature": "revision-owner"},
    )
    client.post(f"/api/tasks/{revision['task_id']}/generate")
    client.post(
        f"/api/tasks/{revision['task_id']}/review",
        json={"review_decision": "pass", "review_message": "新版可入庫", "reviewer_signature": "revision-review"},
    )
    client.post(
        f"/api/tasks/{revision['task_id']}/storage-request",
        json={"selected_targets": ["logic", "corpus", "memory", "vector"], "user_decision": "custom", "signature": "revision-request"},
    )
    stored = client.post(
        f"/api/tasks/{revision['task_id']}/storage-confirm",
        json={"storage_confirmed": True, "second_confirm": True, "confirmed_by": "user", "signature": "revision-storage", "selected_targets": ["logic", "corpus", "memory", "vector"]},
    ).json()

    assert stored["compiled_rule"]["version"] == 2
    assert stored["compiled_rule"]["supersedes"] == original_rule_id
    assert stored["supersession_result"]["status"] == "superseded"
    after_storage = {item["rule_id"]: item for item in main.list_rules()["rules"]}
    assert after_storage[original_rule_id]["activation_status"] == "superseded"
    assert after_storage[stored["compiled_rule"]["rule_id"]]["activation_status"] == "active"


def test_stale_parallel_revision_is_rechecked_and_blocked_at_storage_confirm(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    configure_fake_local_model(main, monkeypatch)
    client = TestClient(main.app)
    original = complete_owner_signed_rule(client)
    original_rule_id = original["compiled_rule"]["rule_id"]

    first = client.post(
        f"/api/rules/{original_rule_id}/revision",
        json={"instruction": "增加三萬元以上必須再次確認。", "locale": "zh-TW"},
    ).json()
    second = client.post(
        f"/api/rules/{original_rule_id}/revision",
        json={"instruction": "增加沒有書面證據就停止。", "locale": "zh-TW"},
    ).json()
    assert first["source_rule_snapshot"]["evidence_hash"] == second["source_rule_snapshot"]["evidence_hash"]
    assert first["source_rule_snapshot"]["observed_at"] != ""

    prepare_rule_task_for_storage(client, first, "first-revision")
    prepare_rule_task_for_storage(client, second, "second-revision")

    first_commit = client.post(
        f"/api/tasks/{first['task_id']}/storage-confirm",
        json={"storage_confirmed": True, "second_confirm": True, "confirmed_by": "user", "signature": "first-storage", "selected_targets": ["logic", "corpus", "memory", "vector"]},
    )
    assert first_commit.status_code == 200, first_commit.text
    assert first_commit.json()["confirm_time_state_gate"]["conflict"] is False

    stale_commit = client.post(
        f"/api/tasks/{second['task_id']}/storage-confirm",
        json={"storage_confirmed": True, "second_confirm": True, "confirmed_by": "user", "signature": "second-storage", "selected_targets": ["logic", "corpus", "memory", "vector"]},
    )

    assert stale_commit.status_code == 409
    detail = stale_commit.json()["detail"]
    assert detail["code"] == "state_conflict_reconfirmation_required"
    assert detail["conflict"]["confirm_time_rechecked"] is True
    assert detail["conflict"]["expected_evidence_hash"] != detail["conflict"]["current_evidence_hash"]
    stale_task = main._get_task(second["task_id"])
    assert stale_task["status"] == "storage_conflict"
    assert stale_task["storage_confirmed"] is False
    assert stale_task["physical_write_performed"] is False
    assert stale_task["next_required_action"] == "refresh_revision_from_current_rule_and_reconfirm"
    assert not stale_task.get("storage_items")


def test_rule_delete_requires_owner_second_confirm_and_retains_replay(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    configure_fake_local_model(main, monkeypatch)
    client = TestClient(main.app)
    stored = complete_owner_signed_rule(client)
    rule_id = stored["compiled_rule"]["rule_id"]

    blocked = client.post(
        f"/api/rules/{rule_id}/lifecycle",
        json={"action": "delete", "confirmed_by": "user", "signature": "owner"},
    )
    assert blocked.status_code == 400

    deleted = client.post(
        f"/api/rules/{rule_id}/lifecycle",
        json={"action": "delete", "confirmed_by": "user", "second_confirm": True, "signature": "owner-delete", "reason": "規則不再適用"},
    )
    assert deleted.status_code == 200
    payload = deleted.json()
    assert payload["lifecycle_status"] == "deleted"
    assert payload["hard_delete"] is False
    assert payload["replay_retained"] is True
    task = main._get_task(stored["task_id"])
    assert task["compiled_rule"]["active"] is False
    assert task["compiled_rule"]["lifecycle_status"] == "deleted"
    assert task["storage_items"]
    assert {item["status"] for item in task["storage_items"]} == {"deleted"}
    assert main._rule_state_manager().status()["awareness_state"] == "EMPTY"


def test_fake_cloud_model_path_requires_external_permission_then_runs(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    calls = configure_fake_local_model(main, monkeypatch)
    main.MODEL_SETTINGS.update({"provider": "openai_compatible", "mode": "external", "base_url": "https://api.example.test/v1", "model_name": "fake-cloud-scbkr"})
    client = TestClient(main.app)

    blocked = client.post("/api/tasks/create", json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True}).json()
    assert blocked["status"] == "model_unavailable"
    assert blocked["next_required_action"] == "model_connection_required"
    assert calls == []

    main.PERMISSIONS["external_api"] = True
    allowed = client.post("/api/tasks/create", json={"raw_input": RULE_REQUEST, "task_type": "general", "create_scbkr_draft": True}).json()
    assert allowed["status"] == "waiting_user_confirm"
    assert allowed["model_provider"] == "openai_compatible"
    assert calls
