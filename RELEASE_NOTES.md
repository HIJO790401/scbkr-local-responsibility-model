# Release Notes

## 2.3.1 - FREE Rule Applicability and Evidence Recheck

- Added owner-signed, deterministic rule triggers. Similarity can suggest a rule but cannot make it applicable; legacy rules without trigger closure remain candidates.
- Added applicability receipts to distinguish applicable, unresolved, invalidated, and non-triggered rules in chat and the Rule Center.
- Added trusted evidence-read traces, dependency coverage, and confirmation-time rechecks for rule revisions. Stale or untraceable drafts stop before storage.
- Added a bounded local-file state reader for the ToolGate authorization check. File modification and external-message execution are not provided by this gate; external messages have no production reader and remain blocked.
- Added Traditional Chinese and English UI states and tests for rule matching, evidence drift, and desktop/mobile workflows.

Local verification: `441 passed, 1 skipped` Python tests; `2 passed` desktop/mobile Playwright tests; Web production build and desktop release contract passed. Windows 2.3.1.0 MSIX passed WACK, clean install, upgrade from 2.3.0.0, and installed Runtime launch. The temporary sideload certificate and test package were removed. No live LM Studio/Ollama model was connected during this verification; model-flow tests used a controlled OpenAI-compatible test endpoint.

Release state: FREE 2.3.1.0 is available on [Microsoft Store](https://apps.microsoft.com/detail/9N1SMMBL6J4D). Partner Center showed Submission 3 (`1152921505701978735`) as the current Store state and the Windows 10/11 Desktop package `SCBKR_Responsibility_Chain_Language_Model_2.3.1.0_x64.msix` on 2026-10-03. The validation results above are the earlier local release checks, not a claim of new post-publication runtime testing.

## 2.3.0 - FREE Framework Experience RC

- Rebuilt SCBKR as a chat-first local responsibility-rule desktop product rather than a dashboard demo.
- Added a hard input router for general chat, rule authoring, rule-grounded answers, rule revision, storage confirmation, four-store queries, tool execution, and high-risk actions.
- Required the connected model to author task-specific S/C/B/K/R confirmation sheets with human-readable explanations, missing information, risks, and owner confirmations.
- Removed silent rule-authoring fallback. An unavailable or invalid model is reported honestly and cannot be disguised as a model-authored rule.
- Preserved owner-only signature, review, final storage confirmation, confirm-time source revalidation, version conflict blocking, replay, and post-answer checks.
- Compiled signed rules by responsibility into LOGIC, CORPUS, MEMORY, and recall-only VECTOR stores.
- Added bilingual Traditional Chinese and English product identity, guided onboarding, model settings, editable Workbench, four-store inspection, and honest Token / Context Audit states.
- Added reproducible same-provider, same-model A/B measurement with provider usage, hashes, and a verified `qwen2.5-3b-instruct` result of 69.55% prompt-token savings for one bounded task.
- Built and launched the Windows x64 Tauri/PyInstaller RC and generated an NSIS installer.
- Positioned the public repository as the FREE framework experience edition: users create and own their own rules; ShenYao official/private rule packs are not bundled.

Release boundary: this RC is locally built and tested. It is not code-signed and has not yet been submitted to Microsoft Store.
