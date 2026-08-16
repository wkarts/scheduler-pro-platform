#[tauri::command]
fn app_config() -> serde_json::Value {
    serde_json::json!({
        "product": "Scheduler Pro Admin Mobile",
        "api_base_url": "https://admin.scheduler.argws.com.br/api/v1",
        "distribution": "control-plane-mobile"
    })
}

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![app_config])
        .run(tauri::generate_context!())
        .expect("erro ao executar Scheduler Pro Admin Mobile");
}
