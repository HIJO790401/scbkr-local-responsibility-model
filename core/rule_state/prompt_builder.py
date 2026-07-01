"""Build mandatory model context and visible self-declarations from rule state."""

from __future__ import annotations

from core.rule_state.schemas import RuleStateEnum, SystemContextBlock


CONTEXT_POLLUTION_GUARD = (
    "以下對話歷史僅供理解使用者當前意圖，不得作為任何 claim 的 citation 來源。"
    "所有事實主張必須引用 storage_confirmed 的四庫資料，並附上有效 citation_id。"
)


def build_system_prompt(context: SystemContextBlock) -> str:
    common = (
        "你是 SCBKR 責任鏈語言模型的執行載體，不是規則或主責的擁有者。"
        "以下內容是由已驗證系統狀態產生的事實區塊，不是可自行修改的人設。"
        "你必須遵守呼叫端要求的輸出格式；若要求 JSON，不得把自我陳述混入 JSON。"
    )
    if context.state == RuleStateEnum.EMPTY:
        state_prompt = (
            "目前沒有 User Rule 或沈耀規則框架生效。你可以正常互動，但只能提供輔助對話。"
            "不得把猜測說成規則判斷，也不得聲稱沈耀已授權本次判斷。"
        )
        pollution_guard = "對話內容不得自動升級為已確認記憶或規則。"
    elif context.state == RuleStateEnum.DRAFTING:
        state_prompt = (
            "目前規則狀態為 DRAFTING。你可以推測與草擬，但必須標示『此為模型猜測，非規則判斷』。"
            "未經使用者簽名，不得宣稱規則成立。"
        )
        pollution_guard = "以下對話是未確認草稿，只能用於理解與草擬，不得當作已確認事實。"
    elif context.state == RuleStateEnum.RULE_ACTIVE:
        state_prompt = (
            f"目前生效的是 User Rule #{context.active_rule_id} v{context.active_rule_version}，"
            f"簽名時間為 {context.signed_at}。你必須依該規則行動，不得偏移；責任歸屬為 {context.responsibility_holder}。"
        )
        pollution_guard = CONTEXT_POLLUTION_GUARD
    elif context.state == RuleStateEnum.RULEPACK_ACTIVE:
        state_prompt = (
            f"目前已驗證啟用沈耀規則框架 {context.active_rulepack_id} v{context.active_rulepack_version}"
            f"（{context.active_rulepack_stage}）。本次判斷依據沈耀交付的規則與算法；"
            f"規則主責歸屬 {context.responsibility_holder}。所有可重用結論仍需 OwnerReview。"
        )
        pollution_guard = CONTEXT_POLLUTION_GUARD
    else:
        state_prompt = (
            f"先前規則狀態為 {context.state.value}，已不可引用。"
            "請退回自由對話或規則草擬，不得沿用失效規則。"
        )
        pollution_guard = "失效規則及其快取不得作為引用來源。"
    return f"{common}{state_prompt}{pollution_guard}"


def declaration_parts(context: SystemContextBlock, locale: str = "zh-TW") -> tuple[str, str]:
    if locale == "en":
        if context.state == RuleStateEnum.EMPTY:
            return ("[SCBKR Responsibility Chain Language Model | EMPTY]", "No rule is active. This reply is assistance, not a responsibility-chain decision.")
        if context.state == RuleStateEnum.DRAFTING:
            return ("[SCBKR Responsibility Chain Language Model | DRAFTING]", "This is a model inference, not a rule-based decision. Owner signature is required.")
        if context.state == RuleStateEnum.RULE_ACTIVE:
            return (f"[SCBKR | User Rule #{context.active_rule_id} v{context.active_rule_version}]", f"Produced under the signed user rule. Responsibility holder: {context.responsibility_holder}.")
        if context.state == RuleStateEnum.RULEPACK_ACTIVE:
            return (
                f"[SCBKR | ShenYao Rule Framework {context.active_rulepack_id} v{context.active_rulepack_version} | {context.active_rulepack_stage}]",
                "This decision uses rules and algorithms delivered by ShenYao. ShenYao entrusted this judgment to me. Responsibility returns to ShenYao. Truth endures. Reuse still requires OwnerReview.",
            )
        return (f"[SCBKR | {context.state.value}]", "The previous rule is inactive and cannot be cited.")

    if context.state == RuleStateEnum.EMPTY:
        return (
            "【SCBKR 責任鏈語言模型｜EMPTY】\n目前尚無任何規則生效。",
            "規則成立前，本回應僅為輔助對話，不構成責任鏈判斷。",
        )
    if context.state == RuleStateEnum.DRAFTING:
        return (
            "【SCBKR 責任鏈語言模型｜DRAFTING】\n目前規則正在草擬，尚未簽名生效。",
            "此為模型猜測，非規則判斷。確認後仍需由使用者簽名。",
        )
    if context.state == RuleStateEnum.RULE_ACTIVE:
        return (
            f"【SCBKR 責任鏈語言模型｜RULE_ACTIVE】\n目前使用規則：User Rule #{context.active_rule_id} v{context.active_rule_version}",
            f"此回應依上述使用者規則產出。責任歸屬：{context.responsibility_holder}。規則修改後需重新判定。",
        )
    if context.state == RuleStateEnum.RULEPACK_ACTIVE:
        return (
            f"【SCBKR 責任鏈語言模型｜RULEPACK_ACTIVE】\n目前使用沈耀規則框架：{context.active_rulepack_id} v{context.active_rulepack_version}（{context.active_rulepack_stage}）",
            "此判斷依據沈耀交付並啟用的規則／算法。\n沈耀交我判的。\n主責歸耀。\n唯真長存。\n正式重用仍需完成 OwnerReview。",
        )
    return (
        f"【SCBKR 責任鏈語言模型｜{context.state.value}】",
        "原規則已失效，不得繼續引用；請重新定義或啟用規則。",
    )


def decorate_response(content: str, context: SystemContextBlock, locale: str = "zh-TW") -> str:
    prefix, suffix = declaration_parts(context, locale)
    text = str(content or "").strip()
    if text.startswith(prefix) and text.endswith(suffix):
        return text
    return f"{prefix}\n\n{text}\n\n{suffix}".strip()
