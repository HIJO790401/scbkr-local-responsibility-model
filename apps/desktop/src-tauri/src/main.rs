use std::fs;
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream};
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

struct SidecarState(Mutex<Option<CommandChild>>);

#[derive(Debug, Deserialize, Serialize)]
#[serde(default)]
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

fn load_desktop_config() -> DesktopConfig {
    let mut config = DesktopConfig::default();
    let Some(path) = config_path() else { return config; };
    if !path.exists() {
        if let Some(parent) = path.parent() { let _ = fs::create_dir_all(parent); }
        if let Ok(serialized) = serde_json::to_string_pretty(&config) {
            let _ = fs::write(&path, format!("{serialized}\n"));
        }
        return config;
    }
    if let Ok(raw) = fs::read_to_string(path) {
        if let Ok(parsed) = serde_json::from_str::<DesktopConfig>(&raw) {
            config = parsed;
        }
    }
    if config.api_port.parse::<u16>().ok().filter(|port| *port > 0).is_none() {
        config.api_port = "8787".to_string();
    }
    if config.lan_companion_enabled && !config.companion_token.trim().is_empty() {
        config.api_host = "0.0.0.0".to_string();
    } else {
        config.lan_companion_enabled = false;
        config.api_host = "127.0.0.1".to_string();
    }
    config
}

fn loopback_port_is_open(port: u16) -> bool {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    TcpStream::connect_timeout(&address, Duration::from_millis(350)).is_ok()
}

fn start_api_sidecar(app: &tauri::AppHandle) -> Result<Option<CommandChild>, String> {
    let config = load_desktop_config();
    let port = config.api_port.parse::<u16>().unwrap_or(8787);
    if loopback_port_is_open(port) {
        return Ok(None);
    }
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("SCBKR app data directory could not be resolved: {error}"))?
        .join("data");
    fs::create_dir_all(&data_dir)
        .map_err(|error| format!("SCBKR app data directory could not be created: {error}"))?;
    let command = app
        .shell()
        .sidecar("scbkr-api")
        .map_err(|error| format!("SCBKR API sidecar is not packaged correctly: {error}"))?
        .env("SCBKR_DESKTOP_RUNTIME", "release-candidate")
        .env("SCBKR_DATA_DIR", data_dir.to_string_lossy().as_ref())
        .env("SCBKR_API_HOST", &config.api_host)
        .env("SCBKR_API_PORT", &config.api_port)
        .env("SCBKR_DESKTOP_PARENT_PID", std::process::id().to_string())
        .env("SCBKR_LAN_COMPANION_ENABLED", if config.lan_companion_enabled { "1" } else { "0" })
        .env("SCBKR_COMPANION_TOKEN", &config.companion_token);
    let (_events, child) = command
        .spawn()
        .map_err(|error| format!("SCBKR API sidecar could not start: {error}"))?;
    Ok(Some(child))
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let sidecar = start_api_sidecar(&app.handle())
                .map_err(std::io::Error::other)?;
            app.manage(SidecarState(Mutex::new(sidecar)));
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                if let Some(state) = window.app_handle().try_state::<SidecarState>() {
                    if let Ok(mut child) = state.0.lock() {
                        if let Some(process) = child.take() { let _ = process.kill(); }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running SCBKR Desktop");
}
