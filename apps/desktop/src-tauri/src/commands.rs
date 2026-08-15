use serde::Serialize;

#[derive(Serialize)]
pub struct Bootstrap { pub product: &'static str, pub version: &'static str, pub template_source: &'static str }

#[tauri::command]
pub fn app_bootstrap() -> Bootstrap { Bootstrap { product: "Scheduler Pro Desktop", version: "0.1.0-alpha.1", template_source: "template-app-tauri-desktop-main" } }

#[tauri::command]
pub fn disabled_modules() -> Vec<&'static str> { vec!["licensing", "telemetry", "headless", "local-webhook", "local-websocket"] }

#[tauri::command]
pub fn api_config() -> serde_json::Value { serde_json::json!({"base_url":"https://scheduler.argws.com.br/api/v1","tenant_resolution":"hostname"}) }
