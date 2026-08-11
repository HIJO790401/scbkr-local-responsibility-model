# SCBKR Desktop

This directory contains the Tauri 2 shell used to package SCBKR 2.3 FREE for Windows.

The app embeds the production Web build and launches the PyInstaller `scbkr-api` sidecar automatically. The sidecar binds to `127.0.0.1:8787` by default and stores user data under `%APPDATA%\SCBKR\data`.

## Runtime contract

- General chat and model-assisted rulebook authoring require a user-connected LM Studio, Ollama, or OpenAI-compatible endpoint.
- SCBKR does not bundle a model, download model weights, or include an API key.
- A missing or invalid model is reported as unavailable. No template or direct-kernel fallback may impersonate model authorship.
- The desktop shell cannot bypass owner review, signature, acceptance, second storage confirmation, four-store authority, or tool permission gates.
- LAN Companion Mode is disabled by default and requires an explicit token plus one-time pairing code.

## Windows build

The release candidate command is:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_desktop_release_windows.ps1 -SkipPythonDependencyInstall
```

The build performs the Web production build, PyInstaller sidecar build and smoke test, desktop release-contract check, Tauri release build, and NSIS packaging. Output is staged under:

```text
dist/scbkr-windows-desktop-rc/
```

Tauri resolves `bundle.externalBin = ["sidecar/scbkr-api"]` by appending the Windows target triple. The build therefore stages:

```text
apps/desktop/src-tauri/sidecar/scbkr-api-x86_64-pc-windows-msvc.exe
```

The generated icon is an unsigned placeholder used for the current RC. Microsoft Store submission still requires publisher identity, final brand assets, legal listing data, and the selected signing path.

## Distribution boundaries

- Public edition: FREE framework experience.
- No ShenYao official or private rule pack is bundled.
- No NT$690 or NT$3,300 private product source is published here.
- No code-signing certificate, cloud account, auto-update service, model, or API key is stored in the repository.
