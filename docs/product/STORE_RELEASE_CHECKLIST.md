# Microsoft Store Release Checklist

## Product gates

- [x] Local-first runtime starts.
- [x] Chat, Workbench, Rule Center, and Data Center load.
- [x] Rule generation creates editable S/C/B/K/R.
- [x] Model cannot sign, store, or activate.
- [x] User signature changes status to owner-signed.
- [x] Review and storage confirmation compile an Active rule.
- [x] Confirm-time source state is rechecked before storage.
- [x] Later answers use `current_rule_package.chat_context_used = false`.
- [x] Token / Cost Audit distinguishes verified usage from estimates.
- [x] Traditional Chinese and English desktop/mobile UI does not overlap.
- [x] GitHub Actions Windows RC, pytest, sidecar smoke, and UI tests pass.

## Store account and identity

- [x] Complete free Microsoft Store developer onboarding.
- [x] Reserve `SCBKR Responsibility Chain Language Model`.
- [x] Copy the exact Package/Identity/Name from Partner Center.
- [x] Copy the exact Package/Identity/Publisher from Partner Center.
- [x] Build the final MSIX with those exact identity values.

## Listing and policy

- [x] Traditional Chinese and English listing copy prepared.
- [x] Privacy and support pages prepared for GitHub Pages.
- [x] Four Traditional Chinese and four English store images prepared.
- [ ] Publish GitHub Pages and verify both public URLs.
- [ ] Complete Microsoft age-rating questionnaire.
- [ ] Confirm markets, pricing (Free), category, and publishing schedule.

## Package certification

- [x] Run `scripts/build_msix_store_windows.ps1` with Partner Center identity.
- [x] Verify generated package by unpacking with MakeAppx.
- [ ] Run Windows App Certification Kit against the final package.
- [ ] Confirm install, first launch, sidecar health, close, and uninstall.
- [ ] Upload final MSIX to Partner Center.
- [ ] Add `runFullTrust` justification and certification notes.
- [ ] Review every listing field and submit for certification.
