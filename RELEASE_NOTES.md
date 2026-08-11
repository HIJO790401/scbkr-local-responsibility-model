# Release Notes

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
