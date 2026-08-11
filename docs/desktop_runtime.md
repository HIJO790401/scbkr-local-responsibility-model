# SCBKR 2.3 Desktop Runtime

SCBKR Desktop is a Tauri shell around the local FastAPI rule runtime and the built React interface. It is a runnable Windows release candidate, not a separate mock application.

## Startup

1. Tauri launches `scbkr-api.exe` as a child sidecar.
2. The sidecar binds to `127.0.0.1:8787` by default.
3. The desktop WebView loads the embedded Web build.
4. Runtime data is written under `%APPDATA%\SCBKR\data`, not the repository.
5. Closing the desktop parent stops its sidecar through the parent watchdog.

## Model connection

The user connects LM Studio, Ollama, or an OpenAI-compatible endpoint in Model Settings. A successful connection test and explicit `model_generate` permission are required before chat generation or SCBKR rulebook authoring.

The package includes no model and no API key. When the model is unavailable, authoring fails visibly and remains unfinished; the product does not generate a hidden template fallback.

## Rule authority

- The connected model may draft and explain S/C/B/K/R.
- Only the user may edit, sign, review, second-confirm storage, activate, revise, archive, or delete a formal rule.
- Only signed, reviewed, active LOGIC/CORPUS/MEMORY records can become formal authority.
- VECTOR remains recall-only.
- Follow-up answers use a minimal `current_rule_package` and are post-checked before display.

## Desktop and phone modes

Desktop Mode is loopback-only by default. LAN Companion Mode is an explicit opt-in and requires a connection token and one-time six-digit pairing code. A phone connects to the SCBKR backend; it never connects directly to the local LLM.

## Windows packaging

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_desktop_release_windows.ps1 -SkipPythonDependencyInstall
```

The build creates:

- `scbkr_desktop.exe`
- `SCBKR Local Responsibility Model_2.3.0_x64-setup.exe`
- the packaged FastAPI sidecar
- Web assets, release metadata, and a release readme under `dist/scbkr-windows-desktop-rc/`

The RC is not code-signed and has not been submitted to Microsoft Store. Those are external release steps, not local-build evidence.
