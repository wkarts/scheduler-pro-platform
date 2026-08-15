#[tauri::command]
fn app_info() -> serde_json::Value { serde_json::json!({"name":"Scheduler Pro Mobile","version":"0.1.0-alpha.1"}) }

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![app_info])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar Scheduler Pro Mobile");
}
