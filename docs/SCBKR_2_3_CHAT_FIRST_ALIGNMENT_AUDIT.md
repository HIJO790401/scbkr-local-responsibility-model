# SCBKR 2.3 Chat-first Alignment Audit

Date: 2026-07-08

## Product Verdict

SCBKR 2.3 is a general AI chat product with SCBKR responsibility-chain rule capability. It is not a pure rule-engine dashboard. The default user path must be:

Normal chat -> Zeroth Principle Advisory Gate -> FREE confirmation draft -> Workbench collaboration -> user signature / dual-signature mode -> Rule Center -> Data Center.

## Current System Inventory

1. Formal frontend entry: `apps/web/src/main.tsx` imports and renders `V2App`.
2. `apps/web/src/App.tsx` remains a legacy / regression / contract shell and is not the production entry used by `main.tsx`.
3. Root package version: `2.3.0`.
4. Web package version: `2.3.0`.
5. FastAPI runtime version: `2.3.0`.
6. Desktop / Tauri metadata remains on the existing RC line (`apps/desktop` package and Tauri config still report `2.1.0`) and should be treated as shell metadata, not the product capability version.
7. Product manifest is updated to `2.3.0` / `2.3-chat-first-ui-alignment`.
8. README and Release Notes now describe SCBKR as chat-first plus responsibility-chain rules.

## UI Alignment Status

1. General chat is the default view in `V2App`.
2. The previous auto-route behavior created rule drafts immediately when the user asked for reusable rules. This has been corrected.
3. In normal chat mode, `create_confirmation` and `create_new_rule_confirmation` now show the Zeroth Principle Advisory Gate first.
4. The gate presents:
   - reusable-rule detection,
   - `π | OWNER_REVIEW`,
   - missing responsibility boundary, invalidation conditions, and replay requirements,
   - next step into FREE draft confirmation.
5. The gate actions are:
   - Draft confirmation,
   - Keep chatting,
   - Add role and boundary.
6. FREE draft creation remains available after the user clicks the draft action.
7. The direct `New rule` quick mode still creates a draft because that mode is an explicit rule-building command.

## Plan Semantics

FREE:
- Normal chat.
- Confirmation draft generation.
- S/C/B/K/R initial draft.
- Workbench editing.
- Model collaboration on draft fields.
- User self-signature.
- User-owned rule storage after gates.

NT$690:
- Responsibility-chain structure assistance.
- S/C/B/K/R completion help.
- Basic formation / invalidation condition help.
- Field linkage reminders and limited user-confirmed tool actions.
- It is not the confirmation-draft paywall.

NT$3,300:
- Rulebook closure layer.
- ShenYao creator rule signature plus user signature.
- Formation / invalidation conflict checks, risk, repair, replay, RulePack, OwnerReview, and long-term workflow support.
- It still cannot sign for the user or bypass OwnerReview.

## Gate Preservation

No backend gate was weakened in this alignment pass. The existing backend still enforces:

- Model cannot sign.
- User signature must be explicit and non-empty.
- Edited drafts invalidate downstream signature / generation / review / storage state.
- Review and storage confirmation gates remain separate.
- Data Center write / update / delete requires confirmation.
- LAN Companion token protection remains separate from desktop-local mode.
- External API guard remains enforced for non-loopback model endpoints.
- Four-store targets remain limited to `vector`, `corpus`, `logic`, and `memory`.
- Vector retrieval remains candidate-only and cannot be final K evidence.
- Revoked / archived / superseded records cannot be formally cited.

## Remaining Gaps

1. The Workbench collaboration panel exists, but should be visually upgraded to match the reference images more closely.
2. Rule Center and Data Center already exist, but need a stronger non-engineering presentation for normal users.
3. The FREE / NT$690 / NT$3,300 plan cards are present, but need clearer user-facing copy for exact unlock states.
4. The old `App.tsx` regression shell still contains older wording and direct confirmation behavior; it is not the formal entry, but future cleanup should label it explicitly as legacy.
5. Desktop RC metadata should remain separate until a dedicated desktop release pass updates installer, signing, and distribution state.

## Next Build Step

Proceed with the next UI pass on Workbench / Rule Center / Data Center visual hierarchy, while keeping the chat-first shell and backend gates intact.
