mod commands;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![commands::app_bootstrap, commands::disabled_modules, commands::api_config])
    .run(tauri::generate_context!())
    .expect("erro ao executar Scheduler Pro Mobile");
}
