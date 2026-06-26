use tauri::Manager;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

struct SidecarState(Mutex<Option<Child>>);

fn start_api_sidecar() -> Option<Child> {
    let mut command = Command::new("scbkr-api");
    command
        .env("SCBKR_DESKTOP_RUNTIME", "release-candidate")
        .env("SCBKR_API_HOST", "127.0.0.1")
        .env("SCBKR_API_PORT", "8787")
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    command.spawn().ok()
}

fn main() {
    let sidecar = start_api_sidecar();
    tauri::Builder::default()
        .manage(SidecarState(Mutex::new(sidecar)))
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                if let Some(state) = window.app_handle().try_state::<SidecarState>() {
                    if let Ok(mut child) = state.0.lock() {
                        if let Some(process) = child.as_mut() {
                            let _ = process.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running SCBKR desktop release candidate");
}
