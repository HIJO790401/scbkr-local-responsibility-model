# Release Notes

## 0.15.0-rc.2 — P15-S SCBKR 1.0 Final RC

- Consolidated the product homepage into one bilingual `README.md`.
- Kept Desktop Mode local-only by default at `http://127.0.0.1:8787`.
- Added LAN Companion Mode support with manual opt-in, `0.0.0.0:8787`, and required companion token.
- Added Web UI serving from the API sidecar when `web-dist` is available.
- Allowed LAN Companion public Web UI shell/static assets while keeping `/api/*` protected by the companion token.
- Updated frontend API base selection so LAN browser sessions use `window.location.origin`, while desktop/non-http contexts keep `http://127.0.0.1:8787`.
- Fixed frontend API-base selection so LAN Companion uses the page origin while localhost dev/preview pages still call the sidecar at `127.0.0.1:8787`.
- Finalized the frontend API-base runtime matrix for Desktop RC, LAN Companion, custom LAN ports, dev/preview servers, Tauri/non-http contexts, and VITE_SCBKR_API_URL override.
- Fixed the API-base runtime matrix so `tauri.localhost` is treated as a desktop WebView entrypoint and falls back to the sidecar at `127.0.0.1:8787`.
- Preserved owner signature, review, second confirmation, Data Center, and four-store gates.
- Updated Windows release metadata to `0.15.0-rc.2` / `P15-S-1.0-final-rc` with LAN Companion support flags.

## 0.15.0-rc.1

- Previous Windows Desktop release candidate baseline.
