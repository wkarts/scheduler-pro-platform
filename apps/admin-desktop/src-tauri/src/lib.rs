use tauri::Manager;

#[tauri::command]
fn app_config() -> serde_json::Value {
    serde_json::json!({
        "product": "Scheduler Pro Admin",
        "api_base_url": "https://admin.scheduler.argws.com.br/api/v1",
        "distribution": "control-plane"
    })
}

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![app_config])
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("erro ao executar Scheduler Pro Admin Desktop");
}
