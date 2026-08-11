# SCBKR 2.3 Chat-first Alignment Audit

Date: 2026-07-08

## Product Verdict

SCBKR 2.3 is a general AI chat product with SCBKR responsibility-chain rule capability. It is not a pure rule-engine dashboard. The default user path must be:

Normal chat -> Zeroth Principle Advisory Gate -> FREE confirmation draft -> Workbench collaboration -> user signature -> Rule Center -> Data Center.

## Current System Inventory

1. Formal frontend entry: `apps/web/src/main.tsx` imports and renders `V2App`.
2. `apps/web/src/App.tsx` remains a legacy / regression / contract shell and is not the production entry used by `main.tsx`.
3. Root package version: `2.3.0`.
4. Web package version: `2.3.0`.
5. FastAPI runtime version: `2.3.0`.
6. Desktop / Tauri metadata is aligned with the product capability version at `2.3.0`.
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

## Public Edition Semantics

FREE:
- Normal chat.
- Confirmation draft generation.
- S/C/B/K/R initial draft.
- Workbench editing.
- Model collaboration on draft fields.
- User self-signature.
- User-owned rule storage after gates.

The public repository ships the FREE edition only. Private commercial
extensions are intentionally absent from public source, configuration, tests,
and interface copy.

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
3. The public UI identifies itself as the FREE edition and contains no commercial plan selector.
4. The old `App.tsx` regression shell still contains older wording and direct confirmation behavior; it is not the formal entry, but future cleanup should label it explicitly as legacy.
5. Desktop RC metadata should remain separate until a dedicated desktop release pass updates installer, signing, and distribution state.

## Next Build Step

Proceed with the next UI pass on Workbench / Rule Center / Data Center visual hierarchy, while keeping the chat-first shell and backend gates intact.
