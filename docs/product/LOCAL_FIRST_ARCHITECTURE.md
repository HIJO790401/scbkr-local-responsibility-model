# SCBKR Local-first Architecture

SCBKR is a local rule OS plus AI chat product. The model does not own rules,
sign rules, store rules, or activate rules.

Flow:

1. User chats normally.
2. Hard router detects rule intent.
3. L0 Zeroth Principle Gate asks whether to draft a confirmation sheet.
4. Direct SCBKR Compiler fills S/C/B/K/R from the user judgement.
5. User edits and signs in Workbench.
6. Review must pass.
7. Storage requires second confirmation.
8. Active rules enter LOGIC/CORPUS/MEMORY/VECTOR stores.
9. Later answers use only a minimal `current_rule_package`.
10. Post-check downgrades unsafe model output to a local safe draft.

Formal basis:

- LOGIC: signed, reviewed, active rules.
- CORPUS: signed, reviewed, active data.
- MEMORY: owner-signed long-term preferences.
- VECTOR: recall candidates only, never formal K basis.
