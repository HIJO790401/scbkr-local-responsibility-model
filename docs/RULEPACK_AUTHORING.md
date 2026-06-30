# SCBKR 2.0 RulePack Authoring

RulePacks are versioned rule distributions. A pack does not become active by being imported.

## Trust flow

1. Compile a private source document into scoped public rules.
2. Review rule IDs, scope, tools, automation level, risk, and changelog.
3. Sign the canonical RulePack manifest with Ed25519.
4. Import the pack. SCBKR verifies the author signature.
5. The user adopts a verified rule with an adoption signature and scope.
6. Only active adopted rules can pass the Rule Match Gate.

The private master text does not need to be published. A public compiled pack can carry its source document hash for traceability without exposing the source itself.

The file `config/rulepacks/shen-an-black-shield.v2.draft.json` is intentionally unsigned. It must remain `waiting_owner_signature` until the author signs the canonical manifest. SCBKR must not label an unsigned draft as a ShenYao-signed active pack.
