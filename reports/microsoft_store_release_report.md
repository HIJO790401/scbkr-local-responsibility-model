# Microsoft Store Release Report

- Product: **SCBKR Responsibility Chain Language Model**
- Edition: **FREE**
- Version: **2.3.0 / MSIX 2.3.0.0**
- Report date: **2026-08-23**

## Partner Center identity

- Developer account: created and identity verified.
- Publisher display name: `shenyao888pi`
- Store ID: `9N1SMMBL6J4D`
- Submission ID: `1152921505701704042`
- Package/Identity/Name: `shenyao888pi.SCBKRResponsibilityChainLanguageModel`
- Package/Identity/Publisher: `CN=FEB91682-9693-4284-BDDE-2EC33CF8EF23`
- Package family name: `shenyao888pi.SCBKRResponsibilityChainLanguageModel_qbw047d7k5vp4`
- Application ID: `SCBKR`
- Reserved product name: `SCBKR Responsibility Chain Language Model`

## Final Store package

- Package: `dist/scbkr-windows-store-msix/SCBKR_Responsibility_Chain_Language_Model_2.3.0.0_x64.msix`
- Architecture: x64
- Size: 30,514,351 bytes
- SHA-256: `45336244E2299660A0C1166884C0488C76B072C52B8B277C45244013BF53E69D`
- MakeAppx pack: PASS
- MakeAppx unpack verification: PASS
- Required packaged runtime files: `scbkr_desktop.exe`, `scbkr-api.exe`
- Manifest identity match: PASS
- Languages: `zh-tw`, `en-us`
- Restricted capability: `runFullTrust`, required only to launch and manage the bundled local FastAPI sidecar.
- Bundled model: no
- Bundled API key: no
- Store upload package signing: intentionally unsigned; Microsoft Store re-signs an accepted MSIX package.

The earlier package with SHA-256 `B7C29FC09C19BE0875193DD7D96565EF54349B840944EE98BC2D0E36E78B6BD9` is superseded and must not be submitted. It contained the staged target-triple sidecar name instead of the runtime name Tauri resolves. Static WACK passed, but a real install-and-launch test correctly exposed the missing sidecar at startup. The build script and regression test now prevent that packaging error.

## WACK and sideload verification

- WACK executable: Windows App Certification Kit 10.0.26100.0.
- WACK report: `reports/wack_store_msix_2_3_0_0.xml`
- WACK report ID: `fbaa1e0f89c2e620d958038be8b70ee5`
- WACK overall result: **PASS**
- Required test failures: **0**
- Optional findings: one blocked-executable/process-launch scan finding. It detects the packaged desktop process launching the local sidecar and PyInstaller string references. This is expected for the declared `runFullTrust` desktop architecture and is covered by the Partner Center capability explanation.
- Temporary signing certificate subject: `CN=FEB91682-9693-4284-BDDE-2EC33CF8EF23`
- Temporary signing certificate thumbprint: `A85E4BEFB76495487F2F89EDF7CEA85ACAEB0B14`
- SignTool SHA-256 signing and trust verification: PASS
- `Add-AppxPackage` install: PASS; package status `Ok`
- Launch from Windows AppsFolder AUMID: PASS
- Desktop executable source: installed `C:\Program Files\WindowsApps` package
- Sidecar executable source: installed `C:\Program Files\WindowsApps` package
- `/health`: HTTP 200 with `runtime=release-candidate`, `rule_assist_plan=FREE`, and LAN companion disabled
- Cold start on this PC: 47.6 seconds from desktop process start to confirmed `/health` response
- Traditional Chinese UI: PASS
- English UI switch and model-settings localization: PASS
- Guided onboarding, model connection status, rule status, and token-audit panel: visible and usable
- Normal UI close: PASS; desktop and sidecar exited and port 8787 was released
- Test package uninstall: PASS
- Temporary certificate cleanup: PASS across CurrentUser My, TrustedPeople, Root, LocalMachine TrustedPeople, and LocalMachine Root

## Product verification

- Python: `417 passed, 1 skipped, 0 failed`
- Playwright desktop/mobile bilingual acceptance: `2 passed`
- Web production build: PASS
- Desktop release contract: PASS
- FastAPI sidecar build and smoke: PASS
- Tauri release build: PASS
- NSIS build: PASS
- Store sidecar filename regression contract: PASS
- Multi-resolution Windows icon: 16, 24, 32, 48, 64, 128, and 256 px

## Partner Center draft

- Submission draft: created.
- Pricing: free.
- Markets: worldwide.
- Audience: public and Store-discoverable.
- Schedule: publish as soon as certification succeeds.
- Category: Productivity.
- Generative AI declaration: yes.
- Personal-data declaration: yes, because user-provided task content may be sent to the model endpoint chosen by the user.
- Website, support, and privacy URLs: completed.
- IARC questionnaire: completed; rating ID `bfdd4084-315d-8fdf-8730-3f7ecf507734`.
- Traditional Chinese Store listing: completed.
- English Store listing: completed.
- `runFullTrust` explanation: completed.

## Remaining gates

- Replace the superseded MSIX in Partner Center with the final package whose SHA-256 is `45336244E2299660A0C1166884C0488C76B072C52B8B277C45244013BF53E69D`.
- Reconfirm Partner Center package validation after replacement.
- Obtain owner confirmation immediately before selecting **Submit for certification**.
- Wait for Microsoft certification. Passing local validation and submitting a package are not proof that the Store listing is live.

This report separates source validation, local Store-package validation, Partner Center submission, Microsoft certification, and live Store publication.
