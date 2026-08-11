# SCBKR RulePack Authoring

RulePacks are versioned rule distributions. A pack does not become active by being imported.

The public repository is the FREE framework experience edition. It does not bundle ShenYao official or private rule packs. Users author, review, sign, own, and remain responsible for their own rules. Official packs and commercial customization require a future product or a separate commercial agreement.

## Trust flow

1. Compile a private source document into scoped public rules.
2. Review rule IDs, scope, tools, automation level, risk, and changelog.
3. Sign the canonical RulePack manifest with Ed25519.
4. Import the pack. SCBKR verifies the author signature.
5. The user adopts a verified rule with an adoption signature and scope.
6. Only active adopted rules can pass the Rule Match Gate.

The private master text does not need to be published. A public compiled pack can carry its source document hash for traceability without exposing the source itself.

An unsigned or unverifiable pack must remain `waiting_owner_signature`. SCBKR must never label an unsigned draft as author-verified, active, or officially supplied.
