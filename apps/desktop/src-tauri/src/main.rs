use std::fs;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

struct SidecarState(Mutex<Option<Child>>);

#[derive(Debug)]
struct DesktopConfig {
    lan_companion_enabled: bool,
    companion_token: String,
    api_host: String,
    api_port: String,
}

impl Default for DesktopConfig {
    fn default() -> Self {
        Self {
            lan_companion_enabled: false,
            companion_token: String::new(),
            api_host: "127.0.0.1".to_string(),
            api_port: "8787".to_string(),
        }
    }
}

fn config_path() -> Option<PathBuf> {
    std::env::var_os("APPDATA").map(|base| PathBuf::from(base).join("SCBKR").join("desktop_config.json"))
}

fn read_bool(raw: &str, key: &str) -> bool {
    raw.contains(&format!("\"{}\": true", key))
}

fn read_string(raw: &str, key: &str, default_value: &str) -> String {
    let needle = format!("\"{}\"", key);
    let Some(key_start) = raw.find(&needle) else { return default_value.to_string(); };
    let Some(colon) = raw[key_start + needle.len()..].find(':') else { return default_value.to_string(); };
    let after_colon = key_start + needle.len() + colon + 1;
    let Some(open_quote) = raw[after_colon..].find('"') else { return default_value.to_string(); };
    let value_start = after_colon + open_quote + 1;
    let Some(close_quote) = raw[value_start..].find('"') else { return default_value.to_string(); };
    raw[value_start..value_start + close_quote].to_string()
}

fn load_desktop_config() -> DesktopConfig {
    let default_config = DesktopConfig::default();
    let Some(path) = config_path() else { return default_config; };
    if !path.exists() {
        if let Some(parent) = path.parent() { let _ = fs::create_dir_all(parent); }
        let _ = fs::write(&path, "{\n  \"lan_companion_enabled\": false,\n  \"companion_token\": \"\",\n  \"api_host\": \"127.0.0.1\",\n  \"api_port\": \"8787\"\n}\n");
        return default_config;
    }
    let Ok(raw) = fs::read_to_string(path) else { return default_config; };
    let lan_companion_enabled = read_bool(&raw, "lan_companion_enabled");
    let companion_token = read_string(&raw, "companion_token", "");
    if lan_companion_enabled && !companion_token.trim().is_empty() {
        DesktopConfig { lan_companion_enabled, companion_token, api_host: "0.0.0.0".to_string(), api_port: read_string(&raw, "api_port", "8787") }
    } else {
        default_config
    }
}

fn start_api_sidecar() -> Option<Child> {
    let config = load_desktop_config();
    let mut command = Command::new("scbkr-api");
    command
        .env("SCBKR_DESKTOP_RUNTIME", "release-candidate")
        .env("SCBKR_API_HOST", &config.api_host)
        .env("SCBKR_API_PORT", &config.api_port)
        .env("SCBKR_LAN_COMPANION_ENABLED", if config.lan_companion_enabled { "1" } else { "0" })
        .env("SCBKR_COMPANION_TOKEN", &config.companion_token)
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
                        if let Some(process) = child.as_mut() { let _ = process.kill(); }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running SCBKR desktop release candidate");
}
