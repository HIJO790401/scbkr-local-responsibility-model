# Microsoft Store Release Report

- Product: **SCBKR Responsibility Chain Language Model**
- Edition: **FREE**
- Version: **2.3.0 / MSIX 2.3.0.0**
- Report date: **2026-08-20**

## Partner Center identity

- Developer account: created and identity verified.
- Publisher display name: `shenyao888pi`
- Store ID: `9N1SMMBL6J4D`
- Package/Identity/Name: `shenyao888pi.SCBKRResponsibilityChainLanguageModel`
- Package/Identity/Publisher: `CN=FEB91682-9693-4284-BDDE-2EC33CF8EF23`
- Reserved product name: `SCBKR Responsibility Chain Language Model`

## Store package

- Package: `dist/scbkr-windows-store-msix/SCBKR_Responsibility_Chain_Language_Model_2.3.0.0_x64.msix`
- Architecture: x64
- Size: 30,514,417 bytes
- SHA-256: `B7C29FC09C19BE0875193DD7D96565EF54349B840944EE98BC2D0E36E78B6BD9`
- MakeAppx pack: PASS
- MakeAppx unpack verification: PASS
- Manifest identity match: PASS
- Languages: `zh-tw`, `en-us`
- Restricted capability: `runFullTrust`, required to launch the bundled local FastAPI sidecar.
- Bundled model: no
- Bundled API key: no
- Store upload package signing: intentionally unsigned; Microsoft Store re-signs an accepted MSIX package.

## Product verification

- Python: `416 passed, 1 skipped, 0 failed`
- Playwright desktop/mobile bilingual acceptance: `2 passed`
- Web production build: PASS
- FastAPI sidecar build and smoke: PASS
- Tauri release build: PASS
- NSIS build: PASS
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
- Website and support URLs: GitHub repository and GitHub Issues.
- Privacy URL: prepared on GitHub Pages.
- OneDrive application-data backup: disabled in the Store declaration.

## Open gates

- Publish and verify the GitHub Pages privacy and support URLs.
- Complete the IARC age-rating questionnaire.
- Upload and validate the final MSIX in Partner Center.
- Run Windows App Certification Kit from an elevated user session.
- Temporarily sign the MSIX with a test certificate, install, launch, close, uninstall, and remove the test certificate.
- Complete Traditional Chinese and English Store listings and media uploads.
- Obtain owner confirmation immediately before final certification submission.

This report separates local validation from Microsoft certification. The product is not described as published until Partner Center certification has succeeded and the Store listing is live.
